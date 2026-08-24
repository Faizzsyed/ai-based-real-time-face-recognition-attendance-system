import logging
import re,time
from uuid import uuid4
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from app.api.router import router
from app.core.config import get_settings
from app.core.logging import configure_logging,request_id_var,safe_log
from app.db.mongo import mongo
from app.core.errors import AppError
from app.modules.face_ai.engine import FaceEngine

settings = get_settings()
configure_logging(settings)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    mongo.configure()
    detector=recognizer=False
    if settings.face_ai_enabled:
        try:FaceEngine(settings.face_detection_model_path,settings.face_recognition_model_path,settings.face_detection_threshold)._models();detector=recognizer=True
        except AppError:logger.warning("Face AI models unavailable; manual attendance remains available")
    logger.info("================ AttendAI Backend ================")
    safe_log(logger,logging.INFO,"startup",environment=settings.app_env,api=f"http://{settings.api_host}:{settings.api_port}",database=settings.mongodb_database,mongodb=mongo.status,face_ai="enabled" if settings.face_ai_enabled else "disabled",yunet="loaded" if detector else "unavailable",sface="loaded" if recognizer else "unavailable",face_encryption="configured" if settings.face_embedding_encryption_key else "not_configured",log_level=settings.log_level)
    logger.info("===================================================")
    yield
    mongo.close()


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
@app.middleware("http")
async def request_observability(request:Request,call_next):
    incoming=request.headers.get("X-Request-ID","");request_id=incoming if re.fullmatch(r"[A-Za-z0-9._-]{8,80}",incoming) else uuid4().hex
    token=request_id_var.set(request_id);started=time.perf_counter()
    if settings.enable_api_request_logging:safe_log(logger,logging.INFO,"request started",method=request.method,path=request.url.path)
    try:
        response=await call_next(request);duration=round((time.perf_counter()-started)*1000,2);response.headers["X-Request-ID"]=request_id
        if settings.enable_api_request_logging:safe_log(logger,logging.INFO,"request finished",method=request.method,path=request.url.path,status=response.status_code,duration_ms=duration)
        return response
    except Exception:
        logger.exception("unhandled request exception");raise
    finally:request_id_var.reset(token)
origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
if origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )
app.include_router(router)


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "AI Based Real-Time Face Recognition Attendance System API", "docs": "/docs"}


@app.exception_handler(Exception)
async def safe_error_handler(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled application error", exc_info=exc)
    return JSONResponse(status_code=500, content={"success": False, "message": "An unexpected server error occurred."})


@app.exception_handler(AppError)
async def application_error_handler(_: Request, exc: AppError) -> JSONResponse:
    error = {"code": exc.code, "message": exc.message}
    if exc.details is not None:
        error["details"] = exc.details
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "error": error},
    )

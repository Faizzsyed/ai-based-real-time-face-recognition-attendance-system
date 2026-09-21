from fastapi import APIRouter
from app.core.config import get_settings
from app.db.mongo import mongo
from app.api.dev_academic import router as dev_academic_router
from app.modules.auth.router import router as auth_router
from app.api.admin_academic import router as admin_academic_router
from app.api.students import router as students_router
from app.api.faculty import router as faculty_router
from app.api.timetable import router as timetable_router
from app.api.attendance import router as attendance_router
from app.api.face_enrollment import router as face_enrollment_router
from app.modules.reports.router import router as reports_router
from app.modules.requests.router import router as requests_router
from app.modules.notifications.router import router as notifications_router
from app.modules.audit.router import router as audit_router

router = APIRouter(prefix="/api/v1")
router.include_router(dev_academic_router)
router.include_router(auth_router)
router.include_router(admin_academic_router)
router.include_router(students_router)
router.include_router(faculty_router)
router.include_router(timetable_router)
router.include_router(attendance_router)
router.include_router(face_enrollment_router)
router.include_router(reports_router)
router.include_router(requests_router)
router.include_router(notifications_router)
router.include_router(audit_router)


@router.get("/health")
def health() -> dict[str, object]:
    settings = get_settings()
    payload = {"success": True, "status": "ok", "app": settings.app_name, "apiVersion": "v1", "database": mongo.status}
    if mongo.status == "connected":
        payload["databaseName"] = settings.mongodb_database
    return payload


from fastapi import HTTPException
@router.get("/ready")
def ready() -> dict[str, object]:
    if mongo.status != "connected":
        raise HTTPException(status_code=503, detail="Database not ready")
    return {"success": True, "status": "ready"}


@router.get("/system/info")
def system_info() -> dict[str, object]:
    settings = get_settings()
    return {"success": True, "app": settings.app_name, "apiVersion": "v1", "environment": settings.app_env, "faceAiEnabled": settings.face_ai_enabled, "database": mongo.status}

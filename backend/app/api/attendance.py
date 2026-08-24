"""Role-scoped manual attendance APIs."""
from datetime import date
from typing import Annotated
from fastapi import APIRouter,Depends,File,Form,Query,UploadFile
from fastapi.responses import FileResponse
from app.core.config import get_settings
from app.core.errors import AppError
from app.modules.attendance.schemas import AdministrativeAction,AdministrativeEdit,DraftSave,SessionCreate
from app.modules.attendance.service import AttendanceService
from app.modules.face_ai.identification import FaceIdentificationService
from app.modules.auth.dependencies import require_role

router=APIRouter(tags=["attendance"])
def get_attendance_service():return AttendanceService()
def get_face_identification_service():return FaceIdentificationService(get_attendance_service())
async def _face_bytes(image:UploadFile):
    limit=get_settings().face_max_image_bytes;data=await image.read(limit+1);mime=image.content_type;await image.close()
    if len(data)>limit:raise AppError("FACE_IMAGE_TOO_LARGE",f"Face image must not exceed {limit//(1024*1024)} MB.",413)
    return data,mime

@router.post("/faculty/attendance/sessions",status_code=201)
def start_session(payload:SessionCreate,user:Annotated[dict,Depends(require_role("faculty"))],service:Annotated[AttendanceService,Depends(get_attendance_service)]):return service.start(payload,user)
@router.get("/faculty/attendance/sessions")
def faculty_sessions(user:Annotated[dict,Depends(require_role("faculty"))],service:Annotated[AttendanceService,Depends(get_attendance_service)],status:str|None=Query(None,pattern="^(draft|submitted|locked|reopened)$")):return {"items":service.faculty_sessions(user,status)}
@router.get("/faculty/attendance/sessions/{session_id}")
def faculty_session(session_id:str,user:Annotated[dict,Depends(require_role("faculty"))],service:Annotated[AttendanceService,Depends(get_attendance_service)]):return service.details(session_id,user)
@router.put("/faculty/attendance/sessions/{session_id}/draft")
def save_draft(session_id:str,payload:DraftSave,user:Annotated[dict,Depends(require_role("faculty"))],service:Annotated[AttendanceService,Depends(get_attendance_service)]):return service.save(session_id,payload,user)
@router.post("/faculty/attendance/sessions/{session_id}/submit")
def submit(session_id:str,user:Annotated[dict,Depends(require_role("faculty"))],service:Annotated[AttendanceService,Depends(get_attendance_service)]):return service.submit(session_id,user)
@router.get("/faculty/attendance/sessions/{session_id}/face/status")
def face_attendance_status(session_id:str,user:Annotated[dict,Depends(require_role("faculty"))],service:Annotated[FaceIdentificationService,Depends(get_face_identification_service)]):return service.status(session_id,user)
@router.get("/faculty/attendance/sessions/{session_id}/face/recognized")
def face_attendance_recognized(session_id:str,user:Annotated[dict,Depends(require_role("faculty"))],service:Annotated[FaceIdentificationService,Depends(get_face_identification_service)]):return service.recognized(session_id,user)
@router.post("/faculty/attendance/sessions/{session_id}/face/analyze")
async def face_attendance_analyze(session_id:str,image:Annotated[UploadFile,File(...)],user:Annotated[dict,Depends(require_role("faculty"))],service:Annotated[FaceIdentificationService,Depends(get_face_identification_service)]):
    data,mime=await _face_bytes(image);return service.analyze_preview(session_id,user,data,mime)
@router.post("/faculty/attendance/sessions/{session_id}/face/identify")
async def face_attendance_identify(session_id:str,image:Annotated[UploadFile,File(...)],user:Annotated[dict,Depends(require_role("faculty"))],service:Annotated[FaceIdentificationService,Depends(get_face_identification_service)],student_id:Annotated[str|None,Form(alias="studentId")]=None,liveness_images:Annotated[list[UploadFile]|None,File(alias="livenessImages")]=None):
    data,mime=await _face_bytes(image);liveness=[await _face_bytes(item) for item in (liveness_images or [])]
    return service.identify(session_id,user,data,mime,student_id,liveness)
@router.get("/faculty/attendance/sessions/{session_id}/face/students/{student_id}/reference")
def faculty_face_reference(session_id:str,student_id:str,user:Annotated[dict,Depends(require_role("faculty"))],service:Annotated[FaceIdentificationService,Depends(get_face_identification_service)]):
    session=service._session(session_id,user);roster={str(x["student_id"]) for x in service._records(session,user)}
    if student_id not in roster:raise AppError("STUDENT_NOT_IN_SESSION_ROSTER","Student is not in this attendance roster.",403)
    path=service.storage.reference(user["institution_id"],student_id)
    if path is None:raise AppError("FACE_REFERENCE_NOT_FOUND","Enrollment reference image was not found.",404)
    return FileResponse(path,media_type="image/jpeg",headers={"Cache-Control":"private, no-store"})

@router.get("/admin/attendance/sessions")
def admin_sessions(user:Annotated[dict,Depends(require_role("admin"))],service:Annotated[AttendanceService,Depends(get_attendance_service)],page:int=Query(1,ge=1),page_size:int=Query(20,alias="pageSize",ge=1),faculty_id:str|None=None,class_division_id:str|None=None,subject_id:str|None=None,status:str|None=Query(None,pattern="^(draft|submitted|locked|reopened)$"),lecture_date:date|None=None):
    if page_size>get_settings().max_page_size:raise AppError("VALIDATION_ERROR","pageSize exceeds the configured limit.",422)
    filters={k:v for k,v in locals().items() if k in {"faculty_id","class_division_id","subject_id","status","lecture_date"} and v is not None};return service.admin_list(user,filters,page,page_size)
@router.get("/admin/attendance/sessions/{session_id}")
def admin_session(session_id:str,user:Annotated[dict,Depends(require_role("admin"))],service:Annotated[AttendanceService,Depends(get_attendance_service)]):return service.details(session_id,user,admin=True)
@router.post("/admin/attendance/sessions/{session_id}/reopen")
def reopen(session_id:str,payload:AdministrativeAction,user:Annotated[dict,Depends(require_role("admin"))],service:Annotated[AttendanceService,Depends(get_attendance_service)]):return service.admin_action(session_id,"reopen",payload.reason,user)
@router.post("/admin/attendance/sessions/{session_id}/lock")
def lock(session_id:str,payload:AdministrativeAction,user:Annotated[dict,Depends(require_role("admin"))],service:Annotated[AttendanceService,Depends(get_attendance_service)]):return service.admin_action(session_id,"lock",payload.reason,user)
@router.put("/admin/attendance/sessions/{session_id}/records")
def admin_edit(session_id:str,payload:AdministrativeEdit,user:Annotated[dict,Depends(require_role("admin"))],service:Annotated[AttendanceService,Depends(get_attendance_service)]):return service.save(session_id,payload,user,administrative=True,reason=payload.reason)

@router.get("/student/attendance/summary")
def student_summary(user:Annotated[dict,Depends(require_role("student"))],service:Annotated[AttendanceService,Depends(get_attendance_service)]):
    report=service.student_report(user);return {"summary":report["summary"],"subjects":report["subjects"],"formula":report["formula"]}
@router.get("/student/attendance/history")
def student_history(user:Annotated[dict,Depends(require_role("student"))],service:Annotated[AttendanceService,Depends(get_attendance_service)]):
    report=service.student_report(user);return {"items":report["history"],"formula":report["formula"]}
@router.get("/student/attendance/sessions/{session_id}")
def student_session(session_id:str,user:Annotated[dict,Depends(require_role("student"))],service:Annotated[AttendanceService,Depends(get_attendance_service)]):return service.student_report(user,session_id)

"""Admin-only, memory-buffered Student face enrollment APIs."""
from typing import Annotated
from fastapi import APIRouter,Depends,File,Form,UploadFile
from fastapi.responses import FileResponse
from app.core.config import get_settings
from app.core.errors import AppError
from app.modules.auth.dependencies import require_role
from app.modules.face_ai.service import FaceEnrollmentService

router=APIRouter(tags=["face-enrollment"])
def get_face_enrollment_service():return FaceEnrollmentService()
async def _read(file:UploadFile):
    limit=get_settings().face_max_image_bytes;data=await file.read(limit+1);await file.close()
    if len(data)>limit:raise AppError("FACE_IMAGE_TOO_LARGE",f"Face image must not exceed {limit//(1024*1024)} MB.",413)
    return data,file.content_type

@router.get("/admin/students/{student_id}/face/status")
def face_status(student_id:str,admin:Annotated[dict,Depends(require_role("admin"))],service:Annotated[FaceEnrollmentService,Depends(get_face_enrollment_service)]):return service.status(student_id,str(admin["institution_id"]))
@router.get("/admin/students/{student_id}/face/reference")
def face_reference(student_id:str,admin:Annotated[dict,Depends(require_role("admin"))],service:Annotated[FaceEnrollmentService,Depends(get_face_enrollment_service)]):
    status=service.status(student_id,str(admin["institution_id"]));path=service.storage.reference(admin["institution_id"],student_id)
    if not status.get("enrolled") or path is None:raise AppError("FACE_REFERENCE_NOT_FOUND","Enrollment reference image was not found.",404)
    return FileResponse(path,media_type="image/jpeg",headers={"Cache-Control":"private, no-store"})
@router.post("/admin/students/{student_id}/face/analyze")
async def face_analyze(student_id:str,image:Annotated[UploadFile,File(...)],admin:Annotated[dict,Depends(require_role("admin"))],service:Annotated[FaceEnrollmentService,Depends(get_face_enrollment_service)]):
    data,mime=await _read(image);return service.analyze(student_id,str(admin["institution_id"]),data,mime)
@router.post("/admin/students/{student_id}/face/enroll")
async def face_enroll(student_id:str,images:Annotated[list[UploadFile],File(...)],consent_confirmed:Annotated[bool,Form()],enrollment_method:Annotated[str,Form(pattern="^(camera|profile_photo)$")],admin:Annotated[dict,Depends(require_role("admin"))],service:Annotated[FaceEnrollmentService,Depends(get_face_enrollment_service)]):
    frames=[await _read(image) for image in images];return service.enroll(student_id,str(admin["institution_id"]),str(admin["_id"]),frames,enrollment_method,consent_confirmed)
@router.post("/admin/students/{student_id}/face/enroll-from-profile")
def face_enroll_profile(student_id:str,consent_confirmed:Annotated[bool,Form()],admin:Annotated[dict,Depends(require_role("admin"))],service:Annotated[FaceEnrollmentService,Depends(get_face_enrollment_service)]):return service.enroll_profile(student_id,str(admin["institution_id"]),str(admin["_id"]),consent_confirmed)
@router.delete("/admin/students/{student_id}/face")
def face_remove(student_id:str,admin:Annotated[dict,Depends(require_role("admin"))],service:Annotated[FaceEnrollmentService,Depends(get_face_enrollment_service)]):return service.remove(student_id,str(admin["institution_id"]),str(admin["_id"]))

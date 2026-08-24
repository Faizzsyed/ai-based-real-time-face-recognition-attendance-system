"""Secure Student biometric enrollment orchestration and safe metadata contracts."""
from datetime import datetime,timezone
from pathlib import Path
from app.core.config import get_settings
from app.core.errors import AppError
from app.db.object_id import parse_object_id
from app.modules.face_ai.crypto import ENCRYPTION_VERSION,encrypt_embedding
from app.modules.face_ai.engine import FaceEngine
from app.modules.face_ai.repositories import FaceEnrollmentRepository
from app.modules.face_ai.storage import EnrollmentImageStorage
from app.modules.students.repositories import StudentRepository
import logging
from app.core.logging import safe_log
logger=logging.getLogger("FACE")

class FaceEnrollmentService:
    def __init__(self,enrollments=None,students=None,engine=None,settings=None,storage=None):
        self.enrollments=enrollments or FaceEnrollmentRepository();self.students=students or StudentRepository();self.settings=settings or get_settings();self.engine=engine or FaceEngine(self.settings.face_detection_model_path,self.settings.face_recognition_model_path,self.settings.face_detection_threshold,getattr(self.settings,"face_enrollment_consistency_threshold",.40));self.storage=storage or EnrollmentImageStorage()
    def _student(self,student_id,iid):
        student=self.students.find_by_id(student_id,iid)
        if not student:raise AppError("STUDENT_NOT_FOUND","Student was not found in this Institution.",404)
        return student
    def _enabled(self):
        safe_log(logger,logging.INFO,"capability check",face_ai_enabled=self.settings.face_ai_enabled,encryption_configured=bool(self.settings.face_embedding_encryption_key))
        if not self.settings.face_ai_enabled:raise AppError("FACE_AI_DISABLED","Face enrollment is disabled for this deployment.",503)
        if not self.settings.face_embedding_encryption_key:raise AppError("FACE_ENCRYPTION_NOT_CONFIGURED","Face embedding encryption is not configured.",503)
        self.engine._models()
    def capability(self):
        if not self.settings.face_ai_enabled:return {"faceEnrollment":"disabled","reason":"deployment_disabled"}
        if not self.settings.face_embedding_encryption_key:return {"faceEnrollment":"unavailable","reason":"encryption_not_configured"}
        try:self.engine._models()
        except AppError:return {"faceEnrollment":"unavailable","reason":"models_unavailable"}
        return {"faceEnrollment":"available","reason":None}
    @staticmethod
    def safe(document):
        if not document:return {"enrolled":False,"status":"not_enrolled","method":None,"modelVersion":None,"captureCount":0,"localImageCount":0,"livenessMethod":None,"livenessPassed":False,"quality":None,"consentConfirmed":False,"enrolledAt":None,"updatedAt":None}
        return {"enrolled":document.get("status")=="active","status":document.get("status"),"method":document.get("enrollment_method"),"modelVersion":document.get("model_version"),"captureCount":document.get("capture_count",0),"localImageCount":document.get("local_image_count",0),"livenessMethod":document.get("liveness_method"),"livenessPassed":bool(document.get("liveness_passed")),"quality":document.get("quality_metadata"),"consentConfirmed":bool(document.get("consent_confirmed")),"enrolledAt":document.get("enrolled_at"),"updatedAt":document.get("updated_at")}
    def status(self,student_id,iid):self._student(student_id,iid);return {**self.safe(self.enrollments.find(student_id,iid)),"capability":self.capability()}
    def analyze(self,student_id,iid,data,mime):
        self._student(student_id,iid);safe_log(logger,logging.INFO,"enrollment analyze started",student_id=str(student_id));self._enabled()
        try:result=self.engine.analyze_preview(data,mime) if hasattr(self.engine,"analyze_preview") else self.engine.analyze(data,mime)
        except AppError as exc:safe_log(logger,logging.WARNING,"enrollment analyze rejected",student_id=str(student_id),stage=exc.code);raise
        safe_log(logger,logging.INFO,"enrollment analyze accepted",student_id=str(student_id),faces_detected=result["faceCount"],quality="accepted",embedding_generated=False);return {"valid":True,"faceCount":result["faceCount"],"detectionConfidence":result["detectionConfidence"],"quality":result["quality"],"pose":result.get("pose","center"),"faceBox":result.get("faceBox"),"modelVersion":result["modelVersion"]}
    def enroll(self,student_id,iid,actor,frames,method,consent):
        self._student(student_id,iid)
        self._enabled()
        if not consent:raise AppError("BIOMETRIC_CONSENT_REQUIRED","Explicit biometric consent confirmation is required.",422)
        if method=="camera" and len(frames)!=3:raise AppError("THREE_FACE_FRAMES_REQUIRED","Camera enrollment requires exactly three distinct frames.",422)
        if method=="profile_photo" and len(frames)!=1:raise AppError("ONE_PROFILE_PHOTO_REQUIRED","Profile-photo enrollment requires one image.",422)
        result=self.engine.analyze_enrollment_frames(frames) if hasattr(self.engine,"analyze_enrollment_frames") else self.engine.analyze_frames(frames);liveness=result.get("liveness") or {"method":"not_available","passed":False}
        if getattr(self.settings,"face_liveness_mode","optional")=="required" and not liveness.get("passed"):raise AppError("LIVENESS_FAILED","Development liveness challenge was not completed.",422)
        now=datetime.now(timezone.utc);existing=self.enrollments.find(student_id,iid);encrypted=encrypt_embedding(result["embedding"],iid,student_id,result["modelVersion"],self.settings.face_embedding_encryption_key);local_count=self.storage.save(iid,student_id,frames) if method=="camera" else 0
        safe_log(logger,logging.INFO,"enrollment embedding prepared",student_id=str(student_id),captures=len(frames),embedding_encrypted=True)
        document={"institution_id":parse_object_id(iid),"student_id":parse_object_id(student_id),"model_version":result["modelVersion"],"encrypted_embedding":encrypted,"encryption_version":ENCRYPTION_VERSION,"enrollment_method":method,"capture_count":result["captureCount"],"local_image_count":local_count,"liveness_method":liveness.get("method"),"liveness_passed":bool(liveness.get("passed")),"quality_metadata":result["quality"],"consent_confirmed":True,"enrolled_at":existing.get("enrolled_at") if existing else now,"enrolled_by":parse_object_id(actor),"status":"active","created_at":existing.get("created_at") if existing else now,"administrative_event":{"action":"replaced" if existing else "enrolled","at":now,"by":parse_object_id(actor)}}
        saved=self.enrollments.upsert(student_id,iid,document);safe_log(logger,logging.INFO,"enrollment saved",student_id=str(student_id),action="replaced" if existing else "created");return self.safe(saved)
    def enroll_profile(self,student_id,iid,actor,consent):
        student=self._student(student_id,iid);self._enabled();url=student.get("profile_photo_url")
        if not url or not str(url).startswith("/uploads/student_profiles/"):raise AppError("PROFILE_PHOTO_UNAVAILABLE","A managed local Student profile photo is required.",422)
        root=Path(__file__).resolve().parents[4]/"uploads"/"student_profiles";target=(root/Path(url).name).resolve()
        if root.resolve() not in target.parents or not target.is_file():raise AppError("PROFILE_PHOTO_UNAVAILABLE","Managed Student profile photo could not be read.",422)
        mime={".jpg":"image/jpeg",".jpeg":"image/jpeg",".png":"image/png",".webp":"image/webp"}.get(target.suffix.casefold())
        if not mime:raise AppError("INVALID_FACE_IMAGE_FORMAT","Managed profile photo format is unsupported.",422)
        data=target.read_bytes()
        if len(data)>self.settings.face_max_image_bytes:raise AppError("FACE_IMAGE_TOO_LARGE","Face image must not exceed the configured size limit.",413)
        return self.enroll(student_id,iid,actor,[(data,mime)],"profile_photo",consent)
    def remove(self,student_id,iid,actor):
        self._student(student_id,iid)
        if not self.enrollments.remove(student_id,iid):raise AppError("FACE_ENROLLMENT_NOT_FOUND","Student has no active face enrollment.",404)
        self.storage.remove(iid,student_id)
        safe_log(logger,logging.INFO,"enrollment removed",student_id=str(student_id))
        return {"removed":True,"studentId":str(student_id),"removedBy":str(actor)}

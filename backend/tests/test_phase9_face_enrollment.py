"""Phase 9 biometric encryption, quality, tenant, lifecycle, and API safety tests."""
import base64
from pathlib import Path
from types import SimpleNamespace
import cv2,numpy as np,pytest
from bson import ObjectId
from fastapi.testclient import TestClient
from app.api.face_enrollment import get_face_enrollment_service
from app.core.errors import AppError
from app.main import app
from app.modules.auth.dependencies import get_current_user
from app.modules.face_ai.crypto import decrypt_embedding,encrypt_embedding
from app.modules.face_ai.engine import FaceEngine,MODEL_VERSION
from app.modules.face_ai.service import FaceEnrollmentService

IID=ObjectId();OTHER=ObjectId();SID=ObjectId();ADMIN=ObjectId();USER=ObjectId();KEY=base64.b64encode(b"k"*32).decode()
class EnrollmentMemory:
    def __init__(self):self.doc=None
    def find(self,sid,iid):return self.doc if self.doc and str(self.doc["student_id"])==str(sid) and str(self.doc["institution_id"])==str(iid) else None
    def upsert(self,sid,iid,document):self.doc={**document,"_id":self.doc.get("_id",ObjectId()) if self.doc else ObjectId(),"updated_at":__import__("datetime").datetime.now(__import__("datetime").timezone.utc)};return self.doc
    def remove(self,sid,iid):
        if self.find(sid,iid):self.doc=None;return 1
        return 0
class Students:
    def __init__(self):self.doc={"_id":SID,"institution_id":IID,"display_name":"Ada Student","status":"active"}
    def find_by_id(self,sid,iid):return self.doc if str(sid)==str(SID) and str(iid)==str(IID) else None
class StorageMemory:
    def __init__(self):self.count=0
    def save(self,iid,sid,frames):self.count=len(frames);return self.count
    def remove(self,iid,sid):self.count=0
    def reference(self,*_):return None
class FakeEngine:
    def _models(self):return None
    def analyze(self,data,mime):
        if data==b"bad":raise AppError("IMAGE_TOO_BLURRY","Hold still.",422)
        return {"embedding":np.array([1.,0.,0.]),"modelVersion":MODEL_VERSION,"faceCount":1,"detectionConfidence":.98,"quality":{"blurAccepted":True,"lightingAccepted":True,"faceSizeAccepted":True},"fingerprint":"x"}
    def analyze_frames(self,frames):
        if len({x[0] for x in frames})!=len(frames):raise AppError("DUPLICATE_FACE_FRAMES","Duplicates",422)
        return {"embedding":[.8,.6,0.],"modelVersion":MODEL_VERSION,"captureCount":len(frames),"quality":{"stable":True,"frames":[{} for _ in frames]}}
def settings(tmp_path=None,key=KEY):return SimpleNamespace(face_ai_enabled=True,face_embedding_encryption_key=key,face_detection_model_path=Path("missing"),face_recognition_model_path=Path("missing"),face_detection_threshold=.9,face_max_image_bytes=5*1024*1024)
def service():return FaceEnrollmentService(EnrollmentMemory(),Students(),FakeEngine(),settings(),StorageMemory())

def test_aes_gcm_round_trip_and_tenant_bound_authentication():
    payload=encrypt_embedding([.1,.2,.3],IID,SID,MODEL_VERSION,KEY);assert payload["algorithm"]=="AES-256-GCM" and decrypt_embedding(payload,IID,SID,MODEL_VERSION,KEY)==[.1,.2,.3]
    with pytest.raises(AppError) as error:decrypt_embedding(payload,OTHER,SID,MODEL_VERSION,KEY)
    assert error.value.code=="FACE_EMBEDDING_DECRYPTION_FAILED"
def test_encryption_requires_exact_256_bit_key():
    with pytest.raises(AppError) as error:encrypt_embedding([1.],IID,SID,MODEL_VERSION,"hardcoded-short-key")
    assert error.value.code=="FACE_ENCRYPTION_KEY_INVALID"
def test_enroll_returns_safe_metadata_never_embedding_and_replaces():
    svc=service();first=svc.enroll(SID,IID,ADMIN,[(b"1","image/jpeg"),(b"2","image/jpeg"),(b"3","image/jpeg")],"camera",True);assert first["enrolled"] and "encrypted_embedding" not in first and "embedding" not in str(first).casefold()
    original_id=svc.enrollments.doc["_id"];second=svc.enroll(SID,IID,ADMIN,[(b"4","image/jpeg")],"profile_photo",True);assert second["method"]=="profile_photo" and svc.enrollments.doc["_id"]==original_id and "encrypted_embedding" in svc.enrollments.doc
def test_consent_frame_count_duplicates_and_quality_errors():
    svc=service()
    with pytest.raises(AppError) as error:svc.enroll(SID,IID,ADMIN,[(b"1","image/jpeg")]*3,"camera",False)
    assert error.value.code=="BIOMETRIC_CONSENT_REQUIRED"
    with pytest.raises(AppError) as error:svc.enroll(SID,IID,ADMIN,[(b"1","image/jpeg")],"camera",True)
    assert error.value.code=="THREE_FACE_FRAMES_REQUIRED"
    with pytest.raises(AppError) as error:svc.enroll(SID,IID,ADMIN,[(b"1","image/jpeg")]*3,"camera",True)
    assert error.value.code=="DUPLICATE_FACE_FRAMES"
    with pytest.raises(AppError) as error:svc.analyze(SID,IID,b"bad","image/jpeg")
    assert error.value.code=="IMAGE_TOO_BLURRY"
def test_status_remove_replace_and_cross_tenant_scope():
    svc=service();assert svc.status(SID,IID)["status"]=="not_enrolled";svc.enroll(SID,IID,ADMIN,[(b"a","image/jpeg")],"profile_photo",True);assert svc.status(SID,IID)["captureCount"]==1;assert svc.remove(SID,IID,ADMIN)["removed"]
    with pytest.raises(AppError):svc.remove(SID,IID,ADMIN)
    with pytest.raises(AppError) as error:svc.status(SID,OTHER)
    assert error.value.code=="STUDENT_NOT_FOUND"
def test_model_unavailable_and_invalid_format_fail_safely(tmp_path):
    engine=FaceEngine(tmp_path/"missing-detector.onnx",tmp_path/"missing-recognizer.onnx")
    with pytest.raises(AppError) as error:engine.analyze(b"image","image/jpeg")
    assert error.value.code=="FACE_MODEL_UNAVAILABLE"
    detector=tmp_path/"d.onnx";recognizer=tmp_path/"r.onnx";detector.write_bytes(b"model");recognizer.write_bytes(b"model");engine=FaceEngine(detector,recognizer)
    with pytest.raises(AppError) as error:engine.decode(b"x","application/pdf")
    assert error.value.code=="INVALID_FACE_IMAGE_FORMAT"
def test_disabled_deployment_fails_without_processing():
    configured=settings();configured.face_ai_enabled=False;svc=FaceEnrollmentService(EnrollmentMemory(),Students(),FakeEngine(),configured)
    with pytest.raises(AppError) as error:svc.analyze(SID,IID,b"frame","image/jpeg")
    assert error.value.code=="FACE_AI_DISABLED"
def test_capability_distinguishes_enabled_disabled_models_and_encryption(tmp_path):
    enabled=service();assert enabled.capability()=={"faceEnrollment":"available","reason":None}
    disabled=settings();disabled.face_ai_enabled=False;assert FaceEnrollmentService(EnrollmentMemory(),Students(),FakeEngine(),disabled).capability()["reason"]=="deployment_disabled"
    no_key=settings(key="");missing_key=FaceEnrollmentService(EnrollmentMemory(),Students(),FakeEngine(),no_key);assert missing_key.capability()["reason"]=="encryption_not_configured"
    with pytest.raises(AppError) as error:missing_key.enroll(SID,IID,ADMIN,[(b"1","image/jpeg")],"profile_photo",True)
    assert error.value.code=="FACE_ENCRYPTION_NOT_CONFIGURED"
    missing=settings();missing.face_detection_model_path=tmp_path/"missing.onnx";missing.face_recognition_model_path=tmp_path/"missing2.onnx";model_service=FaceEnrollmentService(EnrollmentMemory(),Students(),None,missing);assert model_service.capability()["reason"]=="models_unavailable"
    with pytest.raises(AppError) as error:model_service.analyze(SID,IID,b"x","image/jpeg")
    assert error.value.code=="FACE_MODEL_UNAVAILABLE"
def test_real_quality_gate_rejects_blurry_frame_without_embedding(tmp_path):
    detector_path=tmp_path/"d.onnx";recognizer_path=tmp_path/"r.onnx";detector_path.write_bytes(b"model");recognizer_path.write_bytes(b"model")
    class Detector:
        def setInputSize(self,_):pass
        def detect(self,_):return None,np.array([[20,20,120,120,0,0,0,0,0,0,0,0,0,0,.99]],dtype=np.float32)
    engine=FaceEngine(detector_path,recognizer_path);engine.detector=Detector();engine.recognizer=object();ok,data=cv2.imencode(".jpg",np.full((180,180,3),120,dtype=np.uint8));assert ok
    with pytest.raises(AppError) as error:engine.analyze(data.tobytes(),"image/jpeg")
    assert error.value.code=="IMAGE_TOO_BLURRY" and error.value.details["quality"]["lightingAccepted"]
def test_admin_only_api_and_safe_model_failure():
    class Stub:
        def status(self,*_):return {"enrolled":False,"status":"not_enrolled"}
        def analyze(self,*_):raise AppError("FACE_MODEL_UNAVAILABLE","Models unavailable.",503)
    app.dependency_overrides[get_face_enrollment_service]=lambda:Stub()
    try:
        app.dependency_overrides[get_current_user]=lambda:{"_id":USER,"institution_id":IID,"role":"student"};client=TestClient(app);assert client.get(f"/api/v1/admin/students/{SID}/face/status").status_code==403
        app.dependency_overrides[get_current_user]=lambda:{"_id":ADMIN,"institution_id":IID,"role":"admin"};client=TestClient(app);assert client.get(f"/api/v1/admin/students/{SID}/face/status").status_code==200;response=client.post(f"/api/v1/admin/students/{SID}/face/analyze",files={"image":("face.jpg",b"x","image/jpeg")});assert response.status_code==503 and response.json()["error"]["code"]=="FACE_MODEL_UNAVAILABLE"
    finally:app.dependency_overrides.clear()

"""Phase 10 roster-scoped identification, safety, lifecycle, and API tests."""
import base64
from datetime import datetime,timezone
from pathlib import Path
from types import SimpleNamespace
import numpy as np,pytest
from bson import ObjectId
from fastapi.testclient import TestClient
from app.api.attendance import get_face_identification_service
from app.core.errors import AppError
from app.main import app
from app.modules.auth.dependencies import get_current_user
from app.modules.face_ai.crypto import encrypt_embedding
from app.modules.face_ai.engine import MODEL_VERSION
from app.modules.face_ai.identification import FaceIdentificationService
from backend.tests.test_phase8_attendance import domain,faculty_user,start,FAC_USER,STUDENT_USER,IID,OTHER

KEY=base64.b64encode(b"z"*32).decode()
class Enrollments:
    def __init__(self,docs):self.docs=docs
    def active_for_students(self,ids,iid):return [x for x in self.docs if str(x["institution_id"])==str(iid) and str(x["student_id"]) in {str(v) for v in ids} and x.get("status")=="active"]
class Engine:
    def __init__(self,vector=(1.,0.,0.),error=None):self.vector=np.asarray(vector,dtype=np.float32);self.error=error
    def analyze(self,*_):
        if self.error:raise AppError(self.error,"rejected",422,{"quality":{"safe":True}})
        return {"embedding":self.vector,"modelVersion":MODEL_VERSION}
def cfg(tmp_path,threshold=.6,margin=.1):
    detector=tmp_path/"d.onnx";recognizer=tmp_path/"r.onnx";detector.write_bytes(b"model");recognizer.write_bytes(b"model")
    return SimpleNamespace(face_ai_enabled=True,face_embedding_encryption_key=KEY,face_detection_model_path=detector,face_recognition_model_path=recognizer,face_detection_threshold=.9,face_match_threshold=threshold,face_identification_min_margin=margin,face_recognition_cooldown_seconds=8)
def enrollment(sid,vector,iid=IID,status="active"):
    return {"institution_id":iid,"student_id":sid,"status":status,"model_version":MODEL_VERSION,"encrypted_embedding":encrypt_embedding(vector,iid,sid,MODEL_VERSION,KEY)}
def built(tmp_path,vectors=((1.,0.,0.),(0.,1.,0.)),engine=None,threshold=.6,margin=.1):
    attendance,ids,_,_=domain();session=start(attendance,ids);docs=[enrollment(ids[f"s{i+1}"],v) for i,v in enumerate(vectors)];service=FaceIdentificationService(attendance,Enrollments(docs),engine or Engine(),cfg(tmp_path,threshold,margin));return service,attendance,ids,session

def test_identifies_only_roster_candidate_and_marks_one_ai_suggestion(tmp_path):
    service,attendance,ids,session=built(tmp_path);result=service.identify(session["_id"],faculty_user(),b"frame","image/jpeg");details=attendance.details(session["_id"],faculty_user());row=next(x for x in details["records"] if str(x["student_id"])==str(ids["s1"]));assert result["result"]=="identified" and result["student"]["id"]==str(ids["s1"]) and row["source"]=="face_recognition" and row["status"]=="present" and len(details["records"])==2
    assert "embedding" not in str(result).casefold() and "cipher" not in str(result).casefold()
def test_unknown_and_ambiguous_never_mark(tmp_path):
    service,attendance,ids,session=built(tmp_path,engine=Engine((.8,.6,0.)),threshold=.99);assert service.identify(session["_id"],faculty_user(),b"x","image/jpeg")["result"]=="unknown" and attendance.details(session["_id"],faculty_user())["summary"]["unmarked"]==2
    service,attendance,ids,session=built(tmp_path,vectors=((1.,0.,0.),(.999,.04,0.)),margin=.1);assert service.identify(session["_id"],faculty_user(),b"x","image/jpeg")["result"]=="ambiguous" and attendance.details(session["_id"],faculty_user())["summary"]["unmarked"]==2
@pytest.mark.parametrize("code,result",[("FACE_NOT_FOUND","no_face"),("MULTIPLE_FACES_FOUND","multiple_faces"),("IMAGE_TOO_BLURRY","quality_rejected")])
def test_exactly_one_face_and_quality_results_are_safe(tmp_path,code,result):
    service,attendance,ids,session=built(tmp_path,engine=Engine(error=code));assert service.identify(session["_id"],faculty_user(),b"x","image/jpeg")["result"]==result and attendance.details(session["_id"],faculty_user())["summary"]["unmarked"]==2
def test_cooldown_prevents_duplicate_and_unique_record_remains_authoritative(tmp_path):
    service,attendance,ids,session=built(tmp_path);assert service.identify(session["_id"],faculty_user(),b"1","image/jpeg")["result"]=="identified";assert service.identify(session["_id"],faculty_user(),b"2","image/jpeg")["result"]=="already_recognized";assert len(attendance.details(session["_id"],faculty_user())["records"])==2
def test_manual_override_and_faculty_controlled_submit(tmp_path):
    from app.modules.attendance.schemas import DraftSave,RecordMark
    service,attendance,ids,session=built(tmp_path);service.identify(session["_id"],faculty_user(),b"1","image/jpeg");attendance.save(session["_id"],DraftSave(records=[RecordMark(student_id=str(ids["s1"]),status="late"),RecordMark(student_id=str(ids["s2"]),status="absent")]),faculty_user());details=attendance.details(session["_id"],faculty_user());assert next(x for x in details["records"] if str(x["student_id"])==str(ids["s1"]))["source"]=="manual" and details["status"]=="draft";assert attendance.submit(session["_id"],faculty_user())["status"]=="submitted"
def test_ownership_tenant_and_final_states_rejected(tmp_path):
    service,attendance,ids,session=built(tmp_path)
    with pytest.raises(AppError):service.identify(session["_id"],faculty_user(ObjectId()),b"x","image/jpeg")
    with pytest.raises(AppError):service.identify(session["_id"],faculty_user(FAC_USER,OTHER),b"x","image/jpeg")
    attendance.sessions.update(session["_id"],IID,{"status":"submitted"})
    with pytest.raises(AppError) as error:service.identify(session["_id"],faculty_user(),b"x","image/jpeg")
    assert error.value.code=="ATTENDANCE_NOT_EDITABLE"
    attendance.sessions.update(session["_id"],IID,{"status":"locked"})
    with pytest.raises(AppError):service.status(session["_id"],faculty_user())
def test_status_counts_enrolled_recognized_remaining_manual_only_and_ai_fallback(tmp_path):
    service,attendance,ids,session=built(tmp_path,vectors=((1.,0.,0.),));status=service.status(session["_id"],faculty_user());assert status["stats"]=={"roster":2,"faceEnrolled":1,"recognized":0,"remaining":2,"manualOnly":1};service.settings.face_ai_enabled=False;assert service.identify(session["_id"],faculty_user(),b"x","image/jpeg")["result"]=="ai_unavailable" and attendance.details(session["_id"],faculty_user())["status"]=="draft"
def test_faculty_only_api_contract(tmp_path):
    class Stub:
        def status(self,*_):return {"stats":{"roster":2},"capability":{"faceAttendance":"available"}}
        def identify(self,*_):return {"result":"unknown","attendanceState":"unchanged"}
    app.dependency_overrides[get_face_identification_service]=lambda:Stub()
    try:
        app.dependency_overrides[get_current_user]=lambda:{"_id":STUDENT_USER,"institution_id":IID,"role":"student"};client=TestClient(app);assert client.get("/api/v1/faculty/attendance/sessions/x/face/status").status_code==403
        app.dependency_overrides[get_current_user]=lambda:{"_id":FAC_USER,"institution_id":IID,"role":"faculty"};client=TestClient(app);assert client.get("/api/v1/faculty/attendance/sessions/x/face/status").status_code==200;body=client.post("/api/v1/faculty/attendance/sessions/x/face/identify",files={"image":("x.jpg",b"x","image/jpeg")}).json();assert body["result"]=="unknown" and "embedding" not in str(body).casefold()
    finally:app.dependency_overrides.clear()

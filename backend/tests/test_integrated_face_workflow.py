"""Integrated storage, selected-Student, and liveness enforcement tests."""
from pathlib import Path
import cv2,numpy as np,pytest
from fastapi.testclient import TestClient
from app.api.face_enrollment import get_face_enrollment_service
from app.api.attendance import get_face_identification_service
from app.main import app
from app.modules.auth.dependencies import get_current_user
from app.modules.face_ai.storage import EnrollmentImageStorage
from app.modules.face_ai.engine import FaceEngine,MODEL_VERSION
from backend.tests.test_phase10_face_attendance import Engine,built
from backend.tests.test_phase8_attendance import faculty_user,FAC_USER,STUDENT_USER,IID

def test_private_enrollment_storage_is_scoped_replaced_and_removed(tmp_path):
    iid="0123456789abcdef01234567";sid="89abcdef0123456701234567";ok,jpeg=cv2.imencode(".jpg",np.full((40,40,3),100,dtype=np.uint8));assert ok
    storage=EnrollmentImageStorage(tmp_path);assert storage.save(iid,sid,[(jpeg.tobytes(),"image/jpeg")]*3)==3
    reference=storage.reference(iid,sid);assert reference and reference.parent==tmp_path/iid/sid
    assert storage.save(iid,sid,[(jpeg.tobytes(),"image/jpeg")])==1 and len(list(reference.parent.glob("*.jpg")))==1
    storage.remove(iid,sid);assert storage.reference(iid,sid) is None
    with pytest.raises(ValueError):storage.save(iid,sid,[(b"rejected","image/jpeg")])
    assert not any(tmp_path.rglob("*.jpg")) and "data/face_enrollments/" in (Path(__file__).parents[2]/".gitignore").read_text()
def test_specific_student_never_falls_back_to_another_roster_match(tmp_path):
    service,attendance,ids,session=built(tmp_path)
    denied=service.identify(session["_id"],faculty_user(),b"x","image/jpeg",str(ids["s2"]));assert denied["result"]=="not_verified" and attendance.details(session["_id"],faculty_user())["summary"]["unmarked"]==2
    accepted=service.identify(session["_id"],faculty_user(),b"x","image/jpeg",str(ids["s1"]));assert accepted["result"]=="verified"
def test_required_liveness_rejects_single_frame_and_accepts_server_verified_sequence(tmp_path):
    class LiveEngine(Engine):
        def analyze_frames(self,frames):return {"liveness":{"passed":len(frames)==3,"method":"test-pose-sequence"}}
    service,attendance,ids,session=built(tmp_path,engine=LiveEngine());service.settings.face_liveness_mode="required"
    rejected=service.identify(session["_id"],faculty_user(),b"x","image/jpeg");assert rejected["result"]=="liveness_failed" and attendance.details(session["_id"],faculty_user())["summary"]["unmarked"]==2
    frames=[(bytes([x]),"image/jpeg") for x in (1,2,3)];accepted=service.identify(session["_id"],faculty_user(),b"x","image/jpeg",liveness_frames=frames);assert accepted["result"]=="identified" and accepted["liveness"]["passed"]
def test_server_liveness_requires_ordered_distinct_pose_frames(tmp_path):
    engine=FaceEngine(tmp_path/"d",tmp_path/"r");poses=iter(["center","left","right"])
    engine.analyze=lambda data,mime:{"embedding":np.array([1.,0.,0.]),"modelVersion":MODEL_VERSION,"fingerprint":str(data),"pose":next(poses),"detectionConfidence":.99,"quality":{}}
    assert engine.analyze_frames([(b"1","image/jpeg"),(b"2","image/jpeg"),(b"3","image/jpeg")])["liveness"]["passed"]
    poses=iter(["left","center","right"]);engine.analyze=lambda data,mime:{"embedding":np.array([1.,0.,0.]),"modelVersion":MODEL_VERSION,"fingerprint":str(data),"pose":next(poses),"detectionConfidence":.99,"quality":{}}
    assert not engine.analyze_frames([(b"4","image/jpeg"),(b"5","image/jpeg"),(b"6","image/jpeg")])["liveness"]["passed"]
def test_reference_images_require_admin_or_owned_roster_context(tmp_path):
    reference=tmp_path/"frame_01.jpg";reference.write_bytes(b"jpeg")
    class Storage:
        def reference(self,iid,sid):return reference
    class AdminService:
        storage=Storage()
        def status(self,*_):return {"enrolled":True}
    class FacultyService:
        storage=Storage()
        def _session(self,*_):return {"_id":"session"}
        def _records(self,*_):return [{"student_id":"roster-student"}]
    app.dependency_overrides[get_face_enrollment_service]=lambda:AdminService();app.dependency_overrides[get_face_identification_service]=lambda:FacultyService()
    try:
        app.dependency_overrides[get_current_user]=lambda:{"_id":STUDENT_USER,"institution_id":IID,"role":"student"};client=TestClient(app);assert client.get("/api/v1/admin/students/roster-student/face/reference").status_code==403
        app.dependency_overrides[get_current_user]=lambda:{"_id":FAC_USER,"institution_id":IID,"role":"admin"};client=TestClient(app);assert client.get("/api/v1/admin/students/roster-student/face/reference").status_code==200
        app.dependency_overrides[get_current_user]=lambda:{"_id":FAC_USER,"institution_id":IID,"role":"faculty"};client=TestClient(app);assert client.get("/api/v1/faculty/attendance/sessions/session/face/students/roster-student/reference").status_code==200;assert client.get("/api/v1/faculty/attendance/sessions/session/face/students/other/reference").status_code==403
    finally:app.dependency_overrides.clear()

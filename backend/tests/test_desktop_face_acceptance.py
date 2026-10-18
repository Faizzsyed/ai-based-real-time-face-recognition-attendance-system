"""Desktop acceptance contracts using synthetic vectors and isolated repositories."""
from datetime import timedelta
from unittest.mock import Mock,patch
from types import SimpleNamespace
import asyncio,io,threading
import cv2
import numpy as np
import pytest

from app.core.errors import AppError
from app.modules.face_ai.engine import shared_engine,FaceEngine,MODEL_VERSION
from app.modules.face_ai.crypto import decrypt_embedding
from app.modules.face_ai.storage import EnrollmentImageStorage,reference_response
from app.modules.attendance.schemas import DraftSave,RecordMark
from backend.tests.test_phase10_face_attendance import built,Engine,enrollment
from backend.tests.test_phase8_attendance import faculty_user,IID


def test_shared_models_are_reused_without_reopening_model_files(tmp_path):
    detector=tmp_path/"detector.onnx";recognizer=tmp_path/"recognizer.onnx"
    detector.write_bytes(b"model");recognizer.write_bytes(b"model")
    engine=shared_engine(detector,recognizer)
    assert shared_engine(detector,recognizer) is engine
    assert shared_engine(str(detector),str(recognizer),.90,.40) is engine
    with patch("app.modules.face_ai.engine.cv2.FaceDetectorYN.create",return_value=Mock()) as load_detector,patch("app.modules.face_ai.engine.cv2.FaceRecognizerSF.create",return_value=Mock()) as load_recognizer:
        engine._models();engine._models()
        assert load_detector.call_count==load_recognizer.call_count==1


def test_roster_templates_are_decrypted_once_per_scoped_session(tmp_path):
    service,attendance,ids,session=built(tmp_path)
    with patch("app.modules.face_ai.identification.decrypt_embedding",wraps=decrypt_embedding) as decrypt:
        first=service.identify(session["_id"],faculty_user(),b"one","image/jpeg")
        second=service.identify(session["_id"],faculty_user(),b"two","image/jpeg")
        assert first["result"]=="identified" and second["result"]=="already_recognized"
        assert decrypt.call_count==2  # Two roster candidates, once each.
        replacement=enrollment(ids["s1"],[0.,0.,1.]);service.enrollments.docs[0]=replacement
        assert service.identify(session["_id"],faculty_user(),b"three","image/jpeg")["result"]=="unknown"
        assert decrypt.call_count==4  # Changed ciphertext invalidates prepared templates.


def test_outside_roster_template_is_not_decrypted_or_compared(tmp_path):
    from bson import ObjectId
    service,attendance,ids,session=built(tmp_path,engine=Engine((0.,0.,1.)))
    outsider=enrollment(ObjectId(),[0.,0.,1.])
    service.enrollments.active_for_students=lambda *_:[*service.enrollments.docs,outsider]
    with patch("app.modules.face_ai.identification.decrypt_embedding",wraps=decrypt_embedding) as decrypt:
        assert service.identify(session["_id"],faculty_user(),b"frame","image/jpeg")["result"]=="unknown"
        assert decrypt.call_count==2
    assert attendance.details(session["_id"],faculty_user())["summary"]["unmarked"]==2


def test_already_present_never_writes_again_even_after_cooldown(tmp_path):
    service,attendance,ids,session=built(tmp_path);now=service.clock();service.clock=lambda:now
    save=Mock(wraps=attendance.records.save);attendance.records.save=save
    assert service.identify(session["_id"],faculty_user(),b"frame","image/jpeg")["result"]=="identified"
    service.clock=lambda:now+timedelta(seconds=30)
    assert service.identify(session["_id"],faculty_user(),b"frame","image/jpeg")["result"]=="already_recognized"
    assert save.call_count==1


def test_recognition_does_not_overwrite_a_faculty_manual_override(tmp_path):
    service,attendance,ids,session=built(tmp_path)
    attendance.records.save(session["_id"],IID,[{"student_id":str(ids["s1"]),"status":"late"}],faculty_user()["_id"])
    result=service.identify(session["_id"],faculty_user(),b"frame","image/jpeg")
    assert result["result"]=="manual_override" and result["attendanceState"]=="unchanged"
    assert next(x for x in attendance.details(session["_id"],faculty_user())["records"] if str(x["student_id"])==str(ids["s1"]))["status"]=="late"


def test_failed_draft_write_does_not_start_identity_cooldown(tmp_path):
    service,attendance,ids,session=built(tmp_path);original=attendance.records.save
    attendance.records.save=Mock(side_effect=AppError("DATABASE_UNAVAILABLE","Retry",503))
    with pytest.raises(AppError):service.identify(session["_id"],faculty_user(),b"frame","image/jpeg")
    attendance.records.save=original
    assert service.identify(session["_id"],faculty_user(),b"frame","image/jpeg")["result"]=="identified"


def test_face_suggestion_review_preserves_source_and_never_finalizes(tmp_path):
    service,attendance,ids,session=built(tmp_path)
    service.identify(session["_id"],faculty_user(),b"frame","image/jpeg")
    row=next(x for x in attendance.details(session["_id"],faculty_user())["records"] if x["source"]=="face_recognition")
    payload=DraftSave(records=[RecordMark(student_id=str(row["student_id"]),status=row["status"],remark=row.get("remark"))])
    details=attendance.save(session["_id"],payload,faculty_user())
    assert details["status"]=="draft" and any(x["source"]=="face_recognition" for x in details["records"])
    with pytest.raises(AppError):attendance.submit(session["_id"],faculty_user())  # Other student still unmarked.
    for item in details["records"]:
        if item["status"] is None:attendance.records.save(session["_id"],IID,[{"student_id":str(item["student_id"]),"status":"absent"}],faculty_user()["_id"])
    assert attendance.submit(session["_id"],faculty_user())["status"]=="submitted"
    assert not any(key[:2]==(str(IID),str(session["_id"])) for key in service._templates)


@pytest.mark.parametrize("vector,expected",[((.599,.80075,0.),"unknown"),((.601,.79925,0.),"identified")])
def test_similarity_threshold_is_not_bypassed(tmp_path,vector,expected):
    service,_,_,session=built(tmp_path,vectors=((1.,0.,0.),),engine=Engine(vector),threshold=.6)
    assert service.identify(session["_id"],faculty_user(),b"frame","image/jpeg")["result"]==expected


def test_invalid_probe_vector_never_marks_a_student(tmp_path):
    service,attendance,_,session=built(tmp_path,engine=Engine((float("nan"),0.,0.)))
    assert service.identify(session["_id"],faculty_user(),b"frame","image/jpeg")["result"]=="unknown"
    assert attendance.details(session["_id"],faculty_user())["summary"]["unmarked"]==2


def test_new_reference_images_are_encrypted_and_authenticated(tmp_path):
    iid="0123456789abcdef01234567";sid="89abcdef0123456701234567"
    _,jpeg=cv2.imencode(".jpg",np.full((40,40,3),120,dtype=np.uint8))
    storage=EnrollmentImageStorage(tmp_path,key_text="k"*32)
    storage.save(iid,sid,[(jpeg.tobytes(),"image/jpeg")])
    path=storage.reference(iid,sid);ciphertext=path.read_bytes()
    assert path.suffix==".enc" and jpeg.tobytes() not in ciphertext and not list(tmp_path.rglob("*.jpg"))
    response=reference_response(storage,iid,sid)
    assert response.body.startswith(b"\xff\xd8") and response.headers["cache-control"]=="private, no-store"
    path.write_bytes(ciphertext[:-1]+bytes([ciphertext[-1]^1]))
    with pytest.raises(AppError):storage.read_reference(iid,sid)


def test_encrypted_reference_cannot_be_moved_to_another_student(tmp_path):
    iid="0123456789abcdef01234567";sid="89abcdef0123456701234567";other="89abcdef0123456701234568"
    _,jpeg=cv2.imencode(".jpg",np.full((40,40,3),120,dtype=np.uint8))
    storage=EnrollmentImageStorage(tmp_path,key_text="k"*32);storage.save(iid,sid,[(jpeg.tobytes(),"image/jpeg")])
    destination=storage.directory(iid,other);destination.mkdir()
    (destination/"frame_01.enc").write_bytes(storage.reference(iid,sid).read_bytes())
    with pytest.raises(AppError):storage.read_reference(iid,other)


def test_atomic_template_claim_denies_duplicate_without_replacing_reference_files():
    from backend.tests.test_phase9_face_enrollment import service,SID,IID,ADMIN
    enrollment_service=service()
    enrollment_service.enrollments.create=Mock(side_effect=AppError("FACE_ALREADY_ENROLLED","Duplicate",409))
    enrollment_service.storage.save=Mock()
    with pytest.raises(AppError):enrollment_service.enroll(SID,IID,ADMIN,[(b"one","image/jpeg"),(b"two","image/jpeg"),(b"three","image/jpeg")],"camera",True)
    enrollment_service.storage.save.assert_not_called()
    from types import SimpleNamespace
    from pymongo.errors import DuplicateKeyError
    from app.modules.face_ai.repositories import FaceEnrollmentRepository
    collection=Mock();collection.insert_one.side_effect=DuplicateKeyError("duplicate")
    repository=FaceEnrollmentRepository(SimpleNamespace(face_enrollments=collection))
    with pytest.raises(AppError) as error:repository.create({"institution_id":IID,"student_id":SID})
    assert error.value.code=="FACE_ALREADY_ENROLLED"
    collection.update_one.assert_not_called()


def test_optional_reference_failure_does_not_discard_encrypted_template():
    from backend.tests.test_phase9_face_enrollment import service,SID,IID,ADMIN
    enrollment_service=service();enrollment_service.storage.save=Mock(side_effect=OSError("Private path detail"))
    result=enrollment_service.enroll(SID,IID,ADMIN,[(b"one","image/jpeg"),(b"two","image/jpeg"),(b"three","image/jpeg")],"camera",True)
    assert result["enrolled"] and result["localImageCount"]==0 and "referenceWarning" in result
    assert "Private path" not in str(result) and "encrypted_embedding" in enrollment_service.enrollments.doc


def test_manual_absent_override_remains_authoritative_after_cooldown_and_finalization(tmp_path):
    service,attendance,ids,session=built(tmp_path);now=service.clock()
    service.clock=lambda:now
    service.identify(session["_id"],faculty_user(),b"face","image/jpeg")
    attendance.save(session["_id"],DraftSave(records=[RecordMark(student_id=str(ids["s1"]),status="absent"),RecordMark(student_id=str(ids["s2"]),status="absent")]),faculty_user())
    service.clock=lambda:now+timedelta(seconds=30)
    assert service.identify(session["_id"],faculty_user(),b"again","image/jpeg")["result"]=="manual_override"
    finalized=attendance.submit(session["_id"],faculty_user())
    assert finalized["summary"]["absent"]==2 and finalized["summary"]["present"]==0


def test_finalized_session_during_slow_inference_never_receives_a_suggestion(tmp_path):
    service,attendance,ids,session=built(tmp_path)
    analyze=service.engine.analyze
    def delayed(*args):
        attendance.sessions.update(session["_id"],IID,{"status":"submitted"})
        return analyze(*args)
    service.engine.analyze=delayed;save=Mock(wraps=attendance.records.save);attendance.records.save=save
    with pytest.raises(AppError) as error:service.identify(session["_id"],faculty_user(),b"frame","image/jpeg")
    assert error.value.code=="ATTENDANCE_NOT_EDITABLE"
    save.assert_not_called()


def test_atomic_face_write_preserves_a_manual_choice_made_after_the_service_check():
    from app.modules.attendance.repositories import AttendanceRecordRepository
    from bson import ObjectId
    sid,student,actor=ObjectId(),ObjectId(),ObjectId()
    row={"session_id":sid,"institution_id":IID,"student_id":student,"status":None,"source":"manual"}
    collection=Mock()
    def update(query,operation):
        # A Faculty save wins immediately before the conditional AI update reaches MongoDB.
        row.update(status="absent",source="manual")
        matched=all(row.get(key)==value for key,value in query.items())
        if matched:row.update(operation["$set"])
        return SimpleNamespace(matched_count=int(matched))
    collection.update_one.side_effect=update;collection.find_one.return_value=row
    repository=AttendanceRecordRepository(SimpleNamespace(attendance_records=collection))
    repository.for_session=lambda *_:[row]
    result=repository.save(sid,IID,[{"student_id":str(student),"status":"present"}],actor,source="face_recognition")
    assert result[0]["status"]=="absent" and result[0]["source"]=="manual"


def test_manual_change_keeps_previous_face_suggestion_metadata():
    from app.modules.attendance.repositories import AttendanceRecordRepository
    from bson import ObjectId
    sid,student,actor=ObjectId(),ObjectId(),ObjectId()
    row={"session_id":sid,"institution_id":IID,"student_id":student,"status":None}
    collection=Mock()
    def update(query,operation):
        row.update(operation["$set"])
        return SimpleNamespace(matched_count=1)
    collection.update_one.side_effect=update
    repository=AttendanceRecordRepository(SimpleNamespace(attendance_records=collection));repository.for_session=lambda *_:[row]
    repository.save(sid,IID,[{"student_id":str(student),"status":"present"}],actor,source="face_recognition")
    suggestion=dict(row["face_suggestion"])
    repository.save(sid,IID,[{"student_id":str(student),"status":"absent"}],actor)
    assert row["status"]=="absent" and row["source"]=="manual" and row["review_state"] is None
    assert row["face_suggestion"]==suggestion and suggestion["status"]=="present"


def test_authorized_explicit_replacement_emits_a_safe_audit_event():
    from backend.tests.test_phase9_face_enrollment import service,SID,IID,ADMIN
    enrollment_service=service()
    enrollment_service.enroll(SID,IID,ADMIN,[(b"original","image/jpeg")],"profile_photo",True)
    previous=enrollment_service.enrollments.doc["encrypted_embedding"]
    enrollment_service.enroll(SID,IID,ADMIN,[(b"replacement","image/jpeg")],"profile_photo",True,replace_existing=True)
    assert enrollment_service.enrollments.doc["encrypted_embedding"]!=previous
    call=enrollment_service.audit.record.call_args
    assert call.args[1]=="face.enrollment.replaced" and call.args[3]==SID
    assert not any(word in str(call.args[4]) for word in ("embedding","ciphertext","nonce","image"))


def test_replacement_cross_tenant_rejected_before_analysis_or_storage():
    from backend.tests.test_phase9_face_enrollment import service,SID,OTHER,ADMIN
    enrollment_service=service();enrollment_service.engine=Mock();enrollment_service.storage=Mock()
    with pytest.raises(AppError) as error:enrollment_service.enroll(SID,OTHER,ADMIN,[(b"frame","image/jpeg")],"profile_photo",True,replace_existing=True)
    assert error.value.code=="STUDENT_NOT_FOUND"
    enrollment_service.engine._models.assert_not_called();enrollment_service.storage.save.assert_not_called()
    enrollment_service.audit.record.assert_not_called()


@pytest.mark.parametrize("role",["student","faculty"])
def test_reenrollment_api_rejects_unauthorized_roles(role):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.modules.auth.dependencies import get_current_user
    from app.api.face_enrollment import get_face_enrollment_service
    from backend.tests.test_phase9_face_enrollment import SID,IID,ADMIN
    enrollment_service=Mock()
    app.dependency_overrides[get_face_enrollment_service]=lambda:enrollment_service
    app.dependency_overrides[get_current_user]=lambda:{"_id":ADMIN,"institution_id":IID,"role":role}
    try:
        response=TestClient(app).post(f"/api/v1/admin/students/{SID}/face/enroll",data={"consent_confirmed":"true","enrollment_method":"camera","replace_existing":"true"},files=[("images",("frame.jpg",b"frame","image/jpeg"))])
        assert response.status_code==403
        enrollment_service.enroll.assert_not_called()
    finally:app.dependency_overrides.clear()


def test_legacy_reference_is_read_without_any_migration(tmp_path):
    iid="0123456789abcdef01234567";sid="89abcdef0123456701234567"
    storage=EnrollmentImageStorage(tmp_path,key_text="k"*32);directory=storage.directory(iid,sid);directory.mkdir(parents=True)
    path=directory/"frame_01.jpg";path.write_bytes(b"legacy-jpeg")
    before=path.stat().st_mtime_ns
    assert storage.read_reference(iid,sid)==b"legacy-jpeg"
    assert path.read_bytes()==b"legacy-jpeg" and path.stat().st_mtime_ns==before and not list(directory.glob("*.enc"))


def test_failed_reference_save_cleans_staging_without_plaintext_files(tmp_path):
    iid="0123456789abcdef01234567";sid="89abcdef0123456701234567"
    _,jpeg=cv2.imencode(".jpg",np.full((40,40,3),120,dtype=np.uint8))
    storage=EnrollmentImageStorage(tmp_path,key_text="k"*32)
    with pytest.raises(ValueError):storage.save(iid,sid,[(jpeg.tobytes(),"image/jpeg"),(b"bad","image/jpeg")])
    assert not list(tmp_path.rglob("*.jpg")) and not list(tmp_path.rglob("*.enc"))
    assert not list(tmp_path.rglob("*.staging"))


def test_face_inference_runs_outside_the_api_event_loop():
    from app.api.attendance import face_attendance_identify
    from starlette.datastructures import UploadFile,Headers
    async def scenario():
        entered=asyncio.Event();release=threading.Event();loop=asyncio.get_running_loop();main_thread=threading.get_ident()
        def identify(*_):
            assert threading.get_ident()!=main_thread
            loop.call_soon_threadsafe(entered.set)
            assert release.wait(3)
            return {"result":"unknown","attendanceState":"unchanged"}
        service=SimpleNamespace(identify=identify)
        upload=UploadFile(io.BytesIO(b"frame"),filename="frame.jpg",headers=Headers({"content-type":"image/jpeg"}))
        task=asyncio.create_task(face_attendance_identify("session",upload,faculty_user(),service,None,None))
        try:
            await asyncio.wait_for(entered.wait(),2)
            assert not task.done()  # Other API work can run while inference is pending.
        finally:
            release.set();result=await task
        assert result["result"]=="unknown" and upload.file.closed
    asyncio.run(scenario())


def test_authorized_reference_endpoint_decrypts_encrypted_file_without_exposing_key(tmp_path):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.modules.auth.dependencies import get_current_user
    from app.api.face_enrollment import get_face_enrollment_service
    from backend.tests.test_phase9_face_enrollment import SID,IID,ADMIN
    storage=EnrollmentImageStorage(tmp_path,key_text="k"*32)
    _,jpeg=cv2.imencode(".jpg",np.full((40,40,3),120,dtype=np.uint8))
    storage.save(IID,SID,[(jpeg.tobytes(),"image/jpeg")])
    service=SimpleNamespace(storage=storage,status=lambda *_:{"enrolled":True})
    app.dependency_overrides[get_face_enrollment_service]=lambda:service
    try:
        app.dependency_overrides[get_current_user]=lambda:{"_id":ADMIN,"institution_id":IID,"role":"student"}
        assert TestClient(app).get(f"/api/v1/admin/students/{SID}/face/reference").status_code==403
        app.dependency_overrides[get_current_user]=lambda:{"_id":ADMIN,"institution_id":IID,"role":"admin"}
        response=TestClient(app).get(f"/api/v1/admin/students/{SID}/face/reference")
        assert response.status_code==200 and response.content.startswith(b"\xff\xd8")
        assert response.headers["cache-control"]=="private, no-store"
        assert storage.reference(IID,SID).suffix==".enc" and not list(tmp_path.rglob("*.jpg"))
        assert "encryption_key" not in str(response.headers)
    finally:app.dependency_overrides.clear()

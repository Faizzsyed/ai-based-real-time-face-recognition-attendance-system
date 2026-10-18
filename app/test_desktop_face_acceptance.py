"""Desktop camera acceptance checks without a physical webcam or database."""
import asyncio
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock,patch
import threading
import numpy as np
import pytest

from app.main import PremiumUiController
from app.components.camera import CameraPanelState
from app.services.camera_service import CameraFrame,CameraUnavailable
from app.services.face_preview import DesktopFacePreview,draw_face_box
from app.services.api_client import ApiResult
from app.services.biometric_pipeline import BiometricState
from app.test_management_audit import controller_for,session
from app.core.design import walk_controls


def face(size=200):
    return np.array([80,80,size,size,140,150,220,150,180,200,150,230,210,230,.99],dtype=np.float32)


def analyzer(faces):
    preview=DesktopFacePreview.__new__(DesktopFacePreview);preview.threshold=.9
    preview._lock=threading.RLock()
    preview.detector=Mock();preview.detector.detect.return_value=(None,np.array(faces) if faces else None)
    return preview


def frame(image=None):
    return CameraFrame(np.random.default_rng(9).integers(80,180,(480,640,3),dtype=np.uint8) if image is None else image,1,1.)


def test_local_yunet_preview_detects_single_face_without_embeddings():
    preview=analyzer([face()]);result=preview.analyze(frame())
    assert result["valid"] and result["faceCount"]==1 and result["pose"]=="center"
    assert "embedding" not in result and all(result["quality"][key] for key in ("faceSizeAccepted","lightingAccepted","blurAccepted"))
    preview.analyze(frame());assert preview.detector.detect.call_count==2


@pytest.mark.parametrize("faces,code",[([],"FACE_NOT_FOUND"),([face(),face()],"MULTIPLE_FACES_FOUND"),([face(40)],"FACE_TOO_SMALL")])
def test_one_face_and_minimum_size_are_required(faces,code):
    result=analyzer(faces).analyze(frame())
    assert not result["valid"] and result["code"]==code


def test_quality_rejection_for_blur_and_dark_lighting():
    assert analyzer([face()]).analyze(frame(np.full((480,640,3),120,np.uint8)))["code"]=="IMAGE_TOO_BLURRY"
    dark=np.random.default_rng(9).integers(10,30,(480,640,3),dtype=np.uint8)
    assert analyzer([face()]).analyze(frame(dark))["code"]=="POOR_LIGHTING"


def test_face_rectangle_does_not_modify_capture_pixels():
    original=frame().image;before=original.copy()
    rendered=draw_face_box(original,{"centerX":.5,"centerY":.5,"width":.3,"height":.4})
    assert np.array_equal(original,before) and not np.array_equal(original,rendered)


def live_controller():
    controller,page,_=controller_for("Faculty")
    controller.current_attendance=session();controller.camera_context="attendance";controller.attendance_mode="face"
    controller.camera_service=SimpleNamespace(running=True,stop=Mock())
    controller.render_authenticated_shell=Mock();controller._update_camera_status=Mock()
    controller._recognition_running=True;controller.api_client=Mock()
    updated=deepcopy(session());updated["records"][0].update(status="present",source="face_recognition",review_state="ai_suggested")
    controller.api_client.identify_attendance_face.return_value=ApiResult(True,{"result":"identified","student":{"id":"one","displayName":"One"},"attendanceState":"recognized"})
    controller.api_client.attendance_session.return_value=ApiResult(True,updated)
    controller.api_client.face_attendance_status.return_value=ApiResult(True,{"stats":{"roster":2,"recognized":1,"remaining":1}})
    return controller


def test_recognition_updates_draft_and_keeps_camera_running_for_next_student():
    controller=live_controller();stop=controller.camera_service.stop
    asyncio.run(controller._complete_live_attendance(b"fresh-frame"))
    assert controller.current_attendance["status"]=="draft"
    assert controller.current_attendance["records"][0]["status"]=="present"
    assert controller.current_attendance["records"][0]["review_state"]=="ai_suggested"
    controller.api_client.submit_attendance.assert_not_called();stop.assert_not_called()
    assert controller._await_face_exit and not controller._recognition_running
    assert controller.camera_panel_state.recognized_count==1


def test_pending_manual_marks_survive_server_refresh_after_face_match():
    controller=live_controller();controller.mark_attendance("two","late")
    asyncio.run(controller._complete_live_attendance(b"frame"))
    assert controller.current_attendance["records"][1]["status"]=="late" and controller.attendance_dirty
    assert controller.current_attendance["summary"]["present"]==1 and controller.current_attendance["summary"]["late"]==1


def test_unknown_face_does_not_change_any_roster_record():
    controller=live_controller();before=deepcopy(controller.current_attendance)
    controller.api_client.identify_attendance_face.return_value=ApiResult(True,{"result":"unknown","attendanceState":"unchanged"})
    asyncio.run(controller._complete_live_attendance(b"frame"))
    assert controller.current_attendance==before and "Unknown face" in controller.camera_panel_state.message
    controller.api_client.attendance_session.assert_not_called();controller.api_client.submit_attendance.assert_not_called()
    controller.camera_service.stop.assert_not_called()


def test_api_or_draft_save_failure_releases_camera_and_never_marks_locally():
    controller=live_controller();before=deepcopy(controller.current_attendance)
    controller.api_client.identify_attendance_face.return_value=ApiResult(False,error="Draft save failed. Please retry.")
    asyncio.run(controller._complete_live_attendance(b"frame"))
    assert controller.current_attendance==before and "Draft save failed" in controller.camera_panel_state.message
    controller.camera_service.stop.assert_called_once();controller.api_client.submit_attendance.assert_not_called()


def test_recognized_face_is_not_submitted_repeatedly_before_leaving_view():
    controller=live_controller();asyncio.run(controller._complete_live_attendance(b"frame"))
    analysis=ApiResult(True,{"faceCount":1})
    asyncio.run(controller._handle_camera_analysis(frame(),b"frame2",analysis))
    assert controller.api_client.identify_attendance_face.call_count==1
    assert "Already marked Present" in controller.camera_panel_state.message


def test_face_exit_rearms_capture_for_the_next_student():
    controller=live_controller();asyncio.run(controller._complete_live_attendance(b"frame"))
    analysis=ApiResult(False,{"error":{"code":"FACE_NOT_FOUND"},"faceCount":0})
    asyncio.run(controller._handle_camera_analysis(frame(),b"empty",analysis))
    assert controller._await_face_exit  # One flickering detection must not retrigger the same person.
    controller._face_missing_since-=.4
    asyncio.run(controller._handle_camera_analysis(frame(),b"empty2",analysis))
    assert not controller._await_face_exit and controller.biometric_pipeline.state==BiometricState.SEARCHING_FACE


def test_multiple_faces_clear_partial_enrollment_and_restart_challenge():
    controller=live_controller();controller.camera_context="enrollment";controller.camera_frames=[b"first",b"second"]
    controller.camera_capture_sequences=[1,2];controller.camera_panel_state.capture_count=2;controller.liveness_engine=Mock()
    asyncio.run(controller._handle_camera_analysis(frame(),b"frame",ApiResult(False,{"error":{"code":"MULTIPLE_FACES_FOUND"},"faceCount":2})))
    assert not controller.camera_frames and controller.camera_panel_state.capture_count==0
    assert "Multiple faces" in controller.camera_panel_state.message
    controller.liveness_engine.retry.assert_called_once()


def test_local_preview_loop_does_not_call_preview_api_and_cleans_up_on_failure():
    controller=live_controller();controller._local_face_preview=SimpleNamespace(analyze=Mock(side_effect=RuntimeError("private OpenCV detail")))
    controller.camera_service.raw_snapshot=Mock(return_value=frame())
    controller.camera_service.stop.side_effect=lambda:setattr(controller.camera_service,"running",False)
    asyncio.run(controller._camera_analysis_loop())
    controller.camera_service.stop.assert_called_once()
    controller.api_client.analyze_attendance_face.assert_not_called();controller.api_client.analyze_face.assert_not_called()
    assert "private OpenCV detail" not in controller.camera_panel_state.message and "retry" in controller.camera_panel_state.message


def test_closed_camera_ignores_a_late_recognition_response():
    controller=live_controller();before=deepcopy(controller.current_attendance)
    def identify(*_):
        controller.stop_camera()
        return ApiResult(True,{"result":"identified","student":{"id":"one"},"attendanceState":"recognized"})
    controller.api_client.identify_attendance_face.side_effect=identify
    asyncio.run(controller._complete_live_attendance(b"frame"))
    assert controller.current_attendance==before
    controller.api_client.attendance_session.assert_not_called()


def test_camera_open_runs_off_ui_thread_and_models_are_created_once():
    controller=live_controller();controller.camera_service.running=False;controller.page.run_task=Mock();threads=[]
    def start():threads.append(threading.get_ident());controller.camera_service.running=True
    controller.camera_service.start=start
    with patch("app.main.DesktopFacePreview",return_value=Mock()) as preview,patch("app.main.MediaPipeBlinkDetector",return_value=Mock()) as landmarks:
        main_thread=threading.get_ident();asyncio.run(controller.start_camera());asyncio.run(controller.start_camera())
        assert threads and threads[0]!=main_thread
        assert preview.call_count==landmarks.call_count==1 and controller.page.run_task.call_count==3


def test_failed_camera_open_releases_landmark_resources_without_raw_error():
    controller=live_controller();controller.camera_service.running=False
    controller.camera_service.start=Mock(side_effect=CameraUnavailable("Camera is in use. Close the other app and retry."))
    landmarks=Mock()
    with patch("app.main.DesktopFacePreview",return_value=Mock()),patch("app.main.MediaPipeBlinkDetector",return_value=landmarks):asyncio.run(controller.start_camera())
    landmarks.close.assert_called_once();controller.camera_service.stop.assert_called_once()
    assert controller.camera_panel_state.camera=="unavailable" and controller.blink_detector is None


def test_explicit_reenrollment_flag_is_sent_only_after_user_action():
    controller=live_controller();controller.camera_replace=False
    controller._enroll_current_face("student",[])
    controller.api_client.enroll_face.assert_called_with("student",[])
    controller.authorize_face_reenroll();controller._enroll_current_face("student",[])
    controller.api_client.enroll_face.assert_called_with("student",[],replace_existing=True)


def test_enrollment_request_exception_releases_camera_and_shows_safe_message():
    controller=live_controller();controller.camera_context="enrollment";controller.camera_student={"_id":"student"}
    controller.camera_frames=[b"a",b"b",b"c"];controller.camera_capture_sequences=[1,2,3]
    controller.api_client.enroll_face.side_effect=RuntimeError("Private transport detail")
    controller._face_message=Mock()
    asyncio.run(controller._finalize_live_enrollment())
    controller.camera_service.stop.assert_called_once()
    assert not controller.camera_frames and not controller._enrollment_finalizing
    assert "Private transport detail" not in str(controller._face_message.call_args)


def test_server_duplicate_pair_recaptures_the_offending_slot():
    controller=live_controller();controller.camera_context="enrollment";controller.camera_student={"_id":"student"}
    controller.camera_frames=[b"a",b"b",b"c"];controller.camera_capture_sequences=[1,2,3]
    controller.api_client.enroll_face.return_value=ApiResult(False,{"error":{"code":"DUPLICATE_FACE_FRAMES","details":{"duplicateFrameIndices":[0,1]}}})
    asyncio.run(controller._finalize_live_enrollment())
    assert controller.camera_frames==[b"a",b"c"] and controller.camera_capture_sequences==[1,3]
    controller.camera_service.stop.assert_not_called()


@pytest.mark.parametrize("stage",["identify_attendance_face","attendance_session","face_attendance_status"])
def test_delayed_response_cannot_replace_another_session(stage):
    controller=live_controller();replacement=deepcopy(session());replacement["_id"]="another-session"
    original=getattr(controller.api_client,stage).return_value
    def switch(*_):
        controller.current_attendance=deepcopy(replacement)
        return original
    getattr(controller.api_client,stage).side_effect=switch
    asyncio.run(controller._complete_live_attendance(b"frame"))
    assert controller.current_attendance==replacement
    controller.render_authenticated_shell.assert_not_called()
    assert not controller._recognition_running


def test_slow_recognition_keeps_event_loop_responsive_and_suppresses_inflight_duplicate():
    async def scenario():
        controller=live_controller();entered=asyncio.Event();release=threading.Event();loop=asyncio.get_running_loop()
        response=controller.api_client.identify_attendance_face.return_value
        def slow(*_):
            loop.call_soon_threadsafe(entered.set)
            assert release.wait(3)
            return response
        controller.api_client.identify_attendance_face.side_effect=slow
        task=asyncio.create_task(controller._complete_live_attendance(b"frame"))
        try:
            await asyncio.wait_for(entered.wait(),2)
            assert "saving" in controller.camera_panel_state.message
            await controller._complete_live_attendance(b"duplicate")
            assert controller.api_client.identify_attendance_face.call_count==1
            controller.camera_service.stop.assert_not_called()
            controller.stop_camera();before=deepcopy(controller.current_attendance)
        finally:
            release.set();await task
        assert controller.current_attendance==before
        controller.api_client.attendance_session.assert_not_called()
    asyncio.run(scenario())


def test_manual_override_saved_during_refresh_survives_the_older_response():
    controller=live_controller();stale=deepcopy(controller.api_client.attendance_session.return_value.data)
    def refresh(*_):
        controller.mark_attendance("one","absent")
        saved=deepcopy(controller.current_attendance)
        controller.api_client.save_attendance_draft.return_value=ApiResult(True,saved)
        assert controller.save_attendance()
        return ApiResult(True,stale)
    controller.api_client.attendance_session.side_effect=refresh
    asyncio.run(controller._complete_live_attendance(b"frame"))
    row=controller.current_attendance["records"][0]
    assert row["status"]=="absent" and row["source"]=="manual" and not controller.attendance_dirty
    assert "Faculty mark kept" in controller.camera_panel_state.message
    assert controller.current_attendance["summary"]["attendancePercentage"]==0.


@pytest.mark.parametrize("pipeline",["analysis","preview","liveness"])
def test_old_camera_worker_failure_does_not_stop_new_camera(pipeline):
    controller=live_controller();generation=controller._camera_generation
    controller._recognition_running=False
    controller.camera_service.raw_snapshot=Mock(return_value=frame())
    def late_failure(*_):
        controller._camera_generation+=1
        controller.camera_panel_state=CameraPanelState(camera="connected",message="New camera")
        raise RuntimeError("Old camera task failed")
    controller._local_face_preview=SimpleNamespace(analyze=late_failure)
    controller.camera_service.encode_guided_preview=late_failure
    controller.blink_detector=SimpleNamespace(observe=late_failure)
    controller.biometric_pipeline.state=BiometricState.LIVENESS_TRACKING
    task={"analysis":controller._camera_analysis_loop,"preview":controller._camera_preview_loop,"liveness":controller._camera_liveness_loop}[pipeline]
    asyncio.run(task())
    assert controller._camera_generation==generation+1
    assert controller.camera_panel_state.message=="New camera"
    controller.camera_service.stop.assert_not_called()


def test_delayed_enrollment_response_cannot_close_a_new_student_dialog():
    controller=live_controller();controller.camera_context="enrollment";controller.camera_student={"_id":"old"}
    controller.camera_frames=[b"a",b"b",b"c"];controller._face_message=Mock()
    def enroll(*args,**kwargs):
        controller.stop_camera();controller.camera_student={"_id":"new"}
        controller.camera_panel_state=CameraPanelState(message="New student dialog")
        return ApiResult(True,{"enrolled":True})
    controller.api_client.enroll_face.side_effect=enroll
    asyncio.run(controller._finalize_live_enrollment())
    assert controller.camera_student["_id"]=="new" and controller.camera_panel_state.message=="New student dialog"
    controller._face_message.assert_not_called()


def test_restart_after_failed_draft_write_can_retry_the_same_student():
    controller=live_controller();controller.camera_service.stop.side_effect=lambda:setattr(controller.camera_service,"running",False)
    controller.api_client.identify_attendance_face.side_effect=[ApiResult(False,error="Draft save failed."),controller.api_client.identify_attendance_face.return_value]
    asyncio.run(controller._complete_live_attendance(b"frame"))
    assert not controller._recognition_running and not controller._await_face_exit
    controller.camera_service.running=True
    asyncio.run(controller._complete_live_attendance(b"new-frame"))
    assert controller.current_attendance["records"][0]["status"]=="present"
    assert controller.api_client.identify_attendance_face.call_count==2


def test_back_to_sessions_releases_camera_and_invalidates_pending_response():
    controller=live_controller();controller.load_faculty_attendance=Mock();generation=controller._camera_generation
    controller.back_to_sessions()
    assert controller.current_attendance is None and controller.camera_context is None
    assert controller._camera_generation>generation
    controller.camera_service.stop.assert_called_once()


@pytest.mark.parametrize("interruption",[
    ApiResult(False,{"error":{"code":"MULTIPLE_FACES_FOUND"},"faceCount":2}),
    ApiResult(False,{"error":{"code":"IMAGE_TOO_BLURRY"},"faceCount":1}),
])
def test_face_exit_requires_uninterrupted_empty_view(interruption):
    controller=live_controller();asyncio.run(controller._complete_live_attendance(b"frame"))
    controller.liveness_engine=Mock()
    empty=ApiResult(False,{"error":{"code":"FACE_NOT_FOUND"},"faceCount":0})
    asyncio.run(controller._handle_camera_analysis(frame(),b"",empty))
    controller._face_missing_since-=.4
    asyncio.run(controller._handle_camera_analysis(frame(),b"",interruption))
    asyncio.run(controller._handle_camera_analysis(frame(),b"",empty))
    assert controller._await_face_exit
    controller._face_missing_since-=.4
    asyncio.run(controller._handle_camera_analysis(frame(),b"",empty))
    assert not controller._await_face_exit

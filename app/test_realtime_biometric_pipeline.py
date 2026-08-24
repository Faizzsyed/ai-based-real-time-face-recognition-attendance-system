"""Deterministic real-time pipeline tests; no physical webcam required."""
import asyncio,time
import numpy as np
import pytest
from app.services.camera_service import LatestFrameBuffer,CameraService
from app.services.biometric_pipeline import BiometricPipeline,BiometricState,BlinkChallenge,FaceObservation
from app.components.camera import CameraPanelState
from app.main import PremiumUiController
from app.services.api_client import ApiResult

def observation(t,closed=False,count=1,center=(.5,.5),size=.3,quality=True,seq=1):return FaceObservation(t,count,center,size,quality,closed,seq,b"jpeg"+bytes([seq%255]),1.)
def stable_pipeline():
    pipeline=BiometricPipeline(stability_seconds=.2,blink=BlinkChallenge(2,3,1,1));pipeline.start();pipeline.observe(observation(0));pipeline.observe(observation(.25));return pipeline
def test_latest_frame_buffer_drops_stale_frames():
    buffer=LatestFrameBuffer();buffer.publish(np.zeros((2,2,3),dtype=np.uint8));buffer.publish(np.ones((2,2,3),dtype=np.uint8));latest=buffer.latest();assert latest.sequence==2 and buffer.queued==1 and buffer.dropped==1
def test_capture_loop_is_independent_and_releases():
    class Capture:
        def __init__(self):self.released=False;self.reads=0
        def isOpened(self):return True
        def set(self,*_):return True
        def read(self):self.reads+=1;return True,np.zeros((8,8,3),dtype=np.uint8)
        def release(self):self.released=True
    capture=Capture();service=CameraService(capture_factory=lambda _:capture);service.start();time.sleep(.02);assert capture.reads>1 and service.raw_snapshot() is not None;service.stop();assert capture.released
def test_recognition_is_gated_and_runs_once_after_two_blinks():
    pipeline=stable_pipeline();assert not pipeline.begin_recognition()
    for t,closed in ((.3,False),(.4,True),(.5,False),(.6,False),(.7,True),(.8,False)):pipeline.observe(observation(t,closed,seq=int(t*10)))
    assert pipeline.state==BiometricState.LIVENESS_PASSED and pipeline.blink.blinks==2;assert pipeline.begin_recognition() and not pipeline.begin_recognition()
def test_one_blink_and_timeout_fail():
    pipeline=stable_pipeline()
    for t,closed in ((.3,False),(.4,True),(.5,False),(.6,False)):pipeline.observe(observation(t,closed))
    assert pipeline.blink.blinks==1 and pipeline.state!=BiometricState.LIVENESS_PASSED;pipeline.observe(observation(3.3,False));assert pipeline.state==BiometricState.ERROR and not pipeline.begin_recognition()
def test_continuously_closed_eyes_are_not_multiple_blinks():
    challenge=BlinkChallenge(2,3,1,1);challenge.start(0)
    for t,closed in ((.1,False),(.2,True),(.3,True),(.4,True),(.5,False)):challenge.observe(closed,t)
    assert challenge.blinks==1 and not challenge.passed
def test_invalid_stability_and_multiple_faces_reset_challenge():
    pipeline=stable_pipeline();pipeline.observe(observation(.3,False));assert pipeline.blink.started_at is not None;pipeline.observe(observation(.4,False,center=(.8,.5)));assert pipeline.state==BiometricState.LIVENESS_TRACKING;before=pipeline.blink.blinks;pipeline.observe_liveness(None,.5,face_count=2);assert pipeline.blink.blinks==before and pipeline.blink.failure_reason=="LIVENESS_FACE_LOST"
def test_cooldown_blocks_duplicate_cycle():
    pipeline=stable_pipeline()
    for t,closed in ((.3,False),(.4,True),(.5,False),(.6,False),(.7,True),(.8,False)):pipeline.observe(observation(t,closed))
    assert pipeline.begin_recognition();pipeline.finish_recognition("identified",1);pipeline.cooldown();assert pipeline.observe(observation(1.5))==BiometricState.COOLDOWN

def test_post_liveness_neutral_stability_precedes_three_independent_captures():
    class Page:
        def __init__(self):self.tasks=[]
        def run_task(self,handler,*_):self.tasks.append(handler)
    controller=PremiumUiController.__new__(PremiumUiController);controller.biometric_pipeline=BiometricPipeline();controller.biometric_pipeline.state=BiometricState.RETURN_TO_NEUTRAL;controller.camera_panel_state=CameraPanelState();controller.camera_frames=[];controller.camera_capture_sequences=[];controller._capture_retries=0;controller._final_validation_retries=0;controller._enrollment_finalizing=False;controller._neutral_since=None;controller._neutral_anchor=None;controller._capture_last_at=0.;controller.page=Page();events=[];controller.stop_camera=lambda *_:events.append("released")
    data={"pose":"center"};quality={"faceSizeAccepted":True,"lightingAccepted":True,"blurAccepted":True};box={"centerX":.5,"centerY":.5,"size":.3}
    controller._handle_enrollment_capture(0.,1,b"a",data,quality,box,False,True);assert not controller.camera_frames and controller.biometric_pipeline.state==BiometricState.STABILIZING_FOR_CAPTURE
    controller._handle_enrollment_capture(.8,10,b"b",data,quality,box,False,True);controller._handle_enrollment_capture(1.4,20,b"c",data,quality,box,False,True);controller._handle_enrollment_capture(2.,30,b"d",data,quality,box,False,True)
    assert controller.camera_frames==[b"b",b"c",b"d"] and controller.camera_capture_sequences==[10,20,30] and not events and len(controller.page.tasks)==1 and controller.biometric_pipeline.state==BiometricState.IDENTITY_CONSISTENCY

def test_post_liveness_capture_resets_on_nonfrontal_or_bad_quality():
    controller=PremiumUiController.__new__(PremiumUiController);controller.biometric_pipeline=BiometricPipeline();controller.biometric_pipeline.state=BiometricState.RETURN_TO_NEUTRAL;controller.camera_panel_state=CameraPanelState();controller.camera_frames=[];controller.camera_capture_sequences=[];controller._capture_retries=0;controller._neutral_since=None;controller._neutral_anchor=None;controller._capture_last_at=0.
    controller._handle_enrollment_capture(0.,1,b"a",{"pose":"left"},{},{"centerX":.5,"centerY":.5,"size":.3},False,False)
    assert not controller.camera_frames and controller.biometric_pipeline.state==BiometricState.RETURN_TO_NEUTRAL

def test_duplicate_source_sequence_is_discarded_without_resetting_liveness():
    controller=PremiumUiController.__new__(PremiumUiController);controller.biometric_pipeline=BiometricPipeline();controller.biometric_pipeline.state=BiometricState.CAPTURING;controller.camera_panel_state=CameraPanelState();controller.camera_frames=[b"first"];controller.camera_capture_sequences=[101];controller._capture_retries=0;controller._neutral_since=0.;controller._neutral_anchor=((.5,.5),.3);controller._capture_last_at=0.;controller.stop_camera=lambda *_:(_ for _ in ()).throw(AssertionError("camera must remain open"))
    quality={"faceSizeAccepted":True,"lightingAccepted":True,"blurAccepted":True};controller._handle_enrollment_capture(1.,101,b"second",{"pose":"center"},quality,{"centerX":.5,"centerY":.5,"size":.3},False,True)
    assert controller.camera_frames==[b"first"] and controller.camera_capture_sequences==[101] and controller._capture_retries==1 and controller.biometric_pipeline.state==BiometricState.CAPTURING

def test_capture_slots_require_bounded_spacing_and_new_sequence():
    controller=PremiumUiController.__new__(PremiumUiController);controller.biometric_pipeline=BiometricPipeline();controller.biometric_pipeline.state=BiometricState.CAPTURING;controller.camera_panel_state=CameraPanelState();controller.camera_frames=[b"first"];controller.camera_capture_sequences=[10];controller._capture_retries=0;controller._neutral_since=0.;controller._neutral_anchor=((.5,.5),.3);controller._capture_last_at=1.
    quality={"faceSizeAccepted":True,"lightingAccepted":True,"blurAccepted":True};controller._handle_enrollment_capture(1.2,11,b"second",{"pose":"center"},quality,{"centerX":.5,"centerY":.5,"size":.3},False,True);assert len(controller.camera_frames)==1
    controller._handle_enrollment_capture(1.6,12,b"second",{"pose":"center"},quality,{"centerX":.5,"centerY":.5,"size":.3},False,True);assert controller.camera_capture_sequences==[10,12]

def test_open_eye_calibration_builds_adaptive_threshold():
    challenge=BlinkChallenge(required=1,timeout=5,min_open_frames=2,min_closed_frames=2,calibration_samples=8,closure_delta=.2)
    challenge.start(0)
    for index,value in enumerate((.03,.04,.05,.04,.06,.05,.04,.03),1):challenge.observe_metric(value,index/15)
    assert challenge.open_baseline==pytest.approx(.04) and challenge.closed_threshold==pytest.approx(.24) and challenge.phase=="need_open"

def test_adaptive_open_closed_open_at_15_fps_is_one_blink():
    challenge=BlinkChallenge(required=1,timeout=5,min_open_frames=2,min_closed_frames=2,calibration_samples=3,closure_delta=.2);challenge.start(0)
    samples=[.04,.05,.04,.04,.05,.42,.45,.05,.04]
    for index,value in enumerate(samples,1):challenge.observe_metric(value,index/15)
    assert challenge.passed and challenge.blinks==1
    for index in range(3):challenge.observe_metric(.45,1+index/15)
    assert challenge.blinks==1

def test_one_noisy_closed_sample_does_not_count_and_face_loss_is_safe():
    challenge=BlinkChallenge(required=1,timeout=5,min_open_frames=2,min_closed_frames=2,calibration_samples=2,closure_delta=.2);challenge.start(0)
    for t,value in ((.1,.04),(.2,.05),(.3,.04),(.4,.04),(.5,.5),(.6,.04),(.7,.04)):challenge.observe_metric(value,t)
    assert challenge.blinks==0 and not challenge.passed
    challenge.observe_metric(None,.8,face_valid=False);assert challenge.blinks==0 and challenge.failure_reason=="LIVENESS_FACE_LOST"

def test_five_second_timeout_retries_without_restarting_pipeline():
    challenge=BlinkChallenge(required=1,timeout=5,min_open_frames=2,min_closed_frames=2,calibration_samples=2);pipeline=BiometricPipeline(stability_seconds=.1,blink=challenge);pipeline.start();pipeline.observe(observation(0));pipeline.observe(observation(.2));pipeline.observe_liveness(.04,.3);pipeline.observe_liveness(.04,.4);assert pipeline.state==BiometricState.LIVENESS_TRACKING
    pipeline.observe_liveness(.04,5.4);assert pipeline.state==BiometricState.ERROR
    same=id(pipeline);pipeline.retry_liveness(5.5);assert id(pipeline)==same and pipeline.state==BiometricState.LIVENESS_CALIBRATING and pipeline.blink.blinks==0

def test_liveness_pass_cannot_transition_back_to_tracking():
    pipeline=BiometricPipeline(blink=BlinkChallenge(1,5,1,1));pipeline.state=BiometricState.LIVENESS_PASSED
    pipeline.observe_liveness(0.,1);assert pipeline.state==BiometricState.LIVENESS_PASSED

def test_server_duplicate_recaptures_last_slot_without_stopping_camera():
    class Camera:running=True
    class Api:
        def enroll_face(self,*_):return ApiResult(False,{"error":{"code":"DUPLICATE_FACE_FRAMES"}},422,"fresh frame")
    controller=PremiumUiController.__new__(PremiumUiController);controller.camera_frames=[b"a",b"b",b"c"];controller.camera_capture_sequences=[10,20,30];controller.camera_panel_state=CameraPanelState(capture_count=3);controller.camera_student={"_id":"s","display_name":"Student"};controller.camera_service=Camera();controller.api_client=Api();controller.biometric_pipeline=BiometricPipeline();controller.biometric_pipeline.state=BiometricState.IDENTITY_CONSISTENCY;controller._final_validation_retries=0;controller._enrollment_finalizing=True;controller.stop_camera=lambda *_:(_ for _ in ()).throw(AssertionError("recoverable duplicate must keep camera open"));controller._update_camera_status=lambda:None
    asyncio.run(controller._finalize_live_enrollment());assert controller.camera_frames==[b"a",b"b"] and controller.camera_capture_sequences==[10,20] and controller.biometric_pipeline.state==BiometricState.CAPTURING and not controller._enrollment_finalizing

def test_successful_finalization_releases_camera_and_refreshes_student_status():
    class Camera:running=True
    class Api:
        def enroll_face(self,*_):return ApiResult(True,{"enrolled":True},200)
    events=[];controller=PremiumUiController.__new__(PremiumUiController);controller.camera_frames=[b"a",b"b",b"c"];controller.camera_capture_sequences=[10,20,30];controller.camera_student={"_id":"s","display_name":"Student"};controller.camera_service=Camera();controller.api_client=Api();controller._enrollment_finalizing=True;controller.stop_camera=lambda *_:events.append("released");controller._face_message=lambda *args:events.append("success");controller.load_face_enrollments=lambda:events.append("refreshed")
    asyncio.run(controller._finalize_live_enrollment());assert events==["released","success","refreshed"] and not controller._enrollment_finalizing

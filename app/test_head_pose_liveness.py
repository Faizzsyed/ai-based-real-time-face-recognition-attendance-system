"""Pose geometry and physical-bug regressions; no webcam or database access."""
import asyncio
import math
import time
from types import SimpleNamespace
from unittest.mock import Mock,patch,AsyncMock

import cv2
import numpy as np
import pytest

from app.core.config import get_settings
from app.main import PremiumUiController
from app.services.biometric_pipeline import BlinkChallenge,EyeMetric,BiometricState,head_yaw_from_landmarks,MediaPipeBlinkDetector
from app.services.camera_service import CameraService,CameraFrame
from app.services.liveness_challenge import ChallengeType,LivenessChallengeEngine
from app.test_desktop_face_acceptance import live_controller


def landmarks(turn=0.,roll=0.,mirrored=False,width=960,height=540):
    # Three points from Google's canonical_face_model.obj (indices 1/33/263).
    # https://github.com/google-ai-edge/mediapipe/blob/master/mediapipe/modules/face_geometry/data/canonical_face_model.obj
    points={1:(0.,-1.126865,7.475604),33:(-4.445859,2.663991,3.173422),263:(4.445859,2.663991,3.173422)}
    yaw=math.radians(turn);angle=math.radians(roll);result=[None]*264
    for index,(x,y,z) in points.items():
        # Positive turn points the nose toward the person's left (image right).
        px=(x*math.cos(yaw)+z*math.sin(yaw))*25;py=-y*25
        rx=px*math.cos(angle)-py*math.sin(angle);ry=px*math.sin(angle)+py*math.cos(angle)
        if mirrored:rx=-rx
        result[index]=SimpleNamespace(x=.5+rx/width,y=.5+ry/height)
    return result


def metric(turn=0.,mirrored=False,roll=0.):
    yaw=head_yaw_from_landmarks(landmarks(turn,roll,mirrored),960,540,mirrored)
    return EyeMetric(1,.04,.04,yaw,mirrored)


def challenge(direction=ChallengeType.TURN_LEFT,**kwargs):
    # One supported gesture, selected deterministically for the regression.
    return LivenessChallengeEngine(BlinkChallenge(calibration_samples=8,timeout=9),enrollment_steps=1,chooser=lambda _: (direction,),**kwargs)


def calibrated(value,turn=0.):
    value.start(0.)
    for index in range(8):value.observe(metric(turn),index/15)
    assert value.neutral_yaw is not None
    return 8/15


@pytest.mark.parametrize("mirrored",[False,True])
@pytest.mark.parametrize("turn,direction",[(12.,ChallengeType.TURN_LEFT),(-12.,ChallengeType.TURN_RIGHT)])
def test_human_direction_is_correct_for_raw_and_mirrored_landmarks(mirrored,turn,direction):
    probe=metric(turn,mirrored)
    assert (probe.yaw>0)==(direction==ChallengeType.TURN_LEFT)
    value=challenge(direction);value.start(0.)
    for index in range(8):value.observe(metric(0.,mirrored),index/15)
    for index in range(4):value.observe(probe,1+index/15)
    assert value.passed


@pytest.mark.parametrize("roll",[-15.,15.])
@pytest.mark.parametrize("mirrored",[False,True])
def test_eye_line_projection_rejects_head_roll_and_image_aspect_ratio(roll,mirrored):
    assert metric(0.,mirrored,roll).yaw==pytest.approx(0.,abs=1e-8)
    assert metric(12.,mirrored,roll).yaw==pytest.approx(metric(12.).yaw)


def test_mirror_flag_is_needed_only_for_reflected_analysis_input():
    reflected=landmarks(12.,mirrored=True)
    assert head_yaw_from_landmarks(reflected,960,540)<0
    assert head_yaw_from_landmarks(reflected,960,540,mirrored=True)>0


def test_mediapipe_adapter_passes_actual_mirror_configuration_to_pose_measurement():
    detector=MediaPipeBlinkDetector.__new__(MediaPipeBlinkDetector)
    detector.input_mirrored=True;detector._last_timestamp=0
    detector._mp=SimpleNamespace(Image=lambda **kwargs:kwargs,ImageFormat=SimpleNamespace(SRGB="rgb"))
    detector._landmarker=SimpleNamespace(detect_for_video=lambda *_:SimpleNamespace(face_blendshapes=[[]],face_landmarks=[landmarks(12.,mirrored=True)]))
    observed=detector._observe(np.zeros((540,960,3),np.uint8),1)
    assert observed.yaw>0 and observed.mirrored


def test_capture_preview_and_analysis_keep_the_same_unflipped_orientation():
    image=np.zeros((80,160,3),np.uint8);image[:,:80,0]=240
    camera=CameraService();camera.frames.publish(image)
    raw=camera.raw_snapshot()
    for encoded in (camera.encode_preview(raw),camera.encode_analysis(raw)):
        decoded=cv2.imdecode(np.frombuffer(encoded,np.uint8),cv2.IMREAD_COLOR)
        assert decoded[:,:60,0].mean()>decoded[:,100:,0].mean()+150
    assert np.array_equal(raw.image,image)


def test_neutral_calibration_waits_for_stillness_and_uses_personal_baseline():
    value=challenge();value.start(0.)
    for index in range(8):value.observe(EyeMetric(1,.04,.04,index*.03),index/15)
    assert value.neutral_yaw is None and value.step_started_at is None
    # Time spent settling the head must not consume the nine-second action window.
    for index in range(8):value.observe(EyeMetric(1,.04,.04,.18+(index%2)*.002),8+index/15)
    assert value.neutral_yaw==pytest.approx(.181) and value.step_started_at>8
    for index in range(4):value.observe(EyeMetric(1,.04,.04,.181+.105),9+index/15)
    assert value.passed


def test_pose_scale_explains_old_rejection_of_a_small_natural_turn():
    probe=metric(12.)
    assert probe.yaw==pytest.approx(.10285,abs=.0001)
    assert .10<probe.yaw<.16
    previous=challenge(pose_delta=.16);current=challenge()
    for value in (previous,current):
        calibrated(value)
        for index in range(5):value.observe(probe,1+index/15)
    assert not previous.passed and current.passed


def test_insufficient_or_wrong_direction_movement_never_passes():
    value=challenge();calibrated(value)
    for index in range(20):value.observe(metric(5. if index<10 else -12.),1+index/15)
    assert not value.passed and not value.failed


def test_three_consecutive_filtered_observations_are_required():
    value=challenge();calibrated(value)
    for index in range(3):value.observe(metric(12.),1+index/15)
    assert value.pose_streak==2 and not value.passed
    value.observe(metric(12.),1.3)
    assert value.passed


def test_single_noisy_intermediate_sample_does_not_restart_a_valid_turn():
    value=challenge();calibrated(value);attempt=value.attempt_id;baseline=value.neutral_yaw
    for index,turn in enumerate((12.,12.,0.,12.,12.)):value.observe(metric(turn),1+index/15)
    assert value.passed and value.attempt_id==attempt and value.neutral_yaw==baseline


def test_a_single_spike_or_invalid_sample_never_completes_a_challenge():
    value=challenge();calibrated(value);attempt=value.attempt_id
    for index,turn in enumerate((0.,0.,30.,0.,0.,0.)):value.observe(metric(turn),1+index/15)
    assert not value.passed
    value.observe(EyeMetric(1,.04,.04,float("nan")),2.)
    value.observe(metric(0.),2.1)
    assert not value.failed and not value.passed and value.attempt_id==attempt


def test_nine_second_timeout_and_retry_clear_only_the_attempt_state():
    value=challenge();calibrated(value)
    value.observe(metric(),8.9)
    assert not value.failed
    value.observe(metric(),9.5)
    assert value.failed and value.failure_reason=="LIVENESS_TIMEOUT"
    previous=value.attempt_id;value.retry(10.)
    assert value.attempt_id!=previous and value.neutral_yaw is None and not value.failed
    assert not value._pose_window and not value._neutral_eyes


def test_debug_pose_diagnostics_are_opt_in_and_do_not_enter_production(caplog):
    with caplog.at_level("INFO",logger="LIVENESS"):
        value=challenge();calibrated(value);value.observe(metric(12.),1.)
        assert "current_yaw=" not in caplog.text
        value.blink.debug=True;value.observe(metric(12.,mirrored=True),1.1)
    for key in ("neutral_yaw=","current_yaw=","yaw_delta=","expected_direction=TURN_LEFT","input_mirrored=True"):
        assert key in caplog.text
    settings=get_settings().model_copy(update={"face_liveness_debug":True,"app_env":"production"})
    with patch("app.main.get_settings",return_value=settings):
        assert not PremiumUiController.__new__(PremiumUiController)._new_biometric_pipeline().blink.debug


def test_successful_head_turn_enters_automatic_three_frame_capture():
    controller=live_controller();controller.camera_context="enrollment";controller.biometric_pipeline.state=BiometricState.LIVENESS_CALIBRATING
    controller.page.run_task=Mock();controller.liveness_engine=challenge()
    controller.biometric_pipeline.blink=controller.liveness_engine.blink
    controller.camera_capture_sequences=[];controller._capture_retries=0;controller._enrollment_finalizing=False
    observations=iter([metric() for _ in range(8)]+[metric(12.) for _ in range(4)])
    def observe(*_):
        if controller.biometric_pipeline.state==BiometricState.RETURN_TO_NEUTRAL:
            controller.camera_service.running=False
            return metric()
        return next(observations)
    controller.blink_detector=SimpleNamespace(observe=observe)
    controller.camera_service.raw_snapshot=lambda after:CameraFrame(np.zeros((8,8,3),np.uint8),after+1,time.monotonic())
    with patch("app.main.asyncio.sleep",new_callable=AsyncMock):asyncio.run(controller._camera_liveness_loop())
    assert controller.biometric_pipeline.state==BiometricState.RETURN_TO_NEUTRAL
    assert "challenge passed" in controller.camera_panel_state.message and controller._latest_eyes_open
    controller.camera_service.running=True
    data={"pose":"center"};quality={"faceSizeAccepted":True,"lightingAccepted":True,"blurAccepted":True};box={"centerX":.5,"centerY":.5,"size":.3}
    for timestamp,seq,content in ((0.,1,b"initial"),(.8,2,b"one"),(1.4,3,b"two"),(2.,4,b"three")):
        controller._handle_enrollment_capture(timestamp,seq,content,data,quality,box,False,True)
    assert controller.camera_frames==[b"one",b"two",b"three"] and controller._enrollment_finalizing
    assert controller.biometric_pipeline.state==BiometricState.IDENTITY_CONSISTENCY
    controller.page.run_task.assert_called_once_with(controller._finalize_live_enrollment)

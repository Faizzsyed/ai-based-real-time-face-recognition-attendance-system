"""Biometric state machine and adaptive development-grade blink challenge."""
from __future__ import annotations
import logging,math,statistics,time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import cv2
logger=logging.getLogger("LIVENESS")
class BiometricState(str,Enum):
    IDLE="IDLE";CAMERA_STARTING="CAMERA_STARTING";SEARCHING_FACE="SEARCHING_FACE";MULTIPLE_FACES="MULTIPLE_FACES";FACE_FOUND="FACE_FOUND";STABILIZING="STABILIZING";QUALITY_CHECK="QUALITY_CHECK";LIVENESS_PROMPT="LIVENESS_PROMPT";LIVENESS_CALIBRATING="LIVENESS_CALIBRATING";LIVENESS_TRACKING="LIVENESS_TRACKING";LIVENESS_PASSED="LIVENESS_PASSED";RETURN_TO_NEUTRAL="RETURN_TO_NEUTRAL";STABILIZING_FOR_CAPTURE="STABILIZING_FOR_CAPTURE";CAPTURING="CAPTURING";IDENTITY_CONSISTENCY="IDENTITY_CONSISTENCY";RECOGNIZING="RECOGNIZING";IDENTIFIED="IDENTIFIED";UNKNOWN="UNKNOWN";AMBIGUOUS="AMBIGUOUS";COOLDOWN="COOLDOWN";ERROR="ERROR"
@dataclass(frozen=True)
class FaceObservation:
    timestamp:float;face_count:int;center:tuple[float,float]|None=None;size:float|None=None;quality_ok:bool=False;eyes_closed:bool|None=None;frame_sequence:int=0;frame:bytes|None=None;quality_score:float=0.
@dataclass(frozen=True)
class EyeMetric:
    face_count:int;left:float|None;right:float|None;yaw:float|None=None
    @property
    def bilateral(self):return min(self.left,self.right) if self.left is not None and self.right is not None else None
class BlinkChallenge:
    """Adaptive temporal OPEN -> CLOSED -> OPEN detector.

    MediaPipe eyeBlink scores increase as an eye closes, so calibration derives an
    additive session threshold above the robust open-eye baseline.
    """
    def __init__(self,required=1,timeout=5.,min_open_frames=2,min_closed_frames=2,calibration_samples=0,closure_delta=.20,reopen_ratio=.45,debug=False):
        self.required=max(1,int(required));self.timeout=float(timeout);self.min_open=max(1,int(min_open_frames));self.min_closed=max(1,int(min_closed_frames));self.calibration_required=max(0,int(calibration_samples));self.closure_delta=float(closure_delta);self.reopen_ratio=float(reopen_ratio);self.debug=bool(debug);self.reset()
    def reset(self,now=None):
        self.started_at=now;self.challenge_started_at=None;self.blinks=0;self.phase="calibrating_open" if self.calibration_required else "need_open";self.open_frames=0;self.closed_frames=0;self.open_samples=[];self.open_baseline=None;self.closed_threshold=None;self.reopen_threshold=None;self.current_metric=None;self.passed=False;self.timed_out=False;self.failure_reason=None
    def start(self,now):self.reset(now)
    @property
    def calibration_progress(self):return (len(self.open_samples),self.calibration_required)
    @property
    def timeout_remaining(self):return self.timeout if self.challenge_started_at is None else max(0.,self.timeout-(time.monotonic()-self.challenge_started_at))
    def _finish_calibration(self,now):
        self.open_baseline=float(statistics.median(self.open_samples));self.closed_threshold=min(.90,self.open_baseline+self.closure_delta);self.reopen_threshold=self.open_baseline+self.closure_delta*self.reopen_ratio;self.phase="need_open";self.challenge_started_at=now;logger.info("[LIVENESS] calibration baseline=%.4f closed_threshold=%.4f reopen_threshold=%.4f samples=%s",self.open_baseline,self.closed_threshold,self.reopen_threshold,len(self.open_samples));logger.info("[LIVENESS] challenge started type=blink_once timeout=%.1f",self.timeout)
    def observe_metric(self,metric,now,face_valid=True):
        self.current_metric=metric
        if not face_valid:self.failure_reason="LIVENESS_FACE_LOST";return False
        if metric is None:self.failure_reason="LIVENESS_LANDMARKS_UNAVAILABLE";return False
        self.failure_reason=None
        if self.phase=="calibrating_open":
            self.open_samples.append(float(metric))
            if len(self.open_samples)>=self.calibration_required:self._finish_calibration(now)
            return False
        if self.challenge_started_at is None:self.challenge_started_at=now
        remaining=self.timeout-(now-self.challenge_started_at)
        if remaining<=0:self.timed_out=True;self.failure_reason="LIVENESS_TIMEOUT";return False
        closed=float(metric)>=float(self.closed_threshold if self.closed_threshold is not None else .55);reopened=float(metric)<=float(self.reopen_threshold if self.reopen_threshold is not None else .35)
        if self.phase=="need_open":
            if reopened:
                self.open_frames+=1
                if self.open_frames>=self.min_open:self.phase="open"
        elif self.phase=="open":
            if closed:
                self.closed_frames+=1;self.phase="waiting_reopen" if self.closed_frames>=self.min_closed else "possible_closed"
        elif self.phase=="possible_closed":
            if closed:
                self.closed_frames+=1
                if self.closed_frames>=self.min_closed:self.phase="waiting_reopen"
            else:self.closed_frames=0;self.phase="open"
        elif self.phase=="waiting_reopen":
            if reopened:
                self.open_frames=1
                if self.open_frames>=self.min_open:
                    self.blinks+=1;logger.info("[LIVENESS] blink_count=%s",self.blinks)
                    if self.blinks>=self.required:self.passed=True;self.phase="passed";logger.info("[LIVENESS] passed")
                    else:self.phase="need_open";self.open_frames=0;self.closed_frames=0
                else:self.phase="reopening"
        elif self.phase=="reopening":
            if reopened:
                self.open_frames+=1
                if self.open_frames>=self.min_open:
                    self.blinks+=1;logger.info("[LIVENESS] blink_count=%s",self.blinks)
                    if self.blinks>=self.required:self.passed=True;self.phase="passed";logger.info("[LIVENESS] passed")
                    else:self.phase="need_open";self.open_frames=0;self.closed_frames=0
            elif closed:self.phase="waiting_reopen";self.open_frames=0
        if self.debug:logger.info("[LIVENESS] eye_metric=%.4f baseline=%s closed_threshold=%s state=%s blink_count=%s timeout_remaining=%.2f",metric,f"{self.open_baseline:.4f}" if self.open_baseline is not None else "calibrating",f"{self.closed_threshold:.4f}" if self.closed_threshold is not None else "calibrating",self.phase.upper(),self.blinks,max(0.,remaining))
        return self.passed
    def observe(self,closed,now):
        if self.started_at is None:self.start(now)
        return self.observe_metric(1. if closed else 0. if closed is not None else None,now,closed is not None)
class BiometricPipeline:
    def __init__(self,stability_seconds=.7,center_tolerance=.045,size_tolerance=.12,blink=None,cooldown_seconds=2.):self.stability_seconds=float(stability_seconds);self.center_tolerance=float(center_tolerance);self.size_tolerance=float(size_tolerance);self.blink=blink or BlinkChallenge();self.cooldown_seconds=float(cooldown_seconds);self.state=BiometricState.IDLE;self._stable_since=None;self._anchor=None;self.best_frame=None;self.recognition_started=False;self.cooldown_until=0.
    def start(self):self.state=BiometricState.SEARCHING_FACE;self._reset();return self.state
    def _reset(self):self._stable_since=None;self._anchor=None;self.best_frame=None;self.recognition_started=False;self.blink.reset()
    def observe(self,o):
        if self.state in {BiometricState.LIVENESS_PROMPT,BiometricState.LIVENESS_CALIBRATING,BiometricState.LIVENESS_TRACKING}:
            return self.observe_liveness(1. if o.eyes_closed else 0. if o.eyes_closed is not None else None,o.timestamp,o.face_count) if o.eyes_closed is not None else self.state
        if self.state in {BiometricState.LIVENESS_PASSED,BiometricState.RETURN_TO_NEUTRAL,BiometricState.STABILIZING_FOR_CAPTURE,BiometricState.CAPTURING,BiometricState.IDENTITY_CONSISTENCY}:return self.state
        if self.state==BiometricState.COOLDOWN:
            if o.timestamp>=self.cooldown_until:self.start()
            else:return self.state
        if o.face_count!=1:self._reset();self.state=BiometricState.MULTIPLE_FACES if o.face_count>1 else BiometricState.SEARCHING_FACE;return self.state
        if not o.quality_ok or o.center is None or o.size is None:self._reset();self.state=BiometricState.QUALITY_CHECK;return self.state
        if self._anchor is None:self._anchor=(o.center,o.size);self._stable_since=o.timestamp;self.state=BiometricState.STABILIZING;return self.state
        center,size=self._anchor
        if math.dist(center,o.center)>self.center_tolerance or abs(size-o.size)/max(size,1e-6)>self.size_tolerance:self._anchor=(o.center,o.size);self._stable_since=o.timestamp;self.best_frame=None;self.blink.reset();self.state=BiometricState.STABILIZING;return self.state
        if self.best_frame is None or o.quality_score>self.best_frame.quality_score:self.best_frame=o
        if o.timestamp-self._stable_since<self.stability_seconds:self.state=BiometricState.STABILIZING;return self.state
        self.blink.start(o.timestamp);self.state=BiometricState.LIVENESS_CALIBRATING if self.blink.calibration_required else BiometricState.LIVENESS_PROMPT;logger.info("[FACE] stability passed");return self.state
    def observe_liveness(self,metric,now,face_count=1):
        if self.state not in {BiometricState.LIVENESS_PROMPT,BiometricState.LIVENESS_CALIBRATING,BiometricState.LIVENESS_TRACKING}:return self.state
        passed=self.blink.observe_metric(metric,now,face_valid=face_count==1)
        if passed:self.state=BiometricState.LIVENESS_PASSED
        elif self.blink.timed_out:self.state=BiometricState.ERROR
        elif self.blink.calibration_required and self.blink.open_baseline is None:self.state=BiometricState.LIVENESS_CALIBRATING
        else:self.state=BiometricState.LIVENESS_TRACKING
        return self.state
    def retry_liveness(self,now):self.blink.start(now);self.state=BiometricState.LIVENESS_CALIBRATING if self.blink.calibration_required else BiometricState.LIVENESS_PROMPT;return self.state
    def begin_recognition(self):
        if self.state!=BiometricState.LIVENESS_PASSED or self.recognition_started:return False
        self.recognition_started=True;self.state=BiometricState.RECOGNIZING;logging.getLogger("FACE").info("[FACE] recognition_started");return True
    def finish_recognition(self,result,now=None):self.state={"identified":BiometricState.IDENTIFIED,"verified":BiometricState.IDENTIFIED,"ambiguous":BiometricState.AMBIGUOUS}.get(result,BiometricState.UNKNOWN);self.cooldown_until=(now if now is not None else time.monotonic())+self.cooldown_seconds;return self.state
    def cooldown(self):self.state=BiometricState.COOLDOWN
class MediaPipeBlinkDetector:
    def __init__(self,model_path:Path):
        import mediapipe as mp
        vision=mp.tasks.vision;options=vision.FaceLandmarkerOptions(base_options=mp.tasks.BaseOptions(model_asset_path=str(model_path)),running_mode=vision.RunningMode.VIDEO,num_faces=2,output_face_blendshapes=True,min_face_detection_confidence=.5,min_face_presence_confidence=.5,min_tracking_confidence=.5);self._mp=mp;self._landmarker=vision.FaceLandmarker.create_from_options(options);self._last_timestamp=0
    def observe(self,bgr,timestamp_ms):
        timestamp_ms=max(int(timestamp_ms),self._last_timestamp+1);self._last_timestamp=timestamp_ms;rgb=cv2.cvtColor(bgr,cv2.COLOR_BGR2RGB);result=self._landmarker.detect_for_video(self._mp.Image(image_format=self._mp.ImageFormat.SRGB,data=rgb),timestamp_ms)
        count=len(result.face_blendshapes)
        if count!=1:return EyeMetric(count,None,None,None)
        scores={x.category_name:x.score for x in result.face_blendshapes[0]};landmarks=result.face_landmarks[0];left=landmarks[33];right=landmarks[263];nose=landmarks[1];eye_distance=max(abs(right.x-left.x),1e-6);yaw=(nose.x-(left.x+right.x)/2)/eye_distance;return EyeMetric(1,float(scores.get("eyeBlinkLeft",0.)),float(scores.get("eyeBlinkRight",0.)),float(yaw))
    def close(self):self._landmarker.close()

"""Randomized temporal development challenge-response liveness engine."""
from __future__ import annotations
import logging,math,secrets,statistics,time
from collections import deque
from dataclasses import dataclass
from enum import Enum
from uuid import uuid4
from app.services.biometric_pipeline import BlinkChallenge,EyeMetric
logger=logging.getLogger("LIVENESS")
class ChallengeType(str,Enum):BLINK="BLINK";TURN_LEFT="TURN_LEFT";TURN_RIGHT="TURN_RIGHT";RETURN_CENTER="RETURN_CENTER"
INSTRUCTIONS={ChallengeType.BLINK:"BLINK ONCE",ChallengeType.TURN_LEFT:"TURN YOUR HEAD SLIGHTLY LEFT",ChallengeType.TURN_RIGHT:"TURN YOUR HEAD SLIGHTLY RIGHT",ChallengeType.RETURN_CENTER:"LOOK STRAIGHT"}
ENROLLMENT_PATTERNS=((ChallengeType.BLINK,ChallengeType.TURN_LEFT,ChallengeType.RETURN_CENTER),(ChallengeType.BLINK,ChallengeType.TURN_RIGHT,ChallengeType.RETURN_CENTER),(ChallengeType.TURN_LEFT,ChallengeType.RETURN_CENTER,ChallengeType.BLINK),(ChallengeType.TURN_RIGHT,ChallengeType.RETURN_CENTER,ChallengeType.BLINK))
@dataclass(frozen=True)
class ChallengeStatus:
    attempt_id:str;steps:tuple[ChallengeType,...];index:int;instruction:str;phase:str;passed:bool;failed:bool;failure_reason:str|None
class LivenessChallengeEngine:
    def __init__(self,blink:BlinkChallenge,profile="enrollment",pose_timeout=9.,pose_delta=.10,pose_center_tolerance=.07,pose_frames=3,face_loss_grace=.6,chooser=None,clock=None,enrollment_steps=3,attendance_steps=1):
        self.blink=blink;self.profile=profile;self.pose_timeout=float(pose_timeout);self.pose_delta=float(pose_delta);self.center_tolerance=float(pose_center_tolerance);self.pose_frames=max(1,int(pose_frames));self.face_loss_grace=float(face_loss_grace);self.chooser=chooser or secrets.choice;self.clock=clock or time.monotonic;self.enrollment_steps=max(1,min(3,int(enrollment_steps)));self.attendance_steps=max(1,min(3,int(attendance_steps)));self.attempt_id="";self.steps=();self.index=0;self.neutral_samples=[];self.neutral_yaw=None;self.step_started_at=None;self.pose_streak=0;self.passed=False;self.failed=False;self.failure_reason=None;self.face_lost_at=None
        self._neutral_eyes=[];self._pose_window=deque(maxlen=3)
    @property
    def current(self):return None if self.passed or self.failed or self.index>=len(self.steps) else self.steps[self.index]
    @property
    def instruction(self):return "Liveness verified" if self.passed else INSTRUCTIONS.get(self.current,"Calibrating eyes...")
    def start(self,now=None):
        self._neutral_eyes=[];self._pose_window.clear()
        now=self.clock() if now is None else now;self.attempt_id=uuid4().hex;pattern=tuple(self.chooser(ENROLLMENT_PATTERNS));self.steps=(ChallengeType.BLINK,) if self.profile=="blink" else pattern[:self.enrollment_steps] if self.profile=="enrollment" else pattern[:self.attendance_steps];self.index=0;self.neutral_samples=[];self.neutral_yaw=None;self.step_started_at=None;self.pose_streak=0;self.passed=False;self.failed=False;self.failure_reason=None;self.face_lost_at=None;self.blink.start(now);logger.info("[LIVENESS] session_started attempt_id=%s",self.attempt_id);logger.info("[LIVENESS] sequence_generated steps=%s",len(self.steps));return self.status()
    def retry(self,now=None):return self.start(now)
    def status(self):return ChallengeStatus(self.attempt_id,self.steps,self.index,self.instruction,"passed" if self.passed else "failed" if self.failed else "calibrating" if self.neutral_yaw is None else "active",self.passed,self.failed,self.failure_reason)
    def _face_continuity(self,metric,now):
        if metric.face_count==1 and metric.bilateral is not None and metric.yaw is not None and math.isfinite(metric.bilateral) and math.isfinite(metric.yaw):self.face_lost_at=None;return True
        # A dropped landmark observation pauses confirmation, not the whole attempt.
        self.pose_streak=0;self._pose_window.clear()
        if self.neutral_yaw is None:self.neutral_samples=[];self._neutral_eyes=[]
        if metric.face_count>1:self.failed=True;self.failure_reason="LIVENESS_MULTIPLE_FACES";return False
        if self.face_lost_at is None:self.face_lost_at=now
        if now-self.face_lost_at>self.face_loss_grace:self.failure_reason="LIVENESS_FACE_LOST";self.failed=True
        return False
    def _calibrate(self,metric,now):
        required=max(3,self.blink.calibration_required)
        self.neutral_samples=(self.neutral_samples+[float(metric.yaw)])[-required:]
        self._neutral_eyes=(self._neutral_eyes+[float(metric.bilateral)])[-required:]
        # Neutral must be still. A rolling window lets motion/noise settle without
        # repeatedly restarting the attempt or consuming the action timeout.
        stable=len(self.neutral_samples)==required and max(self.neutral_samples)-min(self.neutral_samples)<=min(self.center_tolerance,self.pose_delta/2)
        if self.blink.debug:logger.info("[LIVENESS] neutral_yaw=%s current_yaw=%.4f yaw_delta=%s expected_direction=%s input_mirrored=%s calibration_stable=%s",self.neutral_yaw,metric.yaw,None,self.current.value,metric.mirrored,stable)
        if not stable:return
        self.neutral_yaw=float(statistics.median(self.neutral_samples))
        self.blink.start(now)
        if self.blink.calibration_required:
            for value in self._neutral_eyes:self.blink.observe_metric(value,now,True)
        else:
            self.blink.open_samples=list(self._neutral_eyes);self.blink._finish_calibration(now)
        self._start_step(now)
    def _start_step(self,now):
        self.step_started_at=now;self.pose_streak=0;current=self.current
        self._pose_window.clear();self._pose_window.extend([self.neutral_yaw]*3)
        if current==ChallengeType.BLINK:
            self.blink.phase="need_open";self.blink.open_frames=0;self.blink.closed_frames=0;self.blink.challenge_started_at=now;self.blink.timed_out=False;self.blink.passed=False
        logger.info("[LIVENESS] challenge_started type=%s",current.value)
    def _pass_step(self,now):
        completed=self.current;logger.info("[LIVENESS] challenge_passed type=%s",completed.value);self.index+=1;self.pose_streak=0
        if self.index>=len(self.steps):self.passed=True;logger.info("[LIVENESS] sequence_passed");return
        self._start_step(now)
    def observe(self,metric:EyeMetric,now=None):
        now=self.clock() if now is None else now
        if self.passed or self.failed:return self.status()
        if not self._face_continuity(metric,now):return self.status()
        if self.neutral_yaw is None:self._calibrate(metric,now);return self.status()
        timeout=self.blink.timeout if self.current==ChallengeType.BLINK else self.pose_timeout
        if self.step_started_at is not None and now-self.step_started_at>=timeout:self.failed=True;self.failure_reason="LIVENESS_TIMEOUT";return self.status()
        if self.current==ChallengeType.BLINK:
            before=self.blink.blinks
            if self.blink.observe_metric(metric.bilateral,now,True) and self.blink.blinks>before:self._pass_step(now)
            return self.status()
        self._pose_window.append(float(metric.yaw))
        relative=float(statistics.median(self._pose_window))-float(self.neutral_yaw);expected=self.current
        valid=(expected==ChallengeType.TURN_LEFT and relative>=self.pose_delta) or (expected==ChallengeType.TURN_RIGHT and relative<=-self.pose_delta) or (expected==ChallengeType.RETURN_CENTER and abs(relative)<=self.center_tolerance)
        self.pose_streak=self.pose_streak+1 if valid else 0
        if self.blink.debug:logger.info("[LIVENESS] neutral_yaw=%.4f current_yaw=%.4f yaw_delta=%.4f filtered_delta=%.4f expected_direction=%s input_mirrored=%s threshold=%.4f confirmation=%s/%s",self.neutral_yaw,metric.yaw,metric.yaw-self.neutral_yaw,relative,expected.value,metric.mirrored,self.pose_delta,self.pose_streak,self.pose_frames)
        if self.pose_streak>=self.pose_frames:self._pass_step(now)
        return self.status()

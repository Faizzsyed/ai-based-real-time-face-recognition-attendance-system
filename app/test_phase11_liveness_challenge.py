"""Phase 11 randomized temporal challenge engine tests."""
from app.services.biometric_pipeline import BlinkChallenge,EyeMetric
from app.services.liveness_challenge import ChallengeType,ENROLLMENT_PATTERNS,LivenessChallengeEngine

def eye(t=.04,yaw=0.,count=1):return EyeMetric(count,t,t,yaw if count==1 else None)
def engine(pattern,**kwargs):
    blink=BlinkChallenge(1,5,1,1,calibration_samples=3,closure_delta=.2);chooser=lambda options:pattern if options==ENROLLMENT_PATTERNS else options[0];return LivenessChallengeEngine(blink,chooser=chooser,pose_frames=2,**kwargs)
def calibrate(value):
    value.start(0)
    for index in range(3):value.observe(eye(yaw=.02),.1+index*.1)
    assert value.neutral_yaw is not None

def test_randomized_generation_uses_only_supported_short_patterns():
    seen=set()
    for _ in range(50):
        value=LivenessChallengeEngine(BlinkChallenge(calibration_samples=1));value.start();seen.add(value.steps);assert value.steps in ENROLLMENT_PATTERNS and len(value.steps)==3
    assert len(seen)>1

def test_blink_turn_left_center_must_pass_in_order():
    value=engine((ChallengeType.BLINK,ChallengeType.TURN_LEFT,ChallengeType.RETURN_CENTER));calibrate(value)
    value.observe(eye(.04,.3),.5);value.observe(eye(.04,.3),.6);assert value.index==0
    for t,metric in ((.7,.04),(.8,.5),(.9,.04)):value.observe(eye(metric,.02),t)
    assert value.index==1
    value.observe(eye(.04,.25),1.);value.observe(eye(.04,.25),1.1);assert value.index==2
    value.observe(eye(.04,.02),1.2);value.observe(eye(.04,.02),1.3);assert value.passed

def test_turn_right_and_wrong_action_does_not_pass():
    value=engine((ChallengeType.TURN_RIGHT,ChallengeType.RETURN_CENTER,ChallengeType.BLINK));calibrate(value)
    value.observe(eye(yaw=.3),.5);value.observe(eye(yaw=.3),.6);assert value.index==0
    value.observe(eye(yaw=-.25),.7);value.observe(eye(yaw=-.25),.8);assert value.index==1

def test_timeout_and_retry_create_clean_attempt():
    value=engine((ChallengeType.TURN_LEFT,ChallengeType.RETURN_CENTER,ChallengeType.BLINK),pose_timeout=.5);calibrate(value);old=value.attempt_id;value.observe(eye(yaw=0),1.);assert value.failed and value.failure_reason=="LIVENESS_TIMEOUT";value.retry(1.1);assert value.attempt_id!=old and value.index==0 and not value.failed and value.neutral_yaw is None

def test_face_loss_grace_and_multiple_face_continuity():
    value=engine((ChallengeType.BLINK,ChallengeType.TURN_LEFT,ChallengeType.RETURN_CENTER),face_loss_grace=.5);calibrate(value);value.observe(eye(count=0),.5);assert not value.failed;value.observe(eye(count=0),1.1);assert value.failed and value.failure_reason=="LIVENESS_FACE_LOST"
    other=engine((ChallengeType.BLINK,ChallengeType.TURN_LEFT,ChallengeType.RETURN_CENTER));calibrate(other);other.observe(eye(count=2),.5);assert other.failed and other.failure_reason=="LIVENESS_MULTIPLE_FACES"

def test_attendance_profile_is_lighter_but_nonempty():
    value=LivenessChallengeEngine(BlinkChallenge(calibration_samples=1),profile="attendance",chooser=lambda options:options[0]);value.start(0);assert len(value.steps)==1 and value.steps[0] in {ChallengeType.BLINK,ChallengeType.TURN_LEFT,ChallengeType.TURN_RIGHT}

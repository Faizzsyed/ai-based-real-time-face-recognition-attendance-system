"""Enrollment uses per-frame quality and identity consistency, not pose-coordinate sameness."""
import logging
import cv2,numpy as np,pytest
from app.core.errors import AppError
from app.modules.face_ai.engine import FaceEngine,MODEL_VERSION

def encoded(level):
    image=np.full((96,96,3),level,dtype=np.uint8);cv2.circle(image,(48+level%3,48),20,(level+20,level+10,level),-1);ok,data=cv2.imencode(".jpg",image);assert ok;return data.tobytes()
def result(data,embedding,pose="center"):
    return {"embedding":np.asarray(embedding,dtype=np.float32),"modelVersion":MODEL_VERSION,"fingerprint":str(hash(data)),"pose":pose,"detectionConfidence":.98,"quality":{"blurAccepted":True,"lightingAccepted":True,"faceSizeAccepted":True}}
def engine_with(outputs):
    engine=FaceEngine("unused-d","unused-r",enrollment_consistency_threshold=.40);iterator=iter(outputs);engine.analyze=lambda data,mime:next(iterator);return engine

def test_natural_frame_variation_same_identity_passes(caplog):
    frames=[(encoded(x),"image/jpeg") for x in (80,86,93)];outputs=[result(frames[0][0],[1,0,0]),result(frames[1][0],[.96,.28,0]),result(frames[2][0],[.94,.34,0])]
    with caplog.at_level(logging.INFO):combined=engine_with(outputs).analyze_enrollment_frames(frames)
    assert combined["quality"]["identityConsistent"] and combined["quality"]["minimumPairSimilarity"]>.8
    assert "array(" not in caplog.text and "embedding=" not in caplog.text and "image=" not in caplog.text

def test_inconsistent_enrollment_embeddings_fail_with_specific_error():
    frames=[(encoded(x),"image/jpeg") for x in (70,90,110)];outputs=[result(frames[0][0],[1,0,0]),result(frames[1][0],[0,1,0]),result(frames[2][0],[0,0,1])]
    with pytest.raises(AppError) as error:engine_with(outputs).analyze_enrollment_frames(frames)
    assert error.value.code=="INCONSISTENT_ENROLLMENT_IDENTITY" and "same person" in error.value.message

def test_exact_and_near_duplicate_enrollment_frames_are_rejected():
    frame=encoded(85);frames=[(frame,"image/jpeg")]*3;outputs=[result(frame,[1,0,0]) for _ in range(3)]
    with pytest.raises(AppError) as error:engine_with(outputs).analyze_enrollment_frames(frames)
    assert error.value.code=="DUPLICATE_FACE_FRAMES"

def test_each_enrollment_capture_must_be_frontal():
    frames=[(encoded(x),"image/jpeg") for x in (70,90,110)];outputs=[result(frames[0][0],[1,0,0]),result(frames[1][0],[1,0,0],"left"),result(frames[2][0],[1,0,0])]
    with pytest.raises(AppError) as error:engine_with(outputs).analyze_enrollment_frames(frames)
    assert error.value.code=="NON_FRONTAL_ENROLLMENT_FRAME"

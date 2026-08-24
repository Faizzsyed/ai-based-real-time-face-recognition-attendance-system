"""Server-side OpenCV YuNet/SFace detection, quality, and embedding pipeline."""
from __future__ import annotations
import hashlib,time
from pathlib import Path
import cv2,numpy as np,logging
from app.core.errors import AppError
logger=logging.getLogger("FACE")

MODEL_VERSION="opencv-yunet-2023mar+sface-2021dec-v1";ALLOWED_MIME={"image/jpeg","image/jpg","image/png","image/webp"};MIN_FACE_PIXELS=80;MIN_FACE_RATIO=.12;MIN_BLUR=45.;MIN_LIGHT=35.;MAX_LIGHT=220.;NEAR_DUPLICATE_MEAN_DELTA=.02
class FaceEngine:
    def __init__(self,detection_path:Path,recognition_path:Path,threshold:float=.90,enrollment_consistency_threshold:float=.40):self.detection_path=Path(detection_path);self.recognition_path=Path(recognition_path);self.threshold=threshold;self.enrollment_consistency_threshold=float(enrollment_consistency_threshold);self.detector=None;self.recognizer=None
    def _models(self):
        for path in (self.detection_path,self.recognition_path):
            if not path.is_file() or path.stat().st_size==0:raise AppError("FACE_MODEL_UNAVAILABLE","Face models are unavailable. Run scripts/download_face_models.py.",503)
            if path.read_bytes()[:128].startswith(b"version https://git-lfs.github.com/spec"):raise AppError("FACE_MODEL_UNAVAILABLE","Face model file is a Git LFS pointer, not an ONNX model.",503)
        if self.detector is None:
            try:self.detector=cv2.FaceDetectorYN.create(str(self.detection_path),"",(320,320),.30,.30,5000);self.recognizer=cv2.FaceRecognizerSF.create(str(self.recognition_path),"");logger.info("models loaded detector=true recognizer=true")
            except Exception as exc:raise AppError("FACE_MODEL_UNAVAILABLE","Face models could not be loaded.",503) from exc
    def decode(self,data:bytes,mime:str|None):
        if mime and mime.casefold() not in ALLOWED_MIME:raise AppError("INVALID_FACE_IMAGE_FORMAT","Use a JPEG, PNG, or WebP image.",422)
        if not data:raise AppError("INVALID_FACE_IMAGE","Face image is empty.",422)
        image=cv2.imdecode(np.frombuffer(data,dtype=np.uint8),cv2.IMREAD_COLOR)
        if image is None or image.ndim!=3:raise AppError("INVALID_FACE_IMAGE","Image data could not be decoded safely.",422)
        return image
    def analyze(self,data:bytes,mime:str|None,include_embedding:bool=True):
        self._models();image=self.decode(data,mime);height,width=image.shape[:2];self.detector.setInputSize((width,height));detect_started=time.perf_counter()
        try:_,detected=self.detector.detect(image)
        except Exception as exc:raise AppError("FACE_ANALYSIS_FAILED","Face analysis failed safely.",503) from exc
        logger.debug("[PERF] yunet_ms=%.2f",(time.perf_counter()-detect_started)*1000)
        faces=[] if detected is None else [np.asarray(x,dtype=np.float32) for x in detected if float(x[-1])>=self.threshold]
        if not faces:raise AppError("FACE_NOT_FOUND","Exactly one clear face is required.",422)
        if len(faces)>1:raise AppError("MULTIPLE_FACES_FOUND","Exactly one face is allowed.",422)
        face=faces[0];x,y,w,h=[int(round(v)) for v in face[:4]];pad=int(max(w,h)*.15);crop=image[max(0,y-pad):min(height,y+h+pad),max(0,x-pad):min(width,x+w+pad)]
        if crop.size==0:raise AppError("INVALID_FACE_IMAGE","Detected face crop is invalid.",422)
        gray=cv2.cvtColor(crop,cv2.COLOR_BGR2GRAY);blur=float(cv2.Laplacian(gray,cv2.CV_64F).var());light=float(gray.mean());ratio=min(float(w),float(h))/min(height,width);quality={"blurVariance":round(blur,2),"lightingMean":round(light,2),"faceSizeRatio":round(ratio,4),"blurAccepted":blur>=MIN_BLUR,"lightingAccepted":MIN_LIGHT<=light<=MAX_LIGHT,"faceSizeAccepted":min(w,h)>=MIN_FACE_PIXELS and ratio>=MIN_FACE_RATIO}
        if not quality["faceSizeAccepted"]:raise AppError("FACE_TOO_SMALL","Move closer so the face fills the guide.",422,{"quality":quality})
        if not quality["blurAccepted"]:raise AppError("IMAGE_TOO_BLURRY","Hold still and capture a sharper frame.",422,{"quality":quality})
        if not quality["lightingAccepted"]:raise AppError("POOR_LIGHTING","Use even lighting without deep shadows or glare.",422,{"quality":quality})
        eye_mid=(float(face[4])+float(face[6]))/2;eye_distance=max(abs(float(face[6])-float(face[4])),1.0);yaw=(float(face[8])-eye_mid)/eye_distance;pose="left" if yaw>.18 else "right" if yaw<-.18 else "center"
        result={"modelVersion":MODEL_VERSION,"faceCount":1,"detectionConfidence":round(float(face[-1]),6),"quality":quality,"pose":pose,"fingerprint":hashlib.sha256(data).hexdigest(),"faceBox":{"centerX":round((x+w/2)/width,5),"centerY":round((y+h/2)/height,5),"size":round(min(w/width,h/height),5)}}
        if not include_embedding:return result
        recognition_started=time.perf_counter()
        try:aligned=self.recognizer.alignCrop(image,face);embedding=self.recognizer.feature(aligned).reshape(-1).astype(np.float32)
        except Exception as exc:raise AppError("FACE_ANALYSIS_FAILED","Face embedding could not be generated.",503) from exc
        logger.debug("[PERF] sface_ms=%.2f",(time.perf_counter()-recognition_started)*1000)
        norm=float(np.linalg.norm(embedding))
        if embedding.size==0 or not np.all(np.isfinite(embedding)) or norm<=0:raise AppError("INVALID_EMBEDDING","Face embedding is invalid.",422)
        result["embedding"]=embedding/norm;return result
    def analyze_preview(self,data:bytes,mime:str|None):return self.analyze(data,mime,include_embedding=False)
    def analyze_frames(self,frames,require_frontal=False):
        results=[self.analyze(data,mime) for data,mime in frames]
        if require_frontal and any(result.get("pose")!="center" for result in results):raise AppError("NON_FRONTAL_ENROLLMENT_FRAME","Look straight at the camera for every enrollment capture.",422)
        if len({x["fingerprint"] for x in results})!=len(results):raise AppError("DUPLICATE_FACE_FRAMES","Capture distinct consecutive frames; exact duplicates are rejected.",422)
        if len(results)==1:
            embedding=np.asarray(results[0]["embedding"],dtype=np.float32);embedding=embedding/np.linalg.norm(embedding)
            return {"embedding":embedding.tolist(),"modelVersion":MODEL_VERSION,"captureCount":1,"quality":{"identityConsistent":True,"minimumPairSimilarity":None,"minimumDetectionConfidence":results[0]["detectionConfidence"],"frames":[results[0]["quality"]]},"liveness":{"method":"not_available","passed":False,"observations":[]}}
        try:decoded=[cv2.resize(cv2.cvtColor(self.decode(data,mime),cv2.COLOR_BGR2GRAY),(64,64),interpolation=cv2.INTER_AREA) for data,mime in frames]
        except AppError:decoded=[]
        pixel_deltas=[]
        for left,right in ((0,1),(0,2),(1,2)):
            if decoded:pixel_deltas.append(float(np.mean(cv2.absdiff(decoded[left],decoded[right]))))
        if pixel_deltas:logger.info("[ENROLL] duplicate_check minimum_delta=%.4f threshold=%.4f",min(pixel_deltas),NEAR_DUPLICATE_MEAN_DELTA)
        if pixel_deltas and min(pixel_deltas)<=NEAR_DUPLICATE_MEAN_DELTA:raise AppError("DUPLICATE_FACE_FRAMES","A camera frame was reused. Waiting for a fresh frame is required.",422)
        embeddings=[]
        for result in results:
            embedding=np.asarray(result["embedding"],dtype=np.float32);embeddings.append(embedding/np.linalg.norm(embedding))
        similarities=[float(np.dot(embeddings[left],embeddings[right])) for left,right in ((0,1),(0,2),(1,2))]
        logger.info("enrollment consistency minimum=%.4f maximum=%.4f threshold=%.4f duplicate_min_delta=%.3f",min(similarities),max(similarities),self.enrollment_consistency_threshold,min(pixel_deltas) if pixel_deltas else 0.)
        if min(similarities)<self.enrollment_consistency_threshold:raise AppError("INCONSISTENT_ENROLLMENT_IDENTITY","Enrollment captures do not appear to belong to the same person.",422)
        average=np.mean(np.stack(embeddings),axis=0);average=average/np.linalg.norm(average)
        poses=[x["pose"] for x in results];ordered=len(poses)==3 and poses[0]=="center" and set(poses[1:])=={"left","right"};liveness={"method":"yunet-pose-sequence-dev-v1","passed":ordered,"observations":poses};logger.info("liveness evaluated method=%s passed=%s frames=%s",liveness["method"],liveness["passed"],len(results))
        return {"embedding":average.tolist(),"modelVersion":MODEL_VERSION,"captureCount":len(results),"quality":{"identityConsistent":True,"minimumPairSimilarity":round(min(similarities),6),"minimumDetectionConfidence":min(x["detectionConfidence"] for x in results),"frames":[x["quality"] for x in results]},"liveness":liveness}
    def analyze_enrollment_frames(self,frames):return self.analyze_frames(frames,require_frontal=True)

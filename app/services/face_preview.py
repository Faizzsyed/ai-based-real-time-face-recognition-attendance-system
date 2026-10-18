"""Desktop-only YuNet guidance. No recognition model or embeddings live here."""
from pathlib import Path
from threading import RLock


class FacePreviewUnavailable(RuntimeError):
    pass


class DesktopFacePreview:
    def __init__(self, path, threshold=.90):
        self._lock=RLock()
        import cv2
        path=Path(path)
        if not path.is_file():raise FacePreviewUnavailable("Face detection model is missing. Restore the configured YuNet model and retry.")
        try:self.detector=cv2.FaceDetectorYN.create(str(path),"",(320,320),.30,.30,5000)
        except Exception as exc:raise FacePreviewUnavailable("Face detection could not start. Check the model installation.") from exc
        self.threshold=float(threshold)

    def analyze(self, frame):
        with self._lock:return self._analyze(frame)

    def _analyze(self, frame):
        import cv2
        image=frame.image
        height,width=image.shape[:2]
        if width>640:
            image=cv2.resize(image,(640,max(1,round(height*640/width))),interpolation=cv2.INTER_AREA)
            height,width=image.shape[:2]
        try:
            self.detector.setInputSize((width,height));_,detected=self.detector.detect(image)
        except Exception as exc:raise FacePreviewUnavailable("Face detection paused. Stop the camera and try again.") from exc
        faces=[] if detected is None else [face for face in detected if float(face[-1])>=self.threshold]
        if len(faces)!=1:
            return {"valid":False,"faceCount":len(faces),"code":"MULTIPLE_FACES_FOUND" if faces else "FACE_NOT_FOUND"}
        face=faces[0];x,y,w,h=[int(round(v)) for v in face[:4]]
        box={"centerX":(x+w/2)/width,"centerY":(y+h/2)/height,"size":min(w/width,h/height),"width":w/width,"height":h/height}
        pad=round(max(w,h)*.15);crop=image[max(0,y-pad):min(height,y+h+pad),max(0,x-pad):min(width,x+w+pad)]
        if not crop.size:return {"valid":False,"faceCount":1,"code":"FACE_NOT_FOUND"}
        gray=cv2.cvtColor(crop,cv2.COLOR_BGR2GRAY);blur=float(cv2.Laplacian(gray,cv2.CV_64F).var());light=float(gray.mean())
        quality={"faceSizeAccepted":min(w,h)>=80 and min(w,h)/min(height,width)>=.12,"blurAccepted":blur>=45.,"lightingAccepted":35.<=light<=220.,"blurVariance":blur,"lightingMean":light}
        eye_mid=(float(face[4])+float(face[6]))/2;distance=max(abs(float(face[6])-float(face[4])),1.);yaw=(float(face[8])-eye_mid)/distance
        code=next((code for accepted,code in ((quality["faceSizeAccepted"],"FACE_TOO_SMALL"),(quality["blurAccepted"],"IMAGE_TOO_BLURRY"),(quality["lightingAccepted"],"POOR_LIGHTING")) if not accepted),None)
        return {"valid":code is None,"code":code,"faceCount":1,"faceBox":box,"quality":quality,"detectionConfidence":float(face[-1]),"pose":"left" if yaw>.18 else "right" if yaw<-.18 else "center"}


GUIDANCE={"FACE_NOT_FOUND":"Looking for face…","MULTIPLE_FACES_FOUND":"Multiple faces detected. Please present one student at a time.",
          "FACE_TOO_SMALL":"Move slightly closer","IMAGE_TOO_BLURRY":"Hold still","POOR_LIGHTING":"Improve lighting"}


def draw_face_box(image,box):
    """Draw on a preview copy, leaving capture/recognition pixels untouched."""
    import cv2
    if not box:return image
    output=image.copy();height,width=output.shape[:2]
    bw=box.get("width",box.get("size",.2));bh=box.get("height",box.get("size",.2))
    left=max(0,round((box["centerX"]-bw/2)*width));top=max(0,round((box["centerY"]-bh/2)*height))
    cv2.rectangle(output,(left,top),(min(width-1,round(left+bw*width)),min(height-1,round(top+bh*height))),(90,210,70),2)
    return output

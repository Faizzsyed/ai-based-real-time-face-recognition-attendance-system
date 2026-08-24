"""Private development-only retained enrollment image storage."""
from __future__ import annotations
import logging,shutil,cv2,numpy as np
from pathlib import Path
from app.core.logging import safe_log
logger=logging.getLogger("STORAGE")
class EnrollmentImageStorage:
    def __init__(self,root=None):self.root=Path(root or Path(__file__).resolve().parents[4]/"data"/"face_enrollments").resolve()
    @staticmethod
    def _id(value):
        text=str(value)
        if len(text)!=24 or any(x not in "0123456789abcdefABCDEF" for x in text):raise ValueError("Invalid scoped identifier")
        return text.casefold()
    def directory(self,institution_id,student_id):return self.root/self._id(institution_id)/self._id(student_id)
    def save(self,institution_id,student_id,frames):
        target=self.directory(institution_id,student_id);staging=target.with_name(target.name+".staging")
        if staging.exists():shutil.rmtree(staging)
        staging.mkdir(parents=True,exist_ok=False)
        try:
            for index,(data,mime) in enumerate(frames,1):
                image=cv2.imdecode(np.frombuffer(data,dtype=np.uint8),cv2.IMREAD_COLOR);ok,encoded=cv2.imencode(".jpg",image) if image is not None else (False,None)
                if not ok:raise ValueError("Enrollment frame could not be stored safely")
                (staging/f"frame_{index:02d}.jpg").write_bytes(encoded.tobytes())
            if target.exists():shutil.rmtree(target)
            staging.replace(target);safe_log(logger,logging.INFO,"enrollment images saved",student_id=str(student_id),count=len(frames));return len(frames)
        except Exception:
            if staging.exists():shutil.rmtree(staging)
            raise
    def remove(self,institution_id,student_id):
        target=self.directory(institution_id,student_id)
        if target.exists():shutil.rmtree(target);safe_log(logger,logging.INFO,"enrollment images removed",student_id=str(student_id))
    def reference(self,institution_id,student_id,index=1):
        target=(self.directory(institution_id,student_id)/f"frame_{int(index):02d}.jpg").resolve()
        if self.root not in target.parents or not target.is_file():return None
        return target

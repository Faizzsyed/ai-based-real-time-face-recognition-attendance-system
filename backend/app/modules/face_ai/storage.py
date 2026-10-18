"""Private development-only retained enrollment image storage."""
from __future__ import annotations
import logging,shutil,cv2,numpy as np,os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag
from app.modules.face_ai.crypto import _key
from app.core.errors import AppError
from pathlib import Path
from app.core.logging import safe_log
logger=logging.getLogger("STORAGE")
PREFIX=b"ATTENDAI-FRAME-1\n"


def encrypt_frame(data,institution_id,student_id,index,key_text):
    image=cv2.imdecode(np.frombuffer(data,dtype=np.uint8),cv2.IMREAD_COLOR)
    ok,encoded=cv2.imencode(".jpg",image) if image is not None else (False,None)
    if not ok:raise ValueError("Enrollment frame could not be stored safely")
    nonce=os.urandom(12);aad=f"AttendAI:frame:{institution_id}:{student_id}:{index}".encode()
    return PREFIX+nonce+AESGCM(_key(key_text)).encrypt(nonce,encoded.tobytes(),aad)


def decrypt_frame(data,institution_id,student_id,index,key_text):
    if not data.startswith(PREFIX):raise AppError("FACE_REFERENCE_UNAVAILABLE","Enrollment reference could not be read safely.",503)
    nonce=data[len(PREFIX):len(PREFIX)+12];encrypted=data[len(PREFIX)+12:]
    try:return AESGCM(_key(key_text)).decrypt(nonce,encrypted,f"AttendAI:frame:{institution_id}:{student_id}:{index}".encode())
    except (InvalidTag,ValueError) as exc:raise AppError("FACE_REFERENCE_UNAVAILABLE","Enrollment reference could not be authenticated.",503) from exc


class EnrollmentImageStorage:
    def __init__(self,root=None,key_text=""):self.root=Path(root or Path(__file__).resolve().parents[4]/"data"/"face_enrollments").resolve();self.key_text=key_text
    @staticmethod
    def _id(value):
        text=str(value)
        if len(text)!=24 or any(x not in "0123456789abcdefABCDEF" for x in text):raise ValueError("Invalid scoped identifier")
        return text.casefold()
    def directory(self,institution_id,student_id):return self.root/self._id(institution_id)/self._id(student_id)
    def save(self,institution_id,student_id,frames):
        _key(self.key_text)  # Fail before creating a staging directory.
        target=self.directory(institution_id,student_id);staging=target.with_name(target.name+".staging")
        if staging.exists():shutil.rmtree(staging)
        staging.mkdir(parents=True,exist_ok=False)
        try:
            for index,(data,mime) in enumerate(frames,1):
                (staging/f"frame_{index:02d}.enc").write_bytes(encrypt_frame(data,institution_id,student_id,index,self.key_text))
            if target.exists():shutil.rmtree(target)
            staging.replace(target);safe_log(logger,logging.INFO,"enrollment images saved",student_id=str(student_id),count=len(frames));return len(frames)
        except Exception:
            if staging.exists():shutil.rmtree(staging)
            raise
    def remove(self,institution_id,student_id):
        target=self.directory(institution_id,student_id)
        if target.exists():shutil.rmtree(target);safe_log(logger,logging.INFO,"enrollment images removed",student_id=str(student_id))
    def reference(self,institution_id,student_id,index=1):
        directory=self.directory(institution_id,student_id)
        target=(directory/f"frame_{int(index):02d}.enc").resolve()
        if not target.is_file():target=(directory/f"frame_{int(index):02d}.jpg").resolve()  # Read legacy references without rewriting user data.
        if self.root not in target.parents or not target.is_file():return None
        return target
    def read_reference(self,institution_id,student_id,index=1):
        path=self.reference(institution_id,student_id,index)
        if path is None:return None
        data=path.read_bytes()
        if path.suffix==".jpg":return data
        return decrypt_frame(data,institution_id,student_id,index,self.key_text)


class MongoEnrollmentImageStorage:
    """Encrypted GridFS payloads with an atomically replaced scoped manifest.

    No keys or plaintext are written to MongoDB. Local files are read only as
    a compatibility fallback; saving never migrates or modifies them.
    """
    def __init__(self,key_text,database=None,bucket=None,local=None):
        self.key_text=key_text;self._database=database;self._bucket=bucket
        self.local=local if local is not None else EnrollmentImageStorage(key_text=key_text)
    @property
    def database(self):
        from app.db.mongo import mongo
        return self._database if self._database is not None else mongo.require_database()
    @property
    def bucket(self):
        if self._bucket is None:
            from gridfs import GridFSBucket
            self._bucket=GridFSBucket(self.database,bucket_name="face_reference_images")
        return self._bucket
    @staticmethod
    def scope(institution_id,student_id):
        return f"{EnrollmentImageStorage._id(institution_id)}:{EnrollmentImageStorage._id(student_id)}"
    def _cleanup(self,ids):
        from gridfs.errors import NoFile
        for file_id in ids:
            try:self.bucket.delete(file_id)
            except NoFile:pass
            except Exception:logger.warning("Encrypted reference cleanup requires a retry")
    def save(self,institution_id,student_id,frames):
        from pymongo import ReturnDocument
        scope=self.scope(institution_id,student_id);ids=[]
        try:
            for index,(data,_) in enumerate(frames,1):
                encrypted=encrypt_frame(data,institution_id,student_id,index,self.key_text)
                ids.append(self.bucket.upload_from_stream(f"frame_{index:02d}.enc",encrypted,metadata={"scope":scope,"encrypted":True,"format":"aes-256-gcm-v1"}))
            previous=self.database.face_reference_sets.find_one_and_replace({"_id":scope},{"_id":scope,"files":ids},upsert=True,return_document=ReturnDocument.BEFORE)
        except Exception:
            self._cleanup(ids)
            raise
        if previous:self._cleanup(previous.get("files",[]))
        return len(ids)
    def read_reference(self,institution_id,student_id,index=1):
        manifest=self.database.face_reference_sets.find_one({"_id":self.scope(institution_id,student_id)})
        if manifest is None:return self.local.read_reference(institution_id,student_id,index)
        index=int(index)
        if not 1<=index<=len(manifest["files"]):return None
        try:encrypted=self.bucket.open_download_stream(manifest["files"][index-1]).read()
        except Exception as exc:raise AppError("FACE_REFERENCE_UNAVAILABLE","Enrollment reference is temporarily unavailable.",503) from exc
        return decrypt_frame(encrypted,institution_id,student_id,index,self.key_text)
    def remove(self,institution_id,student_id):
        previous=self.database.face_reference_sets.find_one_and_delete({"_id":self.scope(institution_id,student_id)})
        if previous:self._cleanup(previous.get("files",[]))
        self.local.remove(institution_id,student_id)


def configured_reference_storage(settings):
    kind=getattr(settings,"face_reference_storage","auto")
    production=getattr(settings,"app_env","development").casefold()=="production"
    if kind=="mongodb" or kind=="auto" and production:
        return MongoEnrollmentImageStorage(settings.face_embedding_encryption_key)
    if production:raise AppError("FACE_STORAGE_NOT_PERSISTENT","Production reference storage must use MongoDB.",503)
    return EnrollmentImageStorage(key_text=settings.face_embedding_encryption_key)


def reference_response(storage,institution_id,student_id):
    from fastapi.responses import Response,FileResponse
    if hasattr(storage,"read_reference"):
        data=storage.read_reference(institution_id,student_id)
        if data is None:raise AppError("FACE_REFERENCE_NOT_FOUND","Enrollment reference image was not found.",404)
        return Response(data,media_type="image/jpeg",headers={"Cache-Control":"private, no-store"})
    path=storage.reference(institution_id,student_id)
    if path is None:raise AppError("FACE_REFERENCE_NOT_FOUND","Enrollment reference image was not found.",404)
    return FileResponse(path,media_type="image/jpeg",headers={"Cache-Control":"private, no-store"})

"""Roster-scoped, server-only face identification for editable attendance sessions."""
from datetime import datetime,timezone
from threading import Lock
from collections import OrderedDict
import hashlib,json,time
import numpy as np,logging
from app.core.config import get_settings
from app.core.errors import AppError
from app.modules.attendance.service import EDITABLE
from app.modules.face_ai.crypto import decrypt_embedding
from app.modules.face_ai.engine import shared_engine
from app.modules.face_ai.repositories import FaceEnrollmentRepository
from app.core.logging import safe_log
logger=logging.getLogger("FACE")
attendance_logger=logging.getLogger("ATTENDANCE")

QUALITY_CODES={"FACE_NOT_FOUND":"no_face","MULTIPLE_FACES_FOUND":"multiple_faces","FACE_TOO_SMALL":"quality_rejected","IMAGE_TOO_BLURRY":"quality_rejected","POOR_LIGHTING":"quality_rejected","INVALID_FACE_IMAGE":"quality_rejected","INVALID_FACE_IMAGE_FORMAT":"quality_rejected"}

class FaceIdentificationService:
    _cooldowns={};_lock=Lock();_templates=OrderedDict();_template_lock=Lock()
    @classmethod
    def invalidate_templates(cls,institution_id):
        with cls._template_lock:
            for key in list(cls._templates):
                if key[0]==str(institution_id):cls._templates.pop(key,None)
    @classmethod
    def invalidate_session(cls,institution_id,session_id):
        with cls._template_lock:
            for key in list(cls._templates):
                if key[:2]==(str(institution_id),str(session_id)):cls._templates.pop(key,None)
        with cls._lock:
            for key in list(cls._cooldowns):
                if key[:2]==(str(institution_id),str(session_id)):cls._cooldowns.pop(key,None)
    def _prepared(self,session,user,docs):
        key=(str(user["institution_id"]),str(session["_id"]),str(user["_id"]),hashlib.sha256(self.settings.face_embedding_encryption_key.encode()).digest())
        signature=tuple(sorted((str(doc["student_id"]),doc["model_version"],hashlib.sha256(json.dumps(doc["encrypted_embedding"],sort_keys=True).encode()).digest()) for doc in docs))
        with self._template_lock:
            now=time.monotonic()
            for expired in [k for k,v in self._templates.items() if now-v[2]>300]:self._templates.pop(expired,None)
            cached=self._templates.get(key)
            if cached and cached[0]==signature:
                self._templates.move_to_end(key);return cached[1]
            prepared=[]
            for doc in docs:
                sid=str(doc["student_id"])
                values=decrypt_embedding(doc["encrypted_embedding"],user["institution_id"],sid,doc["model_version"],self.settings.face_embedding_encryption_key)
                vector=np.asarray(values,dtype=np.float32);norm=float(np.linalg.norm(vector))
                if norm>0 and np.all(np.isfinite(vector)):
                    vector=vector/norm;vector.setflags(write=False);prepared.append((sid,doc["model_version"],vector))
            self._templates[key]=(signature,prepared,now)
            while len(self._templates)>32:self._templates.popitem(last=False)
            return prepared
    def __init__(self,attendance,enrollments=None,engine=None,settings=None,clock=None,storage=None):
        from app.modules.face_ai.storage import configured_reference_storage
        self.attendance=attendance;self.enrollments=enrollments or FaceEnrollmentRepository();self.settings=settings or get_settings();self.engine=engine or shared_engine(self.settings.face_detection_model_path,self.settings.face_recognition_model_path,self.settings.face_detection_threshold,getattr(self.settings,"face_enrollment_consistency_threshold",.40));self.clock=clock or (lambda:datetime.now(timezone.utc));self.storage=storage or configured_reference_storage(self.settings)
    def _session(self,session_id,user):
        session=self.attendance._get(session_id,user["institution_id"]);self.attendance._owned(session,user)
        if session.get("status") not in EDITABLE:raise AppError("ATTENDANCE_NOT_EDITABLE","Face attendance is available only for an editable draft.",409)
        return session
    def capability(self):
        detector=self.settings.face_detection_model_path.is_file();recognizer=self.settings.face_recognition_model_path.is_file();encryption=bool(self.settings.face_embedding_encryption_key)
        available=bool(self.settings.face_ai_enabled and detector and recognizer and encryption)
        return {"detector":"available" if detector else "unavailable","recognizer":"available" if recognizer else "unavailable","encryption":"configured" if encryption else "not_configured","faceAttendance":"available" if available else "unavailable"}
    def _records(self,session,user):return self.attendance.records.for_session(session["_id"],user["institution_id"])
    def status(self,session_id,user):
        session=self._session(session_id,user);records=self._records(session,user);enrolled=self.enrollments.active_for_students([x["student_id"] for x in records],user["institution_id"]);enrolled_ids={str(x["student_id"]) for x in enrolled};recognized=[x for x in records if x.get("source")=="face_recognition" and x.get("status")=="present"]
        return {"sessionId":str(session["_id"]),"sessionStatus":session["status"],"capability":self.capability(),"stats":{"roster":len(records),"faceEnrolled":len(enrolled_ids),"recognized":len(recognized),"remaining":len(records)-len(recognized),"manualOnly":len(records)-len(enrolled_ids)}}
    def recognized(self,session_id,user):
        session=self._session(session_id,user);items=[]
        for x in self._records(session,user):
            if x.get("source")=="face_recognition" and x.get("status")=="present":items.append({"id":str(x["student_id"]),"displayName":x.get("student_name","Student"),"admissionNumber":x.get("admission_number"),"rollNumber":x.get("roll_number"),"attendanceState":"recognized"})
        return {"items":items,"count":len(items)}
    def analyze_preview(self,session_id,user,data,mime):
        self._session(session_id,user)
        if self.capability()["faceAttendance"]!="available":return {"valid":False,"result":"ai_unavailable"}
        result=self.engine.analyze_preview(data,mime) if hasattr(self.engine,"analyze_preview") else self.engine.analyze(data,mime);safe_log(logger,logging.DEBUG,"preview face detected",faces_detected=result["faceCount"],quality="accepted",pose=result.get("pose","center"))
        return {"valid":True,"faceCount":result["faceCount"],"detectionConfidence":result["detectionConfidence"],"quality":result["quality"],"pose":result.get("pose","center"),"faceBox":result.get("faceBox"),"modelVersion":result["modelVersion"]}
    def identify(self,session_id,user,data,mime,selected_student_id=None,liveness_frames=None):
        session=self._session(session_id,user)
        if self.capability()["faceAttendance"]!="available":return {"result":"ai_unavailable","attendanceState":"unchanged"}
        liveness=None;mode=getattr(self.settings,"face_liveness_mode","optional")
        if liveness_frames and mode!="disabled":
            try:liveness=(self.engine.analyze_frames(liveness_frames).get("liveness") or {"passed":False,"method":"not_available"})
            except AppError as exc:
                if exc.code in QUALITY_CODES:return {"result":QUALITY_CODES[exc.code],"attendanceState":"unchanged"}
                raise
        if mode=="required" and not (liveness and liveness.get("passed")):
            return {"result":"liveness_failed","attendanceState":"unchanged","liveness":{"required":True,"passed":False}}
        try:probe=self.engine.analyze(data,mime)
        except AppError as exc:
            if exc.code in QUALITY_CODES:return {"result":QUALITY_CODES[exc.code],"attendanceState":"unchanged","quality":exc.details.get("quality") if exc.details else None}
            if exc.code in {"FACE_MODEL_UNAVAILABLE","FACE_ANALYSIS_FAILED"}:return {"result":"ai_unavailable","attendanceState":"unchanged"}
            raise
        records=self._records(session,user);by_id={str(x["student_id"]):x for x in records}
        if selected_student_id and str(selected_student_id) not in by_id:return {"result":"student_not_enrolled","attendanceState":"unchanged"}
        scope=[selected_student_id] if selected_student_id else list(by_id);docs=self.enrollments.active_for_students(scope,user["institution_id"]);scores=[];safe_log(logger,logging.INFO,"candidate scope",class_division_id=str(session.get("class_division_id")),candidates=len(docs),mode="specific" if selected_student_id else "all")
        probe_vector=np.asarray(probe["embedding"],dtype=np.float32);norm=float(np.linalg.norm(probe_vector))
        if norm<=0 or not np.all(np.isfinite(probe_vector)):return {"result":"unknown","attendanceState":"unchanged"}
        probe_vector=probe_vector/norm
        scoped_docs=[doc for doc in docs if str(doc["student_id"]) in by_id]
        for sid,version,candidate in self._prepared(session,user,scoped_docs):
            if version==probe.get("modelVersion") and candidate.shape==probe_vector.shape:scores.append((float(np.dot(probe_vector,candidate)),sid))
        if not scores:return {"result":"not_verified" if selected_student_id else "unknown","attendanceState":"unchanged"}
        scores.sort(reverse=True);best,sid=scores[0];second=scores[1][0] if len(scores)>1 else -1.0
        if best<self.settings.face_match_threshold:return {"result":"not_verified" if selected_student_id else "unknown","attendanceState":"unchanged"}
        if not selected_student_id and best-second<self.settings.face_identification_min_margin:return {"result":"ambiguous","attendanceState":"unchanged"}
        now=self.clock();key=(str(user["institution_id"]),str(session["_id"]),sid)
        with self._lock:
            # Recheck editable status and the authoritative record after inference.
            self._session(session_id,user)
            fresh=next((x for x in self._records(session,user) if str(x["student_id"])==sid),None)
            if not fresh:return {"result":"student_not_enrolled","attendanceState":"unchanged"}
            previous=self._cooldowns.get(key)
            if fresh.get("source")=="manual" and fresh.get("status") not in (None,"present"):
                return {"result":"manual_override","student":{"id":sid,"displayName":fresh.get("student_name","Student")},"attendanceState":"unchanged"}
            if fresh.get("status")=="present" or (previous and (now-previous).total_seconds()<self.settings.face_recognition_cooldown_seconds):return {"result":"already_recognized","student":{"id":sid,"displayName":fresh.get("student_name","Student"),"admissionNumber":fresh.get("admission_number"),"rollNumber":fresh.get("roll_number")},"attendanceState":"recognized" if fresh.get("status")=="present" else "unchanged"}
            saved=self.attendance.records.save(session["_id"],user["institution_id"],[{"student_id":sid,"status":"present","remark":"AI face suggestion — Faculty review required"}],user["_id"],source="face_recognition")
            authoritative=next((x for x in saved if str(x["student_id"])==sid),None)
            if not authoritative or authoritative.get("status")!="present":
                return {"result":"manual_override","student":{"id":sid,"displayName":fresh.get("student_name","Student")},"attendanceState":"unchanged"}
            self._cooldowns[key]=now
            for expired in [k for k,v in self._cooldowns.items() if (now-v).total_seconds()>max(60,self.settings.face_recognition_cooldown_seconds)]:self._cooldowns.pop(expired,None)
        record=by_id[sid];safe_log(logger,logging.INFO,"identification result",result="verified" if selected_student_id else "identified",student_id=sid);safe_log(attendance_logger,logging.INFO,"AI attendance suggestion",student_id=sid,status="present",review_state="ai_suggested")
        return {"result":"verified" if selected_student_id else "identified","student":{"id":sid,"displayName":record.get("student_name","Student"),"admissionNumber":record.get("admission_number"),"rollNumber":record.get("roll_number")},"confidence":{"score":round(best,6)},"liveness":{"required":mode=="required","passed":bool(liveness and liveness.get("passed")),"method":liveness.get("method") if liveness else None},"attendanceState":"recognized"}

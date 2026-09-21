"""Attendance correction workflow; all resource lookups remain tenant-scoped."""
from datetime import datetime,timezone
from pymongo.errors import DuplicateKeyError
from app.core.errors import AppError
from app.db.mongo import mongo
from app.db.object_id import parse_object_id,serialize_document
from app.modules.attendance.repositories import AttendanceSessionRepository,AttendanceRecordRepository
from app.modules.students.repositories import StudentRepository
from app.modules.faculty.repositories import FacultyRepository,AssignmentRepository
from app.modules.notifications.service import NotificationService
from app.modules.audit.service import AuditService

FINAL_SESSION={"submitted","locked"}; VALID={"present","absent","late","excused"}

class AttendanceRequestService:
    def __init__(self,database=None,sessions=None,records=None,students=None,faculty=None,assignments=None,notifications=None,audit=None):
        self._database=database;self.sessions=sessions or AttendanceSessionRepository(database);self.records=records or AttendanceRecordRepository(database);self.students=students or StudentRepository(database);self.faculty=faculty or FacultyRepository(database);self.assignments=assignments or AssignmentRepository(database);self.notifications=notifications or NotificationService(database);self.audit=audit or AuditService(database)
    @property
    def collection(self): return (self._database or mongo.require_database()).attendance_requests
    @property
    def database(self): return self._database or mongo.require_database()
    def _request(self,request_id,user):
        item=self.collection.find_one({"_id":parse_object_id(request_id,"request_id"),"institution_id":parse_object_id(user["institution_id"])})
        if not item: raise AppError("REQUEST_NOT_FOUND","Attendance correction request was not found.",404)
        return item
    def _student(self,user):
        student=self.students.find_by_user(user["_id"],user["institution_id"])
        if not student: raise AppError("STUDENT_NOT_FOUND","An active Student profile is required.",404)
        return student
    def _session_record(self,session_id,student_id,iid):
        session=self.sessions.find_by_id(session_id,iid)
        if not session: raise AppError("ATTENDANCE_SESSION_NOT_ELIGIBLE","Attendance session was not found or is not eligible.",404)
        if session.get("status") not in FINAL_SESSION: raise AppError("ATTENDANCE_SESSION_NOT_ELIGIBLE","Only submitted or locked attendance can be corrected.",409)
        record=next((x for x in self.records.for_session(session["_id"],iid) if str(x.get("student_id"))==str(student_id)),None)
        if not record or record.get("status") not in VALID: raise AppError("ATTENDANCE_SESSION_NOT_ELIGIBLE","No finalized attendance record exists for this Student.",409)
        return session,record
    def _reviewer_allowed(self,item,user):
        if user.get("role")=="admin": return
        faculty=self.faculty.find_by_user(user["_id"],user["institution_id"])
        session=self.sessions.find_by_id(item["attendance_session_id"],user["institution_id"])
        if not faculty or faculty.get("status")!="active" or not session or str(session.get("faculty_id"))!=str(faculty["_id"]): raise AppError("REQUEST_REVIEW_FORBIDDEN","You are not authorized to review this request.",403)
        assignment=self.assignments.find_scoped(session.get("faculty_assignment_id"),user["institution_id"])
        if not assignment or assignment.get("status")!="active" or str(assignment.get("faculty_id"))!=str(faculty["_id"]): raise AppError("REQUEST_REVIEW_FORBIDDEN","You are not authorized to review this request.",403)
    def _serialize(self,item):
        data=serialize_document(item);session=self.sessions.find_by_id(item["attendance_session_id"],item["institution_id"]);student=self.students.find_by_id(item["student_id"],item["institution_id"])
        if session: data["session"]={"id":str(session["_id"]),"lectureDate":serialize_document(session).get("lecture_date"),"subjectId":str(session.get("subject_id","")),"classDivisionId":str(session.get("class_division_id","")),"status":session.get("status")}
        if student: data["student"]={"id":str(student["_id"]),"displayName":student.get("display_name"),"admissionNumber":student.get("admission_number")}
        return data
    def _reviewer_notifications(self,item,session):
        faculty=self.faculty.collection.find_one({"_id":session.get("faculty_id"),"institution_id":session["institution_id"],"status":"active"})
        recipients=[faculty.get("user_id")] if faculty and faculty.get("user_id") else [x["_id"] for x in self.database.users.find({"institution_id":session["institution_id"],"role":"admin","status":"active"},{"_id":1})]
        for recipient in recipients:
            self.notifications.create(item["institution_id"],recipient,"attendance_request.created","Attendance correction request","A student submitted an attendance correction request.","attendance_request",item["_id"])
    def create(self,payload,user):
        student=self._student(user);session,record=self._session_record(payload.attendance_session_id,student["_id"],user["institution_id"])
        if payload.requested_status not in VALID or payload.requested_status==record["status"]: raise AppError("INVALID_REQUESTED_STATUS","Requested status must be valid and different from the current status.",422)
        now=datetime.now(timezone.utc);document={"institution_id":parse_object_id(user["institution_id"]),"student_id":student["_id"],"attendance_session_id":session["_id"],"original_status":record["status"],"requested_status":payload.requested_status,"reason":payload.reason,"status":"pending","reviewer_user_id":None,"reviewer_role":None,"resolution_note":None,"reviewed_at":None,"created_at":now,"updated_at":now}
        try: result=self.collection.insert_one(document)
        except DuplicateKeyError as exc: raise AppError("REQUEST_ALREADY_PENDING","A pending correction request already exists for this attendance session.",409) from exc
        item={**document,"_id":result.inserted_id};self._reviewer_notifications(item,session);self.audit.record(user,"attendance.request.created","attendance_request",item["_id"],{"attendance_session_id":str(session["_id"]),"original_status":record["status"],"requested_status":payload.requested_status});return self._serialize(item)
    def mine(self,user,status=None,page=1,size=20):
        student=self._student(user);query={"institution_id":parse_object_id(user["institution_id"]),"student_id":student["_id"]}
        if status: query["status"]=status
        total=self.collection.count_documents(query);items=list(self.collection.find(query).sort("created_at",-1).skip((page-1)*size).limit(size));return {"items":[self._serialize(x) for x in items],"pagination":{"page":page,"pageSize":size,"total":total,"pages":(total+size-1)//size}}
    def get(self,request_id,user):
        item=self._request(request_id,user)
        if user.get("role")=="student" and str(item["student_id"])!=str(self._student(user)["_id"]): raise AppError("REQUEST_NOT_FOUND","Attendance correction request was not found.",404)
        if user.get("role")=="faculty": self._reviewer_allowed(item,user)
        return self._serialize(item)
    def cancel(self,request_id,user):
        item=self._request(request_id,user);student=self._student(user)
        if str(item["student_id"])!=str(student["_id"]): raise AppError("REQUEST_NOT_FOUND","Attendance correction request was not found.",404)
        if item["status"]!="pending": raise AppError("REQUEST_ALREADY_RESOLVED","Only pending requests can be cancelled.",409)
        now=datetime.now(timezone.utc);result=self.collection.update_one({"_id":item["_id"],"institution_id":item["institution_id"],"status":"pending"},{"$set":{"status":"cancelled","updated_at":now}})
        if not result.modified_count: raise AppError("REQUEST_ALREADY_RESOLVED","This request is no longer pending.",409)
        item=self.collection.find_one({"_id":item["_id"],"institution_id":item["institution_id"]});self.audit.record(user,"attendance.request.cancelled","attendance_request",item["_id"],{});return self._serialize(item)
    def queue(self,user,filters,page,size):
        query={"institution_id":parse_object_id(user["institution_id"])}
        if filters.get("status"): query["status"]=filters["status"]
        if filters.get("student"): query["student_id"]=parse_object_id(filters["student"],"student")
        session_filter={}
        for source,target in (("class","class_division_id"),("subject","subject_id")):
            if filters.get(source): session_filter[target]=parse_object_id(filters[source],source)
        if filters.get("date"): session_filter["lecture_date"]=filters["date"]
        if session_filter:
            ids=[x["_id"] for x in self.database.attendance_sessions.find({"institution_id":query["institution_id"],**session_filter},{"_id":1})];query["attendance_session_id"]={"$in":ids}
        if user.get("role")=="faculty":
            faculty=self.faculty.find_by_user(user["_id"],user["institution_id"])
            if not faculty: return {"items":[],"pagination":{"page":page,"pageSize":size,"total":0,"pages":0}}
            active_assignments=[x["_id"] for x in self.database.faculty_assignments.find({"institution_id":query["institution_id"],"faculty_id":faculty["_id"],"status":"active"},{"_id":1})]
            ids=[x["_id"] for x in self.database.attendance_sessions.find({"institution_id":query["institution_id"],"faculty_id":faculty["_id"],"faculty_assignment_id":{"$in":active_assignments}},{"_id":1})];query["attendance_session_id"]={"$in":list(set(ids)&set(query.get("attendance_session_id",{}).get("$in",ids)))}
        total=self.collection.count_documents(query);items=list(self.collection.find(query).sort("created_at",-1).skip((page-1)*size).limit(size));return {"items":[self._serialize(x) for x in items],"pagination":{"page":page,"pageSize":size,"total":total,"pages":(total+size-1)//size}}
    def resolve(self,request_id,decision,note,user):
        item=self._request(request_id,user);self._reviewer_allowed(item,user)
        if item["status"]!="pending": raise AppError("REQUEST_ALREADY_RESOLVED","This request has already been resolved.",409)
        session,record=self._session_record(item["attendance_session_id"],item["student_id"],user["institution_id"])
        if record.get("status")!=item["original_status"]: raise AppError("ATTENDANCE_STATE_CHANGED","Attendance changed after this request was created; reload before reviewing.",409)
        now=datetime.now(timezone.utc)
        if decision=="approved":
            result=self.records.collection.update_one({"_id":record["_id"],"institution_id":parse_object_id(user["institution_id"]),"status":item["original_status"]},{"$set":{"status":item["requested_status"],"source":"correction_request","updated_at":now,"marked_at":now,"marked_by":parse_object_id(user["_id"])}})
            if not result.modified_count: raise AppError("ATTENDANCE_STATE_CHANGED","Attendance changed after this request was created; reload before reviewing.",409)
        result=self.collection.update_one({"_id":item["_id"],"institution_id":parse_object_id(user["institution_id"]),"status":"pending"},{"$set":{"status":decision,"reviewer_user_id":parse_object_id(user["_id"]),"reviewer_role":user["role"],"resolution_note":note,"reviewed_at":now,"updated_at":now}})
        if not result.modified_count: raise AppError("REQUEST_ALREADY_RESOLVED","This request has already been resolved.",409)
        item=self.collection.find_one({"_id":item["_id"],"institution_id":parse_object_id(user["institution_id"])});student=self.students.find_by_id(item["student_id"],user["institution_id"])
        self.notifications.create(user["institution_id"],student["user_id"],f"attendance_request.{decision}",f"Attendance correction {decision}",f"Your attendance correction request was {decision}.","attendance_request",item["_id"])
        self.audit.record(user,f"attendance.request.{decision}","attendance_request",item["_id"],{"attendance_session_id":str(session["_id"]),"resolution_note":note})
        if decision=="approved": self.audit.record(user,"attendance.record.corrected","attendance_record",record["_id"],{"attendance_session_id":str(session["_id"]),"student_id":str(item["student_id"]),"from":item["original_status"],"to":item["requested_status"]})
        return self._serialize(item)

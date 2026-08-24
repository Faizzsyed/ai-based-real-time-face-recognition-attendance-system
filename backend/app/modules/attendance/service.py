"""Ownership, state-machine, roster, and reporting rules for manual attendance."""
from datetime import date,datetime,time,timezone
from app.core.errors import AppError
from app.db.object_id import parse_object_id,serialize_document
from app.modules.attendance.repositories import AttendanceRecordRepository,AttendanceRosterRepository,AttendanceSessionRepository
from app.modules.faculty.repositories import AssignmentRepository,FacultyRepository
from app.modules.students.repositories import StudentRepository
from app.modules.timetable.repositories import TimetableRepository
import logging
from app.core.logging import safe_log
logger=logging.getLogger("ATTENDANCE")

EDITABLE={"draft","reopened"};FINAL={"submitted","locked"}
def _dt(value):return datetime.combine(value,time.min,tzinfo=timezone.utc) if isinstance(value,date) and not isinstance(value,datetime) else value
def _serialize_list(items):return [serialize_document(x) for x in items]

class AttendanceService:
    def __init__(self,sessions=None,records=None,roster=None,timetable=None,assignments=None,faculty=None,students=None):
        self.sessions=sessions or AttendanceSessionRepository();self.records=records or AttendanceRecordRepository();self.roster=roster or AttendanceRosterRepository();self.timetable=timetable or TimetableRepository();self.assignments=assignments or AssignmentRepository();self.faculty=faculty or FacultyRepository();self.students=students or StudentRepository()
    def _faculty(self,user):
        faculty=self.faculty.find_by_user(user["_id"],user["institution_id"])
        if not faculty or faculty.get("status")!="active":raise AppError("FACULTY_NOT_FOUND","An active Faculty profile is required.",404)
        return faculty
    def _owned(self,session,user):
        faculty=self._faculty(user)
        if str(session.get("faculty_id"))!=str(faculty["_id"]):raise AppError("FORBIDDEN_ATTENDANCE_SESSION","This attendance session belongs to another Faculty member.",403)
        return faculty
    def _get(self,session_id,iid):
        session=self.sessions.find_by_id(session_id,iid)
        if not session:raise AppError("ATTENDANCE_SESSION_NOT_FOUND","Attendance session was not found.",404)
        return session
    def start(self,payload,user):
        safe_log(logger,logging.INFO,"session start requested",user_id=str(user.get("_id")),timetable_entry_id=payload.timetable_entry_id)
        iid=user["institution_id"];faculty=self._faculty(user);entry=self.timetable.find_by_id(payload.timetable_entry_id,iid)
        if not entry or entry.get("status")!="active" or str(entry.get("faculty_id"))!=str(faculty["_id"]):raise AppError("UNASSIGNED_LECTURE","Faculty may start attendance only for an active lecture they own.",403)
        assignment=self.assignments.find_scoped(entry["faculty_assignment_id"],iid)
        if not assignment or assignment.get("status")!="active" or str(assignment.get("faculty_id"))!=str(faculty["_id"]):raise AppError("INVALID_FACULTY_ASSIGNMENT","The teaching assignment is no longer active.",409)
        lecture_date=payload.lecture_date
        if entry.get("day_of_week")!=lecture_date.strftime("%A").casefold() or lecture_date<_dt(entry["effective_from"]).date() or entry.get("effective_until") and lecture_date>_dt(entry["effective_until"]).date():raise AppError("INVALID_LECTURE_DATE","The selected date is outside this timetable occurrence.",422)
        existing=self.sessions.find_scheduled(iid,entry["_id"],lecture_date)
        if existing:
            if str(existing["faculty_id"])!=str(faculty["_id"]):raise AppError("ATTENDANCE_SESSION_EXISTS","Attendance was already started for this lecture.",409)
            return self.details(existing["_id"],user)
        now=datetime.now(timezone.utc)
        try:session=self.sessions.insert({"institution_id":parse_object_id(iid),"academic_year_id":entry["academic_year_id"],"timetable_entry_id":entry["_id"],"faculty_assignment_id":entry["faculty_assignment_id"],"faculty_id":faculty["_id"],"class_division_id":entry["class_division_id"],"subject_id":entry["subject_id"],"lecture_date":_dt(lecture_date),"scheduled_start":entry["start_time"],"scheduled_end":entry["end_time"],"actual_started_at":now,"submitted_at":None,"status":"draft","topic":payload.topic,"notes":payload.notes,"created_at":now,"updated_at":now,"created_by":parse_object_id(user["_id"]),"status_history":[{"action":"started","at":now,"by":parse_object_id(user["_id"])}]})
        except AppError as exc:
            if exc.code!="ATTENDANCE_SESSION_EXISTS":raise
            concurrent=self.sessions.find_scheduled(iid,entry["_id"],lecture_date)
            if not concurrent or str(concurrent.get("faculty_id"))!=str(faculty["_id"]):raise
            return self.details(concurrent["_id"],user)
        enrollments=self.roster.active_for_class(iid,entry["academic_year_id"],entry["class_division_id"],lecture_date)
        initial=[{"institution_id":parse_object_id(iid),"session_id":session["_id"],"student_id":e["student_id"],"student_enrollment_id":e["_id"],"student_name":e.get("student",{}).get("display_name","Student"),"admission_number":e.get("student",{}).get("admission_number"),"roll_number":e.get("roll_number"),"status":None,"source":"manual","review_state":None,"remark":None,"marked_at":None,"marked_by":None,"updated_at":now} for e in enrollments]
        self.records.initialize_roster(initial);safe_log(logger,logging.INFO,"session started",session_id=str(session["_id"]),roster=len(initial));return self.details(session["_id"],user)
    def details(self,session_id,user,admin=False):
        session=self._get(session_id,user["institution_id"])
        if not admin:self._owned(session,user)
        data=serialize_document(session);data["records"]=_serialize_list(self.records.for_session(session["_id"],user["institution_id"]));data["summary"]=self._summary(data["records"]);return data
    def save(self,session_id,payload,user,administrative=False,reason=None):
        session=self._get(session_id,user["institution_id"])
        if not administrative:self._owned(session,user)
        if session["status"] not in EDITABLE and not administrative:raise AppError("ATTENDANCE_NOT_EDITABLE","Submitted or locked attendance cannot be edited by Faculty.",409)
        if administrative and session["status"]=="locked":raise AppError("ATTENDANCE_LOCKED","Unlock or reopen the session before administrative editing.",409)
        items=[x.model_dump() for x in payload.records];saved=self.records.save(session["_id"],user["institution_id"],items,user["_id"])
        changes={"updated_by":parse_object_id(user["_id"])}
        if hasattr(payload,"topic"):changes.update({"topic":payload.topic,"notes":payload.notes})
        if administrative:changes["last_admin_edit"]={"at":datetime.now(timezone.utc),"by":parse_object_id(user["_id"]),"reason":reason}
        self.sessions.update(session["_id"],user["institution_id"],changes);return self.details(session["_id"],user,admin=administrative)
    @staticmethod
    def _summary(records):
        counts={x:0 for x in ("present","absent","late","excused","unmarked")}
        for r in records:counts[r.get("status") or "unmarked"]+=1
        denominator=counts["present"]+counts["late"]+counts["absent"];counts["total"]=len(records);counts["attendancePercentage"]=round((counts["present"]+counts["late"])*100/denominator,2) if denominator else 0.0;return counts
    def submit(self,session_id,user):
        session=self._get(session_id,user["institution_id"]);self._owned(session,user)
        if session["status"] not in EDITABLE:raise AppError("ATTENDANCE_NOT_SUBMITTABLE","Only draft or reopened attendance can be submitted.",409)
        records=self.records.for_session(session["_id"],user["institution_id"])
        if not records or any(r.get("status") not in {"present","absent","late","excused"} for r in records):raise AppError("INCOMPLETE_ATTENDANCE","Every roster Student must have a valid status before submission.",422,{"summary":self._summary(records)})
        now=datetime.now(timezone.utc);history=[*session.get("status_history",[]),{"action":"submitted","at":now,"by":parse_object_id(user["_id"])}];self.sessions.update(session["_id"],user["institution_id"],{"status":"submitted","submitted_at":now,"status_history":history});safe_log(logger,logging.INFO,"session submitted",session_id=str(session["_id"]),records=len(records));return self.details(session["_id"],user)
    def faculty_sessions(self,user,status=None):
        faculty=self._faculty(user);items=self.sessions.for_faculty(user["institution_id"],faculty["_id"],status);return _serialize_list(items)
    def admin_list(self,user,filters,page,size):
        items,total=self.sessions.list(user["institution_id"],filters,page,size);return {"items":_serialize_list(items),"pagination":{"page":page,"pageSize":size,"total":total,"pages":((total+size-1)//size)}}
    def admin_action(self,session_id,action,reason,user):
        session=self._get(session_id,user["institution_id"])
        allowed={"reopen":{"submitted","locked"},"lock":{"submitted","reopened"}}
        if session["status"] not in allowed[action]:raise AppError("INVALID_ATTENDANCE_TRANSITION",f"Cannot {action} a {session['status']} session.",409)
        status="reopened" if action=="reopen" else "locked";now=datetime.now(timezone.utc);history=[*session.get("status_history",[]),{"action":action,"at":now,"by":parse_object_id(user["_id"]),"reason":reason}];return serialize_document(self.sessions.update(session_id,user["institution_id"],{"status":status,"status_history":history,"updated_by":parse_object_id(user["_id"])}))
    def student_report(self,user,session_id=None):
        student=self.students.find_by_user(user["_id"],user["institution_id"])
        if not student:raise AppError("STUDENT_NOT_FOUND","Student was not found.",404)
        sessions,_=self.sessions.list(user["institution_id"],{"status":"submitted"},1,10000);sessions+=self.sessions.list(user["institution_id"],{"status":"locked"},1,10000)[0]
        session_map={str(s["_id"]):s for s in sessions}
        if session_id:
            session=session_map.get(str(session_id))
            if not session:raise AppError("ATTENDANCE_SESSION_NOT_FOUND","Attendance session was not found.",404)
            record=next((r for r in self.records.for_student(user["institution_id"],student["_id"],[session_id]) if str(r["session_id"])==str(session_id)),None)
            if not record:raise AppError("ATTENDANCE_RECORD_NOT_FOUND","No attendance record exists for this Student and session.",404)
            return {"session":serialize_document(session),"record":serialize_document(record)}
        records=self.records.for_student(user["institution_id"],student["_id"],session_map.keys());history=[];by_subject={}
        for record in records:
            session=session_map.get(str(record["session_id"]));
            if not session:continue
            item={**serialize_document(record),"lectureDate":serialize_document(session).get("lecture_date"),"subjectId":str(session["subject_id"]),"sessionStatus":session["status"]};history.append(item);by_subject.setdefault(str(session["subject_id"]),[]).append(record)
        summary=self._summary(records);subjects=[{"subjectId":sid,**self._summary(rows)} for sid,rows in by_subject.items()]
        return {"summary":summary,"subjects":subjects,"history":history,"formula":{"attended":"present + late","denominator":"present + late + absent","excused":"excluded from denominator"}}

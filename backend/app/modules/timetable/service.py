"""Recurring timetable validation, conflict detection, and local lecture derivation."""
from datetime import date,datetime,time,timedelta,timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo,ZoneInfoNotFoundError
from app.core.errors import AppError
from app.db.object_id import parse_object_id,serialize_document
from app.modules.academic_common.services import build_services
from app.modules.faculty.repositories import AssignmentRepository,FacultyRepository
from app.modules.students.repositories import EnrollmentRepository,StudentRepository
from app.modules.timetable.repositories import TimetableRepository
import logging
from app.core.logging import safe_log
logger=logging.getLogger("TIMETABLE")

DAY_INDEX={name:index for index,name in enumerate(("monday","tuesday","wednesday","thursday","friday","saturday","sunday"))}
def as_datetime(value): return datetime.combine(value,time.min,tzinfo=timezone.utc) if isinstance(value,date) and not isinstance(value,datetime) else value
def as_date(value): return value.date() if isinstance(value,datetime) else value
def clock(value): return value.strftime("%H:%M") if isinstance(value,time) else value
def enum_value(value): return getattr(value,"value",value)

class TimetableService:
    def __init__(self,entries=None,assignments=None,faculty=None,students=None,enrollments=None,academics=None):
        self.entries=entries or TimetableRepository();self.assignments=assignments or AssignmentRepository();self.faculty=faculty or FacultyRepository();self.students=students or StudentRepository();self.enrollments=enrollments or EnrollmentRepository();self.academics=academics or build_services()
    def _academic(self,resource,value,iid,active=True):
        document=self.academics[resource].repository.find_by_id(value)
        if not document or str(document.get("institution_id"))!=str(iid):raise AppError("CROSS_INSTITUTION_REFERENCE","Scheduling reference is outside this Institution.",422)
        if active and document.get("status","active")!="active":raise AppError("INACTIVE_ACADEMIC_REFERENCE","Scheduling reference is inactive.",422)
        return document
    def _timezone(self,iid):
        institution=self.academics["institutions"].repository.find_by_id(iid)
        if not institution:raise AppError("INSTITUTION_NOT_FOUND","Institution was not found.",404)
        try:return ZoneInfo(institution.get("timezone") or "UTC")
        except ZoneInfoNotFoundError as exc:raise AppError("INVALID_INSTITUTION_TIMEZONE","Institution timezone is invalid.",500) from exc
    def _candidate(self,model,iid):
        assignment=self.assignments.find_scoped(model.faculty_assignment_id,iid)
        if not assignment or assignment.get("status")!="active":raise AppError("INVALID_FACULTY_ASSIGNMENT","An active Faculty assignment is required.",422)
        faculty=self.faculty.find_by_id(assignment["faculty_id"],iid)
        if not faculty or faculty.get("status")!="active":raise AppError("FACULTY_INACTIVE","The assigned Faculty is not active.",422)
        year=self._academic("academic-years",assignment["academic_year_id"],iid)
        start=clock(model.start_time);end=clock(model.end_time);effective_from=as_datetime(model.effective_from);effective_until=as_datetime(model.effective_until)
        if start>=end:raise AppError("INVALID_TIMETABLE_TIME","start_time must precede end_time.",422)
        if effective_until and effective_until<effective_from:raise AppError("INVALID_TIMETABLE_DATES","effective_until cannot precede effective_from.",422)
        day=enum_value(model.day_of_week)
        return {"institution_id":parse_object_id(iid),"academic_year_id":assignment["academic_year_id"],"faculty_assignment_id":assignment["_id"],"faculty_id":assignment["faculty_id"],"class_division_id":assignment["class_division_id"],"subject_id":assignment["subject_id"],"day_of_week":day,"day_index":DAY_INDEX[day],"start_time":start,"end_time":end,"room":model.room,"lecture_type":enum_value(model.lecture_type),"effective_from":effective_from,"effective_until":effective_until,"status":enum_value(model.status)},year
    def _validate_hierarchy(self,candidate,iid):
        division=self._academic("classes",candidate["class_division_id"],iid);subject=self._academic("subjects",candidate["subject_id"],iid)
        if str(division.get("academic_year_id"))!=str(candidate["academic_year_id"]) or str(subject.get("program_id"))!=str(division.get("program_id")) or str(subject.get("semester_id"))!=str(division.get("semester_id")):
            raise AppError("INVALID_TIMETABLE_HIERARCHY","Faculty assignment, Class, Subject, and Academic Year do not match.",422)
    def _check_conflicts(self,candidate,iid,exclude=None):
        if candidate["status"]!="active":return
        conflicts=[]
        for existing in self.entries.conflicts(iid,candidate,exclude):
            reasons=[]
            if existing.get("faculty_id")==candidate["faculty_id"]:reasons.append("faculty")
            if existing.get("class_division_id")==candidate["class_division_id"]:reasons.append("class")
            if candidate.get("room") and existing.get("room") and existing["room"].casefold()==candidate["room"].casefold():reasons.append("room")
            if reasons:conflicts.append({"timetableEntryId":str(existing["_id"]),"types":reasons,"day":existing["day_of_week"],"startTime":existing["start_time"],"endTime":existing["end_time"],"room":existing.get("room")})
        if conflicts:safe_log(logger,logging.WARNING,"timetable conflict",conflicts=len(conflicts));raise AppError("TIMETABLE_CONFLICT",f"Schedule conflicts with {len(conflicts)} active timetable entr{'y' if len(conflicts)==1 else 'ies'}.",409,{"conflicts":conflicts})
    def create(self,model,iid,actor):
        candidate,_=self._candidate(model,iid);self._validate_hierarchy(candidate,iid);self._check_conflicts(candidate,iid);now=datetime.now(timezone.utc);candidate.update({"created_at":now,"updated_at":now,"created_by":parse_object_id(actor,"actor_id")});created=self.entries.insert(candidate);safe_log(logger,logging.INFO,"timetable entry created",entry_id=str(created.get("_id")));return serialize_document(created)
    def update(self,entry_id,model,iid,actor):
        current=self.entries.find_by_id(entry_id,iid)
        if not current:raise AppError("TIMETABLE_ENTRY_NOT_FOUND","Timetable entry was not found.",404)
        values={"faculty_assignment_id":str(current["faculty_assignment_id"]),"day_of_week":current["day_of_week"],"start_time":time.fromisoformat(current["start_time"]),"end_time":time.fromisoformat(current["end_time"]),"room":current.get("room"),"lecture_type":current["lecture_type"],"effective_from":as_date(current["effective_from"]),"effective_until":as_date(current.get("effective_until")),"status":current["status"]}
        values.update(model.model_dump(exclude_unset=True));merged=SimpleNamespace(**values);candidate,_=self._candidate(merged,iid);self._validate_hierarchy(candidate,iid);self._check_conflicts(candidate,iid,entry_id);candidate["updated_by"]=parse_object_id(actor,"actor_id");return serialize_document(self.entries.update(entry_id,iid,candidate))
    def set_status(self,entry_id,status,iid,actor):
        status=enum_value(status)
        current=self.entries.find_by_id(entry_id,iid)
        if not current:raise AppError("TIMETABLE_ENTRY_NOT_FOUND","Timetable entry was not found.",404)
        if status=="active":
            values={"faculty_assignment_id":str(current["faculty_assignment_id"]),"day_of_week":current["day_of_week"],"start_time":time.fromisoformat(current["start_time"]),"end_time":time.fromisoformat(current["end_time"]),"room":current.get("room"),"lecture_type":current["lecture_type"],"effective_from":as_date(current["effective_from"]),"effective_until":as_date(current.get("effective_until")),"status":"active"}
            candidate,_=self._candidate(SimpleNamespace(**values),iid);self._validate_hierarchy(candidate,iid);self._check_conflicts(candidate,iid,entry_id)
        return serialize_document(self.entries.update(entry_id,iid,{"status":status,"updated_by":parse_object_id(actor,"actor_id")}))
    def list(self,iid,filters,page,size):
        items,total=self.entries.list(iid,filters,page,size);return {"items":[serialize_document(x) for x in items],"pagination":{"page":page,"pageSize":size,"total":total,"pages":(total+size-1)//size}}
    def _instances(self,items,iid,now=None):
        zone=self._timezone(iid);local_now=(now or datetime.now(timezone.utc)).astimezone(zone);today=local_now.date();instances=[]
        for offset in range(7):
            lecture_date=today+timedelta(days=offset)
            for entry in items:
                if entry.get("status")!="active" or entry["day_of_week"]!=lecture_date.strftime("%A").casefold():continue
                if lecture_date<as_date(entry["effective_from"]) or entry.get("effective_until") and lecture_date>as_date(entry["effective_until"]):continue
                start_local=datetime.combine(lecture_date,time.fromisoformat(entry["start_time"]),zone);end_local=datetime.combine(lecture_date,time.fromisoformat(entry["end_time"]),zone)
                state="upcoming" if local_now<start_local else "active" if local_now<end_local else "completed-window"
                instances.append({"timetableEntryId":str(entry["_id"]),"subject":serialize_document(entry.get("subject")),"class":serialize_document(entry.get("class_division")),"faculty":serialize_document(entry.get("faculty")),"date":lecture_date.isoformat(),"startTime":entry["start_time"],"endTime":entry["end_time"],"room":entry.get("room"),"lectureType":entry["lecture_type"],"state":state,"timezone":str(zone)})
        instances.sort(key=lambda x:(x["date"],x["startTime"]));return instances
    def schedule(self,items,iid,now=None):
        instances=self._instances(items,iid,now);today_date=(now or datetime.now(timezone.utc)).astimezone(self._timezone(iid)).date().isoformat();today=[x for x in instances if x["date"]==today_date];upcoming=[x for x in instances if x["state"] in {"upcoming","active"}]
        return {"today":today,"week":instances,"upcoming":upcoming,"nextLecture":upcoming[0] if upcoming else None,"timezone":str(self._timezone(iid))}
    def faculty_schedule(self,user,now=None):
        faculty=self.faculty.find_by_user(user["_id"],user["institution_id"])
        if not faculty:raise AppError("FACULTY_NOT_FOUND","Faculty was not found.",404)
        return self.schedule(self.entries.active_for_faculty(user["institution_id"],faculty["_id"]),str(user["institution_id"]),now)
    def student_schedule(self,user,now=None):
        student=self.students.find_by_user(user["_id"],user["institution_id"])
        if not student:raise AppError("STUDENT_NOT_FOUND","Student was not found.",404)
        enrollment=self.enrollments.current(student["_id"],user["institution_id"])
        if not enrollment or enrollment.get("enrollment_status","active")!="active":raise AppError("CURRENT_ENROLLMENT_NOT_FOUND","Student has no active current enrollment.",409)
        return self.schedule(self.entries.active_for_class(user["institution_id"],enrollment["class_division_id"]),str(user["institution_id"]),now)

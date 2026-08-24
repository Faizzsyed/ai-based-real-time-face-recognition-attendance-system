"""Phase 7 recurring scheduling, conflict, scope, timezone, and API tests."""
from datetime import datetime,timezone
from types import SimpleNamespace
from bson import ObjectId
from fastapi.testclient import TestClient
import pytest
from app.api.timetable import get_timetable_service
from app.core.errors import AppError
from app.main import app
from app.modules.auth.dependencies import get_current_user
from app.modules.timetable.schemas import TimetableEntryCreate,TimetableEntryUpdate
from app.modules.timetable.service import TimetableService
from tests.test_phase5_students import AcademicRepo
from tests.test_phase6_faculty import FacultyMemory

IID=ObjectId();OTHER=ObjectId();ADMIN=ObjectId();FACULTY_USER=ObjectId();STUDENT_USER=ObjectId()
class EntryMemory:
    def __init__(self,academic,faculty):self.docs=[];self.academic=academic;self.faculty=faculty
    def insert(self,d):d={**d,"_id":ObjectId()};self.docs.append(d);return d
    def find_by_id(self,eid,iid):return next((d for d in self.docs if str(d["_id"])==str(eid) and str(d["institution_id"])==str(iid)),None)
    def update(self,eid,iid,c):d=self.find_by_id(eid,iid);d.update(c);return d
    def conflicts(self,iid,candidate,exclude_id=None):
        def overlaps(a,b):return a["start_time"]<b["end_time"] and a["end_time"]>b["start_time"] and a["effective_from"]<=(b.get("effective_until") or datetime.max.replace(tzinfo=timezone.utc)) and (a.get("effective_until") is None or a["effective_until"]>=b["effective_from"])
        return [d for d in self.docs if str(d["institution_id"])==str(iid) and d["status"]=="active" and d["day_of_week"]==candidate["day_of_week"] and str(d["_id"])!=str(exclude_id) and overlaps(d,candidate)]
    def _enriched(self,d):
        def doc(resource,key):return self.academic[resource].repository.find_by_id(d[key])
        return {**d,"subject":doc("subjects","subject_id"),"class_division":doc("classes","class_division_id"),"faculty":self.faculty.find_by_id(d["faculty_id"],d["institution_id"]),"academic_year":doc("academic-years","academic_year_id")}
    def list(self,iid,filters,page,size):
        rows=[]
        for d in self.docs:
            if str(d["institution_id"])!=str(iid):continue
            if any(filters.get(k) and str(d.get(k))!=str(filters[k]) for k in ("academic_year_id","faculty_id","class_division_id","subject_id","day_of_week","status")):continue
            enriched=self._enriched(d);division=enriched.get("class_division") or {}
            if any(filters.get(k) and str(division.get(k))!=str(filters[k]) for k in ("department_id","program_id","semester_id")):continue
            rows.append(enriched)
        rows.sort(key=lambda x:(x["day_index"],x["start_time"]));return rows[(page-1)*size:page*size],len(rows)
    def active_for_faculty(self,iid,fid):return self.list(iid,{"faculty_id":fid,"status":"active"},1,100)[0]
    def active_for_class(self,iid,cid):return self.list(iid,{"class_division_id":cid,"status":"active"},1,100)[0]
class AssignmentMemory:
    def __init__(self,docs):self.docs=docs
    def find_scoped(self,aid,iid):return next((d for d in self.docs if str(d["_id"])==str(aid) and str(d["institution_id"])==str(iid)),None)
class StudentMemory:
    def __init__(self,student):self.student=student
    def find_by_user(self,uid,iid):return self.student if str(uid)==str(self.student["user_id"]) and str(iid)==str(self.student["institution_id"]) else None
class EnrollmentMemory:
    def __init__(self,enrollment):self.enrollment=enrollment
    def current(self,sid,iid):return self.enrollment if str(sid)==str(self.enrollment["student_id"]) and str(iid)==str(self.enrollment["institution_id"]) else None

def domain():
    ids={x:ObjectId() for x in ("year","department","program","semester","class","subject","faculty","assignment","student","enrollment")}
    docs={"institutions":{"_id":IID,"institution_id":IID,"timezone":"Asia/Kolkata","status":"active"},"academic-years":{"_id":ids["year"],"institution_id":IID,"status":"active","name":"2026-2027"},"departments":{"_id":ids["department"],"institution_id":IID,"status":"active"},"programs":{"_id":ids["program"],"institution_id":IID,"status":"active","department_id":ids["department"]},"semesters":{"_id":ids["semester"],"institution_id":IID,"status":"active","program_id":ids["program"],"academic_year_id":ids["year"]},"classes":{"_id":ids["class"],"institution_id":IID,"status":"active","name":"Semester 4 A","division":"A","academic_year_id":ids["year"],"department_id":ids["department"],"program_id":ids["program"],"semester_id":ids["semester"]},"subjects":{"_id":ids["subject"],"institution_id":IID,"status":"active","name":"Data Structures","code":"DS","department_id":ids["department"],"program_id":ids["program"],"semester_id":ids["semester"]}}
    academics={k:SimpleNamespace(repository=AcademicRepo(v)) for k,v in docs.items()};faculty=FacultyMemory();faculty.docs.append({"_id":ids["faculty"],"institution_id":IID,"user_id":FACULTY_USER,"display_name":"Ada Faculty","status":"active"});assignment={"_id":ids["assignment"],"institution_id":IID,"faculty_id":ids["faculty"],"academic_year_id":ids["year"],"class_division_id":ids["class"],"subject_id":ids["subject"],"status":"active"};student={"_id":ids["student"],"institution_id":IID,"user_id":STUDENT_USER};enrollment={"_id":ids["enrollment"],"institution_id":IID,"student_id":ids["student"],"class_division_id":ids["class"],"is_current":True};entries=EntryMemory(academics,faculty);service=TimetableService(entries,AssignmentMemory([assignment]),faculty,StudentMemory(student),EnrollmentMemory(enrollment),academics)
    payload={"faculty_assignment_id":str(ids["assignment"]),"day_of_week":"tuesday","start_time":"09:00","end_time":"10:00","room":"A-101","lecture_type":"theory","effective_from":"2026-08-01"}
    return service,payload,ids,assignment

def test_schedule_creation_derives_assignment_ownership():
    svc,payload,ids,_=domain();created=svc.create(TimetableEntryCreate(**payload),str(IID),str(ADMIN));assert created["faculty_id"]==str(ids["faculty"]) and created["subject_id"]==str(ids["subject"]) and created["start_time"]=="09:00"
def test_invalid_or_cross_tenant_assignment_rejected():
    svc,payload,_,assignment=domain();assignment["institution_id"]=OTHER
    with pytest.raises(AppError) as error:svc.create(TimetableEntryCreate(**payload),str(IID),str(ADMIN))
    assert error.value.code=="INVALID_FACULTY_ASSIGNMENT"
@pytest.mark.parametrize("field,value,kind",(("faculty_id",ObjectId(),"class"),("class_division_id",ObjectId(),"faculty")))
def test_overlap_conflicts_are_detected(field,value,kind):
    svc,payload,_,_=domain();candidate,_=svc._candidate(TimetableEntryCreate(**payload),str(IID));existing={**candidate,"_id":ObjectId()};existing[field]=value
    svc.entries.docs.append(existing)
    with pytest.raises(AppError) as error:svc.create(TimetableEntryCreate(**payload),str(IID),str(ADMIN))
    assert error.value.code=="TIMETABLE_CONFLICT" and kind in error.value.details["conflicts"][0]["types"]
def test_room_conflict_is_detected_for_different_faculty_and_class():
    svc,payload,_,_=domain();candidate,_=svc._candidate(TimetableEntryCreate(**payload),str(IID));existing={**candidate,"_id":ObjectId(),"faculty_id":ObjectId(),"class_division_id":ObjectId()};svc.entries.docs.append(existing)
    with pytest.raises(AppError) as error:svc.create(TimetableEntryCreate(**payload),str(IID),str(ADMIN))
    assert error.value.code=="TIMETABLE_CONFLICT" and "room" in error.value.details["conflicts"][0]["types"]
def test_non_overlapping_entry_is_accepted():
    svc,payload,_,_=domain();svc.create(TimetableEntryCreate(**payload),str(IID),str(ADMIN));second={**payload,"start_time":"10:00","end_time":"11:00"};assert svc.create(TimetableEntryCreate(**second),str(IID),str(ADMIN))["start_time"]=="10:00"
def test_update_detects_conflict_and_deactivation_is_safe():
    svc,payload,_,_=domain();first=svc.create(TimetableEntryCreate(**payload),str(IID),str(ADMIN));second=svc.create(TimetableEntryCreate(**{**payload,"start_time":"10:00","end_time":"11:00"}),str(IID),str(ADMIN))
    with pytest.raises(AppError):svc.update(second["_id"],TimetableEntryUpdate(start_time="09:30"),str(IID),str(ADMIN))
    changed=svc.set_status(first["_id"],"inactive",str(IID),str(ADMIN));assert changed["status"]=="inactive" and len(svc.entries.docs)==2
def test_faculty_receives_only_own_timezone_aware_schedule():
    svc,payload,_,_=domain();svc.create(TimetableEntryCreate(**payload),str(IID),str(ADMIN));now=datetime(2026,8,11,3,45,tzinfo=timezone.utc);schedule=svc.faculty_schedule({"_id":FACULTY_USER,"institution_id":IID},now);assert schedule["timezone"]=="Asia/Kolkata" and schedule["today"][0]["state"]=="active" and schedule["today"][0]["subject"]["name"]=="Data Structures"
def test_student_schedule_resolves_current_class_only():
    svc,payload,_,_=domain();svc.create(TimetableEntryCreate(**payload),str(IID),str(ADMIN));schedule=svc.student_schedule({"_id":STUDENT_USER,"institution_id":IID},datetime(2026,8,11,0,0,tzinfo=timezone.utc));assert len(schedule["week"])==1 and schedule["nextLecture"] is not None
def test_pagination_and_filters():
    svc,payload,ids,_=domain();svc.create(TimetableEntryCreate(**payload),str(IID),str(ADMIN));listed=svc.list(str(IID),{"faculty_id":str(ids["faculty"]),"department_id":str(ids["department"]),"day_of_week":"tuesday"},1,20);assert listed["pagination"]["total"]==1
def test_timetable_admin_and_self_routes_are_role_scoped():
    class Listing:
        def list(self,*args):return {"items":[],"pagination":{"page":1,"pageSize":20,"total":0,"pages":0}}
    app.dependency_overrides[get_timetable_service]=lambda:Listing()
    try:
        for role in ("faculty","student"):
            app.dependency_overrides[get_current_user]=lambda role=role:{"_id":ObjectId(),"institution_id":IID,"role":role,"status":"active"};assert TestClient(app).get("/api/v1/admin/timetable").status_code==403
        app.dependency_overrides[get_current_user]=lambda:{"_id":ADMIN,"institution_id":IID,"role":"admin","status":"active"};assert TestClient(app).get("/api/v1/admin/timetable").status_code==200
    finally:app.dependency_overrides.clear()

def test_faculty_and_student_timetable_routes_are_self_scoped_without_id_variants():
    class Schedules:
        def faculty_schedule(self,user):return {"owner":str(user["_id"]),"today":[]}
        def student_schedule(self,user):return {"owner":str(user["_id"]),"today":[]}
    app.dependency_overrides[get_timetable_service]=lambda:Schedules()
    try:
        app.dependency_overrides[get_current_user]=lambda:{"_id":FACULTY_USER,"institution_id":IID,"role":"faculty","status":"active"};client=TestClient(app);assert client.get("/api/v1/faculty/timetable").status_code==200 and client.get("/api/v1/faculty/timetable/other").status_code==404 and client.get("/api/v1/student/timetable").status_code==403
        app.dependency_overrides[get_current_user]=lambda:{"_id":STUDENT_USER,"institution_id":IID,"role":"student","status":"active"};client=TestClient(app);assert client.get("/api/v1/student/timetable").status_code==200 and client.get("/api/v1/faculty/timetable").status_code==403
    finally:app.dependency_overrides.clear()

def test_reactivation_runs_conflict_detection():
    svc,payload,_,_=domain();first=svc.create(TimetableEntryCreate(**payload),str(IID),str(ADMIN));svc.set_status(first["_id"],"inactive",str(IID),str(ADMIN));svc.create(TimetableEntryCreate(**payload),str(IID),str(ADMIN))
    with pytest.raises(AppError) as error:svc.set_status(first["_id"],"active",str(IID),str(ADMIN))
    assert error.value.code=="TIMETABLE_CONFLICT"

def test_inactive_academic_year_rejected_and_effective_dates_bound_instances():
    svc,payload,_,_=domain();svc.academics["academic-years"].repository.document["status"]="inactive"
    with pytest.raises(AppError) as error:svc.create(TimetableEntryCreate(**payload),str(IID),str(ADMIN))
    assert error.value.code=="INACTIVE_ACADEMIC_REFERENCE"
    svc,payload,_,_=domain();svc.create(TimetableEntryCreate(**{**payload,"effective_from":"2027-01-01"}),str(IID),str(ADMIN));schedule=svc.faculty_schedule({"_id":FACULTY_USER,"institution_id":IID},datetime(2026,8,11,3,45,tzinfo=timezone.utc));assert schedule["week"]==[] and schedule["nextLecture"] is None

def test_reactivation_requires_assignment_to_remain_active():
    svc,payload,_,assignment=domain();entry=svc.create(TimetableEntryCreate(**payload),str(IID),str(ADMIN));svc.set_status(entry["_id"],"inactive",str(IID),str(ADMIN));assignment["status"]="inactive"
    with pytest.raises(AppError) as error:svc.set_status(entry["_id"],"active",str(IID),str(ADMIN))
    assert error.value.code=="INVALID_FACULTY_ASSIGNMENT"

def test_conflict_api_returns_safe_structured_information():
    class Conflicting:
        def create(self,*args):raise AppError("TIMETABLE_CONFLICT","Schedule conflicts with one active timetable entry.",409,{"conflicts":[{"timetableEntryId":"safe-id","types":["faculty"],"day":"monday","startTime":"09:00","endTime":"10:00","room":"A-101"}]})
    app.dependency_overrides[get_timetable_service]=lambda:Conflicting();app.dependency_overrides[get_current_user]=lambda:{"_id":ADMIN,"institution_id":IID,"role":"admin","status":"active"}
    try:
        response=TestClient(app).post("/api/v1/admin/timetable",json={"faculty_assignment_id":str(ObjectId()),"day_of_week":"monday","start_time":"09:00","end_time":"10:00","effective_from":"2026-08-01"})
        assert response.status_code==409 and response.json()["error"]["details"]["conflicts"][0]["types"]==["faculty"]
    finally:app.dependency_overrides.clear()

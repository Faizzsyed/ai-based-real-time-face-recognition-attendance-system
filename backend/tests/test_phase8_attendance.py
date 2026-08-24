"""Phase 8 manual attendance ownership, roster, lifecycle, reporting, and API tests."""
from datetime import date,datetime,timezone
from bson import ObjectId
from fastapi.testclient import TestClient
import pytest
from app.api.attendance import get_attendance_service
from app.core.errors import AppError
from app.main import app
from app.modules.attendance.schemas import AdministrativeEdit,DraftSave,RecordMark,SessionCreate
from app.modules.attendance.service import AttendanceService
from app.modules.auth.dependencies import get_current_user

IID=ObjectId();OTHER=ObjectId();FAC_USER=ObjectId();FAC2_USER=ObjectId();STUDENT_USER=ObjectId();ADMIN=ObjectId()

class Sessions:
    def __init__(self):self.docs=[]
    def insert(self,d):d={**d,"_id":ObjectId()};self.docs.append(d);return d
    def find_by_id(self,sid,iid):return next((x for x in self.docs if str(x["_id"])==str(sid) and str(x["institution_id"])==str(iid)),None)
    def find_scheduled(self,iid,eid,day):return next((x for x in self.docs if str(x["institution_id"])==str(iid) and str(x["timetable_entry_id"])==str(eid) and x["lecture_date"].date()==day),None)
    def update(self,sid,iid,c):x=self.find_by_id(sid,iid);x.update(c);return x
    def list(self,iid,filters,page=1,size=20):
        rows=[x for x in self.docs if str(x["institution_id"])==str(iid) and all(str(x.get(k))==str(v) for k,v in filters.items())];return rows[(page-1)*size:page*size],len(rows)
    def for_faculty(self,iid,fid,status=None,limit=50):
        rows=[x for x in self.docs if str(x["institution_id"])==str(iid) and str(x["faculty_id"])==str(fid)];return [x for x in rows if not status or x["status"] in status] if isinstance(status,(list,tuple,set)) else [x for x in rows if not status or x["status"]==status]
class Records:
    def __init__(self):self.docs=[]
    def initialize_roster(self,items):
        for x in items:
            if not any(y["session_id"]==x["session_id"] and y["student_id"]==x["student_id"] for y in self.docs):self.docs.append({**x,"_id":ObjectId()})
        return self.for_session(items[0]["session_id"],items[0]["institution_id"]) if items else []
    def for_session(self,sid,iid):return [x for x in self.docs if str(x["session_id"])==str(sid) and str(x["institution_id"])==str(iid)]
    def save(self,sid,iid,items,actor,source="manual"):
        for item in items:
            row=next((x for x in self.for_session(sid,iid) if str(x["student_id"])==str(item["student_id"])),None)
            if not row:raise AppError("STUDENT_NOT_IN_SESSION_ROSTER","Not in roster",422)
            row.update({"status":item["status"],"remark":item.get("remark"),"marked_by":actor,"source":source,"marked_at":datetime.now(timezone.utc)})
        return self.for_session(sid,iid)
    def for_student(self,iid,sid,session_ids=None):return [x for x in self.docs if str(x["institution_id"])==str(iid) and str(x["student_id"])==str(sid) and (session_ids is None or str(x["session_id"]) in {str(v) for v in session_ids})]
class Roster:
    def __init__(self,rows):self.rows=rows
    def active_for_class(self,iid,year,cid,day):return [x for x in self.rows if str(x["institution_id"])==str(iid) and str(x["academic_year_id"])==str(year) and str(x["class_division_id"])==str(cid) and x["enrollment_status"]=="active" and x.get("student",{}).get("status")=="active"]
class One:
    def __init__(self,doc):self.doc=doc
    def find_by_id(self,value,iid):return self.doc if str(value)==str(self.doc["_id"]) and str(iid)==str(self.doc["institution_id"]) else None
    def find_scoped(self,value,iid):return self.find_by_id(value,iid)
    def find_by_user(self,value,iid):return self.doc if str(value)==str(self.doc.get("user_id")) and str(iid)==str(self.doc["institution_id"]) else None

def domain(roster_statuses=("active","active")):
    ids={k:ObjectId() for k in ("faculty","assignment","entry","year","class","subject","s1","s2","e1","e2")};faculty={"_id":ids["faculty"],"institution_id":IID,"user_id":FAC_USER,"status":"active"};assignment={"_id":ids["assignment"],"institution_id":IID,"faculty_id":ids["faculty"],"status":"active"};entry={"_id":ids["entry"],"institution_id":IID,"faculty_id":ids["faculty"],"faculty_assignment_id":ids["assignment"],"academic_year_id":ids["year"],"class_division_id":ids["class"],"subject_id":ids["subject"],"day_of_week":"tuesday","start_time":"09:00","end_time":"10:00","effective_from":datetime(2026,8,1,tzinfo=timezone.utc),"effective_until":None,"status":"active"}
    rows=[]
    for n,key in enumerate(("s1","s2")):
        rows.append({"_id":ids[f"e{n+1}"],"institution_id":IID,"academic_year_id":ids["year"],"class_division_id":ids["class"],"student_id":ids[key],"enrollment_status":roster_statuses[n],"roll_number":str(n+1),"student":{"display_name":f"Student {n+1}","status":"active"}})
    student={"_id":ids["s1"],"institution_id":IID,"user_id":STUDENT_USER,"status":"active"};sessions=Sessions();records=Records();service=AttendanceService(sessions,records,Roster(rows),One(entry),One(assignment),One(faculty),One(student));return service,ids,entry,assignment
def faculty_user(uid=FAC_USER,iid=IID):return {"_id":uid,"institution_id":iid,"role":"faculty"}
def start(service,ids):return service.start(SessionCreate(timetable_entry_id=str(ids["entry"]),lecture_date=date(2026,8,11)),faculty_user())

def test_session_creation_loads_only_active_roster_and_is_idempotent():
    svc,ids,_,_=domain(("active","transferred"));first=start(svc,ids);second=start(svc,ids);assert first["_id"]==second["_id"] and len(first["records"])==1 and first["status"]=="draft"
def test_unassigned_or_inactive_assignment_cannot_start():
    svc,ids,entry,assignment=domain();entry["faculty_id"]=ObjectId()
    with pytest.raises(AppError) as error:start(svc,ids)
    assert error.value.code=="UNASSIGNED_LECTURE"
    svc,ids,entry,assignment=domain();assignment["status"]="inactive"
    with pytest.raises(AppError) as error:start(svc,ids)
    assert error.value.code=="INVALID_FACULTY_ASSIGNMENT"
def test_draft_marking_persists_and_rejects_non_roster_student():
    svc,ids,_,_=domain();session=start(svc,ids);payload=DraftSave(records=[RecordMark(student_id=str(ids["s1"]),status="late"),RecordMark(student_id=str(ids["s2"]),status="excused")]);saved=svc.save(session["_id"],payload,faculty_user());assert saved["summary"]["late"]==1 and saved["summary"]["excused"]==1
    with pytest.raises(AppError):svc.save(session["_id"],DraftSave(records=[RecordMark(student_id=str(ObjectId()),status="present")]),faculty_user())
def test_submission_requires_complete_roster_then_restricts_faculty_editing():
    svc,ids,_,_=domain();session=start(svc,ids);svc.save(session["_id"],DraftSave(records=[RecordMark(student_id=str(ids["s1"]),status="present")]),faculty_user())
    with pytest.raises(AppError) as error:svc.submit(session["_id"],faculty_user())
    assert error.value.code=="INCOMPLETE_ATTENDANCE"
    svc.save(session["_id"],DraftSave(records=[RecordMark(student_id=str(ids["s2"]),status="absent")]),faculty_user());submitted=svc.submit(session["_id"],faculty_user());assert submitted["status"]=="submitted" and submitted["submitted_at"]
    with pytest.raises(AppError) as error:svc.save(session["_id"],DraftSave(records=[RecordMark(student_id=str(ids["s2"]),status="present")]),faculty_user())
    assert error.value.code=="ATTENDANCE_NOT_EDITABLE"
def test_admin_reopen_edit_and_lock_state_machine():
    svc,ids,_,_=domain();session=start(svc,ids);svc.save(session["_id"],DraftSave(records=[RecordMark(student_id=str(ids["s1"]),status="present"),RecordMark(student_id=str(ids["s2"]),status="absent")]),faculty_user());svc.submit(session["_id"],faculty_user());admin={"_id":ADMIN,"institution_id":IID,"role":"admin"};assert svc.admin_action(session["_id"],"reopen","Correction requested",admin)["status"]=="reopened";edited=svc.save(session["_id"],AdministrativeEdit(records=[RecordMark(student_id=str(ids["s2"]),status="excused")],reason="Approved medical leave"),admin,True,"Approved medical leave");assert edited["summary"]["excused"]==1;assert svc.admin_action(session["_id"],"lock","Review complete",admin)["status"]=="locked"
    with pytest.raises(AppError):svc.save(session["_id"],AdministrativeEdit(records=[RecordMark(student_id=str(ids["s1"]),status="absent")],reason="Late correction"),admin,True,"Late correction")
def test_faculty_ownership_and_tenant_isolation():
    svc,ids,_,_=domain();session=start(svc,ids)
    with pytest.raises(AppError) as error:svc.details(session["_id"],faculty_user(FAC2_USER))
    assert error.value.code in {"FACULTY_NOT_FOUND","FORBIDDEN_ATTENDANCE_SESSION"}
    with pytest.raises(AppError):svc.details(session["_id"],faculty_user(FAC_USER,OTHER))
def test_student_summary_formula_subjects_history_and_transfer_snapshot():
    svc,ids,_,_=domain();session=start(svc,ids);svc.save(session["_id"],DraftSave(records=[RecordMark(student_id=str(ids["s1"]),status="late"),RecordMark(student_id=str(ids["s2"]),status="excused")]),faculty_user());svc.submit(session["_id"],faculty_user());report=svc.student_report({"_id":STUDENT_USER,"institution_id":IID,"role":"student"});assert report["summary"]["attendancePercentage"]==100 and report["summary"]["late"]==1 and len(report["subjects"])==1 and len(report["history"])==1 and report["formula"]["excused"]=="excluded from denominator"
def test_student_can_only_read_own_record():
    svc,ids,_,_=domain();session=start(svc,ids);svc.save(session["_id"],DraftSave(records=[RecordMark(student_id=str(ids["s1"]),status="present"),RecordMark(student_id=str(ids["s2"]),status="absent")]),faculty_user());svc.submit(session["_id"],faculty_user());own=svc.student_report({"_id":STUDENT_USER,"institution_id":IID},session["_id"]);assert own["record"]["student_id"]==str(ids["s1"])
def test_attendance_routes_enforce_roles_without_id_override():
    class Stub:
        def faculty_sessions(self,*a):return []
        def student_report(self,*a):return {"summary":{},"subjects":[],"history":[],"formula":{}}
    app.dependency_overrides[get_attendance_service]=lambda:Stub()
    try:
        app.dependency_overrides[get_current_user]=lambda:{"_id":FAC_USER,"institution_id":IID,"role":"faculty"};client=TestClient(app);assert client.get("/api/v1/faculty/attendance/sessions").status_code==200 and client.get("/api/v1/student/attendance/summary").status_code==403
        app.dependency_overrides[get_current_user]=lambda:{"_id":STUDENT_USER,"institution_id":IID,"role":"student"};client=TestClient(app);assert client.get("/api/v1/student/attendance/summary").status_code==200 and client.put("/api/v1/faculty/attendance/sessions/x/draft",json={"records":[]}).status_code==403
    finally:app.dependency_overrides.clear()

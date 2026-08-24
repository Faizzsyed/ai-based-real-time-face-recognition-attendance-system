"""Phase 6 Faculty identity, assignment, import, tenant, and RBAC coverage."""
from types import SimpleNamespace
from bson import ObjectId
from fastapi.testclient import TestClient
import pytest
from app.api.faculty import get_faculty_service,validate_rows
from app.core.errors import AppError
from app.main import app
from app.modules.auth.dependencies import get_current_user
from app.modules.faculty.schemas import AssignmentCreate,AssignmentUpdate,FacultyCreate,FacultyStatusUpdate,FacultyUpdate
from app.modules.faculty.service import FacultyService
from app.db.mongo import mongo
from tests.test_phase5_students import AcademicRepo,MemoryUsers,Passwords

IID=ObjectId();OTHER=ObjectId();ADMIN=ObjectId()
class FacultyMemory:
    def __init__(self):self.docs=[]
    def insert(self,d):d={**d,"_id":ObjectId()};self.docs.append(d);return d
    def find_by_id(self,fid,iid):return next((d for d in self.docs if str(d["_id"])==str(fid) and str(d["institution_id"])==str(iid)),None)
    def find_by_user(self,uid,iid):return next((d for d in self.docs if str(d["user_id"])==str(uid) and str(d["institution_id"])==str(iid)),None)
    def find_by_employee(self,iid,eid):return next((d for d in self.docs if str(d["institution_id"])==str(iid) and d["employee_id"]==eid),None)
    def update(self,fid,iid,c):d=self.find_by_id(fid,iid);d.update(c);return d
    def delete_created(self,fid):self.docs=[d for d in self.docs if d["_id"]!=fid]
    def list(self,iid,filters,search,page,size):
        rows=[{**d,"account":None} for d in self.docs if str(d["institution_id"])==str(iid) and (not filters.get("status") or d["status"]==filters["status"]) and (not filters.get("department_id") or str(d["department_id"])==filters["department_id"]) and (not search or search.casefold() in (d["display_name"]+d["employee_id"]+d["email"]).casefold())]
        return rows[(page-1)*size:page*size],len(rows)
class AssignmentsMemory:
    def __init__(self):self.docs=[];self.fail=False
    def insert(self,d):
        if self.fail:raise RuntimeError("assignment write failed")
        d={**d,"_id":ObjectId()};self.docs.append(d);return d
    def find_by_id(self,aid,fid,iid):return next((d for d in self.docs if str(d["_id"])==str(aid) and str(d["faculty_id"])==str(fid) and str(d["institution_id"])==str(iid)),None)
    def duplicate_active(self,iid,fid,y,s,c,k,exclude=None):return any(str(d["institution_id"])==str(iid) and str(d["faculty_id"])==str(fid) and str(d["academic_year_id"])==str(y) and str(d["subject_id"])==str(s) and str(d["class_division_id"])==str(c) and d["assignment_type"]==k and d["status"]=="active" and str(d["_id"])!=str(exclude) for d in self.docs)
    def list_for_faculty(self,fid,iid,status=None):return [d for d in self.docs if str(d["faculty_id"])==str(fid) and str(d["institution_id"])==str(iid) and (not status or d["status"]==status)]
    def update(self,aid,fid,iid,c):d=self.find_by_id(aid,fid,iid);d.update(c);return d
    def delete_created(self,aid):self.docs=[d for d in self.docs if d["_id"]!=aid]
    def deactivate_for_faculty(self,fid,iid):
        for d in self.list_for_faculty(fid,iid,"active"):d["status"]="inactive"

def domain():
    ids={x:ObjectId() for x in ("year","department","program","semester","class","subject")}
    docs={"academic-years":{"_id":ids["year"],"institution_id":IID,"status":"active","name":"2026-2027"},"departments":{"_id":ids["department"],"institution_id":IID,"status":"active","code":"CSE"},"programs":{"_id":ids["program"],"institution_id":IID,"status":"active","department_id":ids["department"]},"semesters":{"_id":ids["semester"],"institution_id":IID,"status":"active","program_id":ids["program"],"academic_year_id":ids["year"]},"classes":{"_id":ids["class"],"institution_id":IID,"status":"active","academic_year_id":ids["year"],"department_id":ids["department"],"program_id":ids["program"],"semester_id":ids["semester"]},"subjects":{"_id":ids["subject"],"institution_id":IID,"status":"active","department_id":ids["department"],"program_id":ids["program"],"semester_id":ids["semester"]}}
    academics={k:SimpleNamespace(repository=AcademicRepo(v)) for k,v in docs.items()};svc=FacultyService(FacultyMemory(),AssignmentsMemory(),MemoryUsers(),academics,Passwords())
    assignment={"academic_year_id":str(ids["year"]),"subject_id":str(ids["subject"]),"class_division_id":str(ids["class"]),"assignment_type":"primary"}
    payload={"display_name":"Ada Faculty","employee_id":"EMP-1","email":"ada.faculty@example.test","username":"ada.faculty","temporary_password":"Secret123!","department_id":str(ids["department"])}
    return svc,payload,assignment,ids

def test_create_links_faculty_user_and_hashes_password():
    svc,payload,_,_=domain();result=svc.create(FacultyCreate(**payload),str(IID),str(ADMIN));assert result["account"]["username"]=="ada.faculty" and svc.users.docs[0]["role"]=="faculty" and svc.users.docs[0]["password_hash"]=="argon2-test-hash" and "temporary_password" not in svc.faculty.docs[0]
def test_duplicate_employee_username_and_email_rejected():
    svc,payload,_,_=domain();svc.create(FacultyCreate(**payload),str(IID),str(ADMIN))
    with pytest.raises(AppError) as e:svc.create(FacultyCreate(**{**payload,"email":"x@example.test","username":"xx"}),str(IID),str(ADMIN))
    assert e.value.code=="DUPLICATE_EMPLOYEE_ID"
    with pytest.raises(AppError) as email:svc.create(FacultyCreate(**{**payload,"employee_id":"EMP-2","username":"different"}),str(IID),str(ADMIN))
    assert email.value.code=="USER_EMAIL_ALREADY_EXISTS"
    with pytest.raises(AppError) as username:svc.create(FacultyCreate(**{**payload,"employee_id":"EMP-3","email":"different@example.test"}),str(IID),str(ADMIN))
    assert username.value.code=="USER_USERNAME_ALREADY_EXISTS"
def test_cross_tenant_faculty_is_not_found():
    svc,payload,_,_=domain();result=svc.create(FacultyCreate(**payload),str(IID),str(ADMIN))
    with pytest.raises(AppError) as e:svc.get(result["_id"],str(OTHER))
    assert e.value.code=="FACULTY_NOT_FOUND"
def test_assignment_creation_and_duplicate_protection():
    svc,payload,assignment,_=domain();result=svc.create(FacultyCreate(**payload),str(IID),str(ADMIN));svc.create_assignment(result["_id"],AssignmentCreate(**assignment),str(IID),str(ADMIN))
    with pytest.raises(AppError) as e:svc.create_assignment(result["_id"],AssignmentCreate(**assignment),str(IID),str(ADMIN))
    assert e.value.code=="DUPLICATE_FACULTY_ASSIGNMENT"
def test_assignment_rejects_cross_tenant_reference():
    svc,payload,assignment,ids=domain();result=svc.create(FacultyCreate(**payload),str(IID),str(ADMIN));svc.academics["subjects"].repository.document["institution_id"]=OTHER
    with pytest.raises(AppError) as e:svc.create_assignment(result["_id"],AssignmentCreate(**assignment),str(IID),str(ADMIN))
    assert e.value.code=="CROSS_INSTITUTION_REFERENCE"
def test_assignment_rejects_unrelated_subject_hierarchy():
    svc,payload,assignment,_=domain();result=svc.create(FacultyCreate(**payload),str(IID),str(ADMIN));svc.academics["subjects"].repository.document["program_id"]=ObjectId()
    with pytest.raises(AppError) as e:svc.create_assignment(result["_id"],AssignmentCreate(**assignment),str(IID),str(ADMIN))
    assert e.value.code=="INVALID_FACULTY_ASSIGNMENT"
def test_optional_assignment_failure_compensates_faculty_and_user():
    svc,payload,assignment,_=domain();svc.assignments.fail=True
    with pytest.raises(RuntimeError):svc.create(FacultyCreate(**{**payload,"assignments":[assignment]}),str(IID),str(ADMIN))
    assert svc.faculty.docs==[] and svc.users.docs==[]
def test_status_disables_account_and_assignments():
    svc,payload,assignment,_=domain();result=svc.create(FacultyCreate(**{**payload,"assignments":[assignment]}),str(IID),str(ADMIN));changed=svc.set_status(result["_id"],FacultyStatusUpdate(status="inactive"),str(IID),str(ADMIN));assert changed["account"]["status"]=="inactive" and changed["assignments"][0]["status"]=="inactive" and svc.users.docs[0]["token_version"]==1
def test_profile_edit_does_not_change_assignments():
    svc,payload,assignment,_=domain();result=svc.create(FacultyCreate(**{**payload,"assignments":[assignment]}),str(IID),str(ADMIN));svc.update(result["_id"],FacultyUpdate(phone="123"),str(IID),str(ADMIN));assert len(svc.assignments.docs)==1
def test_faculty_self_profile_and_own_assignments():
    svc,payload,assignment,_=domain();svc.create(FacultyCreate(**{**payload,"assignments":[assignment]}),str(IID),str(ADMIN));user=svc.users.docs[0];assert svc.self_profile(user)["employee_id"]=="EMP-1" and len(svc.own_assignments(user))==1
def test_pagination_search_and_department_filter():
    svc,payload,_,ids=domain();svc.create(FacultyCreate(**payload),str(IID),str(ADMIN));listed=svc.list(str(IID),{"department_id":str(ids["department"])},"Ada",1,20);assert listed["pagination"]["total"]==1
def test_csv_preview_resolves_department_and_has_no_writes():
    svc,_,_,_=domain();row={"employee_id":"EMP-2","name":"Grace Faculty","email":"grace@example.test","username":"grace","phone":"","department_code":"CSE","designation":"Professor","temporary_password":"Secret123!"};report=validate_rows([row],svc,str(IID));assert report[0]["valid"] and not svc.faculty.docs
def test_admin_faculty_api_is_role_restricted():
    class Listing:
        def list(self,*a):return {"items":[],"pagination":{"page":1,"pageSize":20,"total":0,"pages":0}}
    app.dependency_overrides[get_faculty_service]=lambda:Listing()
    try:
        for role in ("faculty","student"):
            app.dependency_overrides[get_current_user]=lambda role=role:{"_id":ObjectId(),"institution_id":IID,"role":role,"status":"active"};assert TestClient(app).get("/api/v1/admin/faculty").status_code==403
        app.dependency_overrides[get_current_user]=lambda:{"_id":ADMIN,"institution_id":IID,"role":"admin","status":"active"};assert TestClient(app).get("/api/v1/admin/faculty").status_code==200
    finally:app.dependency_overrides.clear()
def test_faculty_self_api_has_no_arbitrary_id_route():
    class Own:
        def self_profile(self,u):return {"_id":"own"}
    app.dependency_overrides[get_faculty_service]=lambda:Own();app.dependency_overrides[get_current_user]=lambda:{"_id":ObjectId(),"institution_id":IID,"role":"faculty","status":"active"}
    try:
        client=TestClient(app);assert client.get("/api/v1/faculty/profile").status_code==200 and client.get("/api/v1/faculty/profile/other").status_code==404
    finally:app.dependency_overrides.clear()
def test_confirmed_csv_import_creates_faculty_only_after_confirmation():
    svc,_,_,_=domain();app.dependency_overrides[get_faculty_service]=lambda:svc;app.dependency_overrides[get_current_user]=lambda:{"_id":ADMIN,"institution_id":IID,"role":"admin","status":"active"}
    csv_data="employee_id,name,email,username,phone,department_code,designation,temporary_password\nEMP-9,CSV Faculty,csv@example.test,csv.faculty,,CSE,Professor,Secret123!\n"
    try:
        client=TestClient(app);preview=client.post("/api/v1/admin/faculty/import/preview",files={"file":("faculty.csv",csv_data,"text/csv")});assert preview.status_code==200 and svc.faculty.docs==[]
        confirmed=client.post("/api/v1/admin/faculty/import/confirm?confirm=true",files={"file":("faculty.csv",csv_data,"text/csv")});assert confirmed.status_code==200 and len(svc.faculty.docs)==1
    finally:app.dependency_overrides.clear()

def test_inactive_faculty_cannot_receive_new_assignment():
    svc,payload,assignment,_=domain();result=svc.create(FacultyCreate(**payload),str(IID),str(ADMIN));svc.set_status(result["_id"],FacultyStatusUpdate(status="inactive"),str(IID),str(ADMIN))
    with pytest.raises(AppError) as error:svc.create_assignment(result["_id"],AssignmentCreate(**assignment),str(IID),str(ADMIN))
    assert error.value.code=="FACULTY_INACTIVE"

def test_department_change_rejected_while_active_assignments_exist():
    svc,payload,assignment,_=domain();result=svc.create(FacultyCreate(**{**payload,"assignments":[assignment]}),str(IID),str(ADMIN));new_department=ObjectId();svc.academics["departments"].repository.document={"_id":new_department,"institution_id":IID,"status":"active","code":"ECE"}
    with pytest.raises(AppError) as error:svc.update(result["_id"],FacultyUpdate(department_id=str(new_department)),str(IID),str(ADMIN))
    assert error.value.code=="ACTIVE_ASSIGNMENTS_CONFLICT"

def test_client_cannot_supply_institution_id_on_create():
    svc,payload,_,_=domain();app.dependency_overrides[get_faculty_service]=lambda:svc;app.dependency_overrides[get_current_user]=lambda:{"_id":ADMIN,"institution_id":IID,"role":"admin","status":"active"}
    try:
        response=TestClient(app).post("/api/v1/admin/faculty",json={**payload,"institution_id":str(OTHER)})
        assert response.status_code==422 and svc.faculty.docs==[]
    finally:app.dependency_overrides.clear()

def test_faculty_repository_reports_database_unavailable_when_unconfigured(monkeypatch):
    monkeypatch.setattr(mongo,"status","not_configured");monkeypatch.setattr(mongo,"database",None)
    with pytest.raises(AppError) as error:FacultyService().list(str(IID),{},None,1,20)
    assert error.value.code=="DATABASE_UNAVAILABLE" and error.value.status_code==503

def test_assignment_delete_is_safe_deactivation_not_removal():
    svc,payload,assignment,_=domain();faculty=svc.create(FacultyCreate(**payload),str(IID),str(ADMIN));created=svc.create_assignment(faculty["_id"],AssignmentCreate(**assignment),str(IID),str(ADMIN));result=svc.deactivate_assignment(faculty["_id"],created["_id"],str(IID),str(ADMIN))
    assert result["status"]=="inactive" and len(svc.assignments.docs)==1

def test_assignment_update_rejects_invalid_date_range():
    svc,payload,assignment,_=domain();faculty=svc.create(FacultyCreate(**payload),str(IID),str(ADMIN));created=svc.create_assignment(faculty["_id"],AssignmentCreate(**assignment),str(IID),str(ADMIN))
    with pytest.raises(AppError) as error:svc.update_assignment(faculty["_id"],created["_id"],AssignmentUpdate(start_date="2026-08-10",end_date="2026-08-01"),str(IID),str(ADMIN))
    assert error.value.code=="INVALID_ASSIGNMENT_DATES"

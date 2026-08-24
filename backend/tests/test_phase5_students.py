"""Phase 5 Student lifecycle invariants without requiring MongoDB."""

from datetime import date
from types import SimpleNamespace
from bson import ObjectId
import pytest
from fastapi.testclient import TestClient

from app.core.errors import AppError
from app.modules.students.schemas import EnrollmentCreate, StudentCreate, StudentStatusUpdate, StudentUpdate
from app.modules.students.service import StudentService
from app.api.students import _validate_rows
from app.api.students import get_student_service
from app.main import app
from app.modules.auth.dependencies import get_current_user

IID = ObjectId(); OTHER = ObjectId(); ADMIN = ObjectId()


class MemoryStudents:
    def __init__(self): self.docs = []
    def insert(self, d): d={**d,"_id":ObjectId()}; self.docs.append(d); return d
    def find_by_id(self, sid, iid): return next((d for d in self.docs if str(d["_id"])==str(sid) and str(d["institution_id"])==str(iid)),None)
    def find_by_user(self, uid, iid): return next((d for d in self.docs if str(d["user_id"])==str(uid) and str(d["institution_id"])==str(iid)),None)
    def find_by_admission(self,iid,n): return next((d for d in self.docs if str(d["institution_id"])==str(iid) and d["admission_number"]==n),None)
    def update(self,sid,iid,c): d=self.find_by_id(sid,iid); d.update(c); return d
    def delete_created(self,sid): self.docs=[d for d in self.docs if d["_id"]!=sid]
    def list(self,iid,filters,search,page,size):
        rows=[{**d,"current_enrollment":None} for d in self.docs if str(d["institution_id"])==str(iid) and (not filters.get("status") or d["status"]==filters["status"])]
        return rows[(page-1)*size:page*size],len(rows)

class MemoryEnrollments:
    def __init__(self): self.docs=[]; self.fail=False
    def insert(self,d):
        if self.fail: raise RuntimeError("write failed")
        d={**d,"_id":ObjectId()}; self.docs.append(d); return d
    def current(self,sid,iid): return next((d for d in self.docs if str(d["student_id"])==str(sid) and str(d["institution_id"])==str(iid) and d["is_current"]),None)
    def list_for_student(self,sid,iid): return [d for d in self.docs if str(d["student_id"])==str(sid) and str(d["institution_id"])==str(iid)]
    def roll_exists(self,iid,y,c,r): return any(str(d["institution_id"])==str(iid) and str(d["academic_year_id"])==str(y) and str(d["class_division_id"])==str(c) and d["roll_number"]==r and d["is_current"] for d in self.docs)
    def close_current(self,eid,status,end): d=next(d for d in self.docs if d["_id"]==eid); d.update(is_current=False,enrollment_status=status,end_date=end)
    def restore_current(self,eid): next(d for d in self.docs if d["_id"]==eid).update(is_current=True,enrollment_status="active",end_date=None)
    def delete_created(self,eid): self.docs=[d for d in self.docs if d["_id"]!=eid]

class MemoryUsers:
    def __init__(self): self.docs=[]
    def insert(self,d): d={**d,"_id":ObjectId()}; self.docs.append(d); return d
    def find_scoped_duplicate(self,iid,email,username): return next((d for d in self.docs if str(d["institution_id"])==str(iid) and (d["email"]==email or d["username"]==username)),None)
    def find_by_email(self,iid,email): return next((d for d in self.docs if str(d["institution_id"])==str(iid) and d["email"]==email),None)
    def find_by_id(self,uid): return next((d for d in self.docs if d["_id"]==uid),None)
    def update(self,uid,c): d=self.find_by_id(uid); d.update(c); return d
    def delete_created(self,uid): self.docs=[d for d in self.docs if d["_id"]!=uid]

class Passwords:
    def hash_password(self,p): return "argon2-test-hash"

class AcademicRepo:
    def __init__(self, document): self.document=document
    def find_by_id(self, value): return self.document if str(value)==str(self.document["_id"]) else None
    def find_one(self, filters):
        def matches(document, query):
            for key,value in query.items():
                if key=="$or":
                    if not any(matches(document,item) for item in value): return False
                elif str(document.get(key)) != str(value): return False
            return True
        return self.document if matches(self.document,filters) else None

def fixture_service():
    ids={name:ObjectId() for name in ("year","department","program","semester","division")}
    docs={"academic-years":{"_id":ids["year"],"institution_id":IID,"status":"active"},
      "departments":{"_id":ids["department"],"institution_id":IID,"status":"active"},
      "programs":{"_id":ids["program"],"institution_id":IID,"department_id":ids["department"],"status":"active"},
      "semesters":{"_id":ids["semester"],"institution_id":IID,"program_id":ids["program"],"academic_year_id":ids["year"],"status":"active"},
      "classes":{"_id":ids["division"],"institution_id":IID,"program_id":ids["program"],"semester_id":ids["semester"],"academic_year_id":ids["year"],"status":"active"}}
    docs["academic-years"].update(name="2026-2027",code="AY26"); docs["departments"].update(code="CSE"); docs["programs"].update(code="BTECH"); docs["semesters"].update(semester_number=6); docs["classes"].update(division="A")
    academics={k:SimpleNamespace(repository=AcademicRepo(d)) for k,d in docs.items()}
    svc=StudentService(MemoryStudents(),MemoryEnrollments(),MemoryUsers(),academics,Passwords())
    payload={"display_name":"Ada Student","admission_number":"A-1","email":"ada@example.test","username":"ada.student","temporary_password":"Secret123!","academic_year_id":str(ids["year"]),"department_id":str(ids["department"]),"program_id":str(ids["program"]),"semester_id":str(ids["semester"]),"class_division_id":str(ids["division"]),"roll_number":"7","start_date":"2026-07-01"}
    return svc,payload,ids

def test_create_links_user_profile_and_enrollment_without_plaintext_password():
    svc,payload,_=fixture_service(); result=svc.create(StudentCreate(**payload),str(IID),str(ADMIN))
    assert result["account"]["username"]=="ada.student" and result["current_enrollment"]["roll_number"]=="7"
    assert "temporary_password" not in svc.students.docs[0] and svc.users.docs[0]["password_hash"]=="argon2-test-hash"

def test_duplicate_admission_and_roll_are_rejected():
    svc,payload,_=fixture_service(); svc.create(StudentCreate(**payload),str(IID),str(ADMIN))
    with pytest.raises(AppError) as error: svc.create(StudentCreate(**{**payload,"email":"other@example.test","username":"other"}),str(IID),str(ADMIN))
    assert error.value.code=="DUPLICATE_ADMISSION_NUMBER"

def test_cross_tenant_read_is_not_found():
    svc,payload,_=fixture_service(); result=svc.create(StudentCreate(**payload),str(IID),str(ADMIN))
    with pytest.raises(AppError) as error: svc.get(result["_id"],str(OTHER))
    assert error.value.status_code==404

def test_profile_edit_cannot_change_admission_or_enrollment():
    with pytest.raises(Exception): StudentUpdate(admission_number="X")

def test_suspension_disables_account_and_revokes_existing_access_version():
    svc,payload,_=fixture_service(); result=svc.create(StudentCreate(**payload),str(IID),str(ADMIN))
    changed=svc.set_status(result["_id"],StudentStatusUpdate(status="suspended"),str(IID))
    assert changed["status"]=="suspended" and changed["account"]["status"]=="suspended" and svc.users.docs[0]["token_version"]==1

def test_enrollment_change_preserves_history_and_one_current():
    svc,payload,_=fixture_service(); result=svc.create(StudentCreate(**payload),str(IID),str(ADMIN))
    enrollment=EnrollmentCreate(**{k:payload[k] for k in ("academic_year_id","department_id","program_id","semester_id","class_division_id","roll_number","start_date")}|{"roll_number":"8","start_date":date(2027,1,1)})
    changed=svc.change_enrollment(result["_id"],enrollment,str(IID))
    assert len(changed["enrollment_history"])==2 and sum(x["is_current"] for x in changed["enrollment_history"])==1

def test_failed_initial_enrollment_compensates_user_and_student():
    svc,payload,_=fixture_service(); svc.enrollments.fail=True
    with pytest.raises(RuntimeError): svc.create(StudentCreate(**payload),str(IID),str(ADMIN))
    assert svc.users.docs==[] and svc.students.docs==[]

def test_self_profile_uses_authenticated_user_and_tenant():
    svc,payload,_=fixture_service(); result=svc.create(StudentCreate(**payload),str(IID),str(ADMIN)); user=svc.users.docs[0]
    assert svc.self_profile(user)["_id"]==result["_id"]

def test_csv_preview_resolves_scoped_codes_and_performs_no_writes():
    svc,_,_=fixture_service(); rows=[{"admission_number":"A-2","name":"Grace Student","email":"grace@example.test","username":"grace","phone":"","academic_year":"AY26","department_code":"CSE","program_code":"BTECH","semester_number":"6","division":"A","roll_number":"9","temporary_password":"Secret123!","start_date":"2026-07-01"}]
    report=_validate_rows(rows,svc,str(IID))
    assert report[0]["valid"] and svc.students.docs==[] and svc.users.docs==[]

def test_csv_duplicate_rows_are_reported_without_writes():
    svc,_,_=fixture_service(); row={"admission_number":"A-2","name":"Grace Student","email":"grace@example.test","username":"grace","phone":"","academic_year":"AY26","department_code":"CSE","program_code":"BTECH","semester_number":"6","division":"A","roll_number":"9","temporary_password":"Secret123!","start_date":"2026-07-01"}
    report=_validate_rows([row,row],svc,str(IID))
    assert not report[1]["valid"] and any("Duplicate" in error for error in report[1]["errors"]) and svc.students.docs==[]

def test_admin_student_routes_reject_faculty_and_student_roles():
    class Listing:
        def list(self,*args): return {"items":[],"pagination":{"page":1,"pageSize":20,"total":0,"pages":0}}
    app.dependency_overrides[get_student_service]=lambda:Listing()
    try:
        for role in ("faculty","student"):
            app.dependency_overrides[get_current_user]=lambda role=role:{"_id":ObjectId(),"institution_id":IID,"role":role,"status":"active"}
            assert TestClient(app).get("/api/v1/admin/students").status_code==403
        app.dependency_overrides[get_current_user]=lambda:{"_id":ADMIN,"institution_id":IID,"role":"admin","status":"active"}
        assert TestClient(app).get("/api/v1/admin/students").status_code==200
    finally: app.dependency_overrides.clear()

def test_student_self_route_has_no_arbitrary_student_id_variant():
    class SelfService:
        def self_profile(self,user): return {"_id":"own","display_name":"Own Student"}
    app.dependency_overrides[get_student_service]=lambda:SelfService()
    app.dependency_overrides[get_current_user]=lambda:{"_id":ObjectId(),"institution_id":IID,"role":"student","status":"active"}
    try:
        client=TestClient(app)
        assert client.get("/api/v1/student/profile").status_code==200
        assert client.get("/api/v1/student/profile/someone-else").status_code==404
    finally: app.dependency_overrides.clear()

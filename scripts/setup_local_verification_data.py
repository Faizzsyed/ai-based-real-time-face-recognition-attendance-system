"""Idempotently create the approved local Phase 10 verification dataset."""
from __future__ import annotations
import getpass,sys
from datetime import date,datetime,timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/"backend"))
from app.db.mongo import mongo
from app.modules.academic_common.services import build_services
from app.modules.academic_years.schemas import AcademicYearCreate
from app.modules.departments.schemas import DepartmentCreate
from app.modules.programs.schemas import ProgramCreate
from app.modules.semesters.schemas import SemesterCreate
from app.modules.class_divisions.schemas import ClassDivisionCreate
from app.modules.subjects.schemas import SubjectCreate
from app.modules.students.schemas import StudentCreate
from app.modules.students.service import StudentService
from app.modules.faculty.schemas import AssignmentCreate,FacultyCreate
from app.modules.faculty.service import FacultyService
from app.modules.timetable.schemas import TimetableEntryCreate
from app.modules.timetable.service import TimetableService

def password(label):
    first=getpass.getpass(f"{label} temporary password (minimum 8 characters): ");second=getpass.getpass("Confirm: ")
    if first!=second or len(first)<8:raise ValueError("Passwords did not match or were too short.")
    return first
def main():
    mongo.configure();db=mongo.require_database()
    if mongo.database_name!="attendai_python_dev":raise SystemExit("Refusing non-approved database.")
    inst=db.institutions.find_one({"code":"ADI"});admin=db.users.find_one({"institution_id":inst["_id"],"role":"admin"}) if inst else None
    if not inst or not admin:raise SystemExit("Approved Institution/Admin not found.")
    iid,actor=str(inst["_id"]),str(admin["_id"]);services=build_services()
    def ensure(resource,query,model):
        found=services[resource].repository.find_one({"institution_id":iid,**query})
        return found or services[resource].repository.find_by_id(services[resource].create(model,actor)["_id"])
    year=ensure("academic-years",{"name":"2026-2027"},AcademicYearCreate(institution_id=iid,name="2026-2027",start_date=date(2026,7,1),end_date=date(2027,6,30),is_current=True))
    dept=ensure("departments",{"code":"ECS"},DepartmentCreate(institution_id=iid,name="Electronics and Computer Science",code="ECS"))
    program=ensure("programs",{"department_id":dept["_id"],"code":"BE_ECS"},ProgramCreate(institution_id=iid,department_id=str(dept["_id"]),name="BE ECS",code="BE_ECS",degree_type="Bachelor of Engineering",duration_years=4,total_semesters=8))
    semester=ensure("semesters",{"program_id":program["_id"],"academic_year_id":year["_id"],"semester_number":8},SemesterCreate(institution_id=iid,academic_year_id=str(year["_id"]),program_id=str(program["_id"]),semester_number=8,label="Semester 8",start_date=date(2026,7,1),end_date=date(2026,12,31)))
    division=ensure("classes",{"academic_year_id":year["_id"],"program_id":program["_id"],"semester_id":semester["_id"],"division":"A"},ClassDivisionCreate(institution_id=iid,academic_year_id=str(year["_id"]),department_id=str(dept["_id"]),program_id=str(program["_id"]),semester_id=str(semester["_id"]),name="Division A",division="A",room="LAB A",capacity=60))
    subject=ensure("subjects",{"program_id":program["_id"],"semester_id":semester["_id"],"code":"MP1"},SubjectCreate(institution_id=iid,department_id=str(dept["_id"]),program_id=str(program["_id"]),semester_id=str(semester["_id"]),name="Major Project - I",code="MP1",subject_type="project",credits=4,weekly_hours=4))
    student_service=StudentService()
    for number,name in ((1,"Test Student One"),(2,"Test Student Two")):
        admission=f"ADI_TEST_{number:02d}"
        if not db.students.find_one({"institution_id":inst["_id"],"admission_number":admission}):
            secret=password(name)
            student_service.create(StudentCreate(display_name=name,admission_number=admission,email=f"test.student{number}@attendai.local",username=f"test.student{number}",temporary_password=secret,academic_year_id=str(year["_id"]),department_id=str(dept["_id"]),program_id=str(program["_id"]),semester_id=str(semester["_id"]),class_division_id=str(division["_id"]),roll_number=str(number),start_date=date(2026,7,1)),iid,actor);del secret
    faculty_service=FacultyService();faculty=db.faculty.find_one({"institution_id":inst["_id"],"employee_id":"ADI_TEST_F01"})
    if not faculty:
        secret=password("Test Faculty")
        created=faculty_service.create(FacultyCreate(display_name="Test Faculty",employee_id="ADI_TEST_F01",email="test.faculty@attendai.local",username="test.faculty",temporary_password=secret,department_id=str(dept["_id"]),designation="Development Test Faculty"),iid,actor);del secret;faculty=db.faculty.find_one({"_id":__import__('bson').ObjectId(created["_id"])})
    assignment=db.faculty_assignments.find_one({"institution_id":inst["_id"],"faculty_id":faculty["_id"],"academic_year_id":year["_id"],"subject_id":subject["_id"],"class_division_id":division["_id"],"status":"active"})
    if not assignment:
        made=faculty_service.create_assignment(str(faculty["_id"]),AssignmentCreate(academic_year_id=str(year["_id"]),subject_id=str(subject["_id"]),class_division_id=str(division["_id"]),assignment_type="primary",start_date=date(2026,7,1)),iid,actor);assignment=db.faculty_assignments.find_one({"_id":__import__('bson').ObjectId(made["_id"])})
    local=datetime.now(ZoneInfo("Asia/Kolkata"));start=(local+timedelta(minutes=15)).replace(second=0,microsecond=0);end=start+timedelta(hours=1)
    entry=db.timetable_entries.find_one({"institution_id":inst["_id"],"faculty_assignment_id":assignment["_id"],"day_of_week":local.strftime("%A").casefold(),"status":"active"})
    if not entry:TimetableService().create(TimetableEntryCreate(faculty_assignment_id=str(assignment["_id"]),day_of_week=local.strftime("%A").casefold(),start_time=start.time(),end_time=end.time(),room="LAB A",lecture_type="project",effective_from=date(2026,7,1),effective_until=date(2027,6,30)),iid,actor)
    print("LOCAL VERIFICATION DATA SETUP: PASS");print("ACADEMIC HIERARCHY: PASS");print("TEST STUDENTS: 2");print("TEST FACULTY/ASSIGNMENT/TIMETABLE: PASS");print("PASSWORDS DISPLAYED: NO")
    mongo.close()
if __name__=="__main__":raise SystemExit(main())

"""Exercise guided suggestions against real scoped API/service contracts in memory."""
from datetime import date
import importlib.util
from pathlib import Path

import pytest

from tests.test_phase4_admin_academic import phase4_domain, client_as, clear_overrides, post


def frontend_defaults():
    # The backend and frontend intentionally use different `app` packages.
    # Load this dependency-free module explicitly without altering either package.
    path=Path(__file__).resolve().parents[2]/"app"/"services"/"setup_defaults.py"
    spec=importlib.util.spec_from_file_location("guided_defaults",path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def test_guided_defaults_and_semester_plans_use_real_scoped_api_contracts(phase4_domain):
    repos,services,institution,_,users=phase4_domain
    defaults=frontend_defaults()
    try:
        with client_as(services,users["admin_a"]) as client:
            year=post(client,"academic-years",defaults.academic_year_suggestion(date(2026,10,18)))
            department=post(client,"departments",{"name":"Electronics and Computer Science","code":"ECS"})
            program=post(client,"programs",{**defaults.program_suggestion("ECS"),"department_id":department["_id"]})
            plan=defaults.semester_payloads(program["_id"],year["_id"],8,[],demo=True)
            assert len(plan)==1
            semester=post(client,"semesters",plan[0])
            division=post(client,"classes",{"academic_year_id":year["_id"],"department_id":department["_id"],"program_id":program["_id"],"semester_id":semester["_id"],"division":"A","name":defaults.class_name_suggestion("ECS"),"capacity":60})
            subject=post(client,"subjects",{"department_id":department["_id"],"program_id":program["_id"],"semester_id":semester["_id"],"name":"Programming Fundamentals","code":"ECS101","subject_type":"theory"})
            remaining=defaults.semester_payloads(program["_id"],year["_id"],8,[semester],demo=False)
            assert len(remaining)==7
            for payload in remaining:post(client,"semesters",payload)
            listed=client.get("/api/v1/admin/academic/semesters").json()["items"]
            assert not defaults.semester_payloads(program["_id"],year["_id"],8,listed,demo=False)
            assert client.get("/api/v1/admin/academic/setup-status").json()["state"]=="Ready"
            assert all(x["institution_id"]==str(institution["_id"]) for x in (year,department,program,semester,division,subject))
            # Backend constraints remain the final duplicate barrier, even across concurrent clients.
            assert client.post("/api/v1/admin/academic/semesters",json=plan[0]).status_code==409
            assert len(repos["semesters"].documents)==8
    finally:clear_overrides()


@pytest.mark.parametrize("role",["faculty","student"])
def test_every_guided_write_is_admin_only(phase4_domain,role):
    _,services,_,_,users=phase4_domain
    try:
        with client_as(services,users[role]) as client:
            for resource in ("academic-years","departments","programs","semesters","classes","subjects"):
                assert client.post(f"/api/v1/admin/academic/{resource}",json={}).status_code==403
            # Send valid-shaped identity bodies so denial tests authentication rather than validation.
            faculty={"display_name":"Faculty One","employee_id":"FAC001","email":"faculty@example.test","username":"faculty","temporary_password":"Secret123!","department_id":"000000000000000000000001"}
            student={"display_name":"Student One","admission_number":"ADM001","email":"student@example.test","username":"student","temporary_password":"Secret123!","academic_year_id":"000000000000000000000001","department_id":"000000000000000000000002","program_id":"000000000000000000000003","semester_id":"000000000000000000000004","class_division_id":"000000000000000000000005","roll_number":"1","start_date":"2026-10-18"}
            assert client.post("/api/v1/admin/faculty",json=faculty).status_code==403
            assert client.post("/api/v1/admin/students",json=student).status_code==403
            assignment={"academic_year_id":student["academic_year_id"],"class_division_id":student["class_division_id"],"subject_id":"000000000000000000000006"}
            assert client.post("/api/v1/admin/faculty/000000000000000000000007/assignments",json=assignment).status_code==403
            assert client.post("/api/v1/admin/timetable",json={"faculty_assignment_id":"000000000000000000000008","day_of_week":"monday","start_time":"10:00","end_time":"11:00","effective_from":"2026-06-01"}).status_code==403
    finally:clear_overrides()

"""Explicit, idempotent Phase 2 DEMO hierarchy seed. Never runs automatically."""

import argparse
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import get_settings  # noqa: E402
from app.db.mongo import mongo  # noqa: E402
from app.modules.academic_common.services import build_services  # noqa: E402
from app.modules.academic_years.schemas import AcademicYearCreate  # noqa: E402
from app.modules.class_divisions.schemas import ClassDivisionCreate  # noqa: E402
from app.modules.departments.schemas import DepartmentCreate  # noqa: E402
from app.modules.institutions.schemas import InstitutionCreate  # noqa: E402
from app.modules.programs.schemas import ProgramCreate  # noqa: E402
from app.modules.semesters.schemas import SemesterCreate  # noqa: E402
from app.modules.subjects.schemas import SubjectCreate  # noqa: E402

CONFIRMATION = "SEED_PHASE2_DEMO"


def parse_args():
    parser = argparse.ArgumentParser(description="Seed the configured AttendAI Python development database with DEMO Phase 2 data.")
    parser.add_argument("--confirm", required=True, help=f"Must equal {CONFIRMATION}")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = get_settings()
    if args.confirm != CONFIRMATION:
        raise SystemExit("Confirmation text did not match; no data was written.")
    if settings.app_env != "development" or not settings.enable_dev_academic_api:
        raise SystemExit("Development environment and ENABLE_DEV_ACADEMIC_API=true are required.")
    if not settings.mongodb_uri:
        raise SystemExit("MONGODB_URI is not configured; no data was written.")
    if settings.mongodb_database == "attendai" or "python" not in settings.mongodb_database.casefold():
        raise SystemExit("Refusing to seed a database not explicitly named for the Python rewrite.")

    mongo.configure()
    if mongo.status != "connected":
        raise SystemExit("The configured Python development database is unavailable.")
    services = build_services()

    try:
        institution = services["institutions"].repository.find_one({"code": "DEMO"})
        if institution is None:
            institution = services["institutions"].create(InstitutionCreate(name="DEMO Institution", code="DEMO", country="India", timezone="Asia/Kolkata"))
        institution_id = str(institution.get("_id", institution.get("id")))

        department = services["departments"].repository.find_one({"institution_id": institution_id, "code": "ECS"})
        if department is None:
            department = services["departments"].create(DepartmentCreate(institution_id=institution_id, name="DEMO Electronics and Computer Science", code="ECS"))
        department_id = str(department.get("_id", department.get("id")))

        program = services["programs"].repository.find_one({"institution_id": institution_id, "department_id": department_id, "code": "BE"})
        if program is None:
            program = services["programs"].create(ProgramCreate(institution_id=institution_id, department_id=department_id, name="DEMO Bachelor of Engineering", code="BE", degree_type="Bachelor", duration_years=4, total_semesters=8))
        program_id = str(program.get("_id", program.get("id")))

        year = services["academic-years"].repository.find_one({"institution_id": institution_id, "name": "2026-2027"})
        if year is None:
            year = services["academic-years"].create(AcademicYearCreate(institution_id=institution_id, name="2026-2027", start_date=date(2026, 6, 1), end_date=date(2027, 5, 31), is_current=True))
        year_id = str(year.get("_id", year.get("id")))

        semester = services["semesters"].repository.find_one({"institution_id": institution_id, "program_id": program_id, "academic_year_id": year_id, "semester_number": 8})
        if semester is None:
            semester = services["semesters"].create(SemesterCreate(institution_id=institution_id, academic_year_id=year_id, program_id=program_id, semester_number=8, label="DEMO Semester 8"))
        semester_id = str(semester.get("_id", semester.get("id")))

        if services["classes"].repository.find_one({"institution_id": institution_id, "semester_id": semester_id, "division": "A"}) is None:
            services["classes"].create(ClassDivisionCreate(institution_id=institution_id, academic_year_id=year_id, department_id=department_id, program_id=program_id, semester_id=semester_id, name="DEMO BE ECS Semester 8", division="A"))
        if services["subjects"].repository.find_one({"institution_id": institution_id, "program_id": program_id, "semester_id": semester_id, "code": "ECL709"}) is None:
            services["subjects"].create(SubjectCreate(institution_id=institution_id, department_id=department_id, program_id=program_id, semester_id=semester_id, name="DEMO Major Project - I", code="ECL709", subject_type="project", credits=6))
        print(f"DEMO Phase 2 hierarchy is present in database: {settings.mongodb_database}")
    finally:
        mongo.close()


if __name__ == "__main__":
    main()

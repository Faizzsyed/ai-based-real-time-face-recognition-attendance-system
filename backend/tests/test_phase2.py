from datetime import date, datetime, timezone
from typing import Any

import pytest
from bson import ObjectId
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api import dev_academic
from app.core.config import get_settings
from app.core.errors import AppError
from app.db.mongo import mongo
from app.db.object_id import parse_object_id
from app.main import app
from app.modules.academic_common.repositories import BaseRepository
from app.modules.academic_common.services import build_services
from app.modules.academic_years.schemas import AcademicYearCreate
from app.modules.class_divisions.schemas import ClassDivisionCreate
from app.modules.departments.schemas import DepartmentCreate, DepartmentUpdate
from app.modules.institutions.schemas import InstitutionCreate
from app.modules.programs.schemas import ProgramCreate
from app.modules.semesters.schemas import SemesterCreate
from app.modules.subjects.schemas import SubjectCreate


class MemoryRepository:
    def __init__(self) -> None:
        self.documents: list[dict[str, Any]] = []

    @staticmethod
    def _value(key, value):
        return parse_object_id(value, key) if key.endswith("_id") and not isinstance(value, ObjectId) else value

    def find_by_id(self, document_id, institution_id=None):
        oid = parse_object_id(document_id)
        institution_oid = parse_object_id(institution_id) if institution_id else None
        return next((doc for doc in self.documents if doc["_id"] == oid and (institution_oid is None or doc.get("institution_id") == institution_oid)), None)

    def find_one(self, filters):
        return next((doc for doc in self.documents if all(doc.get(key) == self._value(key, value) for key, value in filters.items())), None)

    def list(self, filters, page, page_size):
        matches = [doc for doc in self.documents if all(value is None or doc.get(key) == self._value(key, value) for key, value in filters.items())]
        start = (page - 1) * page_size
        return matches[start : start + page_size], len(matches)

    def insert(self, document):
        now = datetime.now(timezone.utc)
        stored = {**document, "_id": ObjectId(), "created_at": now, "updated_at": now}
        self.documents.append(stored)
        return stored

    def update(self, document_id, changes, institution_id=None):
        document = self.find_by_id(document_id, institution_id)
        if document:
            document.update(changes)
            document["updated_at"] = datetime.now(timezone.utc)
        return document

    def count(self, filters):
        return sum(1 for doc in self.documents if all(doc.get(key) == self._value(key, value) for key, value in filters.items()))

    def unset_current(self, institution_id, exclude_id=None):
        institution_oid = parse_object_id(institution_id)
        for document in self.documents:
            if document.get("institution_id") == institution_oid and document.get("is_current") and str(document["_id"]) != str(exclude_id):
                document["is_current"] = False


@pytest.fixture
def domain():
    repositories = {name: MemoryRepository() for name in ("institutions", "academic-years", "departments", "programs", "semesters", "classes", "subjects")}
    services = build_services(repositories)  # type: ignore[arg-type]
    institution_a = repositories["institutions"].insert({"name": "Demo A", "code": "A", "country": "India", "timezone": "Asia/Kolkata", "status": "active"})
    institution_b = repositories["institutions"].insert({"name": "Demo B", "code": "B", "country": "India", "timezone": "Asia/Kolkata", "status": "active"})
    return repositories, services, institution_a, institution_b


def institution_payload(code="TCET"):
    return InstitutionCreate(name="  Demo Institution  ", code=code, country="India", timezone="Asia/Kolkata")


def test_institution_validation_trims_and_normalizes_code():
    model = institution_payload(" demo ")
    assert model.name == "Demo Institution"
    assert model.code == "DEMO"


def test_duplicate_institution_code(domain):
    _, services, _, _ = domain
    services["institutions"].create(institution_payload("NEW"))
    with pytest.raises(AppError, match="same scoped identifier") as exc:
        services["institutions"].create(institution_payload("NEW"))
    assert exc.value.code == "DUPLICATE_CODE"


def test_academic_year_date_validation():
    with pytest.raises(ValidationError):
        AcademicYearCreate(institution_id=str(ObjectId()), name="2026-2027", start_date=date(2027, 1, 1), end_date=date(2026, 1, 1))


def test_setting_new_current_year_unsets_previous(domain):
    repositories, services, institution, _ = domain
    payload = dict(institution_id=str(institution["_id"]), name="2026-2027", start_date=date(2026, 6, 1), end_date=date(2027, 5, 31), is_current=True)
    first = services["academic-years"].create(AcademicYearCreate(**payload))
    payload["name"] = "2027-2028"
    payload["start_date"] = date(2027, 6, 1)
    payload["end_date"] = date(2028, 5, 31)
    second = services["academic-years"].create(AcademicYearCreate(**payload))
    assert repositories["academic-years"].find_by_id(first["_id"])["is_current"] is False
    assert repositories["academic-years"].find_by_id(second["_id"])["is_current"] is True


def test_department_code_unique_per_institution(domain):
    _, services, institution_a, institution_b = domain
    services["departments"].create(DepartmentCreate(institution_id=str(institution_a["_id"]), name="ECS", code="ECS"))
    services["departments"].create(DepartmentCreate(institution_id=str(institution_b["_id"]), name="ECS", code="ECS"))
    with pytest.raises(AppError) as exc:
        services["departments"].create(DepartmentCreate(institution_id=str(institution_a["_id"]), name="Other", code="ECS"))
    assert exc.value.code == "DUPLICATE_CODE"


def test_program_cross_institution_reference_rejected(domain):
    _, services, institution_a, institution_b = domain
    department = services["departments"].create(DepartmentCreate(institution_id=str(institution_a["_id"]), name="ECS", code="ECS"))
    with pytest.raises(AppError) as exc:
        services["programs"].create(ProgramCreate(institution_id=str(institution_b["_id"]), department_id=department["_id"], name="BE", code="BE", degree_type="Bachelor", duration_years=4, total_semesters=8))
    assert exc.value.code == "CROSS_INSTITUTION_REFERENCE"


def hierarchy(domain):
    _, services, institution, _ = domain
    institution_id = str(institution["_id"])
    department = services["departments"].create(DepartmentCreate(institution_id=institution_id, name="ECS", code="ECS"))
    program = services["programs"].create(ProgramCreate(institution_id=institution_id, department_id=department["_id"], name="BE", code="BE", degree_type="Bachelor", duration_years=4, total_semesters=8))
    year = services["academic-years"].create(AcademicYearCreate(institution_id=institution_id, name="2026-2027", start_date=date(2026, 6, 1), end_date=date(2027, 5, 31), is_current=True))
    return services, institution_id, department, program, year


def test_semester_number_must_fit_program(domain):
    services, institution_id, _, program, year = hierarchy(domain)
    with pytest.raises(AppError) as exc:
        services["semesters"].create(SemesterCreate(institution_id=institution_id, academic_year_id=year["_id"], program_id=program["_id"], semester_number=9))
    assert exc.value.code == "VALIDATION_ERROR"


def test_class_hierarchy_mismatch_rejected(domain):
    services, institution_id, department, program, year = hierarchy(domain)
    other = services["programs"].create(ProgramCreate(institution_id=institution_id, department_id=department["_id"], name="BCA", code="BCA", degree_type="Bachelor", duration_years=3, total_semesters=6))
    semester = services["semesters"].create(SemesterCreate(institution_id=institution_id, academic_year_id=year["_id"], program_id=program["_id"], semester_number=1))
    with pytest.raises(AppError) as exc:
        services["classes"].create(ClassDivisionCreate(institution_id=institution_id, academic_year_id=year["_id"], department_id=department["_id"], program_id=other["_id"], semester_id=semester["_id"], name="Mismatch", division="A"))
    assert exc.value.code == "INVALID_REFERENCE"


def test_subject_ownership_validation(domain):
    services, institution_id, department, program, year = hierarchy(domain)
    semester = services["semesters"].create(SemesterCreate(institution_id=institution_id, academic_year_id=year["_id"], program_id=program["_id"], semester_number=8))
    subject = services["subjects"].create(SubjectCreate(institution_id=institution_id, department_id=department["_id"], program_id=program["_id"], semester_id=semester["_id"], name="Major Project - I", code="ECL709", subject_type="project", credits=6))
    assert subject["code"] == "ECL709"


def test_invalid_object_id_is_safe():
    with pytest.raises(AppError) as exc:
        parse_object_id("not-an-object-id")
    assert exc.value.code == "VALIDATION_ERROR"
    assert exc.value.status_code == 422


def test_pagination_and_filtering(domain):
    _, services, institution, _ = domain
    institution_id = str(institution["_id"])
    for index in range(5):
        services["departments"].create(DepartmentCreate(institution_id=institution_id, name=f"Department {index}", code=f"D{index}"))
    page = services["departments"].list({"institution_id": institution_id, "status": "active"}, 2, 2)
    assert page["page"] == 2 and page["pageSize"] == 2
    assert page["total"] == 5 and page["totalPages"] == 3
    assert len(page["items"]) == 2


def test_resource_in_use_blocks_deactivation(domain):
    services, institution_id, department, _, _ = hierarchy(domain)
    with pytest.raises(AppError) as exc:
        services["departments"].update(department["_id"], DepartmentUpdate(status="inactive"), institution_id)
    assert exc.value.code == "RESOURCE_IN_USE"


def test_repository_reports_database_unavailable(monkeypatch):
    monkeypatch.setattr(mongo, "status", "not_configured")
    monkeypatch.setattr(mongo, "database", None)
    with pytest.raises(AppError) as exc:
        BaseRepository().list({}, 1, 20)
    assert exc.value.code == "DATABASE_UNAVAILABLE"


def test_development_api_disabled_by_default(monkeypatch):
    monkeypatch.setenv("ENABLE_DEV_ACADEMIC_API", "false")
    get_settings.cache_clear()
    with TestClient(app) as client:
        response = client.get("/api/v1/dev/institutions")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "DEV_API_DISABLED"
    get_settings.cache_clear()


def test_development_api_enabled_with_fake_service(monkeypatch):
    class FakeService:
        def list(self, filters, page, page_size):
            return {"items": [], "page": page, "pageSize": page_size, "total": 0, "totalPages": 0}

    monkeypatch.setenv("ENABLE_DEV_ACADEMIC_API", "true")
    monkeypatch.setitem(dev_academic.services, "institutions", FakeService())
    get_settings.cache_clear()
    with TestClient(app) as client:
        response = client.get("/api/v1/dev/institutions?page=1&pageSize=10")
    assert response.status_code == 200
    assert response.json() == {"items": [], "page": 1, "pageSize": 10, "total": 0, "totalPages": 0}
    get_settings.cache_clear()

"""Phase 4 production Admin academic workflow and authorization tests."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

from app.api.admin_academic import get_admin_services
from app.db.object_id import parse_object_id
from app.main import app
from app.modules.academic_common.services import build_services
from app.modules.auth.dependencies import get_current_user
from app.modules.academic_common.repositories import DepartmentRepository
from app.core.errors import AppError
from app.core.config import get_settings
from pymongo.errors import DuplicateKeyError


class MemoryRepository:
    def __init__(self) -> None:
        self.documents: list[dict[str, Any]] = []

    @staticmethod
    def _normalize(key, value):
        return parse_object_id(value, key) if key.endswith("_id") and not isinstance(value, (ObjectId, dict)) else value

    def _matches(self, document, filters):
        for key, value in filters.items():
            if value is None:
                continue
            if key == "$or":
                if not any(self._matches(document, option) for option in value):
                    return False
                continue
            actual = document.get(key)
            value = self._normalize(key, value)
            if isinstance(value, dict) and "$regex" in value:
                if re.search(value["$regex"], str(actual or ""), re.I if value.get("$options") == "i" else 0) is None:
                    return False
            elif actual != value:
                return False
        return True

    def find_by_id(self, document_id, institution_id=None):
        oid = parse_object_id(document_id)
        scope = parse_object_id(institution_id) if institution_id else None
        return next((doc for doc in self.documents if doc["_id"] == oid and (scope is None or doc.get("institution_id") == scope)), None)

    def find_one(self, filters):
        return next((doc for doc in self.documents if self._matches(doc, filters)), None)

    def list(self, filters, page, page_size):
        matches = [doc for doc in self.documents if self._matches(doc, filters)]
        start = (page - 1) * page_size
        return matches[start:start + page_size], len(matches)

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
        return sum(1 for document in self.documents if self._matches(document, filters))

    def unset_current(self, institution_id, exclude_id=None):
        scope = parse_object_id(institution_id)
        for document in self.documents:
            if document.get("institution_id") == scope and document.get("is_current") and str(document["_id"]) != str(exclude_id):
                document["is_current"] = False


@pytest.fixture
def phase4_domain():
    repositories = {name: MemoryRepository() for name in ("institutions", "academic-years", "departments", "programs", "semesters", "classes", "subjects")}
    services = build_services(repositories)  # type: ignore[arg-type]
    institution_a = repositories["institutions"].insert({"name": "Demo Institution", "code": "DEMO", "country": "India", "timezone": "Asia/Kolkata", "status": "active"})
    institution_b = repositories["institutions"].insert({"name": "Other Institution", "code": "OTHER", "country": "India", "timezone": "Asia/Kolkata", "status": "active"})
    users = {
        "admin_a": {"_id": ObjectId(), "institution_id": institution_a["_id"], "role": "admin", "status": "active"},
        "admin_b": {"_id": ObjectId(), "institution_id": institution_b["_id"], "role": "admin", "status": "active"},
        "faculty": {"_id": ObjectId(), "institution_id": institution_a["_id"], "role": "faculty", "status": "active"},
        "student": {"_id": ObjectId(), "institution_id": institution_a["_id"], "role": "student", "status": "active"},
    }
    return repositories, services, institution_a, institution_b, users


def client_as(services, user=None):
    app.dependency_overrides[get_admin_services] = lambda: services
    if user is not None:
        app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


def clear_overrides():
    app.dependency_overrides.clear()


def post(client, resource, payload):
    response = client.post(f"/api/v1/admin/academic/{resource}", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def create_hierarchy(client):
    year = post(client, "academic-years", {"name": "2026-2027", "start_date": "2026-06-01", "end_date": "2027-05-31", "is_current": True})
    department = post(client, "departments", {"name": "Electronics and Computer Science", "code": "ECS"})
    program = post(client, "programs", {"department_id": department["_id"], "name": "BE ECS", "code": "BE-ECS", "degree_type": "Bachelor", "duration_years": 4, "total_semesters": 8})
    semester = post(client, "semesters", {"academic_year_id": year["_id"], "program_id": program["_id"], "semester_number": 8, "label": "Semester 8"})
    class_division = post(client, "classes", {"academic_year_id": year["_id"], "department_id": department["_id"], "program_id": program["_id"], "semester_id": semester["_id"], "name": "BE ECS Semester 8", "division": "A", "room": "Lab 4", "capacity": 60})
    subject = post(client, "subjects", {"department_id": department["_id"], "program_id": program["_id"], "semester_id": semester["_id"], "name": "Major Project - I", "code": "ECL709", "subject_type": "project", "credits": 6, "weekly_hours": 8})
    return year, department, program, semester, class_division, subject


def test_no_token_returns_401(phase4_domain):
    _, services, _, _, _ = phase4_domain
    try:
        with client_as(services) as client:
            response = client.get("/api/v1/admin/academic/departments")
        assert response.status_code == 401 and response.json()["error"]["code"] == "AUTH_REQUIRED"
    finally:
        clear_overrides()


def test_no_token_is_rejected_by_every_admin_route_shape(phase4_domain):
    _, services, _, _, _ = phase4_domain
    document_id = str(ObjectId())
    requests = (
        ("get", "/api/v1/admin/academic/institution", None),
        ("patch", "/api/v1/admin/academic/institution", {"city": "Mumbai"}),
        ("get", "/api/v1/admin/academic/setup-status", None),
        ("get", "/api/v1/admin/academic/departments", None),
        ("get", f"/api/v1/admin/academic/departments/{document_id}", None),
        ("post", "/api/v1/admin/academic/departments", {"name": "ECS", "code": "ECS"}),
        ("patch", f"/api/v1/admin/academic/departments/{document_id}", {"name": "ECS"}),
    )
    try:
        with client_as(services) as client:
            for method, path, payload in requests:
                response = client.request(method, path, json=payload)
                assert response.status_code == 401
    finally:
        clear_overrides()


@pytest.mark.parametrize("role", ["faculty", "student"])
def test_cross_role_access_returns_403_for_every_resource(phase4_domain, role):
    _, services, _, _, users = phase4_domain
    try:
        with client_as(services, users[role]) as client:
            for resource in ("academic-years", "departments", "programs", "semesters", "classes", "subjects"):
                response = client.get(f"/api/v1/admin/academic/{resource}")
                assert response.status_code == 403
            assert client.get("/api/v1/admin/academic/institution").status_code == 403
            assert client.patch("/api/v1/admin/academic/institution", json={"city": "Mumbai"}).status_code == 403
            assert client.post("/api/v1/admin/academic/departments", json={"name": "ECS", "code": "ECS"}).status_code == 403
            assert client.patch(f"/api/v1/admin/academic/departments/{ObjectId()}", json={"name": "ECS"}).status_code == 403
    finally:
        clear_overrides()


def test_complete_admin_academic_workflow_and_setup_status(phase4_domain):
    _, services, institution, _, users = phase4_domain
    try:
        with client_as(services, users["admin_a"]) as client:
            hierarchy = create_hierarchy(client)
            response = client.get("/api/v1/admin/academic/setup-status")
            assert response.status_code == 200 and response.json()["state"] == "Ready"
            assert all(str(item["institution_id"]) == str(institution["_id"]) for item in hierarchy)
            subjects = client.get("/api/v1/admin/academic/subjects?search=project&type=project").json()
            assert subjects["total"] == 1 and subjects["items"][0]["name"] == "Major Project - I"
    finally:
        clear_overrides()


def test_institution_view_update_and_immutable_fields(phase4_domain):
    _, services, institution, _, users = phase4_domain
    try:
        with client_as(services, users["admin_a"]) as client:
            assert client.get("/api/v1/admin/academic/institution").json()["code"] == "DEMO"
            updated = client.patch("/api/v1/admin/academic/institution", json={"short_name": "DI", "city": "Mumbai"})
            assert updated.status_code == 200 and updated.json()["city"] == "Mumbai"
            rejected = client.patch("/api/v1/admin/academic/institution", json={"code": "CHANGED"})
            assert rejected.status_code == 422 and institution["code"] == "DEMO"
    finally:
        clear_overrides()


def test_setting_current_year_unsets_previous(phase4_domain):
    repositories, services, _, _, users = phase4_domain
    try:
        with client_as(services, users["admin_a"]) as client:
            first = post(client, "academic-years", {"name": "2026-2027", "start_date": "2026-06-01", "end_date": "2027-05-31", "is_current": True})
            second = post(client, "academic-years", {"name": "2027-2028", "start_date": "2027-06-01", "end_date": "2028-05-31", "is_current": True})
        assert repositories["academic-years"].find_by_id(first["_id"])["is_current"] is False
        assert repositories["academic-years"].find_by_id(second["_id"])["is_current"] is True
    finally:
        clear_overrides()


def test_cross_tenant_ids_cannot_be_read_mutated_or_referenced(phase4_domain):
    _, services, _, _, users = phase4_domain
    try:
        with client_as(services, users["admin_a"]) as client:
            _, department, *_ = create_hierarchy(client)
        with client_as(services, users["admin_b"]) as client:
            assert client.get(f"/api/v1/admin/academic/departments/{department['_id']}").status_code == 404
            assert client.patch(f"/api/v1/admin/academic/departments/{department['_id']}", json={"name": "Stolen"}).status_code == 404
            cross = client.post("/api/v1/admin/academic/programs", json={"department_id": department["_id"], "name": "Cross", "code": "CROSS", "degree_type": "Bachelor", "duration_years": 4, "total_semesters": 8})
            assert cross.status_code == 422 and cross.json()["error"]["code"] == "CROSS_INSTITUTION_REFERENCE"
    finally:
        clear_overrides()


def test_client_institution_id_is_rejected(phase4_domain):
    _, services, _, other, users = phase4_domain
    try:
        with client_as(services, users["admin_a"]) as client:
            response = client.post("/api/v1/admin/academic/departments", json={"institution_id": str(other["_id"]), "name": "Cross", "code": "CROSS"})
        assert response.status_code == 422 and response.json()["error"]["code"] == "IMMUTABLE_FIELD"
    finally:
        clear_overrides()


def test_pagination_filter_and_admin_metadata(phase4_domain):
    repositories, services, _, _, users = phase4_domain
    try:
        with client_as(services, users["admin_a"]) as client:
            for index in range(5):
                post(client, "departments", {"name": f"Department {index}", "code": f"D{index}"})
            page = client.get("/api/v1/admin/academic/departments?page=2&pageSize=2&status=active").json()
        assert page["page"] == 2 and page["pageSize"] == 2 and page["total"] == 5 and len(page["items"]) == 2
        assert all(document["created_by"] == users["admin_a"]["_id"] for document in repositories["departments"].documents)
    finally:
        clear_overrides()


def test_same_tenant_admin_can_read_and_repeatedly_edit_owned_resource(phase4_domain):
    _, services, _, _, users = phase4_domain
    try:
        with client_as(services, users["admin_a"]) as client:
            department = post(client, "departments", {"name": "Electronics", "code": "ECS"})
            first = client.patch(f"/api/v1/admin/academic/departments/{department['_id']}", json={"description": "First update"})
            second = client.patch(f"/api/v1/admin/academic/departments/{department['_id']}", json={"description": "Second update"})
            fetched = client.get(f"/api/v1/admin/academic/departments/{department['_id']}")
        assert first.status_code == 200 and second.status_code == 200
        assert fetched.status_code == 200 and fetched.json()["description"] == "Second update"
        assert fetched.json()["updated_by"] == str(users["admin_a"]["_id"])
    finally:
        clear_overrides()


def test_inactive_department_rejects_new_program(phase4_domain):
    _, services, _, _, users = phase4_domain
    try:
        with client_as(services, users["admin_a"]) as client:
            department = post(client, "departments", {"name": "Dormant", "code": "DORM", "status": "inactive"})
            response = client.post("/api/v1/admin/academic/programs", json={"department_id": department["_id"], "name": "Invalid", "code": "INV", "degree_type": "Bachelor", "duration_years": 4, "total_semesters": 8})
        assert response.status_code == 422 and response.json()["error"]["code"] == "INVALID_REFERENCE"
    finally:
        clear_overrides()


def test_maximum_page_size_is_enforced(phase4_domain):
    _, services, _, _, users = phase4_domain
    try:
        with client_as(services, users["admin_a"]) as client:
            response = client.get("/api/v1/admin/academic/departments?pageSize=101")
        assert response.status_code == 422
    finally:
        clear_overrides()


def test_admin_academic_database_unavailable_is_safe(phase4_domain,monkeypatch):
    _, _, _, _, users = phase4_domain
    monkeypatch.setenv("MONGODB_URI","")
    get_settings.cache_clear()
    app.dependency_overrides[get_current_user] = lambda: users["admin_a"]
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/admin/academic/departments")
        assert response.status_code == 503 and response.json()["error"]["code"] == "DATABASE_UNAVAILABLE"
    finally:
        clear_overrides()
        get_settings.cache_clear()


def test_duplicate_key_exception_is_converted_to_safe_contract():
    class DuplicateCollection:
        def insert_one(self, document):
            raise DuplicateKeyError("sensitive database detail")

    class FakeDatabase:
        def __getitem__(self, name):
            return DuplicateCollection()

    repository = DepartmentRepository(FakeDatabase())  # type: ignore[arg-type]
    with pytest.raises(AppError) as exc:
        repository.insert({"name": "ECS", "code": "ECS"})
    assert exc.value.code == "DUPLICATE_CODE"
    assert "sensitive" not in exc.value.message

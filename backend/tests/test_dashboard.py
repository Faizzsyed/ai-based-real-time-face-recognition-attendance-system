import pytest
from fastapi.testclient import TestClient
from bson import ObjectId
from datetime import date, datetime, time, timedelta, timezone
from types import SimpleNamespace
from app.db.mongo import mongo
from app.main import app
from app.modules.auth.dependencies import get_current_user

class MemoryCollection:
    def __init__(self):
        self.documents = []

    def insert_many(self, documents):
        self.documents.extend(documents)

    def find(self, filters):
        return [doc for doc in self.documents if all(doc.get(key) == value for key, value in filters.items())]

    def count_documents(self, filters):
        return len(self.find(filters))

    def delete_many(self, filters):
        self.documents = [doc for doc in self.documents if not all(
            doc.get(key) in value["$in"] if isinstance(value, dict) else doc.get(key) == value
            for key, value in filters.items()
        )]


@pytest.fixture(autouse=True)
def setup_db(monkeypatch):
    database = SimpleNamespace(**{name: MemoryCollection() for name in (
        "students", "faculty", "attendance_requests", "attendance_sessions"
    )})
    monkeypatch.setattr(mongo, "require_database", lambda: database)
    yield
    app.dependency_overrides.clear()

def test_admin_dashboard_returns_metrics():
    client = TestClient(app)
    institution_id = ObjectId()
    other_institution_id = ObjectId()

    app.dependency_overrides[get_current_user] = lambda: {
        "_id": ObjectId(),
        "institution_id": institution_id,
        "role": "admin"
    }

    db = mongo.require_database()
    try:
        db.students.insert_many([
            {"institution_id": institution_id, "status": "active", "admission_number": "STU001", "user_id": ObjectId()},
            {"institution_id": institution_id, "status": "active", "admission_number": "STU002", "user_id": ObjectId()},
            {"institution_id": other_institution_id, "status": "active", "admission_number": "OTHER001", "user_id": ObjectId()},
        ])
        db.faculty.insert_many([
            {"institution_id": institution_id, "status": "active", "employee_id": "FAC001", "user_id": ObjectId()},
            {"institution_id": other_institution_id, "status": "active", "employee_id": "OTHERFAC", "user_id": ObjectId()},
        ])
        db.attendance_requests.insert_many([
            {"institution_id": institution_id, "status": "pending"},
            {"institution_id": other_institution_id, "status": "pending"},
            {"institution_id": institution_id, "status": "approved"},
        ])
        db.attendance_sessions.insert_many([
            {"institution_id": institution_id, "lecture_date": datetime.combine(date.today(), time.min, tzinfo=timezone.utc)},
            {"institution_id": other_institution_id, "lecture_date": datetime.combine(date.today(), time.min, tzinfo=timezone.utc)},
            {"institution_id": institution_id, "lecture_date": datetime.combine(date.today() - timedelta(days=1), time.min, tzinfo=timezone.utc)},
        ])

        response = client.get("/api/v1/admin/dashboard")
        assert response.status_code == 200
        data = response.json()
        assert data["totalStudents"] == 2
        assert data["totalFaculty"] == 1
        assert data["attendanceToday"] == "1 Sessions"
        assert data["pendingRequests"] == 1
    finally:
        db.students.delete_many({"institution_id": {"$in": [institution_id, other_institution_id]}})
        db.faculty.delete_many({"institution_id": {"$in": [institution_id, other_institution_id]}})
        db.attendance_requests.delete_many({"institution_id": {"$in": [institution_id, other_institution_id]}})
        db.attendance_sessions.delete_many({"institution_id": {"$in": [institution_id, other_institution_id]}})
        app.dependency_overrides.clear()

def test_faculty_cannot_access_dashboard():
    client = TestClient(app)

    app.dependency_overrides[get_current_user] = lambda: {
        "_id": ObjectId(),
        "institution_id": ObjectId(),
        "role": "faculty"
    }

    response = client.get("/api/v1/admin/dashboard")
    assert response.status_code == 403
    app.dependency_overrides.clear()

"""Phase 13 boundary tests: contracts, RBAC routing, and audit redaction."""
from bson import ObjectId
from fastapi.testclient import TestClient
import pytest
from app.main import app
from app.modules.auth.dependencies import get_current_user
from app.modules.requests.router import get_request_service
from app.modules.notifications.router import get_notification_service
from app.modules.audit.router import get_audit_service
from app.modules.requests.schemas import AttendanceRequestCreate
from app.modules.audit.service import _safe

IID=ObjectId();USER=ObjectId()
class Requests:
    def __init__(self):self.calls=[]
    def create(self,payload,user):self.calls.append((payload,user));return {"_id":"request"}
    def mine(self,*args):return {"items":[],"pagination":{}}
    def queue(self,*args):return {"items":[],"pagination":{}}
    def get(self,*args):return {"_id":"request"}
    def cancel(self,*args):return {"_id":"request","status":"cancelled"}
    def resolve(self,*args):return {"_id":"request","status":args[1]}
class Notifications:
    def list(self,*args):return {"items":[],"pagination":{}}
    def unread_count(self,*args):return {"count":0}
    def read(self,*args):return {"_id":"notification"}
    def read_all(self,*args):return {"updated":0}
class Audit:
    def list(self,*args):return {"items":[],"pagination":{}}
    def get(self,*args):return None

@pytest.fixture
def client():
    requests=Requests();app.dependency_overrides[get_request_service]=lambda:requests;app.dependency_overrides[get_notification_service]=lambda:Notifications();app.dependency_overrides[get_audit_service]=lambda:Audit()
    yield TestClient(app),requests
    app.dependency_overrides.clear()
def user(role):return {"_id":USER,"institution_id":IID,"role":role}
def test_request_contract_rejects_spoofed_identity_and_invalid_status():
    with pytest.raises(Exception):AttendanceRequestCreate(attendanceSessionId=str(ObjectId()),requestedStatus="invalid",reason="reason")
    with pytest.raises(Exception):AttendanceRequestCreate(attendanceSessionId=str(ObjectId()),requestedStatus="present",reason="reason",studentId=str(ObjectId()))
def test_student_create_uses_authenticated_identity_only(client):
    http,requests=client;app.dependency_overrides[get_current_user]=lambda:user("student")
    response=http.post("/api/v1/requests/attendance",json={"attendanceSessionId":str(ObjectId()),"requestedStatus":"present","reason":"Marked incorrectly"})
    assert response.status_code==201 and requests.calls[0][1]["_id"]==USER
def test_request_roles_and_cross_feature_boundaries(client):
    http,_=client;app.dependency_overrides[get_current_user]=lambda:user("student")
    assert http.get("/api/v1/requests/attendance").status_code==403
    assert http.get("/api/v1/audit").status_code==403
    assert http.get("/api/v1/notifications").status_code==200
    app.dependency_overrides[get_current_user]=lambda:user("faculty")
    assert http.get("/api/v1/requests/attendance").status_code==200
    assert http.get("/api/v1/audit").status_code==403
    app.dependency_overrides[get_current_user]=lambda:user("admin")
    assert http.get("/api/v1/audit").status_code==200
def test_notification_routes_are_authenticated(client):
    http,_=client
    assert http.get("/api/v1/notifications").status_code==401
def test_audit_redaction_removes_auth_and_biometric_values():
    safe=_safe({"password":"x","token":"y","face_embedding":[1,2],"ok":{"status":"present"}})
    assert safe["password"]=="[redacted]" and safe["token"]=="[redacted]" and safe["face_embedding"]=="[redacted]" and safe["ok"]["status"]=="present"

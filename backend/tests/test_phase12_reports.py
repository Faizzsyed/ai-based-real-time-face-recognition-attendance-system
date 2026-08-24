"""Deterministic Phase 12 calculation, scope, privacy, and route tests."""
from datetime import datetime,timezone
from bson import ObjectId
from fastapi.testclient import TestClient
import pytest
from app.core.errors import AppError
from app.main import app
from app.modules.auth.dependencies import get_current_user
from app.modules.reports.router import get_report_service
from app.modules.reports.service import ReportService,attendance_counts

IID=ObjectId();OTHER=ObjectId();ADMIN=ObjectId();FAC_USER=ObjectId();STUDENT_USER=ObjectId();FAC=ObjectId();CLASS=ObjectId();SUBJECT=ObjectId();S1=ObjectId();S2=ObjectId()
class Repo:
    def __init__(self):
        self.sessions=[];self.records=[]
        for n in range(11):
            session={"_id":ObjectId(),"institution_id":IID,"faculty_id":FAC,"class_division_id":CLASS,"subject_id":SUBJECT,"academic_year_id":ObjectId(),"lecture_date":datetime(2026,8,n+1,tzinfo=timezone.utc),"status":"draft" if n==10 else "submitted"};self.sessions.append(session)
            if n<10:self.records.extend([{"session_id":session["_id"],"institution_id":IID,"student_id":S1,"student_name":"One","admission_number":"A1","status":"present" if n<8 else "absent","source":"face_recognition" if n<4 else "manual"},{"session_id":session["_id"],"institution_id":IID,"student_id":S2,"student_name":"Two","admission_number":"A2","status":"absent","source":"manual"}])
        self.foreign={"_id":ObjectId(),"institution_id":OTHER,"status":"submitted","lecture_date":datetime(2026,8,1,tzinfo=timezone.utc)}
    def faculty_for_user(self,iid,uid):return {"_id":FAC,"institution_id":IID,"user_id":FAC_USER,"status":"active"} if iid==IID and uid==FAC_USER else None
    def student_for_user(self,iid,uid):return {"_id":S1,"institution_id":IID,"user_id":STUDENT_USER} if iid==IID and uid==STUDENT_USER else None
    def dataset(self,iid,filters=None,faculty_id=None,student_id=None):
        sessions=[x for x in self.sessions if x["institution_id"]==iid and x["status"] in {"submitted","locked"} and (not faculty_id or x["faculty_id"]==faculty_id)]
        if filters and filters.get("class_division_id"):sessions=[x for x in sessions if str(x["class_division_id"])==str(filters["class_division_id"])]
        if filters and filters.get("subject_id"):sessions=[x for x in sessions if str(x["subject_id"])==str(filters["subject_id"])]
        if filters and filters.get("date_from"):sessions=[x for x in sessions if x["lecture_date"].date()>=filters["date_from"]]
        if filters and filters.get("date_to"):sessions=[x for x in sessions if x["lecture_date"].date()<=filters["date_to"]]
        ids={x["_id"] for x in sessions};records=[x for x in self.records if x["session_id"] in ids and (not student_id or str(x["student_id"])==str(student_id))]
        return {"sessions":sessions,"records":records,"classes":{str(CLASS):{"_id":CLASS,"division":"A"}},"subjects":{str(SUBJECT):{"_id":SUBJECT,"name":"Engineering"}},"faculty":{str(FAC):{"_id":FAC,"display_name":"Faculty One"}},"students":{str(S1):{"_id":S1,"display_name":"One","admission_number":"A1"},str(S2):{"_id":S2,"display_name":"Two","admission_number":"A2"}},"programs":{},"departments":{},"semesters":{},"years":{}}
    def draft_count(self,iid):return 1 if iid==IID else 0

def users(role):return {"admin":{"_id":ADMIN,"institution_id":IID,"role":"admin"},"faculty":{"_id":FAC_USER,"institution_id":IID,"role":"faculty"},"student":{"_id":STUDENT_USER,"institution_id":IID,"role":"student"}}[role]
def test_central_policy_eight_of_ten_and_zero_safe():
    assert attendance_counts([{"status":"present"}]*8+[{"status":"absent"}]*2)["percentage"]==80
    assert attendance_counts([{"status":"excused"},{"status":None}])["percentage"] is None
def test_drafts_excluded_threshold_and_source_distribution():
    report=ReportService(Repo(),75).overview(users("admin"));assert report["finalizedSessions"]==10 and report["draftSessions"]==1 and report["studentsBelowThreshold"]==1
    assert {x["source"]:x["count"] for x in report["sourceDistribution"]}=={"face_assisted":4,"manual":16}
def test_student_self_report_subjects_and_history_have_no_biometrics():
    report=ReportService(Repo(),75).student_report(users("student"));assert report["attendance"]["percentage"]==80 and report["subjects"][0]["subject"]=="Engineering" and len(report["recentHistory"])==10
    assert not ({"embedding","image","token","password"}&set(str(report).casefold().split()))
def test_faculty_unassigned_class_and_unrelated_student_denied():
    service=ReportService(Repo(),75)
    with pytest.raises(AppError) as error:service.class_report(users("faculty"),str(ObjectId()),{},True)
    assert error.value.code=="FORBIDDEN_REPORT_SCOPE"
    with pytest.raises(AppError):service.student_report(users("faculty"),str(ObjectId()),True)
def test_date_class_subject_isolation_and_low_attendance():
    service=ReportService(Repo(),75);assert len(service.trend(users("admin"),{"date_from":datetime(2026,8,5).date(),"date_to":datetime(2026,8,6).date()})["items"])==2
    assert service.class_report(users("admin"),str(ObjectId()))["finalizedSessions"]==0
    assert service.subjects(users("admin"),{"subject_id":str(ObjectId())})["items"]==[]
    assert service.low_attendance(users("admin"))["items"][0]["student"]=="Two"
def test_csv_is_human_readable_and_excludes_sensitive_fields():
    service=ReportService(Repo(),75);name,body=service.csv_export(service.low_attendance(users("admin")),"Low Attendance")
    assert name.startswith("AttendAI_Low_Attendance_") and "student,studentNumber" in body and "embedding" not in body
def test_routes_enforce_role_and_do_not_accept_tenant_override():
    service=ReportService(Repo(),75);app.dependency_overrides[get_report_service]=lambda:service
    try:
        app.dependency_overrides[get_current_user]=lambda:users("student");client=TestClient(app);assert client.get("/api/v1/student/reports/attendance").status_code==200;assert client.get("/api/v1/admin/reports/overview").status_code==403
        app.dependency_overrides[get_current_user]=lambda:users("admin");client=TestClient(app);response=client.get("/api/v1/admin/reports/overview",params={"institutionId":str(OTHER)});assert response.status_code==200 and response.json()["finalizedSessions"]==10
    finally:app.dependency_overrides.clear()
def test_scoped_options_and_low_attendance_pagination_search():
    service=ReportService(Repo(),75);assert service.options(users("faculty"))["subjects"][0]["label"]=="Engineering"
    first=service.low_attendance(users("admin"),{"page":1,"page_size":1});assert first["pagination"]=={"page":1,"pageSize":1,"total":1,"pages":1}
    assert service.low_attendance(users("admin"),{"search":"missing"})["items"]==[]

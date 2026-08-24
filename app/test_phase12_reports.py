"""Phase 12 Flet reports surface and client route tests."""
from unittest.mock import Mock,patch
import flet as ft
from app.core.theme import tokens_for_mode
from app.screens.reports import build_reports
from app.services.api_client import ApiClient

def walk(control):
    yield control
    content=getattr(control,"content",None)
    if content is not None:yield from walk(content)
    for child in getattr(control,"controls",[]) or []:yield from walk(child)
def texts(control):return [x.value for x in walk(control) if isinstance(x,ft.Text)]
def test_admin_reports_renders_real_metrics_subjects_and_sources_in_both_themes():
    data={"attendance":{"percentage":80,"present":8,"eligible":10},"finalizedSessions":10,"studentsBelowThreshold":1,"threshold":75,"subjects":[{"subject":"Engineering","present":8,"eligible":10,"percentage":80}],"sourceDistribution":[{"source":"manual","percentage":60}]}
    for mode in ("light","dark"):
        labels=texts(build_reports("Admin",tokens_for_mode(mode),data));assert "80.0%" in labels and "Engineering" in labels and "Manual" in labels
def test_reports_empty_and_error_states_are_explicit():
    control=build_reports("Faculty",tokens_for_mode("light"),{},"API unavailable",lambda _:None);labels=texts(control);assert "No finalized attendance data" in labels and "API unavailable" in labels
def test_report_api_client_uses_role_scoped_paths():
    client=ApiClient("http://test")
    with patch.object(client,"authenticated_request",return_value=Mock()) as request:
        client.reports_overview("Admin",dateFrom="2026-08-01");assert request.call_args.args[1]=="/api/v1/admin/reports/overview?dateFrom=2026-08-01"
        client.reports_overview("Student");assert request.call_args.args[1]=="/api/v1/student/reports/attendance"
def test_loading_low_attendance_pagination_and_no_biometric_text():
    tokens=tokens_for_mode("light");loading=build_reports("Admin",tokens,{},loading=True);assert "Loading attendance report..." in texts(loading)
    data={"attendance":{"percentage":70,"eligible":10},"threshold":75,"subjects":[]};low={"threshold":75,"items":[{"studentId":"s1","student":"One","studentNumber":"A1","class":"A","percentage":70,"subjectsBelowThreshold":["Math"],"present":7,"absent":3,"eligible":10}],"pagination":{"page":1,"pages":2}}
    control=build_reports("Admin",tokens,data,options={},filters={},low=low,on_filter=lambda *_:None,on_reset=lambda _:None,on_range=lambda _:None,on_page=lambda _:None,on_search=lambda _:None,on_student=lambda _:None,on_session=lambda _:None,on_class=lambda _:None,on_export=lambda *_:None);labels=texts(control);table=next(x for x in walk(control) if isinstance(x,ft.DataTable));assert table.rows[0].cells[0].content.value=="One" and "Page 1 of 2" in labels and "embedding" not in str(control).casefold()
def test_student_subject_status_and_recent_history_render():
    data={"attendance":{"percentage":72,"present":7,"absent":3,"eligible":10},"threshold":75,"subjects":[{"subject":"Math","classesHeld":10,"present":7,"late":0,"absent":3,"percentage":70,"status":"Below Required Attendance"}],"recentHistory":[{"subject":"Math","date":"2026-08-24","status":"absent"}],"trend":{"items":[]}}
    labels=texts(build_reports("Student",tokens_for_mode("dark"),data));assert "Below Required Attendance" in labels and "Recent Attendance" in labels and "Classes Missed" in labels
def test_csv_client_uses_authenticated_central_send():
    response=Mock(is_success=True,content=b"Student,Attendance\n",status_code=200,headers={"content-disposition":'attachment; filename="AttendAI.csv"'})
    client=ApiClient("http://test")
    with patch.object(client,"_send",return_value=response) as send:
        result=client.download_report_csv("Admin","classes","c1");assert result.connected and result.data["filename"]=="AttendAI.csv" and send.call_args.kwargs["authenticated"] is True

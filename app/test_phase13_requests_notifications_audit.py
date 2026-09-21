import flet as ft
from app.core.theme import tokens_for_mode
from app.components.navigation import navigation_labels
from app.screens.phase13 import build_requests_page,build_notifications_page,build_audit_page

TOKENS=tokens_for_mode(ft.ThemeMode.LIGHT)
def test_phase13_navigation_is_role_specific():
    assert "Requests" in navigation_labels("Student") and "Notifications" in navigation_labels("Faculty") and "Audit Logs" in navigation_labels("Admin")
def test_requests_views_build_for_student_faculty_and_admin():
    data={"items":[{"_id":"r1","status":"pending","original_status":"absent","requested_status":"present","reason":"Incorrect","session":{"lectureDate":"2026-01-01","subjectId":"S1"},"student":{"displayName":"Student"}}]}
    for role in ("Student","Faculty","Admin"):
        assert build_requests_page(role,TOKENS,data,on_cancel=lambda _:None,on_review=lambda _:None)
def test_notifications_and_audit_support_empty_loading_and_error_states():
    assert build_notifications_page(TOKENS,{"items":[]},on_read=lambda _:None,on_read_all=lambda _:None)
    assert build_notifications_page(TOKENS,None,loading=True)
    assert build_audit_page(TOKENS,None,error="Unavailable",on_refresh=lambda _:None)

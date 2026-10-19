"""Regressions for management blockers found during the October demo audit."""

import asyncio
import inspect
from unittest.mock import AsyncMock, Mock, patch

import flet as ft
import pytest

from app.core.theme import LIGHT
from app.screens.admin.academic import build_academic_form
from app.screens.admin.dashboard import build_admin_dashboard
from app.screens.faculty.attendance import build_take_attendance
from app.screens.reports import build_session_detail
from app.screens.student.attendance import build_student_attendance
from app.services.api_client import ApiResult
from app.test_auth_foundation import auth_payload
from app.test_flet_foundation import make_controller, walk_controls


def controller_for(role):
    controller, page, host = make_controller(width=390)
    controller.auth_state.authenticate(auth_payload(role.casefold()))
    controller.current_role = role
    controller.current_screen = "authenticated"
    return controller, page, host


def session():
    return {"_id": "session", "status": "draft", "records": [
        {"student_id": "one", "student_name": "One", "status": None},
        {"student_id": "two", "student_name": "Two", "status": None},
    ], "summary": {"total": 2, "unmarked": 2}}


def test_marking_complete_roster_enables_review_and_submit():
    controller, _, _ = controller_for("Faculty")
    controller.current_attendance = session()
    controller.render_authenticated_shell = Mock()
    controller.mark_attendance("one", "present")
    assert controller.current_attendance["summary"]["unmarked"] == 1
    controller.mark_attendance("two", "absent")
    assert controller.current_attendance["summary"]["unmarked"] == 0
    view = build_take_attendance(LIGHT, {}, [], controller.current_attendance, *([Mock()] * 5))
    buttons = [x for x in walk_controls(view) if isinstance(x, ft.FilledButton)]
    assert any(x.disabled is False for x in buttons)
    # The last FilledButton is Review & Submit, after each roster row's marks.
    assert buttons[-1].disabled is False


def test_failed_draft_save_never_submits_stale_server_attendance():
    controller, _, _ = controller_for("Faculty")
    controller.current_attendance = session()
    controller.render_authenticated_shell = Mock()
    controller.api_client = Mock()
    controller.api_client.save_attendance_draft.return_value = ApiResult(False, error="Draft could not be saved.")
    controller.submit_attendance()
    controller.api_client.submit_attendance.assert_not_called()
    assert controller.attendance_notice == "Draft could not be saved."


def test_successful_draft_save_precedes_final_submission():
    controller, _, _ = controller_for("Faculty")
    controller.current_attendance = session()
    controller.render_authenticated_shell = Mock()
    controller.api_client = Mock()
    controller.api_client.save_attendance_draft.return_value = ApiResult(True, session())
    controller.api_client.submit_attendance.return_value = ApiResult(True, {**session(), "status": "submitted"})
    controller.submit_attendance()
    assert [call[0] for call in controller.api_client.mock_calls] == ["save_attendance_draft", "submit_attendance"]
    assert controller.current_attendance["status"] == "submitted"


@pytest.mark.parametrize("target", ["Dashboard", "Attendance"])
def test_student_navigation_fetches_new_attendance_and_history(target):
    controller, _, host = controller_for("Student")
    controller.api_client = Mock()
    controller.api_client.notifications.return_value = ApiResult(True, {"items": []})
    controller.api_client.my_attendance_requests.return_value = ApiResult(True, {"items": []})
    controller.api_client.student_attendance_summary.return_value = ApiResult(True, {"summary": {"attendancePercentage": 75}})
    controller.api_client.student_attendance_history.return_value = ApiResult(True, {"items": [{"session_id": "new-session", "status": "absent"}]})
    controller.student_profile_data = {"display_name": "Student"}
    controller.attendance_data = {"summary": {"attendancePercentage": 0}, "history": []}
    controller.select_navigation(target)
    controller.api_client.student_attendance_summary.assert_called_once()
    controller.api_client.student_attendance_history.assert_called_once()
    controller.api_client.reports_overview.assert_not_called()
    assert controller.attendance_data["summary"]["attendancePercentage"] == 75
    assert controller.attendance_data["history"][0]["session_id"] == "new-session"
    assert host.content is not None


def test_student_backend_failure_is_not_a_zero_attendance_metric():
    controller, _, _ = controller_for("Student")
    controller.api_client = Mock()
    controller.api_client.student_attendance_summary.return_value = ApiResult(False, error="Backend timed out.")
    controller.api_client.student_attendance_history.return_value = ApiResult(False)
    controller.load_student_attendance(render=False)
    assert controller.attendance_data is None
    view = build_student_attendance(LIGHT, controller.attendance_data, [], error=controller.attendance_notice)
    labels = [x.value for x in walk_controls(view) if isinstance(x, ft.Text)]
    assert "Backend timed out." in labels and "0.0%" not in labels


def test_failed_cancellation_keeps_error_visible():
    controller, _, _ = controller_for("Student")
    controller.render_authenticated_shell = Mock()
    controller.load_requests = Mock()
    controller.api_client = Mock()
    controller.api_client.cancel_attendance_request.return_value = ApiResult(False, error="Request already resolved.")
    controller.cancel_request("request")
    assert controller.requests_error == "Request already resolved."
    controller.load_requests.assert_not_called()


def test_failed_review_keeps_error_visible():
    controller, page, _ = controller_for("Faculty")
    page.show_dialog = Mock()
    page.pop_dialog = Mock()
    controller.render_authenticated_shell = Mock()
    controller.load_requests = Mock()
    controller.api_client = Mock()
    controller.api_client.resolve_attendance_request.return_value = ApiResult(False, error="Attendance changed. Reload before reviewing.")
    controller.review_request({"_id": "request", "original_status": "absent", "requested_status": "present"})
    dialog = page.show_dialog.call_args.args[0]
    note = next(x for x in walk_controls(dialog.content) if isinstance(x, ft.TextField))
    note.value = "Please preserve this resolution note."
    dialog.actions[-1].on_click(None)
    assert note.value == "Please preserve this resolution note."
    assert any(x.value == "Attendance changed. Reload before reviewing." and x.visible
               for x in walk_controls(dialog.content) if isinstance(x, ft.Text))
    page.pop_dialog.assert_not_called()
    controller.load_requests.assert_not_called()


@pytest.mark.parametrize("resource,field,value", [("semesters", "semester_number", "abc"), ("programs", "duration_years", "NaN"), ("subjects", "credits", "inf")])
def test_invalid_academic_numbers_show_field_errors(resource, field, value):
    submit = Mock()
    view = build_academic_form(resource, LIGHT, submit, Mock())
    control = next(x for x in walk_controls(view) if x.key == f"academic-field-{field}")
    control.value = value
    button = next(x for x in walk_controls(view) if isinstance(x, ft.FilledButton))
    with patch.object(control, "update"):
        button.on_click(None)
    assert control.error
    submit.assert_not_called()


def test_report_export_button_awaits_export_and_file_picker():
    export = AsyncMock()
    view = build_session_detail({"sessionId": "session"}, LIGHT, Mock(), export)
    button = next(x for x in walk_controls(view) if isinstance(x, ft.OutlinedButton))
    assert inspect.iscoroutinefunction(button.on_click)
    asyncio.run(button.on_click(None))
    export.assert_awaited_once_with("sessions", "session")


def test_unavailable_admin_metrics_are_distinct_from_real_zeroes():
    view = build_admin_dashboard(LIGHT, show_setup_wizard=False, show_development_structure=False, api_connected=False)
    labels = [x.value for x in walk_controls(view) if isinstance(x, ft.Text)]
    assert labels.count("—") == 4 and "API Offline" in labels
    assert "API Connected" not in labels and "0" not in labels

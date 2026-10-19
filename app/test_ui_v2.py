"""V2 regression checks for real navigation, responsive controls and draft safety."""
from types import SimpleNamespace
from unittest.mock import Mock
import flet as ft
import pytest
from app.core.design import DESIGN, LIGHT, DARK, attendance_tone, adapt_view, walk_controls, prepare_dialog
from app.components.navigation import build_bottom_navigation, navigation_labels
from app.components.camera import CameraPanelState, build_camera_panel
from app.components.v2 import attendance_hero, notification_item
from app.main import PremiumUiController
from app.screens.admin.academic import build_setup_wizard
from app.screens.admin.dashboard import build_admin_dashboard
from app.screens.auth.login import build_login
from app.screens.faculty.attendance import build_take_attendance
from app.screens.student.dashboard import build_student_dashboard
from app.screens.phase13 import build_requests_page, build_notifications_page
from app.services.api_client import ApiResult
from app.test_flet_foundation import make_controller, has_key
from app.test_phase4_academic import authenticated_admin_controller


def texts(root):
    return [c.value for c in walk_controls(root) if isinstance(c, ft.Text)]


@pytest.mark.parametrize("width", [360, 390, 430, 600, 768, 1024, 1366, 1600])
@pytest.mark.parametrize("role", ["Admin", "Student", "Faculty"])
def test_shell_breakpoints_keep_navigation_accessible(width, role):
    controller, page, host = make_controller(width)
    controller.show_preview(role)
    controls = list(walk_controls(host.content))
    sidebar = next(c for c in controls if c.key == "role-sidebar")
    assert sidebar.visible == (width >= DESIGN.phone)
    assert sidebar.width == (DESIGN.rail_width if DESIGN.phone <= width < DESIGN.desktop else DESIGN.sidebar_width)
    bars = [c for c in controls if isinstance(c, ft.NavigationBar)]
    assert len(bars) == (1 if role != "Admin" and width < DESIGN.phone else 0)
    if bars:
        assert len(bars[0].destinations) == 5
    assert has_key(host.content, f"{role.casefold()}-dashboard")


@pytest.mark.parametrize("role", ["Student", "Faculty"])
def test_mobile_navigation_routes_real_destinations(role):
    selected = []
    bar = build_bottom_navigation(role, "Dashboard", LIGHT, selected.append)
    for index in range(5):
        bar.selected_index = index
        bar.on_change(SimpleNamespace(control=bar))
    assert selected == ["Dashboard", "Attendance" if role == "Student" else "Take Attendance", "Requests", "Notifications", "Profile"]
    assert all(label in navigation_labels(role) for label in selected)


def test_academic_hub_retains_all_advanced_crud_routes():
    controller, _, host = authenticated_admin_controller()
    controller.select_navigation("Academic Management")
    assert controller.academic_state.resource == "academic-years"
    assert has_key(host.content, "academic-management-hub")
    for resource in ("institution", "academic-years", "departments", "programs", "semesters", "classes", "subjects"):
        tab = next(c for c in walk_controls(host.content) if c.key == f"academic-tab-{resource}")
        tab.on_click(None)
        assert controller.academic_state.resource == resource


def test_search_uses_existing_student_endpoint_scope_and_preserves_unsaved_guard():
    controller, _, _ = make_controller()
    controller.current_role = "Admin"
    controller.load_students = Mock()
    controller.search_directory("  real query  ")
    controller.load_students.assert_called_once_with(search="real query")
    controller.load_students.reset_mock()
    controller.attendance_dirty = True
    controller.leave_attendance = Mock()
    controller.search_directory("other")
    controller.load_students.assert_not_called()
    controller.leave_attendance.assert_called_once()


def test_dashboard_missing_values_never_become_fake_zeroes():
    view = build_admin_dashboard(LIGHT, show_setup_wizard=False, show_development_structure=False)
    assert texts(view).count("—") == 4
    assert "Attendance analytics will appear after finalized sessions." in texts(view)
    assert not {"1248", "86", "87%", "92.4%", "1,248"}.intersection(texts(view))
    student = build_student_dashboard(LIGHT)
    assert "Attendance unavailable" in texts(student)


def test_admin_dashboard_enrichment_reads_existing_apis_only():
    controller, _, _ = make_controller()
    controller.current_screen, controller.current_role = "authenticated", "Admin"
    api = Mock()
    api.academic_institution.return_value = ApiResult(True, {"name": "Test institution", "timezone": "Asia/Kolkata"})
    api.list_academic.side_effect = [ApiResult(True, {"items": [{"name": "Current year"}]}), ApiResult(True, {"total": 3})]
    api.reports_overview.return_value = ApiResult(True, {"attendance": {"percentage": 80}})
    api.reports_trend.return_value = ApiResult(True, {"items": [{"date": "2026-10-19", "percentage": 80}]})
    api.reports_subjects.return_value = ApiResult(True, {"items": [{"subject": "Test subject", "percentage": 80}]})
    api.audit_events.return_value = ApiResult(True, {"items": []})
    api.list_timetable.return_value = ApiResult(True, {"items": []})
    controller.api_client = api
    controller.load_dashboard_overview()
    assert controller.dashboard_overview["class_count"] == 3
    assert controller.dashboard_overview["report"]["trend"][0]["percentage"] == 80
    assert controller.dashboard_overview["timetable_ready"] is False
    assert all(call[0] in {"academic_institution", "list_academic", "reports_overview", "reports_trend", "reports_subjects", "audit_events", "list_timetable"} for call in api.method_calls)


def test_setup_includes_actual_timetable_state_and_does_not_claim_completion_early():
    status = {"checks": {key: True for key in ("institution", "academicYear", "department", "program", "semester", "class", "subject")}}
    incomplete = build_setup_wizard(status, LIGHT, timetable_ready=False)
    complete = build_setup_wizard(status, LIGHT, timetable_ready=True)
    assert "88%" in texts(incomplete) and "Academic Setup Complete" not in texts(incomplete)
    assert "100%" in texts(complete) and "Academic Setup Complete" in texts(complete)


@pytest.mark.parametrize("tokens", [LIGHT, DARK])
def test_attendance_hero_uses_finalized_backend_percentage_and_eligible_counts(tokens):
    hero = attendance_hero({"attendancePercentage": 80, "present": 7, "late": 1, "absent": 2, "excused": 3}, tokens)
    assert "80%" in texts(hero) and "8" in texts(hero) and "10" in texts(hero)
    ring = next(c for c in walk_controls(hero) if isinstance(c, ft.ProgressRing))
    assert ring.value == .8
    assert "No attendance yet" in texts(attendance_hero({}, tokens))


@pytest.mark.parametrize("rate,threshold,tone", [(85, 75, "success"), (70, 75, "warning"), (40, 75, "danger"), (70, 65, "success")])
def test_attendance_status_thresholds_are_centralized(rate, threshold, tone):
    assert attendance_tone(rate, threshold) == tone


def test_face_roster_manual_actions_and_draft_review_are_preserved():
    marked, reviewed = [], []
    current = {"status": "draft", "records": [{"student_id": "s", "student_name": "Test Student", "roll_number": "1", "status": "unmarked"}],
               "summary": {"total": 1, "unmarked": 1}}
    view = build_take_attendance(LIGHT, {}, [], current, Mock(), Mock(), lambda sid, state:marked.append((sid,state)),
                                Mock(), lambda _:reviewed.append(True), mode="face")
    controls = list(walk_controls(view))
    for label in ("Present", "Absent", "Late", "Excused"):
        button = next(c for c in controls if isinstance(c, ft.OutlinedButton) and c.content == label)
        button.on_click(None)
    assert marked == [("s", value) for value in ("present", "absent", "late", "excused")]
    review = next(c for c in controls if isinstance(c, ft.FilledButton) and c.content == "Review Draft")
    assert review.disabled  # Unmarked students must be resolved before Faculty review.
    assert has_key(view, "faculty-face-attendance") and has_key(view, "attendance-student-s")
    assert any(isinstance(c, ft.SegmentedButton) for c in controls)


def test_camera_reuses_preview_and_progress_controls_across_layouts():
    state = CameraPanelState(purpose="attendance", recognized_count=2, roster_count=4)
    original = state.image
    for compact in (False, True):
        panel = build_camera_panel(state, LIGHT, Mock(), Mock(), compact=compact)
        assert any(c is original for c in walk_controls(panel))
        assert state.recognition_progress.value == .5
    state.recognized_count = 3
    state.sync()
    assert state.image is original and state.recognition_progress.value == .75


def test_large_roster_uses_native_lazy_list_without_losing_manual_actions():
    current = {"status": "draft", "records": [{"student_id": str(i), "student_name": "Test Student"} for i in range(30)],
               "summary": {"total": 30, "unmarked": 30}}
    view = build_take_attendance(LIGHT, {}, [], current, *([Mock()]*5))
    roster = next(c for c in walk_controls(view) if c.key == "virtualized-attendance-roster")
    assert isinstance(roster, ft.ListView) and roster.build_controls_on_demand
    assert len(roster.controls) == 30


@pytest.mark.parametrize("width", [360, 390, 430, 1366])
def test_forms_stack_fields_and_dialogs_remain_scrollable(width):
    control = adapt_view(ft.Row([ft.TextField(label="Name", width=500), ft.Dropdown(label="Class", width=300)]), width, LIGHT)
    if width < DESIGN.phone:
        assert isinstance(control, ft.Column)
        assert all(c.width is None for c in control.controls)
    dialog = prepare_dialog(ft.AlertDialog(content=ft.Container(ft.Column([ft.TextField(label="Field")]), width=760)),
                            SimpleNamespace(width=width, height=800, media=None), LIGHT)
    assert dialog.content.width <= width - 64
    assert dialog.content.content.scroll == ft.ScrollMode.AUTO


def test_phone_adapter_preserves_horizontal_step_scrolling():
    row = ft.Row([ft.TextButton(str(i)) for i in range(10)], scroll=ft.ScrollMode.AUTO)
    adapted = adapt_view(row, 360, LIGHT)
    assert adapted.scroll == ft.ScrollMode.AUTO and not adapted.wrap


def test_loading_and_empty_states_are_visible_and_notifications_keep_read_action():
    login = build_login(Mock(), LIGHT, ft.Text("Offline"), auth_loading=True)
    assert next(c for c in walk_controls(login) if c.key == "login-submit").disabled
    requests = build_requests_page("Student", LIGHT, {}, loading=True)
    assert has_key(requests, "loading-state")
    notifications = build_notifications_page(LIGHT, {"items": []})
    assert "No notifications" in texts(notifications)
    read = Mock()
    item = notification_item({"_id": "notice", "title": "Real update", "message": "Message", "created_at": "2026-10-19T10:00:00"}, LIGHT, read)
    button = next(c for c in walk_controls(item) if isinstance(c, ft.IconButton))
    button.on_click(None)
    read.assert_called_once_with("notice")

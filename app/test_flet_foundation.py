"""Regression coverage for the premium Phase 1.5 Flet foundation."""

from pathlib import Path
from unittest.mock import patch

import flet as ft
import pytest

from app.components.navigation import (
    build_navigation_drawer,
    build_sidebar,
    navigation_labels,
)
from app.components.ui import api_status_badge, metric_card
from app.core.theme import DARK, LIGHT, build_dark_theme, build_light_theme
from app.main import (
    PremiumUiController,
    build_authenticated_top_bar,
    build_dashboard,
    build_public_shell,
    build_role_switcher,
    main,
)
from app.screens.auth.login import build_login
from app.screens.auth.splash import build_splash
from app.screens.admin.academic import ACADEMIC_RESOURCES, build_academic_preview_page
from app.screens.admin.students import StudentPageState, build_students_page
from app.screens.student.dashboard import build_student_dashboard
from app.screens.faculty.dashboard import build_faculty_dashboard
from app.screens.admin.faculty import FacultyPageState,build_faculty_page
from app.screens.admin.timetable import TimetablePageState,build_timetable_form,build_timetable_page
from app.services.api_client import ApiResult


class FakePage:
    """Minimum page surface needed to exercise shell rendering."""

    def __init__(self, width: int = 1440) -> None:
        self.width = width
        self.controls: list[ft.Control] = []
        self.update_count = 0
        self.drawer = None
        self.on_resize = None
        self.theme_mode = ft.ThemeMode.LIGHT
        self.drawer_open_count = 0

    def add(self, *controls: ft.Control) -> None:
        self.controls.extend(controls)

    def update(self) -> None:
        self.update_count += 1

    def show_drawer(self) -> None:
        self.drawer_open_count += 1


def walk_controls(control: ft.Control | None):
    if control is None:
        return
    yield control
    content = getattr(control, "content", None)
    if isinstance(content, ft.Control):
        yield from walk_controls(content)
    for child in getattr(control, "controls", []) or []:
        if isinstance(child, ft.Control):
            yield from walk_controls(child)


def has_key(root: ft.Control | None, key: str) -> bool:
    return any(getattr(control, "key", None) == key for control in walk_controls(root))


def make_controller(width: int = 1440) -> tuple[PremiumUiController, FakePage, ft.Container]:
    page = FakePage(width)
    host = ft.Container(expand=True)
    controller = PremiumUiController(page, host)  # type: ignore[arg-type]
    return controller, page, host


def test_all_public_and_dashboard_components_construct_in_both_themes() -> None:
    no_event = lambda *_: None
    for tokens in (LIGHT, DARK):
        controls = [
            build_splash(no_event, tokens),
            build_login(no_event, tokens, api_status_badge(True, tokens)),
            build_dashboard("Admin", tokens),
            build_dashboard("Faculty", tokens),
            build_dashboard("Student", tokens),
            build_sidebar("Admin", tokens),
            build_navigation_drawer("Faculty", tokens),
            build_role_switcher("Student", no_event, no_event, tokens),
            build_authenticated_top_bar(
                "Admin",
                tokens,
                api_connected=True,
                on_sidebar_toggle=no_event,
                on_theme_toggle=no_event,
                on_api_check=no_event,
            ),
            build_public_shell(
                ft.Text("Public"),
                tokens,
                api_connected=True,
                on_theme_toggle=no_event,
                on_api_check=no_event,
            ),
            metric_card("Metric", "1", ft.Icons.BAR_CHART_OUTLINED, "Preview", tokens),
        ]
        assert all(isinstance(control, ft.Control) for control in controls)


def test_light_and_dark_themes_construct() -> None:
    assert isinstance(build_light_theme(), ft.Theme)
    assert isinstance(build_dark_theme(), ft.Theme)


def test_main_reaches_public_splash_without_authenticated_sidebar() -> None:
    page = FakePage()
    with patch(
        "app.main.ApiClient.health_check",
        return_value=ApiResult(connected=True, data={"status": "ok"}),
    ):
        controller = main(page)  # type: ignore[arg-type]

    assert controller.current_screen == "splash"
    assert has_key(controller.host.content, "public-shell")
    assert has_key(controller.host.content, "splash-screen")
    assert not has_key(controller.host.content, "authenticated-shell")
    assert not has_key(controller.host.content, "role-sidebar")


def test_login_uses_public_shell_without_authenticated_sidebar() -> None:
    controller, _, host = make_controller()
    controller.show_login()

    assert controller.current_role is None
    assert has_key(host.content, "public-shell")
    assert has_key(host.content, "login-screen")
    assert not has_key(host.content, "role-sidebar")


@pytest.mark.parametrize("role", ["Admin", "Faculty", "Student"])
def test_each_role_gets_only_its_navigation(role: str) -> None:
    controller, _, host = make_controller()
    controller.show_preview(role)

    assert controller.current_role == role
    assert has_key(host.content, "authenticated-shell")
    assert has_key(host.content, "role-sidebar")
    assert navigation_labels(role)[0] == "Dashboard"


def test_admin_academic_preview_pages_construct_and_are_role_isolated() -> None:
    pages = [
        build_academic_preview_page(resource, LIGHT, development_api_enabled=True)
        for resource, _, _ in ACADEMIC_RESOURCES
    ]
    assert len(pages) == 7
    assert all(isinstance(page, ft.Control) for page in pages)

    admin = build_dashboard("Admin", LIGHT, development_academic_api_enabled=True)
    faculty = build_dashboard("Faculty", LIGHT, development_academic_api_enabled=True)
    student = build_dashboard("Student", LIGHT, development_academic_api_enabled=True)
    assert has_key(admin, "admin-academic-structure")
    assert not has_key(faculty, "admin-academic-structure")
    assert not has_key(student, "admin-academic-structure")


def test_role_switching_replaces_navigation() -> None:
    controller, _, _ = make_controller()
    controller.show_preview("Admin")
    admin = navigation_labels("Admin")
    controller.show_preview("Faculty")
    faculty = navigation_labels("Faculty")
    controller.show_preview("Student")
    student = navigation_labels("Student")
    controller.show_preview("Admin")

    assert "Departments" in admin and "Departments" not in faculty
    assert "Take Attendance" in faculty and "Take Attendance" not in student
    assert "Upcoming Classes" in student and "Upcoming Classes" not in admin
    assert controller.current_role == "Admin"


def test_exit_preview_returns_to_public_login() -> None:
    controller, page, host = make_controller()
    controller.show_preview("Admin")
    controller.exit_preview()

    assert controller.current_screen == "login"
    assert controller.current_role is None
    assert page.drawer is None
    assert has_key(host.content, "login-screen")
    assert not has_key(host.content, "role-sidebar")


def test_active_role_is_visually_distinct() -> None:
    switcher = build_role_switcher("Faculty", lambda _: None, lambda *_: None, LIGHT)
    assert isinstance(switcher, ft.Row)
    assert isinstance(switcher.controls[1], ft.OutlinedButton)
    assert isinstance(switcher.controls[2], ft.FilledButton)
    assert isinstance(switcher.controls[3], ft.OutlinedButton)


def test_development_controls_are_disabled_outside_development() -> None:
    page = FakePage()
    controller = PremiumUiController(
        page, ft.Container(expand=True), development_preview_enabled=False
    )  # type: ignore[arg-type]
    controller.show_login()

    with pytest.raises(RuntimeError, match="Development preview is disabled"):
        controller.show_preview("Admin")
    assert controller.current_role is None
    assert not has_key(controller.host.content, "development-preview-panel")


def test_responsive_sidebar_for_desktop_tablet_and_phone() -> None:
    controller, page, host = make_controller(1440)
    controller.show_preview("Admin")
    desktop_sidebar = next(
        control for control in walk_controls(host.content) if control.key == "role-sidebar"
    )
    assert desktop_sidebar.visible is True

    page.width = 768
    controller.handle_resize()
    tablet_sidebar = next(
        control for control in walk_controls(host.content) if control.key == "role-sidebar"
    )
    assert tablet_sidebar.visible is False

    page.width = 390
    controller.handle_resize()
    controller.handle_sidebar_toggle()
    assert page.drawer_open_count == 1


def test_theme_toggle_rebuilds_current_screen() -> None:
    controller, page, host = make_controller()
    controller.show_preview("Student")
    controller.toggle_theme()
    assert page.theme_mode == ft.ThemeMode.DARK
    assert has_key(host.content, "student-dashboard")
    controller.toggle_theme()
    assert page.theme_mode == ft.ThemeMode.LIGHT


def test_removed_flet_api_patterns_do_not_return() -> None:
    app_root = Path(__file__).resolve().parent
    removed_patterns = (
        "ft.alignment.",
        "ft.colors.",
        "ft.icons.",
        "ft.border.",
        "ft.border_radius.",
        "ft.padding.",
        "ft.margin.",
        "page.on_resized",
        "drawer.open",
    )
    sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in app_root.rglob("*.py")
        if path != Path(__file__)
    )
    assert not any(pattern in sources for pattern in removed_patterns)


def test_production_student_dashboard_never_uses_preview_attendance() -> None:
    dashboard = build_student_dashboard(LIGHT, {"display_name": "Ada", "admission_number": "A-1", "email": "ada@example.test", "status": "active", "current_enrollment": {"roll_number": "7"}})
    text = " ".join(str(getattr(control, "value", "")) for control in walk_controls(dashboard))
    assert "Ada" in text and "Attendance not available yet" in text
    assert "82%" not in text and "Preview total" not in text


def test_admin_students_page_constructs_all_primary_states() -> None:
    callbacks = (lambda *_: None,) * 7
    states = [StudentPageState(loading=True), StudentPageState(), StudentPageState(items=[{"_id": "1", "display_name": "Ada", "admission_number": "A-1", "email": "a@b.test", "status": "active", "current_enrollment": {"roll_number": "7"}}])]
    assert all(build_students_page(state, LIGHT, *callbacks).key == "admin-students-page" for state in states)


def test_admin_students_navigation_rebuilds_without_api_calls_in_preview() -> None:
    controller, _, host = make_controller()
    controller.show_preview("Admin")
    controller.select_navigation("Students")
    assert controller.active_navigation == "Students"
    assert controller.student_state and controller.student_state.error
    assert has_key(host.content, "admin-students-page")

def test_production_faculty_dashboard_uses_real_assignments_without_preview_schedule():
    dashboard=build_faculty_dashboard(LIGHT,{"display_name":"Ada Faculty","employee_id":"EMP-1","designation":"Professor","department":{"name":"Computer Science"},"status":"active","assignments":[{"subject_id":"subject","class_division_id":"class","subject":{"name":"Data Structures"},"class_division":{"name":"Semester 4 · A"},"assignment_type":"primary","status":"active"}]})
    text=" ".join(str(getattr(control,"value","")) for control in walk_controls(dashboard))
    assert "Ada Faculty" in text and "No upcoming lecture" in text and "Data Structures" in text
    assert "Major Project - I" not in text and "Development preview" not in text

def test_admin_faculty_page_light_dark_mobile_and_navigation():
    callbacks=(lambda *_:None,)*7
    for tokens in (LIGHT,DARK):
        assert build_faculty_page(FacultyPageState(items=[{"_id":"1","display_name":"Ada","employee_id":"EMP-1","email":"a@b.test","status":"active"}]),tokens,*callbacks).key=="admin-faculty-page"
    controller,page,host=make_controller(width=390);controller.show_preview("Admin");controller.select_navigation("Faculty")
    assert controller.faculty_state and controller.faculty_state.error and has_key(host.content,"admin-faculty-page")

def test_phase7_admin_timetable_grid_list_form_and_mobile_navigation():
    entry={"_id":"entry","faculty_assignment_id":"assignment","faculty_id":"faculty","day_of_week":"monday","start_time":"09:00","end_time":"10:00","room":"A-101","lecture_type":"theory","status":"active","subject":{"name":"Data Structures"},"class_division":{"name":"Semester 4 A"}}
    callbacks=(lambda *_:None,)*5
    for tokens in (LIGHT,DARK):
        assert build_timetable_page(TimetablePageState(items=[entry],view="week",page=1,pages=1),tokens,*callbacks).key=="admin-timetable-page"
        assert build_timetable_page(TimetablePageState(items=[entry],view="list",page=1,pages=1),tokens,*callbacks).key=="admin-timetable-page"
    form=build_timetable_form(LIGHT,lambda *_:None,lambda *_:None,[{"_id":"faculty","display_name":"Ada"}],lambda _:[{"_id":"assignment","status":"active","subject":{"name":"DS"},"class_division":{"name":"A"}}])
    assert form.key=="timetable-form"
    controller,_,host=make_controller(width=390);controller.show_preview("Admin");controller.select_navigation("Timetable")
    assert controller.timetable_state and controller.timetable_state.error and has_key(host.content,"admin-timetable-page")

def test_phase7_real_faculty_and_student_dashboards_show_schedule_without_preview_values():
    lecture={"timetableEntryId":"entry","subject":{"name":"Data Structures"},"class":{"name":"Semester 4 A"},"date":"2026-08-11","startTime":"09:00","endTime":"10:00","room":"A-101","state":"upcoming"}
    schedule={"today":[lecture],"week":[lecture],"upcoming":[lecture],"nextLecture":lecture,"timezone":"Asia/Kolkata"}
    faculty=build_faculty_dashboard(LIGHT,{"display_name":"Ada","employee_id":"E1","status":"active","assignments":[]},schedule)
    student=build_student_dashboard(LIGHT,{"display_name":"Grace","admission_number":"A1","email":"g@example.test","status":"active","current_enrollment":{}},schedule)
    faculty_text=" ".join(str(getattr(c,"value","")) for c in walk_controls(faculty));student_text=" ".join(str(getattr(c,"value","")) for c in walk_controls(student))
    assert "Data Structures" in faculty_text and "Use Take Attendance in navigation" in faculty_text and "Major Project - I" not in faculty_text
    assert "Data Structures" in student_text and "82%" not in student_text

def test_phase7_faculty_and_student_timetable_navigation_is_active():
    faculty,_,faculty_host=make_controller();faculty.show_preview("Faculty");faculty.select_navigation("Timetable");assert faculty.active_navigation=="Timetable" and has_key(faculty_host.content,"faculty-dashboard")
    student,_,student_host=make_controller();student.show_preview("Student");student.select_navigation("Upcoming Classes");assert student.active_navigation=="Upcoming Classes" and has_key(student_host.content,"student-dashboard")

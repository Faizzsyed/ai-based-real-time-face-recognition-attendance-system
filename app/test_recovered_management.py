"""Workflow regressions for the recovered mobile management changes."""
import asyncio
from dataclasses import fields as dataclass_fields
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import flet as ft
import pytest

from app.components.forms import connect_hierarchy, validate
from app.core.design import adapt_view, walk_controls
from app.core.theme import LIGHT
from app.screens.admin.students import build_student_profile_form
from app.screens.student.attendance import build_student_attendance
from app.services.api_client import ApiResult
from app.test_management_audit import controller_for, session


def test_mobile_drawer_awaits_open_and_closes_before_navigation():
    controller, page, _ = controller_for("Faculty")
    page.show_drawer = AsyncMock()
    page.close_drawer = AsyncMock()
    controller.select_navigation = Mock()
    asyncio.run(controller.handle_sidebar_toggle())
    page.show_drawer.assert_awaited_once()
    asyncio.run(controller.select_drawer_navigation(SimpleNamespace(control=SimpleNamespace(selected_index=5))))
    page.close_drawer.assert_awaited_once()
    controller.select_navigation.assert_called_once_with("My Classes")


def test_failed_save_preserves_form_input_and_serialized_field_error():
    controller, page, _ = controller_for("Admin")
    page.show_dialog = Mock(); page.pop_dialog = Mock()
    save = Mock(return_value=ApiResult(False, error="Email already exists.", field_errors={"email": "Choose a different email."}))
    refresh = Mock()
    form = build_student_profile_form({"display_name": "Long Student Name", "email": "student@example.test"}, LIGHT,
                                     lambda payload: controller._save_form(lambda: save(payload), refresh, "Saved."), Mock())
    controller.show_dialog(ft.AlertDialog(content=form, modal=True))
    dialog = controller._dialogs[-1]
    email = next(x for x in walk_controls(dialog) if x.key == "field-email")
    button = next(x for x in walk_controls(dialog) if isinstance(x, ft.FilledButton))
    email.value = "other@example.test"
    button.on_click(None)
    assert email.value == "other@example.test" and email.error == "Choose a different email."
    assert "error" in {field.name for field in dataclass_fields(email)}
    page.pop_dialog.assert_not_called();refresh.assert_not_called()
    assert not button.disabled


def test_dialog_action_buttons_are_disabled_during_a_save():
    controller, page, _ = controller_for("Admin")
    page.show_dialog = Mock();page.pop_dialog = Mock()
    button = ft.FilledButton("Approve")
    controller.show_dialog(ft.AlertDialog(content=ft.Text("Review"), actions=[button]))
    def operation():
        assert button.disabled
        assert not controller._form_request(Mock()).connected
        return ApiResult(True, {})
    controller._form_request(operation)
    assert not button.disabled and not controller._form_busy


def test_hierarchy_clears_transitive_descendants_and_disables_incomplete_choices():
    fields = {name: ft.Dropdown(value=value) for name, value in
              (("academic_year_id", "year"), ("department_id", "old"), ("program_id", "program"),
               ("semester_id", "semester"), ("class_division_id", "class"))}
    records = {"program_id": [{"_id": "program", "department_id": "old", "name": "Program"}],
               "semester_id": [{"_id": "semester", "academic_year_id": "year", "program_id": "program"}],
               "class_division_id": [{"_id": "class", "academic_year_id": "year", "department_id": "old", "program_id": "program", "semester_id": "semester"}]}
    connect_hierarchy(fields, records)
    fields["department_id"].value = "new"
    fields["department_id"].on_select(None)
    assert all(fields[name].value is None for name in ("program_id", "semester_id", "class_division_id"))
    assert fields["semester_id"].disabled and fields["class_division_id"].disabled


@pytest.mark.parametrize("kind", [ft.TextField, ft.Dropdown])
def test_required_validation_uses_visible_flet_error_property(kind):
    control = kind()
    assert not validate({"email": control}, ("email",))
    assert (control.error_text if kind is ft.Dropdown else control.error) == "This field is required."


def test_leaving_dirty_attendance_requires_an_explicit_discard():
    controller, page, _ = controller_for("Faculty")
    page.show_dialog = Mock();page.pop_dialog = Mock()
    controller.current_attendance = session();controller.attendance_dirty = True
    leave = Mock()
    controller.leave_attendance(leave)
    leave.assert_not_called()
    controller._dialogs[-1].actions[-1].on_click(None)
    leave.assert_called_once();assert not controller.attendance_dirty


def test_finalized_roster_cannot_be_changed_or_submitted_again():
    controller, _, _ = controller_for("Faculty")
    controller.api_client = Mock();controller.current_attendance = {**session(), "status": "submitted"}
    controller.mark_attendance("one", "present")
    controller.submit_attendance()
    assert controller.current_attendance["records"][0]["status"] is None
    assert controller.api_client.mock_calls == []


def test_student_subject_names_and_history_actions_survive_mobile_adaptation():
    on_session = Mock()
    history = [{"session_id": "own-session", "subjectId": "internal-id", "subjectName": "Data Structures", "status": "present"}]
    view = adapt_view(build_student_attendance(LIGHT, {"summary": {"present": 1, "total": 1, "attendancePercentage": 100},
                     "subjects": [{"subjectId": "internal-id", "subjectName": "Data Structures", "attendancePercentage": 100}]},
                     history, on_session=on_session), 360, LIGHT)
    labels = [x.value for x in walk_controls(view) if isinstance(x, ft.Text)]
    assert "Data Structures" in labels and not any("internal-id" in str(label) for label in labels)
    next(x for x in walk_controls(view) if isinstance(x, ft.TextButton)).on_click(None)
    on_session.assert_called_once_with(history[0])


def test_reports_become_cards_without_losing_detail_actions():
    open_detail = Mock()
    table = ft.DataTable(columns=[ft.DataColumn(label=ft.Text("Student")), ft.DataColumn(label=ft.Text("Action"))],
                         rows=[ft.DataRow(cells=[ft.DataCell(ft.Text("Student One")), ft.DataCell(ft.TextButton("Open", on_click=open_detail))])])
    mobile = adapt_view(ft.Row([table]), 360, LIGHT)
    assert not any(isinstance(x, ft.DataTable) for x in walk_controls(mobile))
    next(x for x in walk_controls(mobile) if isinstance(x, ft.TextButton)).on_click(None)
    open_detail.assert_called_once()

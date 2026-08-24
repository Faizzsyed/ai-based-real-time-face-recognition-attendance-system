"""Phase 4 Admin academic management UI construction and routing tests."""

import flet as ft

from app.components.navigation import navigation_labels
from app.core.theme import DARK, LIGHT
from app.main import PremiumUiController
from app.screens.admin.academic import (
    AcademicPageState,
    FORM_FIELDS,
    build_academic_form,
    build_academic_management_page,
    build_confirmation_dialog,
    build_setup_wizard,
)
from app.services.api_client import ApiResult
from app.state.auth_state import AuthState
from app.test_auth_foundation import auth_payload
from app.test_flet_foundation import FakePage, has_key


class FakeAcademicApi:
    def __init__(self, state: AuthState, *, error: str | None = None):
        self.auth_state = state
        self.error = error

    def list_academic(self, resource, **filters):
        if self.error:
            return ApiResult(False, status_code=503, error=self.error)
        return ApiResult(True, {"items": [{"_id": "1", "name": "ECS", "code": "ECS", "status": "active"}], "page": filters.get("page", 1), "pageSize": 20, "total": 1, "totalPages": 1})

    def academic_institution(self):
        if self.error:
            return ApiResult(False, status_code=503, error=self.error)
        return ApiResult(True, {"_id": "i1", "name": "Demo Institution", "code": "DEMO", "country": "India", "timezone": "Asia/Kolkata", "status": "active"})

    def academic_setup_status(self):
        return ApiResult(True, {"state": "Partially Configured", "completed": 3, "total": 7, "checks": {"institution": True, "academicYear": True, "department": True}})

    def health_check(self):
        return ApiResult(True, {"status": "ok"})

    def logout(self):
        self.auth_state.clear()
        return ApiResult(True, {"success": True})


def authenticated_admin_controller(error=None):
    page = FakePage()
    host = ft.Container(expand=True)
    state = AuthState()
    state.authenticate(auth_payload("admin"))
    controller = PremiumUiController(page, host, auth_state=state, api_client=FakeAcademicApi(state, error=error))  # type: ignore[arg-type]
    controller.show_authenticated("Admin")
    return controller, page, host


def test_only_admin_navigation_contains_academic_setup_pages():
    admin = navigation_labels("Admin")
    for label in ("Institution", "Academic Years", "Departments", "Programs", "Semesters", "Classes & Divisions", "Subjects"):
        assert label in admin
        if label != "Subjects":
            assert label not in navigation_labels("Faculty")
            assert label not in navigation_labels("Student")
    # Student "Subjects" is an own-academic view, not the Admin management page.
    assert "Institution" not in navigation_labels("Faculty") and "Institution" not in navigation_labels("Student")


def test_real_admin_navigation_loads_production_management_page():
    controller, _, host = authenticated_admin_controller()
    controller.select_navigation("Departments")
    assert controller.active_navigation == "Departments"
    assert has_key(host.content, "admin-academic-departments")
    assert has_key(host.content, "academic-record-list")
    assert not has_key(host.content, "admin-academic-structure")


def test_database_unavailable_state_is_safe():
    controller, _, host = authenticated_admin_controller("The academic database is unavailable.")
    controller.select_navigation("Programs")
    assert has_key(host.content, "academic-api-error-state")
    assert not has_key(host.content, "academic-record-list")


def test_loading_empty_and_pagination_states_construct_in_both_themes():
    callbacks = []
    for tokens in (LIGHT, DARK):
        loading = build_academic_management_page(AcademicPageState("subjects", loading=True), tokens)
        empty = build_academic_management_page(AcademicPageState("departments"), tokens)
        paged = build_academic_management_page(AcademicPageState("programs", items=[{"_id": "1", "name": "BE ECS", "code": "BE-ECS", "status": "active"}], page=2, total=5, total_pages=3), tokens, on_page=callbacks.append)
        assert has_key(loading, "academic-loading-state")
        assert has_key(empty, "academic-empty-state")
        assert has_key(paged, "academic-record-list")


def test_create_and_edit_forms_construct_for_every_resource():
    references = {field: [("id", "Reference")] for fields in FORM_FIELDS.values() for field, _, kind in fields if kind == "reference"}
    for resource in FORM_FIELDS:
        create = build_academic_form(resource, LIGHT, lambda _: None, lambda _: None, references=references)
        record = {name: (True if kind == "bool" else "active" if kind == "status" else "theory" if kind == "subject_type" else "id" if kind == "reference" else 1 if kind in {"integer", "number"} else "Value") for name, _, kind in FORM_FIELDS[resource]}
        edit = build_academic_form(resource, DARK, lambda _: None, lambda _: None, record=record, references=references)
        assert has_key(create, f"academic-{resource}-form")
        assert has_key(edit, f"academic-{resource}-form")


def test_setup_wizard_and_confirmation_dialog_construct():
    status = {"state": "Partially Configured", "checks": {"institution": True, "academicYear": True}}
    assert has_key(build_setup_wizard(status, LIGHT), "academic-setup-wizard")
    dialog = build_confirmation_dialog("Deactivate?", "No records are deleted.", lambda _: None, lambda _: None)
    assert isinstance(dialog, ft.AlertDialog) and dialog.key == "academic-confirmation-dialog"


def test_admin_can_skip_setup_wizard_for_current_session():
    controller, _, host = authenticated_admin_controller()
    assert has_key(host.content, "academic-setup-wizard")
    controller.skip_setup_wizard()
    assert not has_key(host.content, "academic-setup-wizard")


def test_development_preview_academic_page_does_not_call_real_api():
    page = FakePage()
    host = ft.Container(expand=True)
    controller = PremiumUiController(page, host)  # type: ignore[arg-type]
    controller.show_preview("Admin")
    controller.select_navigation("Subjects")
    assert controller.current_screen == "preview"
    assert has_key(host.content, "admin-academic-subjects")
    assert has_key(host.content, "academic-api-error-state")

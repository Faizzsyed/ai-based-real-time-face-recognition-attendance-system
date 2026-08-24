"""Flet authentication state, role-shell, and controlled refresh tests."""

from unittest.mock import patch

import flet as ft
import httpx

from app.core.theme import LIGHT
from app.main import PremiumUiController
from app.screens.auth.login import build_login
from app.services.api_client import ApiClient
from app.state.auth_state import AuthState, AuthenticationStatus, MemoryTokenStorage
from app.test_flet_foundation import FakePage, has_key, walk_controls


def auth_payload(role="admin"):
    return {
        "accessToken": "access-one",
        "refreshToken": "refresh-one",
        "tokenType": "bearer",
        "expiresIn": 900,
        "user": {"id": "1", "institutionId": "2", "displayName": role.title(), "email": f"{role}@example.edu", "username": role, "role": role},
    }


def response(status: int, payload: dict) -> httpx.Response:
    return httpx.Response(status, json=payload)


def test_memory_storage_and_auth_state_lifecycle():
    storage = MemoryTokenStorage()
    state = AuthState(storage=storage)
    state.begin_login()
    assert state.loading and state.status == AuthenticationStatus.authenticating
    state.authenticate(auth_payload())
    assert state.is_authenticated and state.access_token == "access-one"
    state.clear()
    assert not state.is_authenticated and storage.load() == (None, None)


def test_api_login_populates_central_auth_state():
    state = AuthState()
    client = ApiClient(auth_state=state)
    with patch("httpx.request", return_value=response(200, {"success": True, "data": auth_payload("faculty")})):
        result = client.login("faculty", "Correct123")
    assert result.connected and state.current_user["role"] == "faculty"


def test_authenticated_request_refreshes_and_retries_once():
    state = AuthState()
    state.authenticate(auth_payload())
    refreshed = {**auth_payload(), "accessToken": "access-two", "refreshToken": "refresh-two"}
    responses = [
        response(401, {"error": {"message": "expired"}}),
        response(200, {"success": True, "data": refreshed}),
        response(200, {"success": True, "data": {"user": refreshed["user"]}}),
    ]
    with patch("httpx.request", side_effect=responses) as request:
        result = ApiClient(auth_state=state).get_me()
    assert result.connected and request.call_count == 3
    assert state.access_token == "access-two" and state.refresh_token == "refresh-two"
    assert request.call_args_list[2].kwargs["headers"]["Authorization"] == "Bearer access-two"


def test_refresh_failure_does_not_loop_and_clears_state():
    state = AuthState()
    state.authenticate(auth_payload())
    responses = [
        response(401, {"error": {"message": "expired"}}),
        response(401, {"error": {"message": "invalid refresh"}}),
    ]
    with patch("httpx.request", side_effect=responses) as request:
        result = ApiClient(auth_state=state).get_me()
    assert not result.connected and request.call_count == 2
    assert not state.is_authenticated and state.refresh_token is None


def test_login_fields_enable_submit_only_when_complete():
    submitted = []
    screen = build_login(lambda _: None, LIGHT, ft.Text("API"), on_login=lambda identifier, password: submitted.append((identifier, password)))
    controls = {control.key: control for control in walk_controls(screen) if getattr(control, "key", None)}
    identifier = controls["login-identifier"]
    password = controls["login-password"]
    button = controls["login-submit"]
    button.update = lambda: None
    identifier.value = "admin"
    identifier.on_change(None)
    assert button.disabled
    password.value = "Correct123"
    password.on_change(None)
    assert not button.disabled
    button.on_click(None)
    assert submitted == [("admin", "Correct123")]


def test_real_authenticated_shell_routes_role_without_preview_controls():
    for role in ("admin", "faculty", "student"):
        page = FakePage()
        host = ft.Container(expand=True)
        state = AuthState()
        state.authenticate(auth_payload(role))
        controller = PremiumUiController(page, host, auth_state=state)  # type: ignore[arg-type]
        controller.show_authenticated(role.title())
        assert has_key(host.content, f"{role}-dashboard")
        assert has_key(host.content, "role-sidebar")
        assert has_key(host.content, "authenticated-logout")
        assert not has_key(host.content, "development-role-switcher")


def test_real_logout_clears_state_and_returns_to_login():
    page = FakePage()
    host = ft.Container(expand=True)
    state = AuthState()
    state.authenticate(auth_payload())
    controller = PremiumUiController(page, host, auth_state=state)  # type: ignore[arg-type]
    controller.show_authenticated("Admin")
    with patch("httpx.request", return_value=response(200, {"success": True})):
        controller.logout()
    assert not state.is_authenticated and controller.current_screen == "login"
    assert has_key(host.content, "login-screen")

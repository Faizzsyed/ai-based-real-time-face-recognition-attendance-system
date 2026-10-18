"""Structural mobile checks; no physical Android device is required."""
import builtins
from unittest.mock import patch
import httpx
import flet as ft
from app.core.theme import tokens_for_mode
from app.main import build_public_shell,build_authenticated_top_bar
from app.screens.auth.login import build_login
from app.screens.auth.splash import build_splash
from app.screens.phase13 import build_requests_page,build_notifications_page,build_audit_page
from app.services.api_client import ApiClient
from app.services.camera_service import CameraService,CameraUnavailable
from app.services.platform_capabilities import current_platform
from app.test_flet_foundation import FakePage, make_controller
from app.main import main

TOKENS=tokens_for_mode(ft.ThemeMode.LIGHT)
def _walk(control):
    yield control
    content=getattr(control,"content",None)
    if isinstance(content,ft.Control): yield from _walk(content)
    for item in getattr(control,"controls",[]) or []:
        if isinstance(item,ft.Control): yield from _walk(item)
def test_compact_public_shell_has_short_title_and_scrollable_body():
    content=build_login(lambda _:None,TOKENS,ft.Text("Offline"),compact=True)
    shell=build_public_shell(content,TOKENS,api_connected=False,on_theme_toggle=lambda _:None,on_api_check=lambda _:None,compact=True)
    values=[getattr(item,"value",None) for item in _walk(shell)]
    assert "AI Attendance" in values and any(isinstance(item,ft.Column) and item.scroll==ft.ScrollMode.AUTO for item in _walk(shell))
def test_compact_splash_and_authenticated_header_construct_without_overflow_primitives():
    assert build_splash(lambda _:None,TOKENS,compact=True).key=="splash-screen"
    assert build_authenticated_top_bar("Student",TOKENS,api_connected=False,on_sidebar_toggle=lambda _:None,on_theme_toggle=lambda _:None,on_api_check=lambda _:None,compact=True)
def test_android_capabilities_do_not_enable_desktop_cv_or_client_liveness():
    caps=current_platform("android")
    assert caps.is_android and not caps.desktop_camera and not caps.client_liveness and caps.image_picker
def test_camera_service_does_not_import_opencv_until_desktop_camera_start(monkeypatch):
    service=CameraService()
    original=builtins.__import__
    def blocked(name,*args,**kwargs):
        if name=="cv2": raise ImportError("not installed")
        return original(name,*args,**kwargs)
    monkeypatch.setattr(builtins,"__import__",blocked)
    assert not service.running
    monkeypatch.setenv("FLET_PLATFORM","android")
    try:
        service.start()
    except CameraUnavailable:
        pass
    else: assert False
def test_backend_url_configuration_rejects_malformed_values():
    client=ApiClient(base_url="http://127.0.0.1:8000")
    assert not client.set_base_url("backend") and client.set_base_url("https://attendance.example.test/") and client.base_url=="https://attendance.example.test"
def test_phase13_mobile_views_stay_constructible():
    data={"items":[]}
    assert build_requests_page("Student",TOKENS,data,on_cancel=lambda _:None,on_review=lambda _:None)
    assert build_notifications_page(TOKENS,data,on_read=lambda _:None,on_read_all=lambda _:None)
    assert build_audit_page(TOKENS,data)


def test_compact_header_has_flexible_title_and_all_actions_in_menu():
    for mode in (ft.ThemeMode.LIGHT, ft.ThemeMode.DARK):
        tokens = tokens_for_mode(mode)
        shell = build_public_shell(ft.Text("Login"), tokens, api_connected=False,
            on_theme_toggle=lambda _: None, on_api_check=lambda _: None,
            on_server_settings=lambda _: None, compact=True)
        controls = list(_walk(shell))
        header = next(item for item in controls if item.key == "compact-public-header")
        assert header.controls[1].expand and header.controls[1].max_lines == 1
        menu = header.controls[2]
        assert isinstance(menu, ft.PopupMenuButton)
        assert len(menu.items) == 3 and all(item.on_click for item in menu.items)


def test_mobile_login_card_is_first_compact_and_has_readable_errors():
    for mode in (ft.ThemeMode.LIGHT, ft.ThemeMode.DARK):
        tokens = tokens_for_mode(mode)
        login = build_login(lambda _: None, tokens, ft.Text("Offline"), compact=True,
                            auth_error="Invalid credentials.", api_error="Backend timed out.")
        controls = list(_walk(login))
        assert next(item for item in controls if isinstance(item, ft.ResponsiveRow)).controls[0].content.key == "login-card"
        assert next(item for item in controls if item.key == "login-card").padding == 16
        assert next(item for item in controls if item.key == "login-submit").height >= 48
        assert all(next(item for item in controls if item.key == key).color == tokens["danger"] for key in ("login-error", "api-error"))


def test_keyboard_resize_preserves_focused_login_controls():
    controller, page, host = make_controller(width=390)
    controller.show_login()
    original = host.content
    identifier = next(item for item in _walk(original) if item.key == "login-identifier")
    identifier.value = "my-login"
    controller.handle_resize()
    assert host.content is original and identifier.value == "my-login"
    page.width = 1200
    controller.handle_resize()
    assert host.content is not original


def test_page_safe_area_avoids_all_system_bars():
    page = FakePage(width=360)
    with patch("httpx.get", return_value=httpx.Response(200, json={"status": "ok"})):
        main(page)
    safe = page.controls[0]
    assert isinstance(safe, ft.SafeArea)
    assert safe.avoid_intrusions_top and safe.avoid_intrusions_bottom
    assert safe.avoid_intrusions_left and safe.avoid_intrusions_right
    assert safe.maintain_bottom_view_padding


def test_login_http_failure_updates_api_badge_without_authenticating():
    controller, _, _ = make_controller(width=390)
    with patch("httpx.request", return_value=httpx.Response(401, json={"error": {"message": "Invalid credentials."}})):
        controller.handle_login("unknown", "incorrect")
    assert controller.api_connected and controller.current_screen == "login"
    assert controller.auth_state.error == "Invalid credentials."
    assert not controller.auth_state.is_authenticated


def test_api_badge_checks_backend_health_independently_of_database():
    controller, _, _ = make_controller(width=390)
    with patch("httpx.get", return_value=httpx.Response(200, json={"success": True, "status": "ok", "database": "disconnected"})) as get:
        controller.check_api()
    assert get.call_args.args[0].endswith("/api/v1/health")
    assert controller.api_connected and controller.api_error is None
    with patch("httpx.get", side_effect=httpx.ConnectError("private transport detail")):
        controller.check_api()
    assert not controller.api_connected and "private" not in controller.api_error

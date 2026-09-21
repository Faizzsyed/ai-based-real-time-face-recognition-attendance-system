"""Structural mobile checks; no physical Android device is required."""
import builtins
import flet as ft
from app.core.theme import tokens_for_mode
from app.main import build_public_shell,build_authenticated_top_bar
from app.screens.auth.login import build_login
from app.screens.auth.splash import build_splash
from app.screens.phase13 import build_requests_page,build_notifications_page,build_audit_page
from app.services.api_client import ApiClient
from app.services.camera_service import CameraService,CameraUnavailable
from app.services.platform_capabilities import current_platform

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

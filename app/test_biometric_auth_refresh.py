"""Central refresh/retry behavior for biometric and long-running multipart calls."""
import asyncio,logging,threading,time
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
import httpx
from app.services.api_client import ApiClient
from app.state.auth_state import AuthState
from app.main import PremiumUiController
from app.test_flet_foundation import FakePage
import flet as ft

def payload(access="access-old",refresh="refresh-old"):
    return {"accessToken":access,"refreshToken":refresh,"expiresIn":900,"user":{"id":"1","role":"admin"}}
def response(status,body):return httpx.Response(status,json=body)
def expired():return response(401,{"error":{"code":"AUTH_TOKEN_EXPIRED","message":"The access token has expired."}})

def test_face_enrollment_valid_token_uses_central_current_auth():
    state=AuthState();state.authenticate(payload())
    with patch("httpx.request",return_value=response(200,{"valid":True})) as request:result=ApiClient(auth_state=state).analyze_face("s1","f.jpg",b"image","image/jpeg")
    assert result.connected and request.call_args.kwargs["headers"]["Authorization"]=="Bearer access-old"

def test_expired_face_enrollment_refreshes_rotates_and_retries_with_new_token():
    state=AuthState();state.authenticate(payload());rotated=payload("access-new","refresh-new")
    with patch("httpx.request",side_effect=[expired(),response(200,{"success":True,"data":rotated}),response(200,{"valid":True})]) as request:result=ApiClient(auth_state=state).analyze_face("s1","f.jpg",b"image","image/jpeg")
    assert result.connected and request.call_count==3 and state.access_token=="access-new" and state.refresh_token=="refresh-new"
    assert request.call_args_list[0].kwargs["headers"]["Authorization"]=="Bearer access-old" and request.call_args_list[2].kwargs["headers"]["Authorization"]=="Bearer access-new"

def test_faculty_face_identification_has_same_refresh_path():
    state=AuthState();state.authenticate(payload());rotated=payload("access-new","refresh-new")
    with patch("httpx.request",side_effect=[expired(),response(200,{"success":True,"data":rotated}),response(200,{"result":"identified"})]) as request:result=ApiClient(auth_state=state).identify_attendance_face("session","f.jpg",b"image","image/jpeg")
    assert result.connected and result.data["result"]=="identified" and request.call_count==3

def test_concurrent_expired_requests_rotate_refresh_only_once():
    state=AuthState();state.authenticate(payload());client=ApiClient(auth_state=state);barrier=threading.Barrier(2);counts={"refresh":0};lock=threading.Lock()
    def send(method,url,headers=None,**kwargs):
        if url.endswith("/api/v1/auth/refresh"):
            with lock:counts["refresh"]+=1
            time.sleep(.04);return response(200,{"success":True,"data":payload("access-new","refresh-new")})
        if (headers or {}).get("Authorization")=="Bearer access-old":barrier.wait(timeout=2);return expired()
        return response(200,{"valid":True})
    with patch("httpx.request",side_effect=send):
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:client.analyze_face("s1","f.jpg",b"image","image/jpeg"),range(2)))
    assert all(x.connected for x in results) and counts["refresh"]==1

def test_refresh_failure_clears_auth_releases_camera_once_and_does_not_loop():
    state=AuthState();state.authenticate(payload());events=[]
    with patch("httpx.request",side_effect=[expired(),response(401,{"error":{"code":"AUTH_REFRESH_INVALID","message":"invalid"}})]) as request:result=ApiClient(auth_state=state,on_auth_lost=lambda:events.append("camera_released")).analyze_face("s1","f.jpg",b"image","image/jpeg")
    assert not result.connected and request.call_count==2 and not state.is_authenticated and events==["camera_released"]

def test_invalid_access_token_does_not_attempt_refresh_or_loop():
    state=AuthState();state.authenticate(payload());invalid=response(401,{"error":{"code":"AUTH_TOKEN_INVALID","message":"invalid"}})
    with patch("httpx.request",return_value=invalid) as request:result=ApiClient(auth_state=state).analyze_attendance_face("session","f.jpg",b"image","image/jpeg")
    assert not result.connected and request.call_count==1 and not state.is_authenticated

def test_camera_requests_resolve_token_at_request_time_and_logs_hide_tokens(caplog):
    state=AuthState();state.authenticate(payload());client=ApiClient(auth_state=state);state.update_tokens(payload("access-current","refresh-current"))
    with caplog.at_level(logging.INFO),patch("httpx.request",return_value=response(200,{"valid":True})) as request:assert client.analyze_face("s1","f.jpg",b"image","image/jpeg").connected
    assert request.call_args.kwargs["headers"]["Authorization"]=="Bearer access-current" and "access-current" not in caplog.text and "refresh-current" not in caplog.text

def test_controller_auth_loss_releases_camera_and_returns_to_login():
    class Page(FakePage):
        def run_task(self,handler,*args,**kwargs):return asyncio.run(handler(*args))
    class Camera:
        running=True
        def __init__(self):self.stops=0
        def stop(self):self.stops+=1;self.running=False
    controller=PremiumUiController(Page(),ft.Container());camera=Camera();controller.camera_service=camera;controller.camera_context="enrollment";controller._schedule_auth_lost()
    assert camera.stops>=1 and controller.current_screen=="login" and controller.auth_state.error=="Your session has expired. Please sign in again."

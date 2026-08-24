"""Deterministic tests for local camera lifecycle and development liveness."""
import time
import cv2,numpy as np
import flet as ft
from app.components.camera import CameraPanelState,build_camera_panel
from app.core.theme import tokens_for_mode
from app.screens.faculty.attendance import build_take_attendance
from app.main import PremiumUiController
from app.test_flet_foundation import FakePage
from app.services.camera_service import CameraService,CameraUnavailable
from app.services.liveness import DevelopmentLivenessChallenge

class Capture:
    def __init__(self,opened=True):self.opened=opened;self.released=False;self.reads=0
    def isOpened(self):return self.opened
    def read(self):self.reads+=1;return True,np.full((32,32,3),120,dtype=np.uint8)
    def release(self):self.released=True
def test_camera_starts_once_emits_jpeg_and_releases():
    capture=Capture();service=CameraService(capture_factory=lambda _:capture,preview_fps=30);service.start();service.start()
    for _ in range(30):
        frame,number=service.snapshot()
        if frame:break
        time.sleep(.01)
    service.stop();assert frame and number>0 and cv2.imdecode(np.frombuffer(frame,np.uint8),cv2.IMREAD_COLOR) is not None and capture.released
def test_camera_unavailable_is_safe_and_liveness_requires_distinct_ordered_frames():
    capture=Capture(False);service=CameraService(capture_factory=lambda _:capture)
    try:service.start();assert False
    except CameraUnavailable:pass
    assert capture.released
    class Ordered:
        def shuffle(self,values):pass
    challenge=DevelopmentLivenessChallenge(Ordered());assert challenge.steps==["center","left","right"]
    assert not challenge.observe("left","1");assert not challenge.observe("center","2");assert not challenge.observe("center","3");assert not challenge.observe("left","4");assert not challenge.observe("left","5");assert not challenge.observe("right","6");assert challenge.observe("right","7")
def test_flet_preview_state_and_authorized_reference_thumbnail_build():
    state=CameraPanelState();panel=build_camera_panel(state,tokens_for_mode(ft.ThemeMode.LIGHT),lambda _:None,lambda _:None);state.camera="connected";state.face="one_face";state.capture_count=2;state.sync();assert state.status_text.controls[0].content.controls[0].name==ft.Icons.CHECK_CIRCLE and "2 / 3" in state.progress_text.value
    session={"_id":"a","status":"draft","records":[{"student_id":"s","student_name":"Student","roll_number":"1"}],"summary":{"total":1,"unmarked":1}}
    control=build_take_attendance(tokens_for_mode(ft.ThemeMode.DARK),{},[],session,lambda *_:None,lambda *_:None,lambda *_:None,lambda *_:None,lambda *_:None,mode="face",recognition_mode="specific",selected_student_id="s",camera_panel=panel,reference_image=b"jpeg")
    def walk(item):
        yield item
        for child in getattr(item,"controls",[]) or []:yield from walk(child)
        for name in ("content","title","subtitle","trailing"):
            child=getattr(item,name,None)
            if isinstance(child,ft.Control):yield from walk(child)
    assert any(isinstance(item,ft.Image) and item.semantics_label=="Authorized roster enrollment reference" for item in walk(control))
def test_camera_is_released_on_navigation_and_logout():
    class Camera:
        running=False
        def __init__(self):self.stops=0
        def stop(self):self.stops+=1
    page=FakePage();controller=PremiumUiController(page,ft.Container())
    camera=Camera();controller.camera_service=camera;controller.current_role="Faculty";controller.current_screen="preview";controller.active_navigation="Take Attendance";controller.select_navigation("Dashboard");assert camera.stops==1
    controller.api_client=type("Api",(),{"logout":lambda self:None})()
    controller.logout();assert camera.stops>=2 and controller.current_screen=="login"

def test_temporary_read_failure_keeps_last_valid_frame_and_recovers():
    first=np.full((8,8,3),25,dtype=np.uint8);second=np.full((8,8,3),200,dtype=np.uint8)
    class FlakyCapture:
        def __init__(self):self.items=iter([(True,first),(False,None),(True,second),*( [(False,None)]*5 )]);self.released=False
        def isOpened(self):return True
        def set(self,*_):return True
        def read(self):return next(self.items,(False,None))
        def release(self):self.released=True
    capture=FlakyCapture();service=CameraService(capture_factory=lambda _:capture);service.start();time.sleep(.2);latest=service.raw_snapshot();service.stop();assert latest is not None and latest.sequence==2 and int(latest.image.mean())==200 and capture.released

def test_preview_retains_last_valid_jpeg_and_uses_gapless_playback():
    state=CameraPanelState();valid=b"valid-jpeg";assert state.accept_preview(valid);assert state.image.gapless_playback and state.image.src==valid and not state.placeholder.visible
    assert not state.accept_preview(None) and state.image.src==valid and state.last_valid_preview_frame==valid

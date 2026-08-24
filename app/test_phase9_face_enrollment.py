"""Flet Phase 9 privacy, capability, light/dark, and responsive construction tests."""
import flet as ft
from app.core.theme import tokens_for_mode
from app.screens.admin.face_enrollment import FaceEnrollmentState,build_face_enrollment_dialog,build_face_enrollment_page

def walk(control):
    yield control
    for child in getattr(control,"controls",[]) or []:yield from walk(child)
    content=getattr(control,"content",None)
    if content:yield from walk(content)
def noop(*_):pass
def test_face_page_builds_light_dark_and_enrollment_states():
    items=[{"_id":"s1","display_name":"Ada","admission_number":"A1","face":{"enrolled":True,"status":"active"}},{"_id":"s2","display_name":"Grace","admission_number":"A2","face":{"enrolled":False,"status":"not_enrolled"}}]
    for mode in (ft.ThemeMode.LIGHT,ft.ThemeMode.DARK):assert build_face_enrollment_page(FaceEnrollmentState(items=items),tokens_for_mode(mode),noop,noop,noop).key=="admin-face-enrollment"
def test_dialog_explains_consent_privacy_removal_and_camera_capability():
    dialog=build_face_enrollment_dialog({"display_name":"Ada","face":{"enrolled":True,"status":"active","method":"camera","captureCount":3}},tokens_for_mode(ft.ThemeMode.LIGHT),noop,noop,noop,noop);controls=list(walk(dialog));text=" ".join(str(getattr(x,"value","") or getattr(x,"label","") or getattr(x,"text","")) for x in controls);assert dialog.key=="face-enrollment-dialog" and "appropriate consent" in text and "not permanently retained" in text and "no built-in native camera" in text and any(getattr(x,"content",None)=="Remove Template" for x in controls)
def test_page_uses_responsive_controls_for_mobile_and_desktop():
    page=build_face_enrollment_page(FaceEnrollmentState(),tokens_for_mode(ft.ThemeMode.DARK),noop,noop,noop);assert any(isinstance(x,ft.ResponsiveRow) for x in walk(page))

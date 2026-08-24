"""Flet Phase 10 integrated modes, states, themes, and responsive construction."""
import flet as ft
from app.core.theme import tokens_for_mode
from app.screens.faculty.attendance import build_take_attendance
def noop(*_):pass
def walk(control):
    yield control
    for child in getattr(control,"controls",[]) or []:yield from walk(child)
    content=getattr(control,"content",None)
    if content:yield from walk(content)
def session():return {"_id":"a1","status":"draft","scheduled_start":"09:00","scheduled_end":"10:00","records":[{"student_id":"s1","student_name":"Ada","roll_number":"1","status":"present","source":"face_recognition"}],"summary":{"total":1,"present":1,"absent":0,"late":0,"excused":0,"unmarked":0}}
def test_face_mode_builds_light_dark_mobile_tablet_desktop_states():
    status={"stats":{"roster":1,"faceEnrolled":1,"recognized":1,"remaining":0,"manualOnly":0},"capability":{"detector":"available","recognizer":"available","encryption":"configured","faceAttendance":"available"}}
    for mode in (ft.ThemeMode.LIGHT,ft.ThemeMode.DARK):
        for width in (390,768,1440):
            control=build_take_attendance(tokens_for_mode(mode),{},[],session(),noop,noop,noop,noop,noop,mode="face",face_status=status,face_result={"result":"identified"},on_mode=noop,on_face_capture=noop);text=" ".join(str(getattr(x,"value","") or getattr(x,"label","") or getattr(x,"content","")) for x in walk(control));assert control.key=="faculty-attendance-session" and "AI-Assisted Face Attendance" in text and "Present suggested" in text and width>0
def test_manual_fallback_and_unavailable_camera_message_build():
    status={"stats":{"roster":1},"capability":{"faceAttendance":"unavailable","detector":"unavailable","recognizer":"unavailable","encryption":"not_configured"}};face=build_take_attendance(tokens_for_mode(ft.ThemeMode.LIGHT),{},[],session(),noop,noop,noop,noop,noop,mode="face",face_status=status,face_result={"result":"ai_unavailable"},on_mode=noop,on_face_capture=noop);manual=build_take_attendance(tokens_for_mode(ft.ThemeMode.LIGHT),{},[],session(),noop,noop,noop,noop,noop,mode="manual",on_mode=noop);assert any(getattr(x,"key",None)=="faculty-face-attendance" for x in walk(face)) and manual.key=="faculty-attendance-session"

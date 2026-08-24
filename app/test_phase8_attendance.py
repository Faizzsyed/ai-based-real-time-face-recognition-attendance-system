"""Flet construction tests for Phase 8 surfaces."""
import flet as ft
from app.core.theme import tokens_for_mode
from app.screens.admin.attendance import build_admin_attendance
from app.screens.faculty.attendance import build_take_attendance
from app.screens.student.attendance import build_student_attendance

def noop(*_):pass
def test_attendance_surfaces_build_in_light_and_dark():
    for mode in (ft.ThemeMode.LIGHT,ft.ThemeMode.DARK):
        tokens=tokens_for_mode(mode);student={"summary":{"total":4,"present":2,"absent":1,"late":1,"excused":0,"attendancePercentage":75},"subjects":[{"subjectId":"s1","attendancePercentage":75}]};history=[{"lectureDate":"2026-08-11","subjectId":"s1","status":"present"}]
        assert build_student_attendance(tokens,student,history).key=="student-attendance"
        assert build_admin_attendance(tokens,[{"_id":"x","lecture_date":"2026-08-11","scheduled_start":"09:00","faculty_id":"f","subject_id":"s","status":"submitted"}],None,noop,noop).key=="admin-attendance"
def test_faculty_attendance_builds_desktop_and_mobile_friendly_controls():
    for width in (390,1440):
        tokens=tokens_for_mode(ft.ThemeMode.LIGHT);schedule={"today":[{"timetableEntryId":"t1","date":"2026-08-11","startTime":"09:00","endTime":"10:00","room":"A1","subject":{"name":"Algorithms"}}]};control=build_take_attendance(tokens,schedule,[],None,noop,noop,noop,noop,noop);assert control.key=="faculty-take-attendance" and width>0
def test_faculty_roster_quick_status_controls_and_actions_build():
    tokens=tokens_for_mode(ft.ThemeMode.DARK);session={"_id":"a1","status":"draft","records":[{"student_id":"s1","student_name":"A Student","roll_number":"1","status":"present"}],"summary":{"total":1,"present":1,"absent":0,"late":0,"excused":0,"unmarked":0}};assert build_take_attendance(tokens,{},[],session,noop,noop,noop,noop,noop).key=="faculty-attendance-session"

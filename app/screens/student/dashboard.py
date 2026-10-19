"""Student home: attendance first, with a compact academic day."""
import flet as ft
from app.components.ui import page_header, empty_state, attendance_progress_card, status_badge
from app.components.v2 import attendance_hero, dashboard_section, schedule_timeline, notification_item
from app.core.design import ATTENDANCE_THRESHOLD


def build_student_dashboard(tokens, profile=None, schedule_data=None, attendance_data=None, *, notifications=None, requests=None):
    profile = profile or {}
    enrollment = profile.get("current_enrollment") or {}
    schedule_data = schedule_data or {}
    summary = (attendance_data or {}).get("summary") or {}
    threshold = float((attendance_data or {}).get("threshold", ATTENDANCE_THRESHOLD))
    program = enrollment.get("program") or profile.get("program") or {}
    semester = enrollment.get("semester") or profile.get("semester") or {}
    details = [program.get("name"), semester.get("label") or semester.get("name"),
               f"Roll {enrollment['roll_number']}" if enrollment.get("roll_number") else profile.get("admission_number")]
    hero = attendance_hero(summary, tokens, threshold) if attendance_data is not None else empty_state(
        "Attendance unavailable", "Open Attendance to load your finalized records.", ft.Icons.CLOUD_OFF_OUTLINED, tokens)
    subjects = [attendance_progress_card(x.get("subjectName") or "Subject", float(x.get("attendancePercentage") or 0),
                "Safe" if float(x.get("attendancePercentage") or 0) >= threshold else "Needs attention", tokens, threshold=threshold)
                for x in (attendance_data or {}).get("subjects", [])]
    return ft.Container(ft.Column([
        ft.Column([ft.Text("Welcome back,", size=14, color=tokens["text_secondary"]),
                   ft.Text(profile.get("display_name") or "Student", size=28, weight=ft.FontWeight.BOLD, color=tokens["text_primary"]),
                   ft.Text(" · ".join(str(x) for x in details if x) or "Your academic day, in one place.",
                           size=12, color=tokens["text_secondary"])], spacing=6),
        hero,
        ft.ResponsiveRow([
            dashboard_section("Subject Attendance", ft.Column(subjects or [empty_state("No subject attendance yet",
                "Your subject breakdown appears after sessions are finalized.", ft.Icons.MENU_BOOK_OUTLINED, tokens)], spacing=12),
                tokens, col={"xs":12,"lg":6}),
            dashboard_section("Today's Timetable", schedule_timeline(schedule_data.get("today") or [], tokens), tokens,
                schedule_data.get("timezone"), col={"xs":12,"lg":6}),
        ], spacing=20, run_spacing=20),
        dashboard_section("Recent Notifications", ft.Column([notification_item(x, tokens) for x in (notifications or {}).get("items", [])[:3]] or [
            empty_state("All quiet for now", "Your attendance and request updates will appear here.", ft.Icons.NOTIFICATIONS_NONE, tokens)], spacing=10), tokens),
    ], spacing=24, scroll=ft.ScrollMode.AUTO), padding=24, expand=True, key="student-dashboard")

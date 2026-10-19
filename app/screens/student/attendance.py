"""Student attendance, with real subject labels and finalized session history."""
import flet as ft
from app.components.ui import attendance_progress_card, empty_state, metric_card, page_header, section_header, status_badge, surface_card
from app.core.theme import ThemeTokens
from app.components.v2 import attendance_hero
from app.core.design import ATTENDANCE_THRESHOLD


def build_student_attendance(tokens: ThemeTokens, data: dict | None, history: list[dict] | None, *,
                             error: str | None = None, on_session=None) -> ft.Control:
    if data is None:
        return ft.Container(empty_state("Attendance unavailable", error or "Reopen Attendance to retry.",
                                        ft.Icons.ERROR_OUTLINE, tokens), padding=24, expand=True, key="student-attendance")
    summary = data.get("summary") or {}
    percentage = float(summary.get("attendancePercentage", 0))
    eligible = sum(summary.get(key, 0) for key in ("present", "late", "absent"))
    threshold = float(data.get("threshold", ATTENDANCE_THRESHOLD))
    rows = []
    for item in history or []:
        session_id = item.get("session_id") or item.get("sessionId")
        rows.append(surface_card(ft.Column([
            ft.Text(item.get("subjectName") or "Scheduled subject", weight=ft.FontWeight.W_600),
            ft.Text(str(item.get("lectureDate") or "Lecture")[:10], color=tokens["text_secondary"]),
            ft.Row([
                status_badge(str(item.get("status", "unmarked")).title(), tokens,
                             {"present": "success", "absent": "danger", "late": "warning"}.get(item.get("status"), "secondary")),
                *([ft.TextButton("View session", on_click=lambda _, row=item: on_session(row))] if on_session and session_id else []),
            ], wrap=True),
        ], spacing=8), tokens, padding=14))
    metrics = ft.ResponsiveRow([
        metric_card("Total Classes", str(summary.get("total", 0)), ft.Icons.MENU_BOOK_OUTLINED, "Finalized records", tokens, col={"xs": 6, "lg": 3}),
        metric_card("Present", str(summary.get("present", 0)), ft.Icons.CHECK_CIRCLE_OUTLINED, "On time", tokens, tone="success", col={"xs": 6, "lg": 3}),
        metric_card("Absent", str(summary.get("absent", 0)), ft.Icons.ERROR_OUTLINE, "Classes missed", tokens, tone="danger", col={"xs": 6, "lg": 3}),
        metric_card("Late / Excused", f"{summary.get('late', 0)} / {summary.get('excused', 0)}", ft.Icons.SCHEDULE, "Late counts attended", tokens, tone="warning", col={"xs": 6, "lg": 3}),
    ], spacing=12, run_spacing=12)
    ring = attendance_hero(summary, tokens, threshold)
    subject_cards = [attendance_progress_card(item.get("subjectName") or "Subject attendance",
                                              float(item.get("attendancePercentage", 0)),
                                              "Safe" if float(item.get("attendancePercentage", 0)) >= threshold else "Needs attention", tokens, threshold=threshold)
                     for item in data.get("subjects", [])]
    return ft.Container(ft.Column([
        page_header("My Attendance", "Your finalized classes, attendance, and correction history.", tokens),
        *([ft.Text(error, color=tokens["danger"])] if error else []), ring, metrics,
        surface_card(ft.Column([section_header("Subject Attendance", tokens), *(subject_cards or [empty_state(
            "No subject attendance", "Submitted sessions will appear here.", ft.Icons.QUERY_STATS, tokens)])], spacing=12), tokens),
        surface_card(ft.Column([section_header("Attendance History", tokens), *(rows or [empty_state(
            "No attendance history", "No finalized records are available.", ft.Icons.HISTORY, tokens)])], spacing=12), tokens),
    ], spacing=16, scroll=ft.ScrollMode.AUTO), padding=24, expand=True, key="student-attendance")

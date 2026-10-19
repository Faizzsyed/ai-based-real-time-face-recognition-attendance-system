"""Faculty home for the next lecture, drafts and assigned teaching work."""
import flet as ft
from app.components.ui import page_header, status_badge, empty_state, compact_list_row, surface_card
from app.components.v2 import dashboard_section, schedule_timeline, action_button


def build_faculty_dashboard(tokens, profile=None, schedule_data=None, attendance_data=None, *, on_attendance=None, requests=None):
    profile = profile or {}
    schedule = schedule_data or {}
    today = schedule.get("today") or []
    upcoming = schedule.get("nextLecture")
    assignments = [x for x in profile.get("assignments", []) if x.get("status") == "active"]
    drafts = sum(x.get("status") in {"draft", "reopened"} for x in (attendance_data or {}).get("sessions", []))
    next_card = surface_card(ft.Column([
        status_badge("NEXT LECTURE", tokens, "secondary", ft.Icons.SCHEDULE_OUTLINED),
        ft.Text((upcoming.get("subject") or {}).get("name", "Scheduled subject") if upcoming else "No upcoming lecture",
                size=26, weight=ft.FontWeight.BOLD, color=tokens["text_primary"]),
        *([schedule_timeline([upcoming], tokens)] if upcoming else [ft.Text("Your next scheduled lecture will appear here.", color=tokens["text_secondary"])]),
        action_button("Take Attendance", on_attendance, icon=ft.Icons.CO_PRESENT_OUTLINED),
        ft.Text("Use Take Attendance in navigation to start or continue a session." if on_attendance is None else
                "Recognition saves a draft. Review and finalize when your class is ready.", size=12, color=tokens["text_secondary"]),
    ], spacing=16), tokens, key="faculty-next-real-lecture")
    next_card.bgcolor = tokens["surface_accent"]
    rows = [compact_list_row((x.get("subject") or {}).get("name", "Assigned subject"),
             (x.get("class_division") or {}).get("name", "Assigned class"),
             status_badge(str(x.get("assignment_type", "primary")).replace("_", " ").title(), tokens, "secondary"),
             ft.Icons.CLASS_OUTLINED, tokens) for x in assignments]
    pending = [x for x in (requests or {}).get("items", []) if x.get("status") == "pending"]
    return ft.Container(ft.Column([
        page_header(f"Welcome, {profile.get('display_name') or 'Faculty'}", "A fresh day. A clear teaching plan.", tokens),
        next_card,
        ft.Row([status_badge(f"{len(today)} Today's Lectures", tokens),
                status_badge(f"{len(assignments)} Assigned Classes", tokens, "secondary"),
                status_badge(f"{drafts} Attendance Drafts", tokens, "warning")], wrap=True),
        ft.ResponsiveRow([
            dashboard_section("Today's Lectures", schedule_timeline(today, tokens), tokens, col={"xs":12,"lg":7}),
            dashboard_section("Assigned Classes and Subjects", ft.Column(rows or [empty_state("No active assignments",
                "Your administrator will assign your classes and subjects.", ft.Icons.CLASS_OUTLINED, tokens)], spacing=8),
                tokens, col={"xs":12,"lg":5}),
        ], spacing=20, run_spacing=20),
        dashboard_section("Pending Requests", ft.Column([ft.Text((x.get("student") or {}).get("displayName") or "Attendance correction",
            weight=ft.FontWeight.W_600) for x in pending[:5]] or [empty_state("No requests to review",
            "New correction requests will appear in your queue.", ft.Icons.TASK_ALT, tokens)], spacing=12), tokens),
    ], spacing=24, scroll=ft.ScrollMode.AUTO), padding=24, expand=True, key="faculty-dashboard")

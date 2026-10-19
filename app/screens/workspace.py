"""Real profile, teaching assignment, curriculum and timetable destinations."""
import flet as ft
from app.components.ui import empty_state, page_header, status_badge, surface_card
from app.components.v2 import identity_avatar, workflow_status, dashboard_section


def build_workspace(role, destination, profile, schedule, subjects, tokens, on_refresh, error=None, loading=False, on_navigate=None):
    profile = profile or {}
    body = [ft.Row([ft.Column([ft.Text(destination, size=26, weight=ft.FontWeight.BOLD),
                             ft.Text(f"{role} workspace", color=tokens["text_secondary"])], expand=True),
                   ft.IconButton(ft.Icons.REFRESH, tooltip="Refresh workspace", on_click=on_refresh)])]
    if loading:
        body.append(ft.ProgressBar())
    if error:
        body.append(surface_card(ft.Text(error, color=tokens["danger"]), tokens))
    if destination == "Profile":
        body.append(surface_card(ft.Column([
            identity_avatar(profile.get("display_name", role), tokens, 34),
            ft.Text(profile.get("display_name", role), size=22, weight=ft.FontWeight.BOLD),
            ft.Text(profile.get("email") or "Email not available"),
            ft.Text(profile.get("employee_id") or profile.get("admission_number") or role),
            workflow_status(profile.get("status", "active"), tokens),
            ft.Text("Contact your administrator to update your account details.", color=tokens["text_secondary"]),
        ], spacing=20), tokens, key="profile-card"))
        if on_navigate:
            destinations = ("Timetable", "Subjects", "Upcoming Classes") if role == "Student" else ("My Classes", "Timetable", "Attendance History", "Reports") if role == "Faculty" else ("Easy Setup", "Academic Management")
            body.append(dashboard_section("Your workspace", ft.Column([ft.OutlinedButton(label, icon=ft.Icons.CHEVRON_RIGHT, on_click=lambda _, target=label:on_navigate(target)) for label in destinations], spacing=8), tokens))
    elif destination == "My Classes":
        assignments = [x for x in profile.get("assignments", []) if x.get("status") == "active"]
        body.extend(surface_card(ft.Column([
            ft.Text((x.get("subject") or {}).get("name", "Assigned subject"), size=18, weight=ft.FontWeight.BOLD),
            ft.Text((x.get("class_division") or {}).get("name", "Assigned class")),
            status_badge(x.get("assignment_type", "primary").replace("_", " ").title(), tokens),
        ], spacing=10), tokens) for x in assignments)
        if not assignments:
            body.append(empty_state("No teaching assignments yet", "Your administrator will assign your classes and subjects.", ft.Icons.CLASS_OUTLINED, tokens))
    elif destination == "Subjects":
        body.extend(surface_card(ft.Column([
            ft.Text(x.get("name", "Subject"), size=18, weight=ft.FontWeight.BOLD),
            ft.Text(x.get("code", ""), color=tokens["text_secondary"]),
            status_badge(str(x.get("subject_type", "theory")).title(), tokens),
        ], spacing=10), tokens) for x in (subjects or []))
        if not subjects:
            body.append(empty_state("No subjects available", "Subjects appear when your current class curriculum is configured.", ft.Icons.MENU_BOOK_OUTLINED, tokens))
    else:
        key = "today" if destination == "Today's Lectures" else "upcoming" if destination == "Upcoming Classes" else "week"
        lectures = (schedule or {}).get(key) or []
        body.extend(surface_card(ft.Column([
            ft.Text((x.get("subject") or {}).get("name", "Scheduled subject"), size=18, weight=ft.FontWeight.BOLD),
            ft.Text(f"{x.get('date', '')}  ·  {x.get('startTime', '')} – {x.get('endTime', '')}"),
            ft.Text(f"{(x.get('class') or {}).get('name', 'Your class')}  ·  {x.get('room') or 'Room to be confirmed'}", color=tokens["text_secondary"]),
            status_badge(x.get("state", "upcoming").replace("-window", "").title(), tokens),
        ], spacing=10), tokens) for x in lectures)
        if not lectures:
            body.append(empty_state("No timetable entries available", "Your administrator will publish your teaching schedule.", ft.Icons.CALENDAR_MONTH_OUTLINED, tokens))
    return ft.Container(ft.Column(body, spacing=16, scroll=ft.ScrollMode.AUTO), padding=24, expand=True,
                        key=f"{role.casefold()}-{destination.casefold().replace(' ', '-')}")

"""Institution dashboard built entirely from existing, scoped API responses."""
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import flet as ft
from app.components.ui import metric_card, page_header, status_badge, empty_state, surface_card
from app.components.v2 import dashboard_section, quick_action, schedule_timeline
from app.screens.admin.academic import build_academic_structure_preview, build_setup_wizard


def build_admin_dashboard(tokens, development_api_enabled=False, setup_status=None, on_setup_step=None,
                          show_development_structure=True, show_setup_wizard=True, on_skip_setup=None,
                          attendance_data=None, dashboard_data=None, api_connected=False, *,
                          overview=None, on_navigate=None, display_name="Admin", loading=False):
    data = dashboard_data or {}
    overview = overview or {}
    report = overview.get("report") or {}
    stats = report.get("attendance") or {}
    institution = overview.get("institution") or {}
    try:
        today = datetime.now(ZoneInfo(institution.get("timezone") or "Asia/Kolkata"))
    except (ZoneInfoNotFoundError, ValueError):
        today = datetime.now()
    year = overview.get("year") or {}
    semester = overview.get("semester") or {}
    context = [today.strftime("%A, %d %B %Y"), year.get("name"), semester.get("label")]
    header = ft.ResponsiveRow([
        ft.Column([page_header(f"Welcome back, {display_name}!", institution.get("name") or "Your institution at a glance.", tokens)], col={"xs":12,"lg":7}),
        ft.Column([ft.Text(str(value), size=12, color=tokens["text_secondary"]) for value in context if value],
                  col={"xs":12,"lg":5}, spacing=5, horizontal_alignment=ft.CrossAxisAlignment.END),
    ], run_spacing=12)
    metrics = [
        ("Total Students", data.get("totalStudents", "—"), ft.Icons.PEOPLE_OUTLINED, "Active students", "primary"),
        ("Total Faculty", data.get("totalFaculty", "—"), ft.Icons.SCHOOL_OUTLINED, "Active faculty", "secondary"),
        ("Classes", overview.get("class_count", "—"), ft.Icons.CLASS_OUTLINED, "Active classes & divisions", "primary"),
        ("Attendance Rate", f"{stats['percentage']:g}%" if stats.get("percentage") is not None else "—",
         ft.Icons.QUERY_STATS, "Finalized sessions only", "success"),
    ]
    kpis = ft.ResponsiveRow([metric_card(title, str(value), icon, caption, tokens, tone=tone,
        col={"xs":6,"lg":3}) for title,value,icon,caption,tone in metrics], spacing=16, run_spacing=16)
    trend = report.get("trend") or []
    if isinstance(trend, dict): trend = trend.get("items") or []
    analytics = ft.Column([ft.Row([
        ft.Text(str(x.get("date", ""))[:10], width=80, size=11, color=tokens["text_secondary"]),
        ft.ProgressBar(value=max(0,min(1,float(x.get("percentage") or 0)/100)), expand=True,
                       color=tokens["secondary"], bgcolor=tokens["secondary_soft"], bar_height=8, border_radius=6),
        ft.Text(f"{x.get('percentage', 0) or 0:g}%", width=52, size=12),
    ], spacing=12) for x in trend[-7:] if x.get("percentage") is not None], spacing=16) if trend else empty_state(
        "A clearer picture, with every class", "Attendance analytics will appear after finalized sessions.", ft.Icons.INSIGHTS_OUTLINED, tokens)
    subjects = [x for x in report.get("subjects", []) if x.get("percentage") is not None]
    if subjects:
        analytics = ft.Column([analytics, ft.Divider(color=tokens["border"]),
            *[ft.Column([ft.Row([ft.Text(x.get("subject") or "Subject", expand=True, size=13),
                ft.Text(f"{x['percentage']:g}%", size=12, weight=ft.FontWeight.W_600)], spacing=8),
                ft.ProgressBar(value=max(0,min(1,float(x["percentage"])/100)), color=tokens["primary"],
                    bgcolor=tokens["primary_soft"], bar_height=6, border_radius=6)], spacing=8) for x in subjects[:4]]], spacing=16)
    lectures = schedule_timeline(overview.get("lectures") or [], tokens) if "lectures" in overview else empty_state(
        "Timetable unavailable", "Open Timetable to load your published lectures.", ft.Icons.CALENDAR_MONTH_OUTLINED, tokens)
    navigate = lambda label: (lambda _: on_navigate(label)) if on_navigate else None
    actions = dashboard_section("Quick Actions", ft.ResponsiveRow([
        quick_action("Add Student", ft.Icons.PERSON_ADD_ALT_1_OUTLINED, navigate("add-student"), tokens),
        quick_action("Add Faculty", ft.Icons.PERSON_ADD_OUTLINED, navigate("add-faculty"), tokens, tone="secondary"),
        quick_action("Start Easy Setup", ft.Icons.AUTO_FIX_HIGH, navigate("Easy Setup"), tokens, tone="secondary"),
        quick_action("Create Timetable", ft.Icons.CALENDAR_MONTH_OUTLINED, navigate("create-timetable"), tokens),
    ], spacing=12, run_spacing=12), tokens, "Everything you need to keep moving", col={"xs":12,"lg":4})
    activity = overview.get("activity") or []
    rows = [ft.Container(ft.Row([ft.Icon(ft.Icons.HISTORY, color=tokens["secondary"], size=18),
        ft.Column([ft.Text(str(x.get("action") or "Activity").replace("_", " ").replace(".", " · ").title(), size=13,
                           weight=ft.FontWeight.W_600),
                   ft.Text(str(x.get("created_at") or "")[:19].replace("T", " · "), size=11, color=tokens["text_secondary"])],
                  expand=True, spacing=5)], spacing=12), padding=ft.Padding.symmetric(vertical=10)) for x in activity[:5]]
    body = [header, *([ft.ProgressBar()] if loading else []), kpis]
    if not data:
        body.append(ft.Text("Dashboard statistics are unavailable. Reopen Dashboard to retry.", color=tokens["text_secondary"], size=12))
    if show_setup_wizard:
        setup = build_setup_wizard(setup_status, tokens, on_setup_step, on_skip_setup,
                                  timetable_ready=overview.get("timetable_ready"))
    else:
        setup = dashboard_section("Academic Management", ft.Column([
            ft.Text("Manage your institution, curriculum and class structure.", color=tokens["text_secondary"]),
            ft.FilledButton("Open Easy Setup", on_click=navigate("Easy Setup"), disabled=on_navigate is None),
        ], spacing=12), tokens)
    setup.col = {"xs":12,"lg":5}
    body.extend([
        ft.ResponsiveRow([setup, dashboard_section("Attendance Overview", analytics, tokens,
            "Based on official, finalized attendance", col={"xs":12,"lg":7}, key="admin-attendance-analytics")], spacing=20, run_spacing=20),
        ft.ResponsiveRow([actions, dashboard_section("Upcoming Lectures", lectures, tokens,
            "Published timetable", col={"xs":12,"lg":4}),
            dashboard_section("Recent Activity", ft.Column(rows, spacing=0) if rows else empty_state(
                "Nothing to catch up on" if "activity" in overview else "Activity unavailable", "Institution activity will appear here as work gets done.", ft.Icons.HISTORY, tokens),
                tokens, col={"xs":12,"lg":4})], spacing=20, run_spacing=20),
        ft.Row([status_badge(data.get("attendanceToday", "Session status unavailable"), tokens, "info"),
                status_badge(f"{data['pendingRequests']} pending requests" if "pendingRequests" in data else "Requests unavailable", tokens, "warning"),
                status_badge("API Connected" if api_connected else "API Offline", tokens, "success" if api_connected else "warning"),
                status_badge("Database Available" if setup_status else "Database Status Unavailable", tokens, "success" if setup_status else "warning"),
                status_badge("Face AI Not Checked", tokens, "info")], wrap=True),
    ])
    if show_development_structure:
        body.append(build_academic_structure_preview(tokens, development_api_enabled))
    return ft.Container(ft.Column(body, spacing=24, scroll=ft.ScrollMode.AUTO), padding=24, expand=True, key="admin-dashboard")

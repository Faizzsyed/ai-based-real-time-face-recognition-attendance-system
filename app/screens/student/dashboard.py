"""Premium static Student dashboard preview."""

import flet as ft

from app.components.ui import (
    attendance_progress_card,
    compact_list_row,
    empty_state,
    metric_card,
    page_header,
    section_header,
    status_badge,
    surface_card,
)
from app.core.theme import ThemeTokens

SUMMARY = (("Present Days", "41"), ("Absent Days", "9"), ("Total Classes", "50"))
SUBJECTS = (("Major Project", 88, "Safe"), ("Data Structures", 79, "Watch"), ("IoT Systems", 81, "Safe"))


def build_student_dashboard(tokens: ThemeTokens, profile: dict | None = None, schedule_data: dict | None = None, attendance_data: dict | None = None) -> ft.Control:
    if profile is not None:
        enrollment = profile.get("current_enrollment") or {}
        schedule_data=schedule_data or {};upcoming=schedule_data.get("upcoming") or [];today=schedule_data.get("today") or [];week=schedule_data.get("week") or []
        upcoming_rows=[compact_list_row((x.get("subject") or {}).get("name","Subject"),f"{x.get('date')} · {x.get('startTime')}–{x.get('endTime')} · {x.get('room') or 'Room not set'}",status_badge(x.get("state","upcoming").title(),tokens,"success" if x.get("state")=="active" else "primary"),ft.Icons.EVENT_NOTE_OUTLINED,tokens) for x in upcoming[:8]]
        today_rows=[compact_list_row((x.get("subject") or {}).get("name","Subject"),f"{x.get('startTime')}–{x.get('endTime')} · {x.get('room') or 'Room not set'}",status_badge(x.get("state","upcoming").replace("-window","").title(),tokens,"success" if x.get("state")=="active" else "primary"),ft.Icons.TODAY,tokens) for x in today]
        week_rows=[compact_list_row((x.get("subject") or {}).get("name","Subject"),f"{x.get('date')} · {x.get('startTime')}–{x.get('endTime')}",status_badge(x.get("lectureType","theory").title(),tokens,"secondary"),ft.Icons.CALENDAR_VIEW_WEEK,tokens) for x in week]
        return ft.Container(
            ft.Column([
                page_header(f"Hi, {profile.get('display_name', 'Student')}", "Your verified Student identity and current academic enrollment.", tokens),
                surface_card(ft.Column([
                    section_header("Student Profile", tokens),
                    ft.Text(f"Admission number: {profile.get('admission_number', '—')}", color=tokens["text_primary"]),
                    ft.Text(f"Email: {profile.get('email', '—')}", color=tokens["text_secondary"]),
                    ft.Text(f"Roll number: {enrollment.get('roll_number', 'Not enrolled')}", color=tokens["text_secondary"]),
                    status_badge(str(profile.get("status", "inactive")).title(), tokens, "success" if profile.get("status") == "active" else "warning"),
                ], spacing=10), tokens),
                ft.ResponsiveRow([surface_card(ft.Column([section_header("Today",tokens,schedule_data.get("timezone")),*(today_rows or [empty_state("No classes today","Your class has no active lectures today.",ft.Icons.EVENT_AVAILABLE,tokens)])],spacing=8),tokens,col={"xs":12,"lg":6}),surface_card(ft.Column([section_header("Week",tokens),*(week_rows or [empty_state("No weekly schedule","Your class timetable has no active entries this week.",ft.Icons.CALENDAR_MONTH_OUTLINED,tokens)])],spacing=8),tokens,col={"xs":12,"lg":6})]),
                surface_card(ft.Column([section_header("Upcoming Classes",tokens,schedule_data.get("timezone")),*(upcoming_rows or [empty_state("No upcoming classes","Your class timetable has no upcoming entries.",ft.Icons.EVENT_AVAILABLE,tokens)])],spacing=8),tokens),
                attendance_progress_card("Overall Attendance",float((attendance_data.get("summary") or {}).get("attendancePercentage",0)),"Safe" if float((attendance_data.get("summary") or {}).get("attendancePercentage",0))>=75 else "Watch",tokens) if attendance_data is not None else empty_state("Attendance not available yet", "Real attendance data is currently unavailable. No preview figures are shown in production sessions.", ft.Icons.FACT_CHECK_OUTLINED, tokens),
            ], spacing=18, scroll=ft.ScrollMode.AUTO), padding=24, expand=True, key="student-dashboard")
    overall = surface_card(
        ft.ResponsiveRow(
            [
                ft.Container(
                    ft.Stack(
                        [
                            ft.ProgressRing(
                                value=0.82,
                                width=132,
                                height=132,
                                stroke_width=11,
                                color=tokens["success"],
                                bgcolor=tokens["success_soft"],
                                semantics_label="Overall attendance",
                                semantics_value=82,
                            ),
                            ft.Container(
                                ft.Column(
                                    [
                                        ft.Text("82%", size=30, weight=ft.FontWeight.BOLD, color=tokens["text_primary"]),
                                        ft.Text("Overall", size=11, color=tokens["text_secondary"]),
                                    ],
                                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                    spacing=1,
                                ),
                                width=132,
                                height=132,
                                alignment=ft.Alignment.CENTER,
                            ),
                        ],
                        width=132,
                        height=132,
                    ),
                    alignment=ft.Alignment.CENTER,
                    col={"xs": 12, "md": 4},
                ),
                ft.Container(
                    ft.Column(
                        [
                            section_header("Overall Attendance", tokens, "Development preview through today"),
                            status_badge("Safe", tokens, "success", ft.Icons.CHECK_CIRCLE_OUTLINED),
                            ft.Text("You are 7 percentage points above the preview minimum threshold.", size=12, color=tokens["text_secondary"]),
                            ft.ProgressBar(value=0.82, color=tokens["success"], bgcolor=tokens["success_soft"], bar_height=9, border_radius=8, semantics_label="Overall attendance", semantics_value=82),
                        ],
                        spacing=12,
                    ),
                    col={"xs": 12, "md": 8},
                ),
            ],
            spacing=16,
            run_spacing=16,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        tokens,
        key="student-overall-attendance",
    )

    metrics = ft.ResponsiveRow(
        [
            metric_card("Present Days", "41", ft.Icons.TASK_ALT, "Preview total", tokens, tone="success", col={"xs": 12, "sm": 4}),
            metric_card("Absent Days", "9", ft.Icons.ERROR_OUTLINE, "Preview total", tokens, tone="danger", col={"xs": 12, "sm": 4}),
            metric_card("Total Classes", "50", ft.Icons.MENU_BOOK_OUTLINED, "Preview total", tokens, tone="primary", col={"xs": 12, "sm": 4}),
        ],
        spacing=14,
        run_spacing=14,
    )

    subject_section = surface_card(
        ft.Column(
            [
                section_header("Subject Attendance", tokens, "Preview performance by subject"),
                *[attendance_progress_card(subject, percentage, status, tokens) for subject, percentage, status in SUBJECTS],
            ],
            spacing=12,
        ),
        tokens,
    )

    activity = ft.ResponsiveRow(
        [
            surface_card(
                ft.Column(
                    [
                        section_header("Upcoming Classes", tokens),
                        compact_list_row("Major Project - I", "10:30 AM · Lab 4", status_badge("Next", tokens, "primary"), ft.Icons.EVENT_NOTE_OUTLINED, tokens),
                        compact_list_row("Data Structures", "12:00 PM · A-301", status_badge("Later", tokens, "secondary"), ft.Icons.MENU_BOOK_OUTLINED, tokens),
                    ],
                    spacing=8,
                ),
                tokens,
                col={"xs": 12, "lg": 6},
            ),
            surface_card(
                ft.Column(
                    [
                        section_header("Recent Attendance", tokens),
                        compact_list_row("Major Project", "Today · 10:30 AM", status_badge("Present", tokens, "success"), ft.Icons.CHECK_CIRCLE_OUTLINED, tokens),
                        compact_list_row("IoT Systems", "Yesterday · 2:00 PM", status_badge("Present", tokens, "success"), ft.Icons.CHECK_CIRCLE_OUTLINED, tokens),
                        compact_list_row("Data Structures", "Monday · 12:00 PM", status_badge("Absent", tokens, "danger"), ft.Icons.ERROR_OUTLINE, tokens),
                    ],
                    spacing=8,
                ),
                tokens,
                col={"xs": 12, "lg": 6},
            ),
        ],
        spacing=14,
        run_spacing=14,
    )

    requests = surface_card(
        ft.Column(
            [
                section_header("Requests", tokens),
                empty_state("No pending requests", "Your request activity will appear here after Phase 13 integration.", ft.Icons.SUPPORT_AGENT_OUTLINED, tokens),
            ],
            spacing=12,
        ),
        tokens,
    )

    return ft.Container(
        content=ft.Column(
            [
                page_header("Hi, Student", "Here’s your attendance and academic overview.", tokens),
                overall,
                metrics,
                subject_section,
                activity,
                requests,
                ft.Text("All attendance and academic values are development-preview data.", size=11, color=tokens["text_secondary"]),
            ],
            spacing=18,
            scroll=ft.ScrollMode.AUTO,
        ),
        padding=24,
        expand=True,
        key="student-dashboard",
    )

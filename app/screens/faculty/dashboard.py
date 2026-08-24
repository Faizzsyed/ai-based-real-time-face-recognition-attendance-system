"""Faculty schedule and attendance activity dashboard."""

import flet as ft

from app.components.ui import (
    compact_list_row,
    empty_state,
    lecture_card,
    page_header,
    section_header,
    status_badge,
    surface_card,
)
from app.core.theme import ThemeTokens

LECTURES = (
    ("Major Project - I", "10:30 AM – 11:30 AM", "Lab 4"),
    ("Data Structures", "12:00 PM – 1:00 PM", "A-301"),
    ("IoT Systems", "2:00 PM – 3:00 PM", "Lab 2"),
)


def build_faculty_dashboard(tokens: ThemeTokens, profile: dict | None = None, schedule_data: dict | None = None, attendance_data: dict | None = None) -> ft.Control:
    if profile is not None:
        assignments=profile.get("assignments") or []
        schedule_data=schedule_data or {};today=schedule_data.get("today") or [];week=schedule_data.get("week") or [];next_lecture=schedule_data.get("nextLecture")
        rows=[compact_list_row((item.get("subject") or {}).get("name",f"Subject {item.get('subject_id','—')}"),(item.get("class_division") or {}).get("name",f"Class {item.get('class_division_id','—')}"),status_badge(str(item.get("assignment_type","primary")).replace("_"," ").title(),tokens,"primary"),ft.Icons.CLASS_OUTLINED,tokens) for item in assignments if item.get("status")=="active"]
        sessions=(attendance_data or {}).get("sessions") or [];drafts=sum(1 for x in sessions if x.get("status") in {"draft","reopened"})
        next_card=surface_card(ft.Column([section_header("Next Lecture",tokens,schedule_data.get("timezone")),ft.Text((next_lecture.get("subject") or {}).get("name","No upcoming lecture") if next_lecture else "No upcoming lecture",size=22,weight=ft.FontWeight.BOLD),ft.Text(f"{next_lecture.get('date')} · {next_lecture.get('startTime')}–{next_lecture.get('endTime')} · {next_lecture.get('room') or 'Room not set'}" if next_lecture else "Your next scheduled lecture will appear here."),status_badge(f"{drafts} Attendance Drafts",tokens,"warning" if drafts else "success"),ft.Text("Use Take Attendance in navigation to start or continue a session.",size=11,color=tokens["text_secondary"])],spacing=10),tokens,key="faculty-next-real-lecture")
        today_rows=[compact_list_row((x.get("subject") or {}).get("name","Subject"),f"{x.get('startTime')}–{x.get('endTime')} · {x.get('room') or 'Room not set'}",status_badge(x.get("state","upcoming").replace("-window","").title(),tokens,"success" if x.get("state")=="active" else "primary"),ft.Icons.SCHEDULE,tokens) for x in today]
        week_rows=[compact_list_row((x.get("subject") or {}).get("name","Subject"),f"{x.get('date','')} · {x.get('startTime')}–{x.get('endTime')}",status_badge(x.get("lectureType","theory").title(),tokens,"secondary"),ft.Icons.CALENDAR_VIEW_WEEK,tokens) for x in week]
        return ft.Container(ft.Column([page_header(f"Welcome, {profile.get('display_name','Faculty')}","Your verified teaching schedule and attendance activity.",tokens),next_card,ft.ResponsiveRow([surface_card(ft.Column([section_header("Today",tokens),*(today_rows or [empty_state("No lectures today","There are no active timetable entries for today.",ft.Icons.EVENT_AVAILABLE,tokens)])],spacing=8),tokens,col={"xs":12,"lg":6}),surface_card(ft.Column([section_header("Week",tokens),*(week_rows or [empty_state("No weekly schedule","An Admin has not created timetable entries yet.",ft.Icons.CALENDAR_MONTH_OUTLINED,tokens)])],spacing=8),tokens,col={"xs":12,"lg":6})]),surface_card(ft.Column([section_header("Assigned Classes and Subjects",tokens),*(rows or [empty_state("No active assignments","An Admin has not assigned a Class and Subject yet.",ft.Icons.CLASS_OUTLINED,tokens)])],spacing=9),tokens)],spacing=18,scroll=ft.ScrollMode.AUTO),padding=24,expand=True,key="faculty-dashboard")
    next_lecture = surface_card(
        ft.Column(
            [
                ft.Row(
                    [
                        status_badge("NEXT LECTURE", tokens, "primary", ft.Icons.SCHEDULE_OUTLINED),
                        ft.Text("Development preview", size=11, color=tokens["text_secondary"]),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                ft.Text("Major Project - I", size=25, weight=ft.FontWeight.BOLD, color=tokens["text_primary"]),
                ft.Text("BE ECS · Semester 8 · Division A", color=tokens["text_secondary"]),
                ft.ResponsiveRow(
                    [
                        ft.Container(
                            ft.Row([ft.Icon(ft.Icons.SCHEDULE_OUTLINED, color=tokens["primary"]), ft.Text("10:30 AM – 11:30 AM", weight=ft.FontWeight.W_600, color=tokens["text_primary"])], spacing=8),
                            col={"xs": 12, "sm": 6},
                        ),
                        ft.Container(
                            ft.Row([ft.Icon(ft.Icons.LOCATION_ON_OUTLINED, color=tokens["secondary"]), ft.Text("Lab 4", weight=ft.FontWeight.W_600, color=tokens["text_primary"])], spacing=8),
                            col={"xs": 12, "sm": 6},
                        ),
                    ],
                    spacing=8,
                    run_spacing=8,
                ),
                ft.Row(
                    [
                        status_badge("19 Students", tokens, "secondary", ft.Icons.GROUP_OUTLINED),
                        status_badge("Face status unavailable", tokens, "warning", ft.Icons.FACE_RETOUCHING_NATURAL),
                    ],
                    wrap=True,
                ),
                ft.FilledButton(
                    "Take Attendance · Coming in a later phase",
                    icon=ft.Icons.CO_PRESENT_OUTLINED,
                    disabled=True,
                ),
            ],
            spacing=14,
        ),
        tokens,
        key="faculty-next-lecture",
    )

    schedule = surface_card(
        ft.Column(
            [
                section_header("Today's Schedule", tokens, "Compact preview timeline"),
                lecture_card("Data Structures", "12:00 PM – 1:00 PM", "A-301", tokens),
                lecture_card("IoT Systems", "2:00 PM – 3:00 PM", "Lab 2", tokens),
            ],
            spacing=12,
        ),
        tokens,
        col={"xs": 12, "lg": 7},
    )

    classes = surface_card(
        ft.Column(
            [
                section_header("Assigned Classes", tokens),
                compact_list_row("BE ECS · Division A", "Major Project - I", status_badge("19", tokens, "primary"), ft.Icons.CLASS_OUTLINED, tokens),
                compact_list_row("SE CSE · Division B", "Data Structures", status_badge("42", tokens, "primary"), ft.Icons.CLASS_OUTLINED, tokens),
                compact_list_row("TE ECS · Division A", "IoT Systems", status_badge("36", tokens, "primary"), ft.Icons.CLASS_OUTLINED, tokens),
            ],
            spacing=8,
        ),
        tokens,
        col={"xs": 12, "lg": 5},
    )

    previews = ft.ResponsiveRow(
        [
            surface_card(
                ft.Column(
                    [
                        section_header("Attendance Sessions", tokens),
                        empty_state("No live sessions", "Attendance sessions will appear after Phase 8 is enabled.", ft.Icons.FACT_CHECK_OUTLINED, tokens),
                    ],
                    spacing=12,
                ),
                tokens,
                col={"xs": 12, "md": 6},
            ),
            surface_card(
                ft.Column(
                    [
                        section_header("Pending Requests", tokens),
                        empty_state("You're all caught up", "Faculty requests will appear after data integration.", ft.Icons.SUPPORT_AGENT_OUTLINED, tokens),
                    ],
                    spacing=12,
                ),
                tokens,
                col={"xs": 12, "md": 6},
            ),
        ],
        spacing=14,
        run_spacing=14,
    )

    return ft.Container(
        content=ft.Column(
            [
                page_header("Good afternoon, Faculty", "Here’s your teaching schedule for today.", tokens),
                next_lecture,
                ft.ResponsiveRow([schedule, classes], spacing=14, run_spacing=14),
                previews,
                ft.Text("Schedule and class details are development-preview data.", size=11, color=tokens["text_secondary"]),
            ],
            spacing=18,
            scroll=ft.ScrollMode.AUTO,
        ),
        padding=24,
        expand=True,
        key="faculty-dashboard",
    )

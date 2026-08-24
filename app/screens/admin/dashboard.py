"""Premium static Admin dashboard preview; no live data is used."""

import flet as ft

from app.components.ui import (
    compact_list_row,
    metric_card,
    mini_bar_chart,
    page_header,
    section_header,
    status_badge,
    surface_card,
)
from app.core.theme import ThemeTokens
from app.screens.admin.academic import build_academic_structure_preview, build_setup_wizard

METRICS = (
    ("Total Students", "1,248", ft.Icons.PEOPLE_OUTLINED, "Preview enrolment", "primary"),
    ("Total Faculty", "86", ft.Icons.SCHOOL_OUTLINED, "Preview workforce", "secondary"),
    ("Attendance Today", "91%", ft.Icons.FACT_CHECK_OUTLINED, "2.4% above preview avg.", "success"),
    ("Face Enrolled", "734", ft.Icons.FACE_RETOUCHING_NATURAL, "59% preview coverage", "warning"),
)


def _department_row(name: str, students: int, attendance: int, tokens: ThemeTokens) -> ft.Control:
    return ft.Column(
        [
            ft.Row(
                [
                    ft.Text(name, weight=ft.FontWeight.W_600, color=tokens["text_primary"]),
                    ft.Text(f"{students} students · {attendance}%", size=11, color=tokens["text_secondary"]),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            ft.ProgressBar(
                value=attendance / 100,
                color=tokens["primary"],
                bgcolor=tokens["primary_soft"],
                bar_height=7,
                border_radius=6,
                semantics_label=f"{name} attendance",
                semantics_value=attendance,
            ),
        ],
        spacing=7,
    )


def build_admin_dashboard(
    tokens: ThemeTokens,
    development_api_enabled: bool = False,
    setup_status: dict | None = None,
    on_setup_step=None,
    show_development_structure: bool = True,
    show_setup_wizard: bool = True,
    on_skip_setup=None,
    attendance_data: dict | None = None,
) -> ft.Control:
    database_connected = setup_status is not None
    metrics=METRICS
    if attendance_data is not None:
        sessions=attendance_data.get("items") or [];submitted=sum(1 for x in sessions if x.get("status") in {"submitted","locked"});metrics=(*METRICS[:2],("Attendance Today",str(submitted),ft.Icons.FACT_CHECK_OUTLINED,"Submitted or locked sessions","success"),*METRICS[3:])
    kpis = ft.ResponsiveRow(
        [
            metric_card(
                title,
                value,
                icon,
                caption,
                tokens,
                tone=tone,
                col={"xs": 12, "sm": 6, "xl": 3},
            )
            for title, value, icon, caption, tone in metrics
        ],
        spacing=14,
        run_spacing=14,
    )

    secondary = ft.ResponsiveRow(
        [
            metric_card(
                "Active Lectures",
                "12",
                ft.Icons.PLAY_LESSON_OUTLINED,
                "Across 7 preview departments",
                tokens,
                tone="primary",
                col={"xs": 12, "sm": 6},
            ),
            metric_card(
                "Pending Requests",
                "18",
                ft.Icons.PENDING_ACTIONS_OUTLINED,
                "5 marked high priority",
                tokens,
                tone="warning",
                col={"xs": 12, "sm": 6},
            ),
        ],
        spacing=14,
        run_spacing=14,
    )

    analytics = ft.ResponsiveRow(
        [
            surface_card(
                ft.Column(
                    [
                        section_header("Attendance Overview", tokens, "Seven-day development preview"),
                        mini_bar_chart((72, 88, 81, 96, 84, 102, 110), tokens),
                        ft.Row(
                            [
                                status_badge("91% today", tokens, "success", ft.Icons.TRENDING_UP),
                                ft.Text("Preview data", size=11, color=tokens["text_secondary"]),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                    ],
                    spacing=14,
                ),
                tokens,
                col={"xs": 12, "lg": 7},
            ),
            surface_card(
                ft.Column(
                    [
                        section_header("Department Overview", tokens, "Attendance and student volume"),
                        _department_row("ECS", 326, 93, tokens),
                        _department_row("CSE", 412, 91, tokens),
                        _department_row("IT", 286, 88, tokens),
                        _department_row("Mechanical", 224, 86, tokens),
                    ],
                    spacing=15,
                ),
                tokens,
                col={"xs": 12, "lg": 5},
            ),
        ],
        spacing=14,
        run_spacing=14,
    )

    operations = ft.ResponsiveRow(
        [
            surface_card(
                ft.Column(
                    [
                        section_header("Active Lectures", tokens),
                        compact_list_row("Major Project - I", "ECS · Semester 8 · Lab 4", status_badge("Live", tokens, "success"), ft.Icons.PLAY_LESSON_OUTLINED, tokens),
                        compact_list_row("Data Structures", "CSE · Semester 4 · A-301", status_badge("12:00", tokens, "primary"), ft.Icons.MENU_BOOK_OUTLINED, tokens),
                        compact_list_row("IoT Systems", "ECS · Semester 6 · Lab 2", status_badge("14:00", tokens, "primary"), ft.Icons.WAVES_OUTLINED, tokens),
                    ],
                    spacing=8,
                ),
                tokens,
                col={"xs": 12, "lg": 6},
            ),
            surface_card(
                ft.Column(
                    [
                        section_header("Pending Requests", tokens),
                        compact_list_row("Attendance correction", "Student · 12 min ago", status_badge("High", tokens, "danger"), ft.Icons.SUPPORT_AGENT_OUTLINED, tokens),
                        compact_list_row("Timetable adjustment", "Faculty · 38 min ago", status_badge("Medium", tokens, "warning"), ft.Icons.CALENDAR_MONTH_OUTLINED, tokens),
                        compact_list_row("Profile update", "Student · 1 hr ago", status_badge("Normal", tokens, "primary"), ft.Icons.PERSON_OUTLINED, tokens),
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

    systems = surface_card(
        ft.Column(
            [
                section_header("System & Face AI Status", tokens, "Safe Phase 1 configuration"),
                ft.ResponsiveRow(
                    [
                        ft.Container(status_badge("API Connected", tokens, "success", ft.Icons.CLOUD_DONE_OUTLINED), col={"xs": 12, "sm": 4}),
                        ft.Container(status_badge("Face AI Not Configured", tokens, "warning", ft.Icons.FACE_RETOUCHING_NATURAL), col={"xs": 12, "sm": 4}),
                        ft.Container(status_badge("Database Connected" if database_connected else "Database Not Configured", tokens, "success" if database_connected else "warning", ft.Icons.STORAGE_OUTLINED), col={"xs": 12, "sm": 4}),
                    ],
                    spacing=10,
                    run_spacing=10,
                ),
            ],
            spacing=14,
        ),
        tokens,
    )

    return ft.Container(
        content=ft.Column(
            [
                page_header("Welcome back, Admin", "Here’s what’s happening across your institution today.", tokens),
                kpis,
                secondary,
                analytics,
                operations,
                systems,
                *([build_setup_wizard(setup_status, tokens, on_step=on_setup_step, on_skip=on_skip_setup)] if show_setup_wizard else []),
                *([build_academic_structure_preview(tokens, development_api_enabled)] if show_development_structure else []),
                ft.Text("Student, Faculty, attendance, and Face AI values remain clearly labeled preview data.", size=11, color=tokens["text_secondary"]),
            ],
            spacing=18,
            scroll=ft.ScrollMode.AUTO,
        ),
        padding=24,
        expand=True,
        key="admin-dashboard",
    )

"""Live, institution-scoped Admin dashboard controls."""

import flet as ft

from app.components.ui import metric_card, page_header, section_header, status_badge, surface_card
from app.core.theme import ThemeTokens
from app.screens.admin.academic import build_academic_structure_preview, build_setup_wizard


def build_admin_dashboard(
    tokens: ThemeTokens,
    development_api_enabled: bool = False,
    setup_status: dict | None = None,
    on_setup_step=None,
    show_development_structure: bool = True,
    show_setup_wizard: bool = True,
    on_skip_setup=None,
    attendance_data: dict | None = None,
    dashboard_data: dict | None = None,
    api_connected: bool = False,
) -> ft.Control:
    """Render only values returned for the authenticated Admin institution."""
    database_connected = setup_status is not None
    dashboard_data = dashboard_data or {}
    metrics = (
        ("Total Students", str(dashboard_data.get("totalStudents", "—")), ft.Icons.PEOPLE_OUTLINED, "Active institution enrolment", "primary"),
        ("Total Faculty", str(dashboard_data.get("totalFaculty", "—")), ft.Icons.SCHOOL_OUTLINED, "Active institution workforce", "secondary"),
        ("Attendance Today", str(dashboard_data.get("attendanceToday", "—")), ft.Icons.FACT_CHECK_OUTLINED, "Sessions scheduled today", "success"),
        ("Pending Requests", str(dashboard_data.get("pendingRequests", "—")), ft.Icons.PENDING_ACTIONS_OUTLINED, "Requires review", "warning"),
    )
    kpis = ft.ResponsiveRow(
        [
            metric_card(title, value, icon, caption, tokens, tone=tone, col={"xs": 6, "sm": 6, "xl": 3})
            for title, value, icon, caption, tone in metrics
        ],
        spacing=14,
        run_spacing=14,
    )
    systems = surface_card(
        ft.Column(
            [
                section_header("System & Face AI Status", tokens, "Current environment configuration"),
                ft.ResponsiveRow(
                    [
                        ft.Container(status_badge("API Connected" if api_connected else "API Offline", tokens, "success" if api_connected else "warning", ft.Icons.CLOUD_DONE_OUTLINED), col={"xs": 12, "sm": 4}),
                        ft.Container(status_badge("Face AI Not Checked", tokens, "warning", ft.Icons.FACE_RETOUCHING_NATURAL), col={"xs": 12, "sm": 4}),
                        ft.Container(status_badge("Database Available" if database_connected else "Database Status Unavailable", tokens, "success" if database_connected else "warning", ft.Icons.STORAGE_OUTLINED), col={"xs": 12, "sm": 4}),
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
                page_header("Welcome back, Admin", "Here is your institution's current activity.", tokens),
                surface_card(ft.Column([
                    section_header("Easy Setup", tokens, "Set up your academic structure step-by-step in a few minutes."),
                    ft.FilledButton("Start Easy Setup",icon=ft.Icons.AUTO_FIX_HIGH,on_click=(lambda _:on_setup_step("easy-setup")) if on_setup_step else None),
                ],spacing=12),tokens,key="admin-easy-setup-entry"),
                *([build_setup_wizard(setup_status, tokens, on_step=on_setup_step, on_skip=on_skip_setup)] if show_setup_wizard else []),
                kpis,
                *([ft.Text("Dashboard statistics are unavailable. Reopen Dashboard to retry.", color=tokens["danger"])] if not dashboard_data else []),
                systems,
                *([build_academic_structure_preview(tokens, development_api_enabled)] if show_development_structure else []),
            ],
            spacing=18,
            scroll=ft.ScrollMode.AUTO,
        ),
        padding=24,
        expand=True,
        key="admin-dashboard",
    )

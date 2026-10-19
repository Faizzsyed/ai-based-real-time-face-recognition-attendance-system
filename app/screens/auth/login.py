"""Premium public login screen with real authentication and isolated UI previews."""

from collections.abc import Callable

import flet as ft

from app.components.ui import status_badge, surface_card
from app.components.branding import PROJECT_TITLE, attendai_emblem
from app.core.theme import ThemeTokens
from app.core.design import RADIUS, TYPOGRAPHY

PHASE_NOTICE = "Preview sessions are UI-only and never create authentication tokens."


def _academic_visual(tokens: ThemeTokens, compact: bool = False) -> ft.Control:
    nodes = [
        (ft.Icons.SCHOOL_OUTLINED, "Academic management"),
        (ft.Icons.FACT_CHECK_OUTLINED, "Attendance intelligence"),
        (ft.Icons.FACE_OUTLINED, "Face recognition attendance"),
    ]
    return ft.Column(
        [
            ft.Row([attendai_emblem(tokens, 52 if compact else 62), ft.Text("AttendAI", size=22 if compact else 24, weight=ft.FontWeight.BOLD, color=tokens["text_primary"])], spacing=12,wrap=True),
            ft.Text(PROJECT_TITLE, size=14, color=tokens["text_secondary"]),
            ft.Text("Less admin.\nMore learning.", size=30 if compact else 38, weight=ft.FontWeight.BOLD, color=tokens["text_primary"]),
            ft.Text("A simpler way to bring your people, academic schedules, and attendance together.", size=14, color=tokens["text_secondary"]),
            ft.Column(
                [
                    ft.Row(
                        [
                            ft.Container(ft.Icon(icon, size=19, color=tokens["primary"]), width=40, height=40, alignment=ft.Alignment.CENTER, bgcolor=tokens["primary_soft"], border_radius=12),
                            ft.Text(label, weight=ft.FontWeight.W_600, color=tokens["text_primary"]),
                        ],
                        spacing=12,
                    )
                    for icon, label in nodes
                ],
                spacing=12,
            ),
        ],
        spacing=22,
    )


def _development_panel(
    on_preview: Callable[[str], None],
    tokens: ThemeTokens,
) -> ft.Control:
    return ft.Container(
        content=ft.Column(
            [
                ft.Row(
                    [
                        status_badge("DEVELOPMENT ONLY", tokens, "warning", ft.Icons.LOCK_OUTLINED),
                        ft.Text("Static role previews", size=11, color=tokens["text_secondary"]),
                    ],
                    wrap=True,
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                ft.Text(PHASE_NOTICE, size=11, color=tokens["text_secondary"]),
                ft.Row(
                    [
                        ft.OutlinedButton(role, on_click=lambda _, selected_role=role: on_preview(selected_role))
                        for role in ("Admin", "Faculty", "Student")
                    ],
                    wrap=True,
                    spacing=7,
                ),
            ],
            spacing=11,
        ),
        padding=14,
        bgcolor=tokens["warning_soft"],
        border=ft.Border.all(1, tokens["warning"]),
        border_radius=14,
        key="development-preview-panel",
    )


def build_login(
    on_preview: Callable[[str], None],
    tokens: ThemeTokens,
    api_status: ft.Control,
    development_preview_enabled: bool = True,
    on_login: Callable[[str, str], None] | None = None,
    auth_loading: bool = False,
    auth_error: str | None = None,
    compact: bool = False,
    api_error: str | None = None,
) -> ft.Control:
    identifier = ft.TextField(label="Email / Username", prefix_icon=ft.Icons.PERSON_OUTLINED, key="login-identifier")
    identifier.autofill_hints = [ft.AutofillHint.USERNAME]
    password = ft.TextField(label="Password", prefix_icon=ft.Icons.LOCK_OUTLINED, password=True, can_reveal_password=True, key="login-password")
    password.autofill_hints = [ft.AutofillHint.PASSWORD]
    identifier.disabled = password.disabled = auth_loading
    login_button = ft.FilledButton("Signing in..." if auth_loading else "Sign in", icon=ft.Icons.LOGIN, disabled=True, height=52, key="login-submit")

    def validate_fields(_: ft.ControlEvent | None = None) -> None:
        login_button.disabled = auth_loading or not bool((identifier.value or "").strip() and password.value)
        login_button.update()

    def submit(_: ft.ControlEvent | None = None) -> None:
        if on_login and not login_button.disabled:
            on_login((identifier.value or "").strip(), password.value or "")

    identifier.on_change = validate_fields
    identifier.on_submit = submit
    password.on_change = validate_fields
    password.on_submit = submit
    login_button.on_click = submit
    login_controls: list[ft.Control] = [
        *([
            ft.Row([attendai_emblem(tokens, 36), ft.Text("AttendAI", size=20, weight=ft.FontWeight.BOLD, color=tokens["text_primary"])], spacing=10),
            ft.Text(PROJECT_TITLE, size=13, color=tokens["text_secondary"]),
        ] if compact else []),
        ft.Text("Your day starts here.", size=28, weight=ft.FontWeight.BOLD, color=tokens["text_primary"]),
        ft.Text("Sign in to continue to your institution workspace.", size=13, color=tokens["text_secondary"]),
        identifier,
        password,
        login_button,
        ft.Text("Need help signing in? Contact your administrator.",size=12,color=tokens["text_secondary"]),
        ft.Row([api_status, ft.Text("Attendance service", size=11, color=tokens["text_secondary"])], spacing=8, wrap=True),
    ]
    if api_error:
        login_controls.append(ft.Text(api_error, color=tokens["danger"], size=12, key="api-error"))
    if auth_error:
        login_controls.insert(5, ft.Text(auth_error, color=tokens["danger"], size=12, key="login-error"))
    if development_preview_enabled:
        login_controls.append(ft.ExpansionTile(title=ft.Text("Development previews", size=12),
            controls=[_development_panel(on_preview, tokens)], key="development-preview-expander"))

    login_card = surface_card(
        ft.Column(login_controls, spacing=10 if compact else 14, horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
        tokens,
        padding=16 if compact else 26,
        key="login-card",
    )
    return ft.Container(
        content=ft.Container(ft.ResponsiveRow(
            [
                *([] if compact else [ft.Container(_academic_visual(tokens), col={"xs": 12, "md": 7}, padding=ft.Padding.symmetric(horizontal=18, vertical=24))]),
                ft.Container(login_card, col={"xs": 12, "md": 5}, padding=ft.Padding.symmetric(horizontal=0 if compact else 8, vertical=12 if compact else 18)),
            ],
            spacing=22,
            run_spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        width=None if compact else 1120),
        padding=ft.Padding.symmetric(horizontal=12 if compact else 32, vertical=16 if compact else 40),
        bgcolor=tokens["background"],
        alignment=ft.Alignment.CENTER,
        expand=not compact,
        key="login-screen",
    )

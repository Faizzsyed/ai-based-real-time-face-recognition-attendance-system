"""Premium public login screen with real authentication and isolated UI previews."""

from collections.abc import Callable

import flet as ft

from app.components.ui import status_badge, surface_card
from app.core.theme import ThemeTokens
from app.screens.auth.splash import attendai_emblem

PHASE_NOTICE = "Preview sessions are UI-only and never create authentication tokens."


def _academic_visual(tokens: ThemeTokens) -> ft.Control:
    nodes = [
        (ft.Icons.SCHOOL_OUTLINED, "Academic management"),
        (ft.Icons.FACT_CHECK_OUTLINED, "Attendance intelligence"),
        (ft.Icons.AUTO_AWESOME_OUTLINED, "AI-assisted workflows"),
    ]
    return ft.Column(
        [
            ft.Row([attendai_emblem(tokens, 62), ft.Text("AI Based Face Attendance", size=24, weight=ft.FontWeight.BOLD, color=tokens["text_primary"])], spacing=14),
            ft.Text("Intelligent Attendance.\nSmarter Academics.", size=38, weight=ft.FontWeight.BOLD, color=tokens["text_primary"]),
            ft.Text("One secure foundation for institutional operations, academic insight, and future AI-assisted attendance.", size=14, color=tokens["text_secondary"]),
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
) -> ft.Control:
    identifier = ft.TextField(label="Email / Username", prefix_icon=ft.Icons.PERSON_OUTLINED, key="login-identifier")
    password = ft.TextField(label="Password", prefix_icon=ft.Icons.LOCK_OUTLINED, password=True, can_reveal_password=True, key="login-password")
    login_button = ft.FilledButton("Signing in..." if auth_loading else "Login", icon=ft.Icons.LOGIN, disabled=True, key="login-submit")

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
        ft.Text("Welcome back", size=27, weight=ft.FontWeight.BOLD, color=tokens["text_primary"]),
        ft.Text("Sign in to continue to your institution workspace.", size=13, color=tokens["text_secondary"]),
        identifier,
        password,
        login_button,
        ft.TextButton("Forgot Password (coming soon)"),
        ft.Row([api_status, ft.Text("Foundation API", size=11, color=tokens["text_secondary"])], spacing=8),
    ]
    if auth_error:
        login_controls.insert(5, ft.Text(auth_error, color=tokens["danger"], size=12, key="login-error"))
    if development_preview_enabled:
        login_controls.append(_development_panel(on_preview, tokens))

    login_card = surface_card(
        ft.Column(login_controls, spacing=14),
        tokens,
        padding=26,
        key="login-card",
    )
    return ft.Container(
        content=ft.ResponsiveRow(
            [
                ft.Container(_academic_visual(tokens), col={"xs": 12, "md": 7}, padding=ft.Padding.symmetric(horizontal=18, vertical=24)),
                ft.Container(login_card, col={"xs": 12, "md": 5}, padding=ft.Padding.symmetric(horizontal=8, vertical=18)),
            ],
            spacing=22,
            run_spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=ft.Padding.symmetric(horizontal=20, vertical=14),
        bgcolor=tokens["background"],
        alignment=ft.Alignment.CENTER,
        expand=True,
        key="login-screen",
    )

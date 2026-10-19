"""Premium responsive public splash screen."""

from collections.abc import Callable

import flet as ft

from app.components.branding import PROJECT_TITLE, attendai_emblem
from app.core.theme import ThemeTokens


def build_splash(on_continue: Callable, tokens: ThemeTokens, compact: bool = False) -> ft.Control:
    accent = ft.Container(
        width=230 if compact else 360,
        height=230 if compact else 360,
        right=-110,
        top=-120,
        border_radius=999,
        gradient=ft.RadialGradient(
            colors=[tokens["primary_soft"], tokens["background"]]
        ),
    )
    content = ft.Container(
        content=ft.Column(
            [
                attendai_emblem(tokens),
                ft.Text("AttendAI", size=29 if compact else 36, weight=ft.FontWeight.BOLD, color=tokens["text_primary"],text_align=ft.TextAlign.CENTER),
                ft.Text(
                    PROJECT_TITLE,
                    size=15,
                    color=tokens["text_secondary"],
                    text_align=ft.TextAlign.CENTER,
                ),
                ft.FilledButton(
                    "Continue to sign in",
                    icon=ft.Icons.ARROW_FORWARD,
                    on_click=on_continue,
                ),
                ft.Text("Smart attendance for your institution", size=11, color=tokens["text_secondary"]),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=15,
        ),
        alignment=ft.Alignment.CENTER,
        padding=16 if compact else 24,
        expand=True,
    )
    return ft.Container(
        content=ft.Stack([accent, content], expand=True, clip_behavior=ft.ClipBehavior.NONE),
        bgcolor=tokens["background"],
        expand=True,
        key="splash-screen",
    )

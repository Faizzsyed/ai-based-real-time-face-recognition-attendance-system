"""Premium responsive public splash screen."""

from collections.abc import Callable

import flet as ft

from app.core.theme import ThemeTokens


def attendai_emblem(tokens: ThemeTokens, size: int = 84) -> ft.Control:
    return ft.Container(
        content=ft.Stack(
            [
                ft.Icon(ft.Icons.SCHOOL_OUTLINED, size=size * 0.44, color=tokens["on_accent"]),
                ft.Container(
                    ft.Icon(ft.Icons.AUTO_AWESOME_OUTLINED, size=size * 0.2, color=tokens["on_accent"]),
                    right=8,
                    top=7,
                ),
            ],
            alignment=ft.Alignment.CENTER,
            width=size,
            height=size,
        ),
        width=size,
        height=size,
        alignment=ft.Alignment.CENTER,
        gradient=ft.LinearGradient(colors=[tokens["primary"], tokens["secondary"]]),
        border_radius=24,
        shadow=ft.BoxShadow(blur_radius=28, color=tokens["shadow"], offset=ft.Offset(0, 9)),
    )


def build_splash(on_continue: Callable, tokens: ThemeTokens) -> ft.Control:
    accent = ft.Container(
        width=360,
        height=360,
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
                ft.Text("AI Based Face Attendance", size=36, weight=ft.FontWeight.BOLD, color=tokens["text_primary"]),
                ft.Text(
                    "AI-Powered Academic & Attendance Platform",
                    size=15,
                    color=tokens["text_secondary"],
                    text_align=ft.TextAlign.CENTER,
                ),
                ft.ProgressBar(
                    value=0.72,
                    width=170,
                    bar_height=4,
                    color=tokens["primary"],
                    bgcolor=tokens["primary_soft"],
                    border_radius=4,
                    semantics_label="Foundation ready",
                    semantics_value=72,
                ),
                ft.FilledButton(
                    "Continue to sign in",
                    icon=ft.Icons.ARROW_FORWARD,
                    on_click=on_continue,
                ),
                ft.Text("Phase 1.5 development foundation", size=11, color=tokens["text_secondary"]),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=15,
        ),
        alignment=ft.Alignment.CENTER,
        padding=24,
        expand=True,
    )
    return ft.Container(
        content=ft.Stack([accent, content], expand=True, clip_behavior=ft.ClipBehavior.NONE),
        bgcolor=tokens["background"],
        expand=True,
        key="splash-screen",
    )

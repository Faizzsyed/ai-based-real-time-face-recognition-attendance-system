"""Shared face-recognition branding for public and workspace screens."""

import flet as ft

from app.core.theme import ThemeTokens


PROJECT_TITLE = "AI Based Real-Time Face Recognition Attendance System"


def attendai_emblem(tokens: ThemeTokens, size: int = 84) -> ft.Control:
    return ft.Container(
        content=ft.Stack(
            [
                ft.Icon(ft.Icons.CROP_FREE, size=size * 0.80, color=tokens["on_accent"]),
                ft.Icon(ft.Icons.FACE_OUTLINED, size=size * 0.46, color=tokens["on_accent"]),
            ],
            alignment=ft.Alignment.CENTER,
            width=size,
            height=size,
        ),
        width=size,
        height=size,
        alignment=ft.Alignment.CENTER,
        gradient=ft.LinearGradient(colors=[tokens["primary"], tokens["secondary"]]),
        border_radius=size * 0.28,
        shadow=ft.BoxShadow(blur_radius=size / 3, color=tokens["shadow"], offset=ft.Offset(0, size * 0.1)),
        tooltip="AttendAI - Face recognition attendance",
    )

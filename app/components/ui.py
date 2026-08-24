"""Reusable premium UI controls used across Phase 1.5 previews."""

from collections.abc import Sequence

import flet as ft

from app.core.theme import ThemeTokens


def surface_card(
    content: ft.Control,
    tokens: ThemeTokens,
    *,
    padding: int = 20,
    col: dict[str, int] | int = 12,
    key: str | None = None,
) -> ft.Container:
    return ft.Container(
        content=content,
        padding=padding,
        bgcolor=tokens["surface"],
        border=ft.Border.all(1, tokens["border"]),
        border_radius=18,
        shadow=ft.BoxShadow(
            blur_radius=18,
            spread_radius=0,
            color=tokens["shadow"],
            offset=ft.Offset(0, 5),
        ),
        col=col,
        key=key,
    )


def status_badge(
    text: str,
    tokens: ThemeTokens,
    tone: str = "primary",
    icon: int | None = None,
) -> ft.Container:
    color = tokens.get(tone, tokens["primary"])
    background = tokens.get(f"{tone}_soft", tokens["surface_accent"])
    controls: list[ft.Control] = []
    if icon is not None:
        controls.append(ft.Icon(icon, size=14, color=color))
    controls.append(ft.Text(text, size=12, weight=ft.FontWeight.W_600, color=color))
    return ft.Container(
        content=ft.Row(controls, spacing=5, tight=True),
        padding=ft.Padding.symmetric(horizontal=10, vertical=6),
        bgcolor=background,
        border_radius=999,
    )


def api_status_badge(connected: bool, tokens: ThemeTokens) -> ft.Control:
    return status_badge(
        "API Connected" if connected else "API Offline",
        tokens,
        "success" if connected else "danger",
        ft.Icons.CHECK_CIRCLE_OUTLINED if connected else ft.Icons.ERROR_OUTLINE,
    )


def page_header(title: str, subtitle: str, tokens: ThemeTokens) -> ft.Control:
    return ft.Column(
        [
            ft.Text(
                title,
                size=28,
                weight=ft.FontWeight.BOLD,
                color=tokens["text_primary"],
            ),
            ft.Text(subtitle, size=14, color=tokens["text_secondary"]),
        ],
        spacing=5,
    )


def section_header(
    title: str,
    tokens: ThemeTokens,
    subtitle: str | None = None,
) -> ft.Control:
    controls = [
        ft.Text(
            title,
            size=17,
            weight=ft.FontWeight.W_600,
            color=tokens["text_primary"],
        )
    ]
    if subtitle:
        controls.append(ft.Text(subtitle, size=12, color=tokens["text_secondary"]))
    return ft.Column(controls, spacing=3)


def metric_card(
    title: str,
    value: str,
    icon: int,
    caption: str,
    tokens: ThemeTokens,
    *,
    tone: str = "primary",
    col: dict[str, int] | int = 12,
) -> ft.Container:
    color = tokens.get(tone, tokens["primary"])
    icon_bg = tokens.get(f"{tone}_soft", tokens["surface_accent"])
    return surface_card(
        ft.Column(
            [
                ft.Row(
                    [
                        ft.Container(
                            ft.Icon(icon, size=21, color=color),
                            width=42,
                            height=42,
                            alignment=ft.Alignment.CENTER,
                            bgcolor=icon_bg,
                            border_radius=12,
                        ),
                        ft.Icon(ft.Icons.MORE_HORIZ, color=tokens["text_secondary"]),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                ft.Text(
                    value,
                    size=27,
                    weight=ft.FontWeight.BOLD,
                    color=tokens["text_primary"],
                ),
                ft.Text(title, size=13, weight=ft.FontWeight.W_600, color=tokens["text_primary"]),
                ft.Text(caption, size=11, color=tokens["text_secondary"]),
            ],
            spacing=8,
        ),
        tokens,
        padding=18,
        col=col,
    )


def lecture_card(
    title: str,
    time: str,
    location: str,
    tokens: ThemeTokens,
    *,
    status: str = "Upcoming",
) -> ft.Container:
    return ft.Container(
        content=ft.Row(
            [
                ft.Container(
                    width=4,
                    height=50,
                    bgcolor=tokens["primary"],
                    border_radius=4,
                ),
                ft.Column(
                    [
                        ft.Text(title, weight=ft.FontWeight.W_600, color=tokens["text_primary"]),
                        ft.Row(
                            [
                                ft.Icon(ft.Icons.SCHEDULE_OUTLINED, size=14, color=tokens["text_secondary"]),
                                ft.Text(time, size=12, color=tokens["text_secondary"]),
                                ft.Icon(ft.Icons.LOCATION_ON_OUTLINED, size=14, color=tokens["text_secondary"]),
                                ft.Text(location, size=12, color=tokens["text_secondary"]),
                            ],
                            wrap=True,
                            spacing=5,
                        ),
                    ],
                    spacing=6,
                    expand=True,
                ),
                status_badge(status, tokens, "primary"),
            ],
            spacing=12,
        ),
        padding=14,
        bgcolor=tokens["surface_secondary"],
        border=ft.Border.all(1, tokens["border"]),
        border_radius=14,
    )


def attendance_progress_card(
    subject: str,
    percentage: int,
    status: str,
    tokens: ThemeTokens,
) -> ft.Container:
    tone = "success" if status == "Safe" else "warning"
    return ft.Container(
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Text(subject, weight=ft.FontWeight.W_600, color=tokens["text_primary"]),
                        ft.Text(f"{percentage}%", weight=ft.FontWeight.BOLD, color=tokens[tone]),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                ft.ProgressBar(
                    value=percentage / 100,
                    color=tokens[tone],
                    bgcolor=tokens[f"{tone}_soft"],
                    border_radius=6,
                    bar_height=8,
                    semantics_label=f"{subject} attendance",
                    semantics_value=percentage,
                ),
                status_badge(status, tokens, tone),
            ],
            spacing=10,
        ),
        padding=14,
        bgcolor=tokens["surface_secondary"],
        border_radius=14,
        border=ft.Border.all(1, tokens["border"]),
    )


def empty_state(
    title: str,
    message: str,
    icon: int,
    tokens: ThemeTokens,
) -> ft.Control:
    return ft.Container(
        content=ft.Column(
            [
                ft.Container(
                    ft.Icon(icon, size=24, color=tokens["primary"]),
                    width=46,
                    height=46,
                    alignment=ft.Alignment.CENTER,
                    bgcolor=tokens["primary_soft"],
                    border_radius=14,
                ),
                ft.Text(title, weight=ft.FontWeight.W_600, color=tokens["text_primary"]),
                ft.Text(message, size=12, color=tokens["text_secondary"], text_align=ft.TextAlign.CENTER),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=8,
        ),
        padding=18,
        alignment=ft.Alignment.CENTER,
        bgcolor=tokens["surface_secondary"],
        border=ft.Border.all(1, tokens["border"]),
        border_radius=14,
    )


def profile_avatar(initials: str, tokens: ThemeTokens) -> ft.CircleAvatar:
    return ft.CircleAvatar(
        content=ft.Text(initials, size=12, weight=ft.FontWeight.BOLD, color=tokens["primary"]),
        bgcolor=tokens["primary_soft"],
        radius=18,
        tooltip="Preview profile",
    )


def compact_list_row(
    title: str,
    subtitle: str,
    trailing: ft.Control,
    icon: int,
    tokens: ThemeTokens,
) -> ft.Control:
    return ft.Container(
        content=ft.Row(
            [
                ft.Container(
                    ft.Icon(icon, size=18, color=tokens["primary"]),
                    width=38,
                    height=38,
                    alignment=ft.Alignment.CENTER,
                    bgcolor=tokens["primary_soft"],
                    border_radius=10,
                ),
                ft.Column(
                    [
                        ft.Text(title, weight=ft.FontWeight.W_600, color=tokens["text_primary"]),
                        ft.Text(subtitle, size=11, color=tokens["text_secondary"]),
                    ],
                    spacing=3,
                    expand=True,
                ),
                trailing,
            ],
            spacing=10,
        ),
        padding=ft.Padding.symmetric(horizontal=4, vertical=9),
        border=ft.Border.only(bottom=ft.BorderSide(1, tokens["border"])),
    )


def mini_bar_chart(values: Sequence[int], tokens: ThemeTokens) -> ft.Control:
    return ft.Container(
        content=ft.Row(
            [
                ft.Column(
                    [
                        ft.Container(
                            width=18,
                            height=max(18, value),
                            bgcolor=tokens["primary"] if index == len(values) - 1 else tokens["primary_soft"],
                            border_radius=ft.BorderRadius.only(top_left=6, top_right=6),
                        ),
                        ft.Text(str(index + 1), size=9, color=tokens["text_secondary"]),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.END,
                    spacing=5,
                )
                for index, value in enumerate(values)
            ],
            alignment=ft.MainAxisAlignment.SPACE_AROUND,
            vertical_alignment=ft.CrossAxisAlignment.END,
            height=130,
        ),
        padding=ft.Padding.only(top=8),
    )

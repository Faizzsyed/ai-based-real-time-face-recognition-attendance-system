"""Central design tokens and Flet themes for AttendAI Pro."""

from collections.abc import Mapping

import flet as ft

from app.core.design import LIGHT, DARK

ThemeTokens = Mapping[str, str]


def _build_theme(tokens):
    style = ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12),
                           padding=ft.Padding.symmetric(horizontal=20, vertical=14))
    return ft.Theme(
        color_scheme_seed=tokens["primary"], scaffold_bgcolor=tokens["background"], use_material3=True,
        font_family="Segoe UI",
        color_scheme=ft.ColorScheme(primary=tokens["primary"], on_primary=tokens["on_accent"],
            primary_container=tokens["primary_soft"], secondary=tokens["secondary"],
            secondary_container=tokens["secondary_soft"], surface=tokens["surface"],
            on_surface=tokens["text_primary"], on_surface_variant=tokens["text_secondary"],
            outline=tokens["border"], error=tokens["danger"]),
        filled_button_theme=ft.FilledButtonTheme(style=style),
        outlined_button_theme=ft.OutlinedButtonTheme(style=style),
        text_button_theme=ft.TextButtonTheme(style=style),
        dialog_theme=ft.DialogTheme(bgcolor=tokens["surface"], shape=ft.RoundedRectangleBorder(radius=20),
            title_text_style=ft.TextStyle(size=20, color=tokens["text_primary"], weight=ft.FontWeight.W_600)),
        navigation_bar_theme=ft.NavigationBarTheme(height=80, elevation=0, label_text_style=ft.TextStyle(size=11)),
    )


def build_light_theme() -> ft.Theme:
    return _build_theme(LIGHT)


def build_dark_theme() -> ft.Theme:
    return _build_theme(DARK)


def tokens_for_mode(mode: ft.ThemeMode) -> ThemeTokens:
    return DARK if mode == ft.ThemeMode.DARK else LIGHT


def configure_page(page: ft.Page) -> None:
    page.theme_mode = ft.ThemeMode.LIGHT
    page.bgcolor = LIGHT["background"]
    page.padding = 0
    page.theme = build_light_theme()
    page.dark_theme = build_dark_theme()

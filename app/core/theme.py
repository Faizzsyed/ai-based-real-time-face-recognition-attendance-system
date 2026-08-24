"""Central design tokens and Flet themes for AttendAI Pro."""

from collections.abc import Mapping

import flet as ft

LIGHT = {
    "mode": "light",
    "background": "#F4F7FB",
    "surface": "#FFFFFF",
    "surface_secondary": "#F8FAFC",
    "surface_accent": "#EEF4FF",
    "border": "#E2E8F0",
    "text_primary": "#14213D",
    "text_secondary": "#64748B",
    "primary": "#2563EB",
    "primary_soft": "#DBEAFE",
    "secondary": "#6D5CE7",
    "secondary_soft": "#EDE9FE",
    "success": "#059669",
    "success_soft": "#D1FAE5",
    "warning": "#D97706",
    "warning_soft": "#FEF3C7",
    "danger": "#DC2626",
    "danger_soft": "#FEE2E2",
    "shadow": "#14213D14",
    "on_accent": "#FFFFFF",
}

DARK = {
    "mode": "dark",
    "background": "#0F172A",
    "surface": "#172033",
    "surface_secondary": "#1E293B",
    "surface_accent": "#172554",
    "border": "#334155",
    "text_primary": "#F8FAFC",
    "text_secondary": "#A8B3C7",
    "primary": "#60A5FA",
    "primary_soft": "#1E3A5F",
    "secondary": "#A78BFA",
    "secondary_soft": "#3B2F63",
    "success": "#34D399",
    "success_soft": "#123D35",
    "warning": "#FBBF24",
    "warning_soft": "#493614",
    "danger": "#F87171",
    "danger_soft": "#4A2025",
    "shadow": "#00000033",
    "on_accent": "#FFFFFF",
}

# Compatibility aliases for the existing API-status boundary.
LIGHT["text"] = LIGHT["text_primary"]
LIGHT["muted"] = LIGHT["text_secondary"]
DARK["text"] = DARK["text_primary"]
DARK["muted"] = DARK["text_secondary"]

ThemeTokens = Mapping[str, str]


def build_light_theme() -> ft.Theme:
    return ft.Theme(
        color_scheme_seed=LIGHT["primary"],
        scaffold_bgcolor=LIGHT["background"],
        use_material3=True,
    )


def build_dark_theme() -> ft.Theme:
    return ft.Theme(
        color_scheme_seed=DARK["primary"],
        scaffold_bgcolor=DARK["background"],
        use_material3=True,
    )


def tokens_for_mode(mode: ft.ThemeMode) -> ThemeTokens:
    return DARK if mode == ft.ThemeMode.DARK else LIGHT


def configure_page(page: ft.Page) -> None:
    page.theme_mode = ft.ThemeMode.LIGHT
    page.bgcolor = LIGHT["background"]
    page.padding = 0
    page.theme = build_light_theme()
    page.dark_theme = build_dark_theme()

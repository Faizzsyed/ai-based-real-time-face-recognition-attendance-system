"""Role-aware navigation controls for authenticated development previews."""

from dataclasses import dataclass
from collections.abc import Callable

import flet as ft

from app.core.theme import ThemeTokens


@dataclass(frozen=True)
class NavigationItem:
    section: str
    label: str
    icon: int


ROLE_NAVIGATION = {
    "Admin": (
        NavigationItem("OVERVIEW", "Dashboard", ft.Icons.DASHBOARD_OUTLINED),
        NavigationItem("PEOPLE", "Students", ft.Icons.PEOPLE_OUTLINED),
        NavigationItem("PEOPLE", "Faculty", ft.Icons.SCHOOL_OUTLINED),
        NavigationItem("ACADEMIC SETUP", "Institution", ft.Icons.ACCOUNT_BALANCE_OUTLINED),
        NavigationItem("ACADEMIC SETUP", "Academic Years", ft.Icons.DATE_RANGE_OUTLINED),
        NavigationItem("ACADEMIC SETUP", "Departments", ft.Icons.ACCOUNT_TREE_OUTLINED),
        NavigationItem("ACADEMIC SETUP", "Programs", ft.Icons.CATEGORY_OUTLINED),
        NavigationItem("ACADEMIC SETUP", "Semesters", ft.Icons.FILTER_6_OUTLINED),
        NavigationItem("ACADEMIC SETUP", "Classes & Divisions", ft.Icons.CLASS_OUTLINED),
        NavigationItem("ACADEMIC SETUP", "Subjects", ft.Icons.MENU_BOOK_OUTLINED),
        NavigationItem("ACADEMICS", "Timetable", ft.Icons.CALENDAR_MONTH_OUTLINED),
        NavigationItem("ATTENDANCE", "Attendance", ft.Icons.FACT_CHECK_OUTLINED),
        NavigationItem("ATTENDANCE", "Face Enrollment", ft.Icons.FACE_RETOUCHING_NATURAL),
        NavigationItem("ATTENDANCE", "Face AI", ft.Icons.FACE_RETOUCHING_NATURAL),
        NavigationItem("ATTENDANCE", "Reports", ft.Icons.BAR_CHART_OUTLINED),
        NavigationItem("SYSTEM", "Requests", ft.Icons.SUPPORT_AGENT_OUTLINED),
        NavigationItem("SYSTEM", "Notifications", ft.Icons.NOTIFICATIONS_OUTLINED),
        NavigationItem("SYSTEM", "Audit Logs", ft.Icons.HISTORY_OUTLINED),
        NavigationItem("SYSTEM", "Settings", ft.Icons.SETTINGS_OUTLINED),
    ),
    "Faculty": (
        NavigationItem("OVERVIEW", "Dashboard", ft.Icons.DASHBOARD_OUTLINED),
        NavigationItem("TEACHING", "Today's Lectures", ft.Icons.PLAY_LESSON_OUTLINED),
        NavigationItem("TEACHING", "Take Attendance", ft.Icons.CO_PRESENT_OUTLINED),
        NavigationItem("TEACHING", "Attendance History", ft.Icons.HISTORY_OUTLINED),
        NavigationItem("TEACHING", "Reports", ft.Icons.BAR_CHART_OUTLINED),
        NavigationItem("TEACHING", "My Classes", ft.Icons.CLASS_OUTLINED),
        NavigationItem("TEACHING", "Timetable", ft.Icons.CALENDAR_MONTH_OUTLINED),
        NavigationItem("COMMUNICATION", "Requests", ft.Icons.SUPPORT_AGENT_OUTLINED),
        NavigationItem("COMMUNICATION", "Notifications", ft.Icons.NOTIFICATIONS_OUTLINED),
        NavigationItem("ACCOUNT", "Profile", ft.Icons.PERSON_OUTLINED),
        NavigationItem("ACCOUNT", "Settings", ft.Icons.SETTINGS_OUTLINED),
    ),
    "Student": (
        NavigationItem("OVERVIEW", "Dashboard", ft.Icons.DASHBOARD_OUTLINED),
        NavigationItem("ACADEMICS", "Attendance", ft.Icons.FACT_CHECK_OUTLINED),
        NavigationItem("ACADEMICS", "Subjects", ft.Icons.MENU_BOOK_OUTLINED),
        NavigationItem("ACADEMICS", "Timetable", ft.Icons.CALENDAR_MONTH_OUTLINED),
        NavigationItem("ACADEMICS", "Upcoming Classes", ft.Icons.EVENT_NOTE_OUTLINED),
        NavigationItem("COMMUNICATION", "Requests", ft.Icons.SUPPORT_AGENT_OUTLINED),
        NavigationItem("COMMUNICATION", "Notifications", ft.Icons.NOTIFICATIONS_OUTLINED),
        NavigationItem("ACCOUNT", "Profile", ft.Icons.PERSON_OUTLINED),
        NavigationItem("ACCOUNT", "Settings", ft.Icons.SETTINGS_OUTLINED),
    ),
}


def navigation_items(role: str) -> tuple[NavigationItem, ...]:
    try:
        return ROLE_NAVIGATION[role]
    except KeyError as exc:
        raise ValueError(f"Unsupported preview role: {role}") from exc


def navigation_labels(role: str) -> tuple[str, ...]:
    return tuple(item.label for item in navigation_items(role))


def _sidebar_item(
    item: NavigationItem,
    tokens: ThemeTokens,
    collapsed: bool,
    active: bool,
    on_select: Callable[[str], None] | None = None,
) -> ft.Control:
    color = tokens["primary"] if active else tokens["text_secondary"]
    controls: list[ft.Control] = [ft.Icon(item.icon, size=20, color=color)]
    if not collapsed:
        controls.append(
            ft.Text(
                item.label,
                size=13,
                weight=ft.FontWeight.W_600 if active else ft.FontWeight.W_400,
                color=tokens["text_primary"] if active else tokens["text_secondary"],
            )
        )
    return ft.Container(
        content=ft.Row(
            controls,
            alignment=ft.MainAxisAlignment.CENTER if collapsed else ft.MainAxisAlignment.START,
            spacing=12,
        ),
        height=44,
        padding=10 if collapsed else ft.Padding.symmetric(horizontal=13, vertical=10),
        bgcolor=tokens["primary_soft"] if active else tokens["surface"],
        border_radius=12,
        tooltip=item.label,
        disabled=on_select is None and not active,
        on_click=(lambda _, label=item.label: on_select(label)) if on_select else None,
    )


def build_sidebar(
    role: str,
    tokens: ThemeTokens,
    *,
    collapsed: bool = False,
    visible: bool = True,
    active_label: str = "Dashboard",
    on_select: Callable[[str], None] | None = None,
) -> ft.Container:
    controls: list[ft.Control] = []
    current_section = None
    for index, item in enumerate(navigation_items(role)):
        if item.section != current_section:
            current_section = item.section
            if not collapsed:
                controls.append(
                    ft.Text(
                        item.section,
                        size=10,
                        weight=ft.FontWeight.BOLD,
                        color=tokens["text_secondary"],
                    )
                )
        controls.append(_sidebar_item(item, tokens, collapsed, active=item.label == active_label, on_select=on_select))

    return ft.Container(
        content=ft.Column(controls, spacing=5, scroll=ft.ScrollMode.AUTO),
        width=78 if collapsed else 246,
        padding=12,
        bgcolor=tokens["surface"],
        border=ft.Border.only(right=ft.BorderSide(1, tokens["border"])),
        visible=visible,
        key="role-sidebar",
    )


def build_navigation_drawer(role: str, tokens: ThemeTokens, *, active_label: str = "Dashboard", on_select: Callable[[str], None] | None = None) -> ft.NavigationDrawer:
    controls: list[ft.Control] = [
        ft.Container(
            content=ft.Column(
                [
                    ft.Text("AI Face Attendance", size=20, weight=ft.FontWeight.BOLD, color=tokens["text_primary"]),
                    ft.Text(f"{role} preview", size=12, color=tokens["text_secondary"]),
                ],
                spacing=3,
            ),
            padding=18,
        )
    ]
    current_section = None
    items = navigation_items(role)
    for index, item in enumerate(items):
        if item.section != current_section:
            current_section = item.section
            controls.append(
                ft.Container(
                    ft.Text(
                        item.section,
                        size=10,
                        weight=ft.FontWeight.BOLD,
                        color=tokens["text_secondary"],
                    ),
                    padding=ft.Padding.only(left=20, top=12, bottom=3),
                )
            )
        controls.append(
            ft.NavigationDrawerDestination(
                label=item.label,
                icon=item.icon,
                selected_icon=item.icon,
                disabled=on_select is None and item.label != active_label,
            )
        )
    return ft.NavigationDrawer(
        controls=controls,
        selected_index=next((index for index, item in enumerate(items) if item.label == active_label), 0),
        on_change=(lambda event: on_select(items[event.control.selected_index].label)) if on_select else None,
        bgcolor=tokens["surface"],
        indicator_color=tokens["primary_soft"],
    )

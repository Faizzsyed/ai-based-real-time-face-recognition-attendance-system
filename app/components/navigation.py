"""Role-aware navigation controls for authenticated development previews."""

from dataclasses import dataclass
from collections.abc import Callable

import flet as ft

from app.core.theme import ThemeTokens
from app.core.design import DESIGN
from app.components.v2 import identity_avatar
from app.components.branding import attendai_emblem


@dataclass(frozen=True)
class NavigationItem:
    section: str
    label: str
    icon: int


ROLE_NAVIGATION = {
    "Admin": (
        NavigationItem("OVERVIEW", "Dashboard", ft.Icons.SPACE_DASHBOARD_OUTLINED),
        NavigationItem("PEOPLE", "Faculty", ft.Icons.SCHOOL_OUTLINED),
        NavigationItem("PEOPLE", "Students", ft.Icons.PEOPLE_OUTLINED),
        NavigationItem("ACADEMICS", "Easy Setup", ft.Icons.AUTO_FIX_HIGH),
        NavigationItem("ACADEMICS", "Academic Management", ft.Icons.ACCOUNT_TREE_OUTLINED),
        NavigationItem("ACADEMICS", "Timetable", ft.Icons.CALENDAR_MONTH_OUTLINED),
        NavigationItem("ATTENDANCE", "Attendance", ft.Icons.FACT_CHECK_OUTLINED),
        NavigationItem("ATTENDANCE", "Face Enrollment", ft.Icons.FACE_RETOUCHING_NATURAL),
        NavigationItem("INSIGHTS", "Reports", ft.Icons.BAR_CHART_OUTLINED),
        NavigationItem("INSIGHTS", "Requests", ft.Icons.SUPPORT_AGENT_OUTLINED),
        NavigationItem("INSIGHTS", "Notifications", ft.Icons.NOTIFICATIONS_OUTLINED),
        NavigationItem("INSIGHTS", "Audit Logs", ft.Icons.HISTORY_OUTLINED),
        NavigationItem("ACCOUNT", "Profile", ft.Icons.PERSON_OUTLINED),
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
    institution_name: str = "Institution workspace",
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
        controls.append(_sidebar_item(item, tokens, collapsed, active=item.label == active_label or (item.label == "Academic Management" and active_label in {"Institution", "Academic Years", "Departments", "Programs", "Semesters", "Classes & Divisions", "Subjects"}), on_select=on_select))

    brand = ft.Row([
        attendai_emblem(tokens, 46),
        *([] if collapsed else [ft.Column([ft.Text("AttendAI", size=23, weight=ft.FontWeight.BOLD,
            color=tokens["text_primary"]), ft.Text("Smart Attendance", size=11, color=tokens["text_secondary"])], spacing=2)]),
    ], spacing=10, alignment=ft.MainAxisAlignment.CENTER if collapsed else ft.MainAxisAlignment.START)
    footer = ft.Container(ft.Row([identity_avatar(institution_name, tokens, 18),
        *([] if collapsed else [ft.Column([ft.Text(institution_name, size=12, weight=ft.FontWeight.W_600,
             max_lines=2, overflow=ft.TextOverflow.ELLIPSIS), ft.Text(role, size=11, color=tokens["text_secondary"])],
             spacing=3, expand=True)])], spacing=10), padding=12, bgcolor=tokens["surface_secondary"], border_radius=14)
    return ft.Container(ft.Column([
        ft.Container(brand, padding=ft.Padding.symmetric(vertical=16, horizontal=4)),
        ft.Divider(height=8, color=tokens["border"]),
        ft.Column(controls, spacing=4, scroll=ft.ScrollMode.AUTO, expand=True), footer,
    ], spacing=12), width=DESIGN.rail_width if collapsed else DESIGN.sidebar_width,
        padding=12, bgcolor=tokens["surface"],
        border=ft.Border.only(right=ft.BorderSide(1, tokens["border"])), visible=visible, key="role-sidebar")



def build_navigation_drawer(role: str, tokens: ThemeTokens, *, active_label: str = "Dashboard", on_select: Callable[[str], None] | None = None) -> ft.NavigationDrawer:
    controls: list[ft.Control] = [
        ft.Container(
            content=ft.Row(
                [attendai_emblem(tokens, 36), ft.Column([
                    ft.Text("AttendAI", size=20, weight=ft.FontWeight.BOLD, color=tokens["text_primary"]),
                    ft.Text(f"{role} workspace", size=12, color=tokens["text_secondary"]),
                ], spacing=3)],
                spacing=10,
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


MOBILE_DESTINATIONS = {
    "Student": (("Home", "Dashboard", ft.Icons.HOME_OUTLINED),
                ("Attendance", "Attendance", ft.Icons.FACT_CHECK_OUTLINED),
                ("Requests", "Requests", ft.Icons.EDIT_NOTE),
                ("Notifications", "Notifications", ft.Icons.NOTIFICATIONS_OUTLINED),
                ("Profile", "Profile", ft.Icons.PERSON_OUTLINED)),
    "Faculty": (("Home", "Dashboard", ft.Icons.HOME_OUTLINED),
                ("Attendance", "Take Attendance", ft.Icons.CO_PRESENT_OUTLINED),
                ("Requests", "Requests", ft.Icons.EDIT_NOTE),
                ("Notifications", "Notifications", ft.Icons.NOTIFICATIONS_OUTLINED),
                ("Profile", "Profile", ft.Icons.PERSON_OUTLINED)),
}


def build_bottom_navigation(role, active, tokens, on_select):
    items = MOBILE_DESTINATIONS.get(role)
    if not items:
        return None
    selected = next((i for i, item in enumerate(items) if item[1] == active), None)
    return ft.NavigationBar(destinations=[ft.NavigationBarDestination(label=label, icon=icon) for label, _, icon in items],
        selected_index=selected, bgcolor=tokens["surface"], indicator_color=tokens["primary_soft"],
        on_change=lambda event: on_select(items[event.control.selected_index][1]),
        label_behavior=ft.NavigationBarLabelBehavior.ALWAYS_SHOW, key="mobile-bottom-navigation")

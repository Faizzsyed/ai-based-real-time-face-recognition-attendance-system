"""Admin academic previews plus production Phase 4 management controls."""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import flet as ft

from app.components.ui import empty_state, page_header, section_header, status_badge, surface_card
from app.core.theme import ThemeTokens

ACADEMIC_RESOURCES = (
    ("institutions", "Institutions", ft.Icons.ACCOUNT_BALANCE_OUTLINED),
    ("academic-years", "Academic Years", ft.Icons.DATE_RANGE_OUTLINED),
    ("departments", "Departments", ft.Icons.ACCOUNT_TREE_OUTLINED),
    ("programs", "Programs", ft.Icons.CATEGORY_OUTLINED),
    ("semesters", "Semesters", ft.Icons.FILTER_6_OUTLINED),
    ("classes", "Classes", ft.Icons.CLASS_OUTLINED),
    ("subjects", "Subjects", ft.Icons.MENU_BOOK_OUTLINED),
)

MANAGEMENT_RESOURCES = (
    ("institution", "Institution", ft.Icons.ACCOUNT_BALANCE_OUTLINED),
    ("academic-years", "Academic Years", ft.Icons.DATE_RANGE_OUTLINED),
    ("departments", "Departments", ft.Icons.ACCOUNT_TREE_OUTLINED),
    ("programs", "Programs", ft.Icons.CATEGORY_OUTLINED),
    ("semesters", "Semesters", ft.Icons.FILTER_6_OUTLINED),
    ("classes", "Classes & Divisions", ft.Icons.CLASS_OUTLINED),
    ("subjects", "Subjects", ft.Icons.MENU_BOOK_OUTLINED),
)

NAVIGATION_RESOURCES = {
    "Institution": "institution", "Academic Years": "academic-years", "Departments": "departments",
    "Programs": "programs", "Semesters": "semesters", "Classes & Divisions": "classes", "Subjects": "subjects",
}

FORM_FIELDS = {
    "institution": (("name", "Name", "text"), ("short_name", "Short name", "text"), ("email", "Email", "text"), ("phone", "Phone", "text"), ("address", "Address", "text"), ("city", "City", "text"), ("state", "State", "text"), ("country", "Country", "text"), ("timezone", "Timezone", "text")),
    "academic-years": (("name", "Academic year", "text"), ("start_date", "Start date (YYYY-MM-DD)", "text"), ("end_date", "End date (YYYY-MM-DD)", "text"), ("is_current", "Current academic year", "bool"), ("status", "Status", "status")),
    "departments": (("name", "Name", "text"), ("code", "Code", "text"), ("description", "Description", "text"), ("status", "Status", "status")),
    "programs": (("department_id", "Department", "reference"), ("name", "Name", "text"), ("code", "Code", "text"), ("degree_type", "Degree type", "text"), ("duration_years", "Duration years", "number"), ("total_semesters", "Total semesters", "integer"), ("status", "Status", "status")),
    "semesters": (("academic_year_id", "Academic year", "reference"), ("program_id", "Program", "reference"), ("semester_number", "Semester number", "integer"), ("label", "Label", "text"), ("start_date", "Start date (YYYY-MM-DD)", "text"), ("end_date", "End date (YYYY-MM-DD)", "text"), ("status", "Status", "status")),
    "classes": (("academic_year_id", "Academic year", "reference"), ("department_id", "Department", "reference"), ("program_id", "Program", "reference"), ("semester_id", "Semester", "reference"), ("name", "Name", "text"), ("division", "Division", "text"), ("room", "Room", "text"), ("capacity", "Capacity", "integer"), ("status", "Status", "status")),
    "subjects": (("department_id", "Department", "reference"), ("program_id", "Program", "reference"), ("semester_id", "Semester", "reference"), ("name", "Name", "text"), ("code", "Code", "text"), ("subject_type", "Subject type", "subject_type"), ("credits", "Credits", "number"), ("weekly_hours", "Weekly hours", "number"), ("status", "Status", "status")),
}


@dataclass
class AcademicPageState:
    resource: str
    items: list[dict[str, Any]] = field(default_factory=list)
    page: int = 1
    page_size: int = 20
    total: int = 0
    total_pages: int = 0
    loading: bool = False
    error: str | None = None
    search: str = ""
    status_filter: str | None = None
    filters: dict[str, str] = field(default_factory=dict)
    filter_options: dict[str, list[tuple[str, str]]] = field(default_factory=dict)


def _management_details(resource: str) -> tuple[str, int]:
    try:
        _, title, icon = next(item for item in MANAGEMENT_RESOURCES if item[0] == resource)
        return title, icon
    except StopIteration as exc:
        raise ValueError(f"Unsupported academic resource: {resource}") from exc


def build_academic_form(
    resource: str,
    tokens: ThemeTokens,
    on_submit: Callable[[dict[str, Any]], None],
    on_cancel: Callable,
    *, record: dict[str, Any] | None = None,
    references: dict[str, list[tuple[str, str]]] | None = None,
) -> ft.Control:
    title, _ = _management_details(resource)
    references = references or {}
    controls: dict[str, ft.Control] = {}
    fields: list[ft.Control] = []
    for name, label, kind in FORM_FIELDS[resource]:
        value = (record or {}).get(name)
        if kind == "bool":
            control: ft.Control = ft.Checkbox(label=label, value=bool(value), key=f"academic-field-{name}")
        elif kind in {"status", "subject_type", "reference"}:
            options = references.get(name, [])
            if kind == "status":
                options = [("active", "Active"), ("inactive", "Inactive")]
            elif kind == "subject_type":
                options = [(item, item.title()) for item in ("theory", "practical", "project", "elective")]
            control = ft.Dropdown(value=str(value) if value is not None else ("active" if kind == "status" else None), options=[ft.DropdownOption(key=key, text=text) for key, text in options], label=label, key=f"academic-field-{name}", enable_search=True)
        else:
            control = ft.TextField(label=label, value=str(value) if value is not None else "", keyboard_type=ft.KeyboardType.NUMBER if kind in {"number", "integer"} else ft.KeyboardType.TEXT, key=f"academic-field-{name}")
        controls[name] = control
        fields.append(ft.Container(control, col={"xs": 12, "md": 6}))

    def submit(_: ft.ControlEvent | None = None) -> None:
        payload: dict[str, Any] = {}
        for name, _, kind in FORM_FIELDS[resource]:
            value = getattr(controls[name], "value", None)
            if value in (None, "") and kind != "bool":
                continue
            if kind == "integer":
                value = int(value)
            elif kind == "number":
                value = float(value)
            payload[name] = bool(value) if kind == "bool" else value
        on_submit(payload)

    return ft.Container(ft.Column([
        section_header(f"{'Edit' if record else 'Create'} {title.rstrip('s')}", tokens, "Validated by the production Admin API."),
        ft.ResponsiveRow(fields, spacing=10, run_spacing=10),
        ft.Row([ft.TextButton("Cancel", on_click=on_cancel), ft.FilledButton("Save", icon=ft.Icons.SAVE_OUTLINED, on_click=submit)], alignment=ft.MainAxisAlignment.END),
    ], spacing=14, scroll=ft.ScrollMode.AUTO, tight=True), width=720, padding=8, key=f"academic-{resource}-form")


def build_confirmation_dialog(title: str, message: str, on_confirm: Callable, on_cancel: Callable) -> ft.AlertDialog:
    return ft.AlertDialog(title=ft.Text(title), content=ft.Text(message), actions=[ft.TextButton("Cancel", on_click=on_cancel), ft.FilledButton("Confirm", on_click=on_confirm)], key="academic-confirmation-dialog")


def _item_title(resource: str, item: dict[str, Any]) -> str:
    if resource == "semesters":
        return str(item.get("label") or f"Semester {item.get('semester_number', '')}")
    return str(item.get("name") or "Academic record")


def build_academic_management_page(
    state: AcademicPageState,
    tokens: ThemeTokens,
    *, on_create: Callable | None = None,
    on_edit: Callable[[dict[str, Any]], None] | None = None,
    on_search: Callable[[str], None] | None = None,
    on_filter: Callable[[str | None], None] | None = None,
    on_resource_filter: Callable[[str, str | None], None] | None = None,
    on_page: Callable[[int], None] | None = None,
) -> ft.Control:
    title, icon = _management_details(state.resource)
    search = ft.TextField(hint_text=f"Search {title.lower()}", value=state.search, prefix_icon=ft.Icons.SEARCH, on_submit=(lambda event: on_search(event.control.value or "")) if on_search else None, col={"xs": 12, "md": 6}, key="academic-search")
    status = ft.Dropdown(value=state.status_filter or "all", options=[ft.DropdownOption(key="all", text="All statuses"), ft.DropdownOption(key="active", text="Active"), ft.DropdownOption(key="inactive", text="Inactive")], on_select=(lambda event: on_filter(None if event.control.value == "all" else event.control.value)) if on_filter else None, col={"xs": 12, "md": 3}, key="academic-status-filter")
    filter_controls: list[ft.Control] = []
    for field_name, options in state.filter_options.items():
        label = field_name.removesuffix("_id").replace("_", " ").title()
        filter_controls.append(ft.Dropdown(value=state.filters.get(field_name, "all"), label=label, options=[ft.DropdownOption(key="all", text=f"All {label.lower()}")] + [ft.DropdownOption(key=key, text=text) for key, text in options], on_select=(lambda event, selected_field=field_name: on_resource_filter(selected_field, None if event.control.value == "all" else event.control.value)) if on_resource_filter else None, col={"xs": 12, "md": 3}, key=f"academic-filter-{field_name}"))
    if state.loading:
        body: ft.Control = ft.Container(ft.Column([ft.ProgressRing(), ft.Text("Loading academic data…", color=tokens["text_secondary"])], horizontal_alignment=ft.CrossAxisAlignment.CENTER), alignment=ft.Alignment.CENTER, padding=40, key="academic-loading-state")
    elif state.error:
        database_error = "database" in state.error.casefold() or "configured" in state.error.casefold()
        body = empty_state("Database Not Configured" if database_error else "Academic data unavailable", state.error, ft.Icons.STORAGE_OUTLINED if database_error else ft.Icons.ERROR_OUTLINE, tokens)
        body.key = "academic-api-error-state"
    elif not state.items:
        body = empty_state(f"No {title.lower()} yet", "Create the first record to continue the academic setup workflow.", icon, tokens)
        body.key = "academic-empty-state"
    else:
        rows = []
        for item in state.items:
            rows.append(ft.Container(ft.Row([
                ft.Container(ft.Icon(icon, color=tokens["primary"]), width=38, height=38, alignment=ft.Alignment.CENTER, bgcolor=tokens["primary_soft"], border_radius=10),
                ft.Column([ft.Text(_item_title(state.resource, item), weight=ft.FontWeight.W_600, color=tokens["text_primary"]), ft.Text(str(item.get("code") or item.get("division") or item.get("label") or "Academic record"), size=11, color=tokens["text_secondary"])], spacing=2, expand=True),
                status_badge(str(item.get("status", "active")).title(), tokens, "success" if item.get("status", "active") == "active" else "warning"),
                ft.IconButton(ft.Icons.EDIT_OUTLINED, tooltip="Edit", on_click=(lambda _, selected=item: on_edit(selected)) if on_edit else None),
            ], spacing=10), padding=10, border=ft.Border.only(bottom=ft.BorderSide(1, tokens["border"]))))
        body = ft.Column(rows, spacing=2, key="academic-record-list")
    action_label = "Edit Institution" if state.resource == "institution" else f"Create {title.rstrip('s')}"
    return ft.Container(ft.Column([
        ft.Row([page_header(title, "Authenticated Admin academic management", tokens), ft.FilledButton(action_label, icon=ft.Icons.EDIT_OUTLINED if state.resource == "institution" else ft.Icons.ADD, on_click=on_create)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, wrap=True),
        ft.ResponsiveRow([search, status, *filter_controls], spacing=10, run_spacing=10, visible=state.resource != "institution"),
        surface_card(body, tokens),
        ft.Row([ft.Text(f"Page {state.page} of {state.total_pages} · {state.total} records", size=11, color=tokens["text_secondary"]), ft.Row([ft.IconButton(ft.Icons.CHEVRON_LEFT, disabled=state.page <= 1, on_click=(lambda _: on_page(state.page - 1)) if on_page else None), ft.IconButton(ft.Icons.CHEVRON_RIGHT, disabled=state.page >= state.total_pages, on_click=(lambda _: on_page(state.page + 1)) if on_page else None)])], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, visible=state.resource != "institution"),
    ], spacing=16, scroll=ft.ScrollMode.AUTO), padding=24, expand=True, key=f"admin-academic-{state.resource}")


def build_setup_wizard(status: dict[str, Any] | None, tokens: ThemeTokens, on_step: Callable[[str], None] | None = None, on_skip: Callable | None = None) -> ft.Control:
    steps = (("Institution", "institution", "institution"), ("Academic Year", "academic-years", "academicYear"), ("Department", "departments", "department"), ("Program", "programs", "program"), ("Semester", "semesters", "semester"), ("Class / Division", "classes", "class"), ("Subjects", "subjects", "subject"))
    checks = (status or {}).get("checks", {})
    tiles = []
    for index, (label, resource, check_key) in enumerate(steps, 1):
        complete = bool(checks.get(check_key))
        tiles.append(ft.Container(ft.Column([ft.Row([ft.CircleAvatar(content=ft.Text(str(index)), radius=14), ft.Text(label, weight=ft.FontWeight.W_600, color=tokens["text_primary"]), status_badge("Done" if complete else "Pending", tokens, "success" if complete else "warning")], spacing=8), ft.TextButton("Configure", on_click=(lambda _, selected=resource: on_step(selected)) if on_step else None)], spacing=6), padding=10, bgcolor=tokens["surface_secondary"], border_radius=12, col={"xs": 12, "md": 6, "xl": 4}))
    return surface_card(ft.Column([
        ft.Row([section_header("Academic Setup", tokens, "Complete each step using the production Admin API."), status_badge((status or {}).get("state", "Incomplete"), tokens, "success" if (status or {}).get("state") == "Ready" else "warning")], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, wrap=True),
        ft.ResponsiveRow(tiles, spacing=8, run_spacing=8),
        ft.TextButton("Skip wizard and configure manually", on_click=on_skip),
    ], spacing=12), tokens, key="academic-setup-wizard")


def build_academic_preview_page(resource: str, tokens: ThemeTokens, development_api_enabled: bool = False) -> ft.Control:
    try:
        _, title, icon = next(item for item in ACADEMIC_RESOURCES if item[0] == resource)
    except StopIteration as exc:
        raise ValueError(f"Unsupported academic preview resource: {resource}") from exc
    api_badge = status_badge(
        "Development API Enabled" if development_api_enabled else "Development API Disabled",
        tokens,
        "success" if development_api_enabled else "warning",
        ft.Icons.CHECK_CIRCLE_OUTLINED if development_api_enabled else ft.Icons.LOCK_OUTLINED,
    )
    return ft.Container(
        content=ft.Column(
            [
                ft.Row([section_header(title, tokens, "Development Data · Phase 2 inspection page"), api_badge], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, wrap=True),
                ft.Row([ft.OutlinedButton("Create preview", icon=ft.Icons.ADD, disabled=True), ft.OutlinedButton("Edit selected", icon=ft.Icons.EDIT_OUTLINED, disabled=True)], wrap=True),
                empty_state(f"No {title.lower()} loaded", "Enable the guarded development API and configure the new Python database to inspect records. Forms remain preview-only until Admin RBAC.", icon, tokens),
                ft.Row([ft.Text("Page 1 of 0", size=11, color=tokens["text_secondary"]), ft.Row([ft.IconButton(ft.Icons.CHEVRON_LEFT, disabled=True), ft.IconButton(ft.Icons.CHEVRON_RIGHT, disabled=True)])], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ],
            spacing=14,
        ),
        padding=18,
        bgcolor=tokens["surface"],
        border=ft.Border.all(1, tokens["border"]),
        border_radius=18,
        key=f"admin-academic-{resource}",
    )


def build_academic_structure_preview(tokens: ThemeTokens, development_api_enabled: bool = False) -> ft.Control:
    tiles = [
        ft.Container(
            content=ft.Row([ft.Container(ft.Icon(icon, color=tokens["primary"]), width=42, height=42, alignment=ft.Alignment.CENTER, bgcolor=tokens["primary_soft"], border_radius=12), ft.Column([ft.Text(title, weight=ft.FontWeight.W_600, color=tokens["text_primary"]), ft.Text("Development Data", size=11, color=tokens["text_secondary"])], spacing=3)], spacing=11),
            padding=13,
            bgcolor=tokens["surface_secondary"],
            border=ft.Border.all(1, tokens["border"]),
            border_radius=14,
            col={"xs": 12, "sm": 6, "lg": 4},
            tooltip=f"{title} Phase 2 preview",
        )
        for _, title, icon in ACADEMIC_RESOURCES
    ]
    return surface_card(
        ft.Column(
            [
                ft.Row([section_header("Academic Structure", tokens, "Admin-only Phase 2 development inspection"), status_badge("API Enabled" if development_api_enabled else "API Guarded", tokens, "success" if development_api_enabled else "warning", ft.Icons.LOCK_OUTLINED)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, wrap=True),
                ft.ResponsiveRow(tiles, spacing=10, run_spacing=10),
                ft.Text("Create and edit controls remain intentionally disabled until a development database is explicitly configured.", size=11, color=tokens["text_secondary"]),
            ],
            spacing=14,
        ),
        tokens,
        key="admin-academic-structure",
    )

"""Production Admin Student workspace controls."""

from dataclasses import dataclass, field
from typing import Callable
import flet as ft

from app.components.ui import empty_state, metric_card, page_header, status_badge, surface_card
from app.core.theme import ThemeTokens
from app.core.design import person_card
from app.components.forms import validate, connect_hierarchy, date_field, update
from app.services.setup_defaults import local_today, username_suggestion


@dataclass
class StudentPageState:
    items: list[dict] = field(default_factory=list)
    loading: bool = False
    error: str | None = None
    search: str = ""
    status: str | None = None
    page: int = 1
    total: int = 0
    total_pages: int = 0
    active_total: int = 0
    inactive_total: int = 0
    filters: dict[str, str] = field(default_factory=dict)
    reference_options: dict = field(default_factory=dict)


def build_students_page(state: StudentPageState, tokens: ThemeTokens, on_search: Callable[[str], None], on_filter: Callable[[str | None], None], on_academic_filter: Callable[[dict], None], on_refresh: Callable, on_add: Callable, on_import: Callable, on_action: Callable[[str, str], None], on_page=None) -> ft.Control:
    rows: list[ft.Control] = []
    for item in state.items:
        enrollment = item.get("current_enrollment") or {}
        actions=ft.PopupMenuButton(icon=ft.Icons.MORE_VERT,tooltip="Student actions",items=[
            ft.PopupMenuItem(label,icon=icon,on_click=lambda _,sid=item.get("_id"),action=action:on_action(sid,action))
            for label,icon,action in (("View",ft.Icons.VISIBILITY_OUTLINED,"view"),("Edit profile",ft.Icons.EDIT_OUTLINED,"edit"),("Academic history",ft.Icons.HISTORY,"history"),("Change enrollment",ft.Icons.SWAP_HORIZ,"enrollment"),("Face enrollment",ft.Icons.FACE_RETOUCHING_NATURAL,"face"),("Deactivate" if item.get("status")=="active" else "Activate",ft.Icons.POWER_SETTINGS_NEW,"status"))])
        rows.append(person_card(item.get("display_name","Student"),f"{item.get('admission_number','')} ? {item.get('email','')}",f"Roll {enrollment.get('roll_number') or 'not assigned'} ? {dict(state.reference_options.get('class_division_id',[])).get(str(enrollment.get('class_division_id')),'Class not available')}",status_badge(str(item.get("status","inactive")).title(),tokens,"success" if item.get("status")=="active" else "warning"),actions,tokens))
    if state.loading: body: ft.Control = ft.ProgressRing()
    elif state.error: body = empty_state("Students unavailable", state.error, ft.Icons.ERROR_OUTLINE, tokens)
    elif not rows: body = empty_state("No students added yet" if not state.search else "No students match your search", "Add your first student to begin building your class roster.", ft.Icons.PEOPLE_OUTLINED, tokens)
    else: body = ft.Column(rows, spacing=8)
    filter_fields = {name: ft.Dropdown(label=label, value=state.filters.get(name) or "", options=[ft.DropdownOption(key="",text="All"),*[ft.DropdownOption(key=k,text=v) for k,v in state.reference_options.get(name,[])]], enable_search=True, col={"xs":12,"md":4}) for name,label in (("academic_year_id","Academic year"),("department_id","Department"),("program_id","Program"),("semester_id","Semester"),("class_division_id","Class / Division"))}
    filter_fields["account_status"] = ft.Dropdown(label="Account status",value=state.filters.get("account_status") or "",options=[ft.DropdownOption(key="",text="All"),*[ft.DropdownOption(key=x,text=x.title()) for x in ("active","inactive","suspended")]],col={"xs":12,"md":4})
    return ft.Container(ft.Column([
        page_header("Students", "Manage Student identities, account status, and academic enrollment.", tokens),
        ft.ResponsiveRow([metric_card("Total Students", str(state.total), ft.Icons.PEOPLE_OUTLINED, "Institution", tokens, col={"xs": 12, "sm": 4}), metric_card("Active Students", str(state.active_total), ft.Icons.CHECK_CIRCLE_OUTLINED, "Current status", tokens, tone="success", col={"xs": 12, "sm": 4}), metric_card("Inactive Students", str(state.inactive_total), ft.Icons.PAUSE_CIRCLE_OUTLINE, "Current status", tokens, tone="warning", col={"xs": 12, "sm": 4})]),
        ft.ResponsiveRow([ft.TextField(label="Search name, admission number, email or roll", value=state.search, on_submit=lambda e: on_search(e.control.value), col={"xs": 12, "md": 5}), ft.Dropdown(label="Student status", value=state.status or "all", options=[ft.DropdownOption(key="all",text="All"),*[ft.DropdownOption(key=x,text=x.title()) for x in ("active","inactive","graduated","suspended","archived")]], on_select=lambda e:on_filter(None if e.control.value=="all" else e.control.value), col={"xs":12,"md":3}), ft.FilledButton("Add Student", icon=ft.Icons.PERSON_ADD, on_click=on_add, col={"xs": 12, "md": 2}), ft.OutlinedButton("Import CSV", icon=ft.Icons.UPLOAD_FILE, on_click=on_import, col={"xs": 12, "md": 2}), ft.IconButton(ft.Icons.REFRESH, on_click=on_refresh)]),
        ft.ExpansionTile(title=ft.Text("Academic and account filters"), subtitle=ft.Text("Current enrollment only"), controls=[ft.ResponsiveRow([*filter_fields.values(), ft.FilledButton("Apply filters", icon=ft.Icons.FILTER_ALT, on_click=lambda _:on_academic_filter({k:v.value for k,v in filter_fields.items() if v.value}), col={"xs":12,"md":3}), ft.TextButton("Clear", on_click=lambda _:on_academic_filter({}), col={"xs":12,"md":2})])]),
        body,
        *([ft.Row([ft.IconButton(ft.Icons.CHEVRON_LEFT,tooltip="Previous page",disabled=state.page<=1,on_click=lambda _:on_page(state.page-1)),ft.Text(f"Page {state.page} of {max(state.total_pages,1)}"),ft.IconButton(ft.Icons.CHEVRON_RIGHT,tooltip="Next page",disabled=state.page>=state.total_pages,on_click=lambda _:on_page(state.page+1))],alignment=ft.MainAxisAlignment.CENTER)] if on_page else []),
    ], spacing=16, scroll=ft.ScrollMode.AUTO), padding=24, expand=True, key="admin-students-page")


def build_student_profile_form(record: dict, tokens: ThemeTokens, on_submit: Callable[[dict], None], on_cancel: Callable) -> ft.Control:
    fields = {name: ft.TextField(label=label, value=record.get(name) or "", key=f"field-{name}") for name, label in (("display_name", "Full name"), ("email", "Email"), ("phone", "Phone"), ("first_name", "First name"), ("middle_name", "Middle name"), ("last_name", "Last name"))}
    return ft.Container(ft.Column([page_header("Edit Student", "Profile edits do not alter academic enrollment.", tokens), *fields.values(), ft.Row([ft.TextButton("Cancel", on_click=on_cancel), ft.FilledButton("Save", on_click=lambda _: (on_submit({k:v.value or None for k,v in fields.items()}) if validate(fields,("display_name","email")) else None))], alignment=ft.MainAxisAlignment.END)], spacing=10, scroll=ft.ScrollMode.AUTO), width=600, height=600, padding=8)


def build_enrollment_form(tokens: ThemeTokens, on_submit: Callable[[dict], None], on_cancel: Callable, references=None, records=None) -> ft.Control:
    fields = {name: ft.TextField(label=label) for name,label in (("academic_year_id","Academic Year ID"),("department_id","Department ID"),("program_id","Program ID"),("semester_id","Semester ID"),("class_division_id","Class / Division ID"),("roll_number","Roll number"),("start_date","Start date (YYYY-MM-DD)"))}
    for name, options in (references or {}).items():
        if name in fields:fields[name]=ft.Dropdown(label=name.removesuffix("_id").replace("_"," ").title(),options=[ft.DropdownOption(key=k,text=v) for k,v in options],key=f"field-{name}",enable_search=True)
    fields["start_date"]=date_field("Enrollment date",local_today().isoformat(),key="field-start_date")
    connect_hierarchy(fields,records or {})
    previous = ft.Dropdown(label="Close current enrollment as", value="transferred", options=[ft.DropdownOption(key=x, text=x.title()) for x in ("transferred","completed","withdrawn")])
    return ft.Container(ft.Column([page_header("Change Enrollment", "The existing placement is preserved in academic history.", tokens), *fields.values(), previous, ft.Text("Confirmation creates a new current enrollment; it never overwrites history.", size=11, color=tokens["text_secondary"]), ft.Row([ft.TextButton("Cancel", on_click=on_cancel), ft.FilledButton("Confirm Change", on_click=lambda _: (on_submit({**{k:v.value for k,v in fields.items()},"previous_status":previous.value}) if validate(fields,tuple(fields)) else None))], alignment=ft.MainAxisAlignment.END)], spacing=10, scroll=ft.ScrollMode.AUTO), width=620, height=650, padding=8)


def build_student_create_form(tokens: ThemeTokens, on_submit: Callable[[dict], None], on_cancel: Callable, references: dict[str, list[tuple[str, str]]] = None, records=None, on_setup=None) -> ft.Control:
    references = references or {}
    fields = {}
    for name, label in (
        ("display_name", "Full name"), ("admission_number", "Admission number"), ("email", "Email"), ("username", "Username"), ("temporary_password", "Temporary password"),
        ("phone", "Phone (optional)"), ("academic_year_id", "Academic Year ID"), ("department_id", "Department ID"), ("program_id", "Program ID"),
        ("semester_id", "Semester ID"), ("class_division_id", "Class / Division ID"), ("roll_number", "Roll number"), ("start_date", "Start date (YYYY-MM-DD)")
    ):
        if name in references:
            fields[name] = ft.Dropdown(label=label.removesuffix(" ID"), key=f"field-{name}", enable_search=True, options=[ft.DropdownOption(key=k, text=v) for k, v in references[name]])
        else:
            fields[name] = ft.TextField(label=label, key=f"field-{name}", password=name == "temporary_password", can_reveal_password=name == "temporary_password")

    fields["start_date"]=date_field("Enrollment date",local_today().isoformat(),key="field-start_date")
    def suggest_username(_):
        if not fields["username"].value:
            fields["username"].value=username_suggestion(fields["display_name"].value);update(fields["username"])
    fields["display_name"].on_blur=suggest_username
    connect_hierarchy(fields,records or {})
    def submit(_):
        if validate(fields,tuple(name for name in fields if name!="phone")):
            on_submit({key: control.value for key, control in fields.items() if control.value})
    return ft.Container(ft.Column([
        page_header("Add Student", "Creates the Student login, profile, and current enrollment together.", tokens),
        ft.ResponsiveRow([ft.Container(control, col={"xs": 12, "md": 6}) for name,control in fields.items() if not name.endswith("_id") and name!="start_date"]),
        ft.Text("Academic Placement",weight=ft.FontWeight.BOLD),
        ft.ResponsiveRow([ft.Container(control,col={"xs":12,"md":6}) for name,control in fields.items() if name.endswith("_id") or name=="start_date"]),
        *([ft.Text("Academic setup is incomplete. Complete Easy Setup before adding a student."),ft.TextButton("Return to Easy Setup",on_click=on_setup)] if any(not values for values in references.values()) else []),
        ft.Text("All fields except phone are required. Keep the initial login details safe.", size=11, color=tokens["text_secondary"]),
        ft.Row([ft.TextButton("Cancel", on_click=on_cancel), ft.FilledButton("Create Student", icon=ft.Icons.PERSON_ADD, on_click=submit)], alignment=ft.MainAxisAlignment.END),
    ], spacing=12, scroll=ft.ScrollMode.AUTO), width=760, height=650, padding=8, key="student-create-form")


def build_student_details(record: dict, tokens: ThemeTokens, on_close: Callable, references=None) -> ft.Control:
    enrollment = record.get("current_enrollment") or {}; history = record.get("enrollment_history") or []; account = record.get("account") or {}
    history_rows = [ft.Text(f"{item.get('roll_number', '—')} · {item.get('enrollment_status', '—')} · {item.get('start_date', '—')}", size=12) for item in history]
    return ft.Container(ft.Column([
        page_header(record.get("display_name", "Student"), "Student overview and academic history.", tokens),
        surface_card(ft.Column([ft.Text(f"Admission: {record.get('admission_number', '—')}"), ft.Text(f"Email: {record.get('email', '—')}"), ft.Text(f"Account: {account.get('status', '—')}"), ft.Text(f"Student status: {record.get('status', '—')}")], spacing=8), tokens),
        surface_card(ft.Column([ft.Text("Current Academic Enrollment", weight=ft.FontWeight.BOLD), ft.Text(f"Roll: {enrollment.get('roll_number', 'Not enrolled')}"), ft.Text(f"Class: {enrollment.get('class_division_id', '—')}"), ft.Text(f"Semester: {enrollment.get('semester_id', '—')}")], spacing=8), tokens),
        surface_card(ft.Column([ft.Text("Academic History", weight=ft.FontWeight.BOLD), *(history_rows or [ft.Text("No enrollment history.")])], spacing=8), tokens),
        ft.Text("Attendance and subject reports are available from the attendance workspace.",size=12,color=tokens["text_secondary"]),
        ft.Row([ft.FilledButton("Close", on_click=on_close)], alignment=ft.MainAxisAlignment.END),
    ], spacing=12, scroll=ft.ScrollMode.AUTO), width=700, height=650, padding=8, key="student-details")

"""Production Admin Faculty management workspace."""
from dataclasses import dataclass,field
from typing import Callable
import flet as ft
from app.components.ui import empty_state,metric_card,page_header,status_badge,surface_card
from app.core.theme import ThemeTokens
from app.core.design import person_card
from app.components.v2 import loading_card, error_card
from app.components.forms import validate, update, date_field
from app.services.setup_defaults import single_value, username_suggestion, employee_id_suggestion

@dataclass
class FacultyPageState:
    page:int=1
    pages:int=0
    items:list[dict]=field(default_factory=list); loading:bool=False; error:str|None=None; search:str=""; status:str|None=None; department_id:str|None=None; department_options:list[dict]=field(default_factory=list); total:int=0; active_total:int=0; inactive_total:int=0

def build_faculty_page(state:FacultyPageState,tokens:ThemeTokens,on_search:Callable,on_filter:Callable,on_department:Callable,on_refresh:Callable,on_add:Callable,on_import:Callable,on_action:Callable,on_page=None)->ft.Control:
    rows=[]
    for item in state.items:
        actions=ft.PopupMenuButton(icon=ft.Icons.MORE_VERT,tooltip="Faculty actions",items=[ft.PopupMenuItem(label,icon=icon,on_click=lambda _,fid=item.get("_id"),action=action:on_action(fid,action)) for label,icon,action in (("View",ft.Icons.VISIBILITY_OUTLINED,"view"),("Edit",ft.Icons.EDIT_OUTLINED,"edit"),("Teaching assignments",ft.Icons.CLASS_OUTLINED,"assignments"),("Assign subject",ft.Icons.ADD_TASK,"assign"),("Deactivate" if item.get("status")=="active" else "Activate",ft.Icons.POWER_SETTINGS_NEW,"status"))])
        rows.append(person_card(item.get("display_name","Faculty"),f"{item.get('employee_id','')} · {item.get('email','')}",f"{item.get('designation') or 'Faculty'} · {next((x.get('name','Department') for x in state.department_options if str(x.get('_id'))==str(item.get('department_id'))),'Department not available')}",status_badge(str(item.get("status","inactive")).title(),tokens,"success" if item.get("status")=="active" else "warning"),actions,tokens))
    body=loading_card("Loading faculty…",tokens) if state.loading else error_card(state.error,tokens,on_refresh) if state.error else empty_state("No faculty members yet","Add your first faculty member to begin creating teaching assignments.",ft.Icons.SCHOOL_OUTLINED,tokens) if not rows else ft.Column(rows,spacing=8)
    department_filter=ft.Dropdown(label="Department",key="field-department_id",value=state.department_id or "all",options=[ft.DropdownOption(key="all",text="All Departments"),*[ft.DropdownOption(key=str(x.get("_id")),text=f"{x.get('code','')} · {x.get('name','Department')}") for x in state.department_options]],on_select=lambda e:on_department(None if e.control.value=="all" else e.control.value),col={"xs":12,"md":2})
    return ft.Container(ft.Column([page_header("Faculty","Manage Faculty identities, accounts, Departments, and teaching ownership.",tokens),ft.ResponsiveRow([metric_card("Total Faculty",str(state.total),ft.Icons.SCHOOL_OUTLINED,"Institution",tokens,col={"xs":12,"sm":4}),metric_card("Active Faculty",str(state.active_total),ft.Icons.CHECK_CIRCLE_OUTLINED,"Can authenticate",tokens,tone="success",col={"xs":12,"sm":4}),metric_card("Inactive Faculty",str(state.inactive_total),ft.Icons.PAUSE_CIRCLE_OUTLINE,"Access disabled",tokens,tone="warning",col={"xs":12,"sm":4})]),ft.ResponsiveRow([ft.TextField(label="Search name, employee ID, or email",value=state.search,on_submit=lambda e:on_search(e.control.value),col={"xs":12,"md":4}),ft.Dropdown(label="Status",value=state.status or "all",options=[ft.DropdownOption(key="all",text="All"),*[ft.DropdownOption(key=x,text=x.title()) for x in ("active","inactive","suspended","resigned","archived")]],on_select=lambda e:on_filter(None if e.control.value=="all" else e.control.value),col={"xs":12,"md":2}),department_filter,ft.FilledButton("Add Faculty",icon=ft.Icons.PERSON_ADD,on_click=on_add,col={"xs":12,"md":2}),ft.OutlinedButton("Import CSV",icon=ft.Icons.UPLOAD_FILE,on_click=on_import,col={"xs":12,"md":2}),ft.IconButton(ft.Icons.REFRESH,on_click=on_refresh)]),body,*([ft.Row([ft.IconButton(ft.Icons.CHEVRON_LEFT,tooltip="Previous page",disabled=state.page<=1,on_click=lambda _:on_page(state.page-1)),ft.Text(f"Page {state.page} of {max(state.pages,1)}"),ft.IconButton(ft.Icons.CHEVRON_RIGHT,tooltip="Next page",disabled=state.page>=state.pages,on_click=lambda _:on_page(state.page+1))],alignment=ft.MainAxisAlignment.CENTER)] if on_page else [])],spacing=16,scroll=ft.ScrollMode.AUTO),padding=24,expand=True,key="admin-faculty-page")

def build_faculty_form(tokens,on_submit,on_cancel,record=None,departments=None,existing=None,on_setup=None):
    record=record or {}; create=not record
    specs=[("display_name","Full name"),("employee_id","Employee ID"),("email","Email"),("username","Username"),("temporary_password","Temporary password"),("phone","Phone"),("department_id","Department ID"),("designation","Designation"),("joining_date","Joining date (YYYY-MM-DD)")]
    fields={n:ft.TextField(label=l,key=f"field-{n}",value=str(record.get(n) or ""),password=n=="temporary_password",can_reveal_password=n=="temporary_password",visible=create or n not in {"employee_id","username","temporary_password"}) for n,l in specs}
    if departments is not None: fields["department_id"]=ft.Dropdown(label="Department",key="field-department_id",value=str(record.get("department_id") or "") or None,options=[ft.DropdownOption(key=str(x.get("_id")),text=f"{x.get('code','')} · {x.get('name','Department')}") for x in departments],enable_search=True)
    if departments is not None:
        fields["department_id"].value=single_value([(str(x.get("_id")),x.get("name")) for x in departments],record.get("department_id"))
        if not departments:fields["department_id"].helper_text="No Department available. Return to Easy Setup to create one."
    fields["joining_date"]=date_field("Joining date (optional)",record.get("joining_date"),key="field-joining_date")
    if create and existing is not None:fields["employee_id"].value=employee_id_suggestion(existing)
    def suggest_username(_):
        if create and not fields["username"].value:
            fields["username"].value=username_suggestion(fields["display_name"].value);update(fields["username"])
    fields["display_name"].on_blur=suggest_username
    return ft.Container(ft.Column([page_header("Add Faculty" if create else "Edit Faculty","Account credentials remain separate from the Faculty profile.",tokens),*([ft.Text("No Department available. Complete Easy Setup first."),ft.TextButton("Return to Easy Setup",on_click=on_setup,disabled=on_setup is None)] if departments is not None and not departments else []),ft.ResponsiveRow([ft.Container(x,col={"xs":12,"md":6}) for x in fields.values()]),ft.Row([ft.TextButton("Cancel",on_click=on_cancel),ft.FilledButton("Save Faculty",on_click=lambda _:(on_submit({k:v.value for k,v in fields.items() if v.visible and v.value}) if validate(fields,("display_name","email","department_id",*( ("employee_id","username","temporary_password") if create else () ))) else None))],alignment=ft.MainAxisAlignment.END)],spacing=12,scroll=ft.ScrollMode.AUTO),width=720,height=620,padding=8)

def build_assignment_form(tokens,on_submit,on_cancel,options=None):
    options=options or {}; years=options.get("years",[]); classes=options.get("classes",[]); subjects=options.get("subjects",[])
    year=ft.Dropdown(label="Academic Year",options=[ft.DropdownOption(key=str(x.get("_id")),text=x.get("name","Academic Year")) for x in years]); division=ft.Dropdown(label="Class / Division",disabled=True); subject=ft.Dropdown(label="Subject",disabled=True)
    def year_changed(_):
        division.options=[ft.DropdownOption(key=str(x.get("_id")),text=f"{x.get('name','Class')} · {x.get('division','')}") for x in classes if str(x.get("academic_year_id"))==str(year.value)];division.value=single_value([(x.key,x.text) for x in division.options]);division.disabled=not division.options;division.helper_text=None if division.options else "No matching Class available. Complete Easy Setup.";subject.value=None;subject.options=[];subject.disabled=True;update(division);update(subject);class_changed(None)
    def class_changed(_):
        selected=next((x for x in classes if str(x.get("_id"))==str(division.value)),{});subject.options=[ft.DropdownOption(key=str(x.get("_id")),text=f"{x.get('code','')} · {x.get('name','Subject')}") for x in subjects if str(x.get("program_id"))==str(selected.get("program_id")) and str(x.get("semester_id"))==str(selected.get("semester_id"))];subject.value=single_value([(x.key,x.text) for x in subject.options]);subject.disabled=not subject.options;subject.helper_text=None if subject.options else "No matching Subject available. Complete Easy Setup.";update(subject)
    year.on_select=year_changed;division.on_select=class_changed
    year.value=single_value([(x.key,x.text) for x in year.options]);year.disabled=not year.options;year.helper_text=None if year.options else "No Academic Year available. Complete Easy Setup.";year_changed(None)
    start=date_field("Start date (optional)");end=date_field("End date (optional)");kind=ft.Dropdown(label="Assignment type",value="primary",options=[ft.DropdownOption(key=x,text=x.replace("_"," ").title()) for x in ("primary","co_faculty","practical","project_guide")])
    assignment_fields={"academic_year_id":year,"class_division_id":division,"subject_id":subject,"start_date":start,"end_date":end,"assignment_type":kind}
    for name,control in assignment_fields.items():control.key=f"field-{name}"
    def submit(_):
        if validate(assignment_fields,("academic_year_id","class_division_id","subject_id","assignment_type")):
            on_submit({name:control.value for name,control in assignment_fields.items() if control.value})
    return ft.Container(ft.Column([page_header("Assign Subject","Academic Year → Class → Subject selection is hierarchy-aware.",tokens),year,division,subject,start,end,kind,ft.Text("Only Subjects matching the selected Class Program and Semester are offered and accepted.",size=11,color=tokens["text_secondary"]),ft.Row([ft.TextButton("Cancel",on_click=on_cancel),ft.FilledButton("Confirm Assignment",on_click=submit)],alignment=ft.MainAxisAlignment.END)],spacing=10,scroll=ft.ScrollMode.AUTO),width=620,height=590,padding=8)

def build_faculty_details(record,tokens,on_close):
    account=record.get("account") or {}; assignments=record.get("assignments") or []
    assignment_rows=[ft.Text(f"{x.get('assignment_type','—').replace('_',' ').title()} · {(x.get('subject') or {}).get('name',x.get('subject_id','—'))} · {(x.get('class_division') or {}).get('name',x.get('class_division_id','—'))} · {x.get('status','—')}",size=12) for x in assignments]
    return ft.Container(ft.Column([page_header(record.get("display_name","Faculty"),"Profile, account state, and teaching ownership.",tokens),surface_card(ft.Column([ft.Text(f"Employee ID: {record.get('employee_id','—')}"),ft.Text(f"Email: {record.get('email','—')}"),ft.Text(f"Designation: {record.get('designation','—')}"),ft.Text(f"Department: {(record.get('department') or {}).get('name',record.get('department_id','—'))}"),ft.Text(f"Account: {account.get('status','—')}")],spacing=8),tokens),surface_card(ft.Column([ft.Text("Teaching Assignments",weight=ft.FontWeight.BOLD),*(assignment_rows or [ft.Text("No active teaching assignments.")])],spacing=8),tokens),ft.Text("Assigned lectures are available from the timetable workspace.",size=12,color=tokens["text_secondary"]),ft.Row([ft.FilledButton("Close",on_click=on_close)],alignment=ft.MainAxisAlignment.END)],spacing=12,scroll=ft.ScrollMode.AUTO),width=720,height=650,padding=8)

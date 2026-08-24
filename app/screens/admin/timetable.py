"""Accessible Admin timetable list/grid management for recurring lectures."""
from dataclasses import dataclass,field
from typing import Callable
import flet as ft
from app.components.ui import empty_state,page_header,status_badge,surface_card
from app.core.theme import ThemeTokens

DAYS=("monday","tuesday","wednesday","thursday","friday","saturday","sunday")
@dataclass
class TimetablePageState:
    items:list[dict]=field(default_factory=list);loading:bool=False;error:str|None=None;view:str="week";filters:dict=field(default_factory=dict);options:dict[str,list[dict]]=field(default_factory=dict);page:int=1;total:int=0;pages:int=0

def label(entry):
    subject=(entry.get("subject") or {}).get("name","Subject");division=(entry.get("class_division") or {}).get("name","Class");return f"{entry.get('start_time','—')}–{entry.get('end_time','—')} · {subject} · {division}"
def build_timetable_page(state:TimetablePageState,tokens:ThemeTokens,on_view:Callable,on_filter:Callable,on_add:Callable,on_action:Callable,on_page:Callable)->ft.Control:
    filters=[]
    for field,title,key in (("class_division_id","Class","classes"),("faculty_id","Faculty","faculty"),("department_id","Department","departments"),("semester_id","Semester","semesters")):
        records=state.options.get(key,[]);filters.append(ft.Dropdown(label=title,value=state.filters.get(field,"all"),options=[ft.DropdownOption(key="all",text=f"All {title}"),*[ft.DropdownOption(key=str(x.get("_id")),text=x.get("display_name") or x.get("name") or x.get("label") or str(x.get("_id"))) for x in records]],on_select=lambda e,f=field:on_filter(f,None if e.control.value=="all" else e.control.value),col={"xs":12,"md":3}))
    if state.loading:body=ft.ProgressRing()
    elif state.error:body=empty_state("Timetable unavailable",state.error,ft.Icons.ERROR_OUTLINE,tokens)
    elif not state.items:body=empty_state("No lectures scheduled","Add an accessible recurring lecture entry.",ft.Icons.CALENDAR_MONTH_OUTLINED,tokens)
    elif state.view=="week":
        body=ft.ResponsiveRow([surface_card(ft.Column([ft.Text(day.title(),weight=ft.FontWeight.BOLD),*[ft.Container(ft.Column([ft.Text(label(x),size=12),ft.Row([ft.Text(f"{x.get('room') or 'Room not set'} · {x.get('lecture_type','theory').title()}",size=11,color=tokens["text_secondary"]),status_badge(str(x.get("status","inactive")).title(),tokens,"success" if x.get("status")=="active" else "warning")],wrap=True),ft.PopupMenuButton(icon=ft.Icons.MORE_HORIZ,items=[ft.PopupMenuItem("Edit",on_click=lambda _,entry=x:on_action(entry,"edit")),ft.PopupMenuItem("Deactivate" if x.get("status")=="active" else "Activate",on_click=lambda _,entry=x:on_action(entry,"deactivate" if entry.get("status")=="active" else "activate"))])],spacing=3),padding=8,bgcolor=tokens["surface_secondary"],border_radius=8) for x in state.items if x.get("day_of_week")==day]],spacing=8),tokens,col={"xs":12,"md":6,"xl":3}) for day in DAYS],spacing=10,run_spacing=10)
    else:
        body=ft.Column([surface_card(ft.Row([ft.Column([ft.Text(label(x),weight=ft.FontWeight.BOLD),ft.Text(f"{x.get('day_of_week','').title()} · {x.get('room') or 'Room not set'} · {x.get('lecture_type','theory').title()}",size=11,color=tokens["text_secondary"])],expand=True),status_badge(str(x.get("status","inactive")).title(),tokens,"success" if x.get("status")=="active" else "warning"),ft.PopupMenuButton(icon=ft.Icons.MORE_VERT,items=[ft.PopupMenuItem("Edit",on_click=lambda _,entry=x:on_action(entry,"edit")),ft.PopupMenuItem("Deactivate" if x.get("status")=="active" else "Activate",on_click=lambda _,entry=x:on_action(entry,"deactivate" if entry.get("status")=="active" else "activate"))])]),tokens) for x in state.items],spacing=8)
    pager=ft.Row([ft.IconButton(ft.Icons.CHEVRON_LEFT,disabled=state.page<=1,on_click=lambda _:on_page(state.page-1)),ft.Text(f"Page {state.page} of {max(state.pages,1)}"),ft.IconButton(ft.Icons.CHEVRON_RIGHT,disabled=state.page>=state.pages,on_click=lambda _:on_page(state.page+1))],alignment=ft.MainAxisAlignment.CENTER)
    return ft.Container(ft.Column([page_header("Timetable","Recurring weekly teaching schedule in the Institution timezone.",tokens),ft.Row([ft.SegmentedButton(selected={state.view},segments=[ft.Segment(value="week",label=ft.Text("Weekly grid"),icon=ft.Icon(ft.Icons.CALENDAR_VIEW_WEEK)),ft.Segment(value="list",label=ft.Text("List view"),icon=ft.Icon(ft.Icons.VIEW_LIST))],on_change=lambda e:on_view(next(iter(e.control.selected)))),ft.FilledButton("Add lecture",icon=ft.Icons.ADD,on_click=on_add)],alignment=ft.MainAxisAlignment.SPACE_BETWEEN,wrap=True),ft.ResponsiveRow(filters),body,pager],spacing=16,scroll=ft.ScrollMode.AUTO),padding=24,expand=True,key="admin-timetable-page")

def build_timetable_form(tokens,on_submit,on_cancel,faculty_records,on_assignments,record=None):
    record=record or {};faculty=ft.Dropdown(label="Faculty",value=str(record.get("faculty_id") or "") or None,options=[ft.DropdownOption(key=str(x.get("_id")),text=x.get("display_name","Faculty")) for x in faculty_records],enable_search=True);assignment=ft.Dropdown(label="Faculty Assignment",value=str(record.get("faculty_assignment_id") or "") or None,disabled=not record)
    def selected(_):
        records=on_assignments(faculty.value);assignment.options=[ft.DropdownOption(key=str(x.get("_id")),text=f"{(x.get('subject') or {}).get('name','Subject')} · {(x.get('class_division') or {}).get('name','Class')} · {x.get('assignment_type','primary').replace('_',' ').title()}") for x in records if x.get("status")=="active"];assignment.disabled=False;assignment.value=None;assignment.update()
    faculty.on_select=selected
    day=ft.Dropdown(label="Day",value=record.get("day_of_week"),options=[ft.DropdownOption(key=x,text=x.title()) for x in DAYS]);lecture=ft.Dropdown(label="Lecture type",value=record.get("lecture_type","theory"),options=[ft.DropdownOption(key=x,text=x.title()) for x in ("theory","practical","project","tutorial")])
    def initial(name):
        value=record.get(name) or "";return str(value).split("T",1)[0] if name.startswith("effective_") and value else str(value)
    fields={n:ft.TextField(label=l,value=initial(n)) for n,l in (("start_time","Start time (HH:MM)"),("end_time","End time (HH:MM)"),("room","Room"),("effective_from","Effective from (YYYY-MM-DD)"),("effective_until","Effective until (optional)"))}
    if record:
        records=on_assignments(faculty.value);assignment.options=[ft.DropdownOption(key=str(x.get("_id")),text=f"{(x.get('subject') or {}).get('name','Subject')} · {(x.get('class_division') or {}).get('name','Class')}") for x in records];assignment.disabled=False
    def submit(_):on_submit({k:v for k,v in {"faculty_assignment_id":assignment.value,"day_of_week":day.value,"lecture_type":lecture.value,**{n:c.value for n,c in fields.items()}}.items() if v not in (None,"")})
    return ft.Container(ft.Column([page_header("Edit lecture" if record else "Add lecture","Conflicts are checked for Faculty, Class, and Room.",tokens),faculty,assignment,day,*fields.values(),lecture,ft.Row([ft.TextButton("Cancel",on_click=on_cancel),ft.FilledButton("Save lecture",on_click=submit)],alignment=ft.MainAxisAlignment.END)],spacing=10,scroll=ft.ScrollMode.AUTO),width=650,height=680,padding=8,key="timetable-form")

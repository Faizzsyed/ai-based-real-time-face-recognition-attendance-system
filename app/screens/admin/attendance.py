"""Admin attendance oversight surface."""
from collections.abc import Callable
import flet as ft
from app.components.ui import empty_state,page_header,section_header,status_badge,surface_card
from app.core.theme import ThemeTokens

def build_admin_attendance(tokens:ThemeTokens,items:list[dict]|None,selected:dict|None,on_open:Callable[[str],None],on_action:Callable[[str,str],None],error:str|None=None,status_filter:str="all",on_filter:Callable[[str],None]|None=None)->ft.Control:
    if selected:
        records=selected.get("records") or [];rows=[ft.ListTile(title=ft.Text(x.get("student_name","Student")),subtitle=ft.Text(f"Roll {x.get('roll_number') or '—'} · {x.get('remark') or 'No remark'}"),trailing=status_badge(str(x.get("status") or "unmarked").title(),tokens,{"present":"success","absent":"danger","late":"warning"}.get(x.get("status"),"secondary"))) for x in records]
        actions=[]
        if selected.get("status") in {"submitted","locked"}:actions.append(ft.OutlinedButton("Reopen",on_click=lambda _:on_action(selected["_id"],"reopen")))
        if selected.get("status") in {"submitted","reopened"}:actions.append(ft.FilledButton("Lock",on_click=lambda _:on_action(selected["_id"],"lock")))
        body=[page_header("Attendance Session",f"Administrative inspection · {selected.get('status','').title()}",tokens),ft.Row(actions,wrap=True),surface_card(ft.Column([section_header("Roster",tokens),*rows],spacing=4),tokens)]
    else:
        rows=[ft.ListTile(title=ft.Text(f"{x.get('lecture_date','Lecture')} · {x.get('scheduled_start','')}"),subtitle=ft.Text(f"Faculty {x.get('faculty_id','—')} · Subject {x.get('subject_id','—')}"),trailing=ft.Row([status_badge(x.get("status","draft").title(),tokens,"success" if x.get("status")=="submitted" else "warning"),ft.TextButton("Inspect",on_click=lambda _,sid=x["_id"]:on_open(sid))],tight=True)) for x in (items or [])]
        filter_control=ft.Dropdown(label="Session status",value=status_filter,width=220,options=[ft.DropdownOption(key=x,text=x.title()) for x in ("all","draft","submitted","locked","reopened")],on_select=(lambda e:on_filter(e.control.value)) if on_filter else None)
        body=[page_header("Attendance Oversight","Inspect, filter, reopen, and lock institution-scoped sessions.",tokens),filter_control,surface_card(ft.Column([section_header("Sessions",tokens),*(rows or [empty_state("No attendance sessions","Sessions will appear after Faculty starts attendance.",ft.Icons.FACT_CHECK_OUTLINED,tokens)])],spacing=6),tokens)]
    if error:body.append(ft.Text(error,color=tokens["danger"]))
    return ft.Container(ft.Column(body,spacing=16,scroll=ft.ScrollMode.AUTO),padding=24,expand=True,key="admin-attendance")

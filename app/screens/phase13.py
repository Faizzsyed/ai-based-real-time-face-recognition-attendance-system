"""Responsive, live-data views for Phase 13 workflows."""
import flet as ft
from app.components.ui import empty_state,page_header,section_header,status_badge,surface_card
from app.core.theme import ThemeTokens

def build_requests_page(role:str,tokens:ThemeTokens,data:dict|None,loading=False,error:str|None=None,on_refresh=None,on_cancel=None,on_review=None)->ft.Control:
    if loading: body=surface_card(ft.Row([ft.ProgressRing(),ft.Text("Loading attendance requests…")]),tokens)
    elif error: body=surface_card(ft.Column([ft.Text(error,color=tokens["danger"]),ft.OutlinedButton("Retry",on_click=on_refresh)]),tokens)
    else:
        rows=[]
        for item in (data or {}).get("items",[]):
            session=item.get("session") or {};student=item.get("student") or {};state=item.get("status","pending");subtitle=f"{session.get('lectureDate','Lecture')} · {item.get('original_status','-').title()} → {item.get('requested_status','-').title()}\n{item.get('reason','')}"
            actions=[]
            if state=="pending" and role=="Student": actions=[ft.TextButton("Cancel",on_click=lambda _,rid=item.get("_id"):on_cancel(rid))]
            if state=="pending" and role in {"Faculty","Admin"}: actions=[ft.FilledButton("Review",on_click=lambda _,request=item:on_review(request))]
            rows.append(ft.Container(ft.ListTile(title=ft.Text(student.get("displayName") if role!="Student" else f"Attendance correction · {session.get('subjectId','Subject')}",weight=ft.FontWeight.BOLD),subtitle=ft.Text(subtitle),trailing=ft.Column([status_badge(state.title(),tokens,{"approved":"success","rejected":"danger","pending":"warning"}.get(state,"secondary")),*actions],tight=True,horizontal_alignment=ft.CrossAxisAlignment.END)),padding=4))
        body=surface_card(ft.Column([section_header("Request queue" if role!="Student" else "My requests",tokens),*(rows or [empty_state("No attendance requests","New and resolved correction requests will appear here.",ft.Icons.SUPPORT_AGENT_OUTLINED,tokens)])],spacing=8),tokens)
    return ft.Container(ft.Column([page_header("Attendance Requests","Request corrections or review only the attendance sessions you are authorized to manage.",tokens),body],spacing=16,scroll=ft.ScrollMode.AUTO),padding=24,expand=True,key=f"{role.casefold()}-requests")

def build_notifications_page(tokens:ThemeTokens,data:dict|None,loading=False,error:str|None=None,on_refresh=None,on_read=None,on_read_all=None)->ft.Control:
    if loading: body=surface_card(ft.Row([ft.ProgressRing(),ft.Text("Loading notifications…")]),tokens)
    elif error: body=surface_card(ft.Column([ft.Text(error,color=tokens["danger"]),ft.OutlinedButton("Retry",on_click=on_refresh)]),tokens)
    else:
        rows=[]
        for item in (data or {}).get("items",[]):
            unread=not item.get("read_at");rows.append(ft.ListTile(title=ft.Text(item.get("title","Notification"),weight=ft.FontWeight.BOLD if unread else ft.FontWeight.NORMAL),subtitle=ft.Text(item.get("message","")),trailing=ft.TextButton("Mark read",on_click=lambda _,nid=item.get("_id"):on_read(nid)) if unread else ft.Icon(ft.Icons.DONE,color=tokens["success"])))
        body=surface_card(ft.Column([ft.Row([section_header("Inbox",tokens),ft.TextButton("Mark all read",on_click=on_read_all)],alignment=ft.MainAxisAlignment.SPACE_BETWEEN),*(rows or [empty_state("No notifications","Attendance request updates will appear here.",ft.Icons.NOTIFICATIONS_NONE,tokens)])],spacing=8),tokens)
    return ft.Container(ft.Column([page_header("Notifications","Private updates for your account.",tokens),body],spacing=16,scroll=ft.ScrollMode.AUTO),padding=24,expand=True,key="notifications")

def build_audit_page(tokens:ThemeTokens,data:dict|None,loading=False,error:str|None=None,on_refresh=None)->ft.Control:
    if loading: body=surface_card(ft.Row([ft.ProgressRing(),ft.Text("Loading audit events…")]),tokens)
    elif error: body=surface_card(ft.Column([ft.Text(error,color=tokens["danger"]),ft.OutlinedButton("Retry",on_click=on_refresh)]),tokens)
    else:
        rows=[ft.ListTile(title=ft.Text(item.get("action","Audit event"),weight=ft.FontWeight.BOLD),subtitle=ft.Text(f"{item.get('created_at','')} · {item.get('actor_role','')} · {item.get('entity_type','')}"),trailing=status_badge(item.get("actor_role","-").title(),tokens,"primary")) for item in (data or {}).get("items",[])]
        body=surface_card(ft.Column([section_header("Append-only audit log",tokens,"System-generated actions only."),*(rows or [empty_state("No audit events","Phase 13 activity will be recorded here.",ft.Icons.HISTORY,tokens)])],spacing=8),tokens)
    return ft.Container(ft.Column([page_header("Audit Log","Read-only institution audit events. Sensitive values are redacted.",tokens),body],spacing=16,scroll=ft.ScrollMode.AUTO),padding=24,expand=True,key="admin-audit")

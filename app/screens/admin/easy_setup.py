"""Responsive Admin onboarding; advanced management screens remain available."""
import flet as ft

from app.components.forms import date_field, time_field, validate, set_error, update
from app.components.ui import surface_card, status_badge
from app.services.easy_setup import STEPS, LINKS, record_id, record_label
from app.services.setup_defaults import (academic_year_suggestion, program_suggestion, class_name_suggestion,
                                         employee_id_suggestion, username_suggestion, local_today)

SPECS = {
    "institution": [("name", "Institution name *"), ("short_name", "Short name (optional)"), ("city", "City (optional)"), ("address", "Address (optional)")],
    "academic-years": [("name", "Academic year name *"), ("start_date", "Start date *"), ("end_date", "End date *")],
    "departments": [("name", "Department name *"), ("code", "Short code *"), ("description", "Description (optional)")],
    "programs": [("degree_type", "Degree *"), ("name", "Program name *"), ("code", "Program code *"), ("duration_years", "Duration in years *"), ("total_semesters", "Number of semesters *")],
    "classes": [("division", "Division *"), ("name", "Class display name *"), ("capacity", "Capacity (optional)")],
    "subjects": [("name", "Subject name *"), ("code", "Subject code *")],
    "faculty": [("display_name", "Full name *"), ("employee_id", "Employee ID *"), ("email", "Email *"), ("username", "Username *"), ("temporary_password", "Temporary password *")],
    "students": [("display_name", "Full name *"), ("admission_number", "Admission number *"), ("roll_number", "Roll number *"), ("email", "Email *"), ("username", "Username *"), ("temporary_password", "Temporary password *"), ("start_date", "Enrollment date *")],
    "teaching": [("start_time", "Start time *"), ("end_time", "End time *"), ("effective_from", "First teaching date *"), ("effective_until", "Last teaching date *")],
}


def build_easy_setup(state, tokens, *, redraw, run, go_step, dashboard, faculty_login, working=False):
    def text(value, **kwargs):return ft.Text(value, color=tokens["text_primary"], **kwargs)
    def button(label, handler, *, primary=False, disabled=False):
        return (ft.FilledButton if primary else ft.OutlinedButton)(label,on_click=handler,disabled=disabled or working,height=48)

    if working or state.loading:
        return ft.SafeArea(ft.Container(ft.Column([text("AttendAI Easy Setup",size=24),ft.ProgressBar(),text("Loading saved records…")],spacing=16),padding=16,expand=True),expand=True,key="admin-easy-setup")
    if not state.loaded:
        return ft.SafeArea(ft.Container(ft.Column([text("Easy Setup"),ft.Text(state.error or "Load your saved records to begin.",color=tokens["danger"]),button("Retry loading",lambda _:run(state.load)),button("Return to Dashboard",lambda _:dashboard())],spacing=16),padding=16,expand=True),expand=True,key="admin-easy-setup")

    if state.complete:
        summary = [text("Setup Complete", size=28, weight=ft.FontWeight.BOLD),
                   text("Your academic structure, accounts, and teaching schedule are ready.")]
        for resource, title, _ in STEPS[:9]:
            summary.append(text(f"{title}: {record_label(state.chosen(resource))}"))
        entry = state.timetable or {}
        summary.extend([text(f"Timetable: {entry.get('day_of_week', '').title()} · {entry.get('start_time', '')[:5]} – {entry.get('end_time', '')[:5]}"),
                        ft.Row([button("Go to Dashboard",lambda _:dashboard(),primary=True),button("Login as Faculty",lambda _:faculty_login())],wrap=True),
                        text("Login as Faculty signs out the Admin and opens the login screen. Enter the faculty credentials yourself.",size=12)])
        body = surface_card(ft.Column(summary,spacing=16),tokens)
    else:
        resource, title, helper = STEPS[state.step]
        selected = state.chosen(resource)
        reuse = bool(selected) and not state.creating and not state.editing
        heading = [ft.Row([text("AttendAI Easy Setup",size=20,weight=ft.FontWeight.BOLD),status_badge(f"{state.step+1} / 10",tokens,"primary")],wrap=True,alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                   ft.ProgressBar(value=(state.step + 1)/10,color=tokens["secondary"]),text(title,size=28,weight=ft.FontWeight.BOLD),text(helper,size=14)]
        progress=[]
        for index,(key,label,_) in enumerate(STEPS):
            done=bool(state.chosen(key)) if key!="teaching" else bool(state.timetable)
            progress.append(ft.TextButton(f"{'✓' if done else '●' if index==state.step else '○'} {label}",on_click=lambda _,step=index:go_step(step),disabled=working))
        heading.append(ft.Row(progress,wrap=True,spacing=0))
        content=[]
        if state.loading or working:content.extend([ft.ProgressBar(),text("Working… Your saved records are kept.")])
        if state.error:content.append(ft.Text(state.error,color=tokens["danger"],key="easy-setup-error"))
        content.append(button("Refresh saved records",lambda _:run(state.load)))
        missing=state.missing(resource)
        if missing:
            for parent in missing:
                index=next(i for i,x in enumerate(STEPS) if x[0]==parent)
                label=STEPS[index][1]
                content.extend([text(f"No {label} selected. Complete this prerequisite first."),button(f"Create / select {label}",lambda _,i=index:go_step(i))])
        else:
            if resource not in ("teaching","institution"):
                options=[ft.DropdownOption(key=record_id(row),text=record_label(row)) for row in state.candidates(resource)]
                if resource!="semesters":options.append(ft.DropdownOption(key="__new__",text=f"Create new {title.lower()}"))
                def choose(event):
                    if event.control.value=="__new__":
                        state.creating=True;state.editing=False;state.drafts.pop(resource,None);state.error=None
                    else:state.choose(resource,event.control.value)
                    redraw()
                content.append(ft.Dropdown(label=f"Reuse existing {title.lower()}",value="__new__" if state.creating else state.selected.get(resource),options=options,on_select=choose,key="easy-existing",disabled=working))
            if resource=="semesters":
                program=state.chosen("programs")
                existing={int(row["semester_number"]) for row in state.candidates("semesters")}
                content.extend([text("Create semesters automatically",size=20,weight=ft.FontWeight.BOLD),
                                text("Default demo choice: Semester 1 only. Existing semesters are reused."),
                                ft.Column([ft.Checkbox(label=f"Semester {n}"+ (" · already saved" if n in existing else ""),value=n in existing or n==1,disabled=True)
                                           for n in range(1,int(program.get("total_semesters",1))+1)]),
                                button("Create only Semester 1 for now",lambda _:run(lambda:state.generate_semesters(True))),
                                button(f"Create all {program.get('total_semesters',1)} semesters",lambda _:run(lambda:state.generate_semesters(False)))])
            elif reuse and resource!="teaching":
                content.extend([status_badge("Done · existing record selected",tokens,"success"),text(record_label(selected),size=20,weight=ft.FontWeight.BOLD)])
                if resource=="institution":content.append(text(f"Institution code: {selected.get('code','')} · Status: {selected.get('status','active').title()}"))
                if resource=="academic-years":
                    content.append(text(f"{selected.get('start_date','').split('T')[0]} to {selected.get('end_date','').split('T')[0]}"))
                    if not selected.get("is_current"):
                        content.extend([text("This year is active but is not the current academic year."),button("Use as current academic year",lambda _:run(state.use_current_year))])
                if resource not in ("faculty","students"):
                    def edit(_):state.editing=True;redraw()
                    content.append(button(f"Edit {title.lower()}",edit))
                else:content.append(text("Existing passwords are never shown. Edit profiles in advanced management."))
                if resource=="subjects":
                    def another(_):state.creating=True;state.drafts.pop(resource,None);redraw()
                    content.append(button("Add another subject",another))
            else:
                fields={}
                department=state.chosen("departments")
                code=department.get("code", "")
                defaults={"status":"active"}
                if resource=="academic-years":defaults.update(academic_year_suggestion())
                elif resource=="programs":defaults.update(program_suggestion(code))
                elif resource=="classes":defaults.update(division="A",capacity=60,name=class_name_suggestion(code,state.chosen("semesters").get("semester_number",1)))
                elif resource=="subjects":defaults.update(subject_type="theory",code=f"{code}101")
                elif resource=="faculty":defaults["employee_id"]=employee_id_suggestion(state.records.get("faculty",[]))
                elif resource=="students":defaults["start_date"]=local_today().isoformat()
                elif resource=="teaching":
                    year=state.chosen("academic-years")
                    defaults.update(start_time="10:00",end_time="11:00",day_of_week="monday",lecture_type="theory",
                                    effective_from=str(year.get("start_date",local_today().isoformat())).split("T")[0],effective_until=str(year.get("end_date",local_today().isoformat())).split("T")[0])
                if state.editing or resource=="institution":
                    for key,_ in SPECS.get(resource,[]):
                        if key in selected:defaults[key]=str(selected[key]).split("T")[0] if key.endswith("_date") else selected[key]
                    if "status" in selected:defaults["status"]=selected["status"]
                    if resource=="academic-years":defaults["is_current"]=selected.get("is_current",False)
                    if resource=="subjects":defaults["subject_type"]=selected.get("subject_type","theory")
                values=state.drafts.setdefault(resource,defaults.copy())
                def remember(name,control):
                    def changed(_):values[name]=control.value
                    control.on_change=changed
                    return control
                if resource=="programs":
                    def duration(event):
                        if event.control.value!="custom":
                            years=int(event.control.value);values["duration_years"]=str(years);values["total_semesters"]=str(years*2);redraw()
                    content.append(ft.Dropdown(label="Common duration",value=str(values.get("duration_years")) if str(values.get("duration_years")) in ("3","4","5") else "custom",options=[ft.DropdownOption(key=str(n),text=f"{n} Years") for n in (3,4,5)]+[ft.DropdownOption(key="custom",text="Custom")],on_select=duration))
                if resource=="teaching":
                    content.extend([text("Part A · Faculty Assignment",size=20,weight=ft.FontWeight.BOLD)])
                    for key in ("faculty","subjects","classes"):
                        rows=state.candidates(key)
                        content.append(ft.Dropdown(label=next(x[1] for x in STEPS if x[0]==key),value=state.selected.get(key),options=[ft.DropdownOption(key=record_id(x),text=record_label(x)) for x in rows],on_select=lambda e,k=key:(state.choose(k,e.control.value),redraw())))
                    content.extend([text("Part B · Timetable",size=20,weight=ft.FontWeight.BOLD),text("The same faculty, subject, and class are used automatically. If the lecture fails to save, retry safely; the assignment is reused.")])
                    fields["day_of_week"]=ft.Dropdown(label="Day *",value=values["day_of_week"],options=[ft.DropdownOption(key=d,text=d.title()) for d in ("monday","tuesday","wednesday","thursday","friday","saturday","sunday")])
                    fields["day_of_week"].on_select=lambda _:values.update(day_of_week=fields["day_of_week"].value)
                for name,label in SPECS.get(resource,[]):
                    value=values.get(name,"")
                    if name.endswith("_date") or name.startswith("effective_"):control=date_field(label,value,key=f"easy-{name}")
                    elif name.endswith("_time"):control=time_field(label,value,key=f"easy-{name}")
                    else:control=ft.TextField(label=label,value=str(value or ""),password=name=="temporary_password",can_reveal_password=name=="temporary_password",key=f"easy-{name}")
                    fields[name]=remember(name,control)
                    if name in state.field_errors:set_error(control,state.field_errors[name])
                if "display_name" in fields:
                    def suggest_username(_):
                        if not values.get("username"):
                            fields["username"].value=username_suggestion(fields["display_name"].value);values["username"]=fields["username"].value;update(fields["username"])
                    fields["display_name"].on_blur=suggest_username
                if resource=="programs":
                    def suggest_program(_):
                        suggestion=program_suggestion(code,fields["degree_type"].value)
                        for key in ("name","code"):
                            fields[key].value=suggestion[key];values[key]=suggestion[key];update(fields[key])
                    content.append(button("Suggest program name and code",suggest_program))
                if resource=="classes":
                    def division_changed(_):
                        values["division"]=fields["division"].value
                        fields["name"].value=class_name_suggestion(code,state.chosen("semesters").get("semester_number",1),values["division"])
                        values["name"]=fields["name"].value;update(fields["name"])
                    fields["division"].on_change=division_changed
                if resource=="academic-years":
                    content.append(button("Use Suggested Academic Year",lambda _:(state.drafts.update({resource:academic_year_suggestion()}),redraw())))
                content.append(ft.ResponsiveRow([ft.Container(control,col={"xs":12,"md":6}) for control in fields.values()],spacing=12,run_spacing=12))
                if resource=="students":content.append(text("Academic Placement",size=18,weight=ft.FontWeight.BOLD))
                for key,parent in LINKS.get(resource,{}).items():
                    row=state.chosen(parent)
                    content.append(text(f"{next(x[1] for x in STEPS if x[0]==parent)}: {record_label(row)}",size=14))
                if LINKS.get(resource):content.append(text("To change this placement, choose the relevant step in the progress list above.",size=12))
                if resource not in ("institution","faculty","students","teaching"):
                    status=ft.Dropdown(label="Status",value=values.get("status","active"),options=[ft.DropdownOption(key=x,text=x.title()) for x in ("active","inactive")],on_select=lambda e:values.update(status=e.control.value))
                    content.append(status)
                else:content.append(text("Status: Active"))
                if resource=="subjects":
                    content.append(text("Subject type: Theory. Other subject types are available in advanced management.",size=12))
                if resource in ("faculty","students"):content.append(text("Use a temporary password of at least 8 characters. Passwords are securely hashed by the backend.",size=12))
                required=[name for name,label in SPECS.get(resource,[]) if label.endswith("*")]
                def save(_):
                    if not validate(fields,required):return
                    payload={name:control.value for name,control in fields.items() if control.value not in (None,"")}
                    for name in ("duration_years","total_semesters","capacity"):
                        if name in payload:
                            try:payload[name]=float(payload[name]) if name=="duration_years" else int(payload[name])
                            except ValueError:set_error(fields[name],"Enter a valid number.");update(fields[name]);return
                    if resource=="teaching":
                        if payload["end_time"]<=payload["start_time"]:
                            set_error(fields["end_time"],"End time must be after start time.");update(fields["end_time"]);return
                        run(lambda:state.save_teaching({**payload,"lecture_type":"theory"}))
                    else:
                        extras={key:values[key] for key in ("status","is_current","subject_type") if key in values}
                        if resource in ("institution","faculty","students"):extras={}
                        run(lambda:state.save({**payload,**extras,**state.placement(resource)}),advance=True)
                content.append(button("Save Teaching Setup" if resource=="teaching" else "Save & Continue",save,primary=True))
        navigation=[button("Back",lambda _:go_step(max(0,state.step-1)),disabled=state.step==0)]
        if reuse and resource!="teaching" and not missing:
            navigation.append(button("Next · Use selected record",lambda _:run(state.advance),primary=True))
        navigation.append(button("Return to Dashboard",lambda _:dashboard()))
        body=surface_card(ft.Column([*heading,ft.Divider(),*content,ft.Row(navigation,wrap=True,spacing=8)],spacing=16),tokens)
    return ft.SafeArea(ft.Container(ft.Column([ft.Container(body,width=960)],scroll=ft.ScrollMode.AUTO,expand=True,horizontal_alignment=ft.CrossAxisAlignment.CENTER),padding=16,expand=True),expand=True,key="admin-easy-setup")

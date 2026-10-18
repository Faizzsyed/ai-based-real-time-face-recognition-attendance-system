"""Small form helpers shared by real management dialogs."""
from datetime import date
import re
import flet as ft
from app.services.setup_defaults import single_value, local_today


def update(control):
    try:control.update()
    except RuntimeError:pass  # Construction tests have no mounted page.


def set_error(control, message):
    # Current Flet TextField serializes `error`; Dropdown uses `error_text`.
    if isinstance(control, ft.Dropdown):
        control.error_text = message
    else:
        control.error = message


def validate(fields, required=()):
    valid=True
    for name, control in fields.items():
        if not isinstance(control,(ft.TextField,ft.Dropdown)):continue
        value=str(control.value or "").strip()
        error=None
        if name in required and not value:error="This field is required."
        elif value and name in {"display_name","username"} and len(value)<2:error="Use at least 2 characters."
        elif value and name == "email" and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+",value):error="Enter a valid email address."
        elif value and name == "temporary_password" and len(value)<8:error="Use at least 8 characters."
        elif value and (name.endswith("_date") or name in {"effective_from","effective_until"}):
            try:date.fromisoformat(value.split("T",1)[0])
            except ValueError:error="Use YYYY-MM-DD."
        set_error(control, error)
        if error:valid=False
        update(control)
    return valid


def connect_hierarchy(fields, records):
    parents={"program_id":("department_id",),"semester_id":("academic_year_id","program_id"),
             "class_division_id":("academic_year_id","department_id","program_id","semester_id")}
    order=("academic_year_id","department_id","program_id","semester_id","class_division_id")
    def refresh(child, clear=False):
        control=fields[child]
        dependencies=[parent for parent in parents.get(child,()) if parent in fields]
        selected=all(fields[parent].value for parent in dependencies)
        candidates=[row for row in records[child] if all(str(row.get(parent))==str(fields[parent].value) for parent in dependencies)] if selected else []
        if clear or not any(str(row.get("_id"))==str(control.value) for row in candidates):control.value=None
        control.disabled=not selected or not candidates
        control.options=[ft.DropdownOption(key=str(row["_id"]),text=row.get("name") or row.get("label") or f"Semester {row.get('semester_number','')}") for row in candidates]
        control.value=single_value([(x.key,x.text) for x in control.options],control.value)
        control.helper_text=None if candidates else "No valid options. Complete the earlier steps in Easy Setup."
        if clear:update(control)
    def changed(name):
        invalidated={name}
        for child in order[order.index(name)+1:]:
            if child not in fields or child not in records:continue
            dependencies=parents.get(child,())
            if not invalidated.intersection(dependencies):continue
            refresh(child,clear=True)
            invalidated.add(child)
    for name in order:
        if name in fields and isinstance(fields[name],ft.Dropdown):
            fields[name].value=single_value([(x.key,x.text) for x in fields[name].options],fields[name].value)
            if name not in parents and not fields[name].options:
                fields[name].helper_text=f"No {fields[name].label or 'academic option'} available. Return to Easy Setup."
                fields[name].disabled=True
            fields[name].on_select=lambda _,field=name:changed(field)
            if name in records and name in parents:refresh(name)


def date_field(label, value=None, *, key=None):
    """Keep the API ISO value while offering a calendar and readable date hint."""
    field=ft.TextField(label=label, value=str(value or "").split("T")[0], read_only=True, key=key)
    def describe():
        try:field.helper_text=date.fromisoformat(field.value).strftime("%d %b %Y")
        except (ValueError,TypeError):field.helper_text="Choose a date from the calendar"
    def changed(event):
        field.value=event.control.value.date().isoformat() if hasattr(event.control.value,"date") else event.control.value.isoformat()
        describe();update(field)
        if field.on_change:field.on_change(event)
    def opened(event):
        try:initial=date.fromisoformat(field.value)
        except (ValueError,TypeError):initial=local_today()
        event.control.page.show_dialog(ft.DatePicker(value=initial,first_date=date(1900,1,1),last_date=date(2100,12,31),on_change=changed))
    field.suffix=ft.IconButton(ft.Icons.CALENDAR_MONTH_OUTLINED,tooltip=f"Choose {label.lower()}",on_click=opened)
    field.on_click=opened
    describe()
    return field


def time_field(label, value="10:00", *, key=None):
    from datetime import time
    field=ft.TextField(label=label,value=value,read_only=True,key=key)
    def describe():
        try:field.helper_text=time.fromisoformat(field.value).strftime("%I:%M %p")
        except (ValueError,TypeError):field.helper_text="Choose a time"
    def changed(event):
        field.value=event.control.value.strftime("%H:%M");describe();update(field)
        if field.on_change:field.on_change(event)
    def opened(event):
        try:initial=time.fromisoformat(field.value)
        except (ValueError,TypeError):initial=time(10)
        event.control.page.show_dialog(ft.TimePicker(value=initial,on_change=changed))
    field.suffix=ft.IconButton(ft.Icons.SCHEDULE,tooltip=f"Choose {label.lower()}",on_click=opened)
    field.on_click=opened;describe()
    return field

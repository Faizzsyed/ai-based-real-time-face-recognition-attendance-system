"""Offline visual QA of empty states; never connects to or writes a database.

Run from the project root: .venv\Scripts\python.exe scripts/preview_ui_v2.py
Use the QA toolbar to select a screen and logical viewport size.
"""
import sys
import argparse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import flet as ft
from app.core.theme import configure_page, LIGHT
from app.core.design import adapt_view, walk_controls
from app.main import PremiumUiController
from app.components.camera import build_camera_panel
from app.components.ui import page_header
from app.screens.admin.academic import AcademicPageState, build_academic_management_page, build_academic_hub
from app.screens.admin.easy_setup import build_easy_setup
from app.screens.admin.students import StudentPageState, build_students_page
from app.screens.admin.faculty import FacultyPageState, build_faculty_page
from app.screens.auth.login import build_login
from app.screens.faculty.attendance import build_take_attendance
from app.screens.phase13 import build_requests_page, build_notifications_page
from app.services.easy_setup import EasySetup


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--screen", default="Admin")
parser.add_argument("--width", type=int, default=1366)
parser.add_argument("--height", type=int, default=768)
ARGS = parser.parse_args() if __name__ == "__main__" else parser.parse_args([])


def main(page):
    configure_page(page)
    page.title = "AttendAI · UI V2 visual QA"
    page.window.width, page.window.height = ARGS.width, ARGS.height
    host = ft.Container(expand=True)
    controller = PremiumUiController(page, host)
    noop = lambda *_: None
    screen = ft.Dropdown(label="Screen", value=ARGS.screen, width=190,
        options=[ft.DropdownOption(x) for x in ("Admin", "Faculty", "Student", "Face Attendance", "Academic Management", "Easy Setup", "Login", "Students", "Faculty List", "Requests", "Notifications", "Form")])
    size = ft.Dropdown(label="Viewport", value=f"{ARGS.width} × {ARGS.height}", width=170,
        options=[ft.DropdownOption(x) for x in ("1366 × 768", "1920 × 1080", "360 × 800", "390 × 844", "430 × 932", "600 × 900", "768 × 1024", "1024 × 768", "1600 × 900")])
    toolbar = ft.Container(ft.Row([screen, size], wrap=True, spacing=8, run_spacing=8), padding=8, bgcolor=LIGHT["surface"])
    def render(_=None):
        name = screen.value
        if name in {"Admin", "Faculty", "Student"}:
            controller.show_preview(name)
            column = host.content.controls[1]
            column.controls = [c for c in column.controls if not any(x.key == "development-role-switcher" for x in walk_controls(c))]
            page.update()
            page.on_resize = render
            return
        if name == "Face Attendance":
            controller.camera_panel_state.purpose = "attendance"
            # Empty UI fixture only. Camera is never opened by this gallery.
            panel = build_camera_panel(controller.camera_panel_state, LIGHT, None, None, "Face Attendance", compact=(page.width or 390)<600)
            content = ft.Container(ft.Column([page_header("Face Attendance", "Offline visual QA · no session or biometric data loaded", LIGHT), panel], scroll=ft.ScrollMode.AUTO), padding=16, expand=True)
        elif name == "Academic Management":
            content = build_academic_hub(build_academic_management_page(AcademicPageState("academic-years"), LIGHT), "academic-years", LIGHT, noop)
        elif name == "Easy Setup":
            state = EasySetup(None, lambda: False)
            state.loaded = True
            content = build_easy_setup(state, LIGHT, redraw=noop, run=noop, go_step=noop, dashboard=noop, faculty_login=noop)
        elif name == "Login":
            content = ft.Column([build_login(noop, LIGHT, ft.Text("Offline"), compact=(page.width or 390)<600, development_preview_enabled=False)], scroll=ft.ScrollMode.AUTO, expand=True)
        elif name == "Students":
            content = build_students_page(StudentPageState(), LIGHT, *([noop]*7))
        elif name == "Faculty List":
            content = build_faculty_page(FacultyPageState(), LIGHT, *([noop]*7))
        elif name == "Requests":
            content = build_requests_page("Student", LIGHT, {"items": []})
        elif name == "Notifications":
            content = build_notifications_page(LIGHT, {"items": []})
        else:
            from app.screens.admin.students import build_student_create_form
            def open_form(_=None):
                form = build_student_create_form(LIGHT, noop, lambda _:controller.close_dialog(), {key:[] for key in ("academic_year_id","department_id","program_id","semester_id","class_division_id")})
                controller.show_dialog(ft.AlertDialog(content=form))
            content = ft.Container(ft.FilledButton("Open student form", on_click=open_form), padding=16, expand=True, alignment=ft.Alignment.TOP_LEFT)
        host.content = adapt_view(content, page.width or 390, LIGHT)
        page.update()
    def resize(_):
        width, height = map(int, size.value.split(" × "))
        page.window.width, page.window.height = width, height
        page.update()
    screen.on_select = render
    size.on_select = resize
    page.on_resize = render
    page.add(ft.SafeArea(ft.Column([toolbar,host], expand=True, spacing=0), expand=True))
    render()
    # Controller previews install their own handler; the gallery must redraw every QA view.
    page.on_resize = render


if __name__ == "__main__":
    ft.run(main)

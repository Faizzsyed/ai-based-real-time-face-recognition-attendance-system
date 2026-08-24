"""AttendAI Pro premium Flet foundation with Phase 3 authentication."""

from collections.abc import Callable
from datetime import date,timedelta
import asyncio
import logging
import time

import flet as ft

from app.components.navigation import (
    build_navigation_drawer,
    build_sidebar,
    navigation_labels,
)
from app.components.ui import api_status_badge, profile_avatar, status_badge
from app.components.camera import CameraPanelState,build_camera_panel
from app.core.config import get_settings
from app.core.logging import configure_logging as configure_runtime_logging,log_ui_event
from app.core.theme import ThemeTokens, configure_page, tokens_for_mode
from app.screens.admin.dashboard import build_admin_dashboard
from app.screens.admin.academic import (
    AcademicPageState,
    NAVIGATION_RESOURCES,
    build_academic_form,
    build_academic_management_page,
    build_confirmation_dialog,
)
from app.screens.admin.students import StudentPageState, build_enrollment_form, build_student_create_form, build_student_details, build_student_profile_form, build_students_page
from app.screens.admin.faculty import FacultyPageState,build_assignment_form,build_faculty_details,build_faculty_form,build_faculty_page
from app.screens.admin.timetable import TimetablePageState,build_timetable_form,build_timetable_page
from app.screens.admin.attendance import build_admin_attendance
from app.screens.admin.face_enrollment import FaceEnrollmentState,build_face_enrollment_dialog,build_face_enrollment_page
from app.screens.auth.login import build_login
from app.screens.auth.splash import build_splash
from app.screens.faculty.dashboard import build_faculty_dashboard
from app.screens.faculty.attendance import build_take_attendance
from app.screens.student.dashboard import build_student_dashboard
from app.screens.student.attendance import build_student_attendance
from app.screens.reports import build_class_detail,build_reports,build_session_detail,build_student_detail
from app.services.api_client import ApiClient
from app.services.camera_service import CameraService,CameraUnavailable
from app.services.biometric_pipeline import BiometricPipeline,BiometricState,BlinkChallenge,FaceObservation,MediaPipeBlinkDetector
from app.services.liveness_challenge import LivenessChallengeEngine
from app.state.auth_state import AuthState

PREVIEW_ROLES = ("Admin", "Faculty", "Student")


def build_dashboard(
    role: str,
    tokens: ThemeTokens,
    development_academic_api_enabled: bool = False,
    setup_status: dict | None = None,
    on_setup_step: Callable[[str], None] | None = None,
    show_development_structure: bool = True,
    show_setup_wizard: bool = True,
    on_skip_setup: Callable | None = None,
    student_profile: dict | None = None,
    faculty_profile: dict | None = None,
    schedule_data: dict | None = None,
    attendance_data: dict | None = None,
) -> ft.Control:
    builders = {
        "Admin": lambda current_tokens: build_admin_dashboard(
            current_tokens, development_academic_api_enabled, setup_status, on_setup_step, show_development_structure, show_setup_wizard, on_skip_setup, attendance_data
        ),
        "Faculty": lambda current_tokens: build_faculty_dashboard(current_tokens, faculty_profile, schedule_data, attendance_data),
        "Student": lambda current_tokens: build_student_dashboard(current_tokens, student_profile, schedule_data, attendance_data),
    }
    try:
        return builders[role](tokens)
    except KeyError as exc:
        raise ValueError(f"Unsupported preview role: {role}") from exc


def build_role_switcher(
    active_role: str,
    on_switch: Callable[[str], None],
    on_exit: Callable,
    tokens: ThemeTokens,
) -> ft.Control:
    if active_role not in PREVIEW_ROLES:
        raise ValueError(f"Unsupported preview role: {active_role}")

    role_buttons: list[ft.Control] = []
    for role in PREVIEW_ROLES:
        button_type = ft.FilledButton if role == active_role else ft.OutlinedButton
        role_buttons.append(
            button_type(
                role,
                on_click=lambda _, selected_role=role: on_switch(selected_role),
            )
        )
    return ft.Row(
        [
            status_badge("Development Preview", tokens, "warning", ft.Icons.LOCK_OUTLINED),
            *role_buttons,
            ft.TextButton("Exit Preview", icon=ft.Icons.LOGOUT, on_click=on_exit),
        ],
        wrap=True,
        spacing=7,
        key="development-role-switcher",
    )


def build_public_shell(
    content: ft.Control,
    tokens: ThemeTokens,
    *,
    api_connected: bool,
    on_theme_toggle: Callable,
    on_api_check: Callable,
) -> ft.Control:
    top_bar = ft.Container(
        content=ft.Row(
            [
                ft.Row(
                    [
                        ft.Container(
                            ft.Icon(ft.Icons.SCHOOL_OUTLINED, size=18, color=tokens["on_accent"]),
                            width=34,
                            height=34,
                            alignment=ft.Alignment.CENTER,
                            gradient=ft.LinearGradient(colors=[tokens["primary"], tokens["secondary"]]),
                            border_radius=11,
                        ),
                        ft.Text("AI Face Attendance", weight=ft.FontWeight.BOLD, color=tokens["text_primary"]),
                    ],
                    spacing=10,
                ),
                ft.Row(
                    [
                        api_status_badge(api_connected, tokens),
                        ft.IconButton(
                            ft.Icons.DARK_MODE_OUTLINED if tokens["mode"] == "light" else ft.Icons.LIGHT_MODE_OUTLINED,
                            tooltip="Toggle light/dark theme",
                            on_click=on_theme_toggle,
                        ),
                        ft.IconButton(ft.Icons.REFRESH, tooltip="Check API", on_click=on_api_check),
                    ],
                    spacing=3,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        ),
        padding=ft.Padding.symmetric(horizontal=18, vertical=10),
        bgcolor=tokens["surface"],
        border=ft.Border.only(bottom=ft.BorderSide(1, tokens["border"])),
    )
    return ft.Column(
        [top_bar, ft.Container(content, expand=True)],
        spacing=0,
        expand=True,
        key="public-shell",
    )


def build_authenticated_top_bar(
    role: str,
    tokens: ThemeTokens,
    *,
    api_connected: bool,
    on_sidebar_toggle: Callable,
    on_theme_toggle: Callable,
    on_api_check: Callable,
    on_logout: Callable | None = None,
    view_label: str = "Dashboard",
) -> ft.Control:
    return ft.Container(
        content=ft.ResponsiveRow(
            [
                ft.Container(
                    ft.Row(
                        [
                            ft.IconButton(ft.Icons.MENU, tooltip="Toggle navigation", on_click=on_sidebar_toggle),
                            ft.Column(
                                [
                                    ft.Text(view_label, size=17, weight=ft.FontWeight.BOLD, color=tokens["text_primary"]),
                                    ft.Text(f"{role} / {view_label}", size=11, color=tokens["text_secondary"]),
                                ],
                                spacing=1,
                            ),
                        ],
                        spacing=7,
                    ),
                    col={"xs": 12, "md": 6},
                ),
                ft.Container(
                    ft.Row(
                        [
                            api_status_badge(api_connected, tokens),
                            ft.IconButton(
                                ft.Icons.DARK_MODE_OUTLINED if tokens["mode"] == "light" else ft.Icons.LIGHT_MODE_OUTLINED,
                                tooltip="Toggle light/dark theme",
                                on_click=on_theme_toggle,
                            ),
                            ft.IconButton(ft.Icons.NOTIFICATIONS_NONE, tooltip="Notifications coming in Phase 13"),
                            profile_avatar(role[:1], tokens),
                            *([ft.TextButton("Logout", icon=ft.Icons.LOGOUT, on_click=on_logout, key="authenticated-logout")] if on_logout else []),
                        ],
                        alignment=ft.MainAxisAlignment.END,
                        spacing=2,
                    ),
                    col={"xs": 12, "md": 6},
                ),
            ],
            spacing=4,
            run_spacing=4,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=ft.Padding.symmetric(horizontal=12, vertical=8),
        bgcolor=tokens["surface"],
        border=ft.Border.only(bottom=ft.BorderSide(1, tokens["border"])),
    )


class PremiumUiController:
    """Owns public/authenticated shell composition and development preview state."""

    def __init__(
        self,
        page: ft.Page,
        host: ft.Container,
        development_preview_enabled: bool = True,
        development_academic_api_enabled: bool = False,
        auth_state: AuthState | None = None,
        api_client: ApiClient | None = None,
    ) -> None:
        self.page = page
        self.host = host
        self.development_preview_enabled = development_preview_enabled
        self.development_academic_api_enabled = development_academic_api_enabled
        self.current_role: str | None = None
        self.current_screen = "splash"
        self.api_connected = False
        self.sidebar_collapsed = False
        self.auth_state = auth_state or AuthState()
        self.api_client = api_client or ApiClient(auth_state=self.auth_state, on_auth_lost=self._schedule_auth_lost)
        self.active_navigation = "Dashboard"
        self.academic_state: AcademicPageState | None = None
        self.setup_status_data: dict | None = None
        self.setup_wizard_visible = True
        self.student_state: StudentPageState | None = None
        self.student_profile_data: dict | None = None
        self.faculty_state: FacultyPageState | None = None
        self.faculty_profile_data: dict | None = None
        self.schedule_data: dict | None = None
        self.timetable_state: TimetablePageState | None = None
        self.attendance_data: dict | None = None
        self.reports_data: dict | None = None
        self.reports_error: str | None = None
        self.reports_options: dict = {}
        self.reports_low: dict = {}
        self.reports_filters: dict = {}
        self.reports_page: int = 1
        self.reports_loading: bool = False
        self.attendance_sessions: list[dict] = []
        self.current_attendance: dict | None = None
        self.attendance_notice: str | None = None
        self.attendance_search = ""
        self.attendance_status_filter = "all"
        self.attendance_mode = "manual"
        self.face_attendance_status_data: dict | None = None
        self.face_attendance_result: dict | None = None
        self.face_recognition_mode = "all"
        self.face_selected_student_id: str | None = None
        self.face_reference_image: bytes | None = None
        self.admin_attendance_filter = "all"
        self.face_enrollment_state: FaceEnrollmentState | None = None
        camera_settings=get_settings();self.camera_service=CameraService(preview_fps=camera_settings.camera_preview_fps);self.camera_panel_state=CameraPanelState();self.camera_context=None;self.camera_student=None;self.camera_consent=False;self.camera_frames=[];self.camera_capture_sequences=[];self._capture_retries=0;self._final_validation_retries=0;self._enrollment_finalizing=False;self._camera_loop_running=False;self._camera_analysis_running=False;self._liveness_loop_running=False;self._recognition_running=False;self._capture_last_at=0.;self._neutral_since=None;self._neutral_anchor=None;self._latest_eyes_open=False;self._latest_eye_at=0.;self.blink_detector=None;self.biometric_pipeline=self._new_biometric_pipeline();self.liveness_engine=None

    def _new_biometric_pipeline(self):
        settings=get_settings();return BiometricPipeline(stability_seconds=settings.face_stability_seconds,blink=BlinkChallenge(settings.face_liveness_required_blinks,settings.face_liveness_timeout_seconds,settings.face_liveness_min_open_frames,settings.face_liveness_min_closed_frames,settings.face_liveness_calibration_samples,settings.face_liveness_closure_delta,settings.face_liveness_reopen_ratio,settings.face_liveness_debug),cooldown_seconds=2.)
    def _new_liveness_engine(self):
        settings=get_settings();profile="blink" if settings.face_liveness_challenge_mode.casefold()=="blink" else "enrollment" if self.camera_context=="enrollment" else "attendance";return LivenessChallengeEngine(self.biometric_pipeline.blink,profile,settings.face_liveness_pose_timeout_seconds,settings.face_liveness_pose_delta,settings.face_liveness_pose_center_tolerance,settings.face_liveness_pose_frames,settings.face_liveness_face_loss_grace_ms/1000,enrollment_steps=settings.face_liveness_enrollment_steps,attendance_steps=settings.face_liveness_attendance_steps)

    @property
    def tokens(self) -> ThemeTokens:
        return tokens_for_mode(self.page.theme_mode)

    def check_api(self, _: ft.ControlEvent | None = None) -> None:
        self.api_connected = self.api_client.health_check().connected
        self.render_current()

    def toggle_theme(self, _: ft.ControlEvent | None = None) -> None:
        self.page.theme_mode = (
            ft.ThemeMode.DARK
            if self.page.theme_mode != ft.ThemeMode.DARK
            else ft.ThemeMode.LIGHT
        )
        self.page.bgcolor = self.tokens["background"]
        self.render_current()

    def handle_sidebar_toggle(self, _: ft.ControlEvent | None = None) -> None:
        if (self.page.width or 0) < 900:
            self.page.show_drawer()
            return
        self.sidebar_collapsed = not self.sidebar_collapsed
        self.render_authenticated_shell()

    def handle_resize(self, _: ft.PageResizeEvent | None = None) -> None:
        self.render_current()

    def show_splash(self, _: ft.ControlEvent | None = None) -> None:
        self.current_role = None
        self.current_screen = "splash"
        self.page.drawer = None
        self.page.on_resize = self.handle_resize
        self.render_public()

    def show_login(self, _: ft.ControlEvent | None = None) -> None:
        self.stop_camera()
        self.current_role = None
        self.current_screen = "login"
        self.current_attendance = None
        self.attendance_sessions = []
        self.attendance_data = None
        self.page.drawer = None
        self.page.on_resize = self.handle_resize
        self.render_public()

    def _schedule_auth_lost(self) -> None:
        logging.getLogger("CAMERA").warning("[CAMERA] stopping due to expired session")
        self.stop_camera()
        async def redirect():
            self.show_login()
            self.auth_state.error="Your session has expired. Please sign in again."
            self.render_public()
        self.page.run_task(redirect)

    def show_preview(self, role: str) -> None:
        if not self.development_preview_enabled:
            raise RuntimeError("Development preview is disabled.")
        navigation_labels(role)
        self.current_role = role
        self.current_screen = "preview"
        self.sidebar_collapsed = False
        self.active_navigation = "Dashboard"
        self.academic_state = None
        self.current_attendance = None
        self.attendance_sessions = []
        self.attendance_data = None
        self.page.on_resize = self.handle_resize
        self.render_preview()

    def show_authenticated(self, role: str) -> None:
        navigation_labels(role)
        self.current_role = role
        self.current_screen = "authenticated"
        self.sidebar_collapsed = False
        self.active_navigation = "Dashboard"
        self.academic_state = None
        self.page.on_resize = self.handle_resize
        self.render_authenticated_shell()

    def handle_login(self, identifier: str, password: str) -> None:
        self.auth_state.begin_login()
        self.render_public()
        result = self.api_client.login(identifier, password)
        if result.connected and self.auth_state.current_user:
            role = str(self.auth_state.current_user["role"]).capitalize()
            if role == "Admin":
                status = self.api_client.academic_setup_status()
                self.setup_status_data = status.data if status.connected else None
                attendance=self.api_client.admin_attendance_sessions(pageSize=100,lecture_date=date.today().isoformat());self.attendance_data=attendance.data if attendance.connected else None
            elif role == "Student":
                profile = self.api_client.student_profile()
                if not profile.connected or not profile.data:
                    self.auth_state.fail(profile.error or "Student profile is unavailable.")
                    self.current_screen = "login"
                    self.render_public()
                    return
                self.student_profile_data = profile.data
                schedule=self.api_client.student_timetable();self.schedule_data=schedule.data if schedule.connected and schedule.data else {"today":[],"week":[],"upcoming":[],"nextLecture":None}
                summary=self.api_client.student_attendance_summary();history=self.api_client.student_attendance_history();self.attendance_data={**(summary.data or {}),"history":((history.data or {}).get("items",[]))} if summary.connected else {"summary":{},"subjects":[],"history":[]}
            elif role == "Faculty":
                profile = self.api_client.faculty_profile()
                if not profile.connected or not profile.data:
                    self.auth_state.fail(profile.error or "Faculty profile is unavailable."); self.current_screen="login"; self.render_public(); return
                self.faculty_profile_data=profile.data
                schedule=self.api_client.faculty_timetable();self.schedule_data=schedule.data if schedule.connected and schedule.data else {"today":[],"week":[],"upcoming":[],"nextLecture":None}
                sessions=self.api_client.faculty_attendance_sessions();self.attendance_sessions=(sessions.data or {}).get("items",[]) if sessions.connected else [];self.attendance_data={"sessions":self.attendance_sessions}
            self.show_authenticated(role)
        else:
            self.current_screen = "login"
            self.render_public()

    def logout(self, _: ft.ControlEvent | None = None) -> None:
        self.stop_camera()
        self.api_client.logout()
        self.show_login()

    def exit_preview(self, _: ft.ControlEvent | None = None) -> None:
        self.show_login()

    def select_navigation(self, label: str) -> None:
        if label!=self.active_navigation:self.stop_camera()
        log_ui_event("navigation selected",role=self.current_role,label=label)
        if self.current_role=="Faculty" and label in {"Dashboard","Today's Lectures","Timetable","Take Attendance","Attendance History","Reports"}:
            if label in {"Take Attendance","Attendance History"} and self.current_screen=="authenticated":self.load_faculty_attendance()
            if label=="Reports" and self.current_screen=="authenticated":self.load_reports()
            self.active_navigation=label;self.render_authenticated_shell();return
        if self.current_role=="Student" and label in {"Dashboard","Timetable","Upcoming Classes","Attendance"}:
            if label=="Attendance" and self.current_screen=="authenticated":self.load_reports()
            self.active_navigation=label;self.render_authenticated_shell();return
        if self.current_role != "Admin" or label not in {"Dashboard", "Students", "Faculty", "Timetable", "Attendance", "Face Enrollment", "Reports", *NAVIGATION_RESOURCES.keys()}:
            return
        self.active_navigation = label
        if label == "Dashboard":
            if self.current_screen == "authenticated":
                status = self.api_client.academic_setup_status()
                self.setup_status_data = status.data if status.connected else None
            self.academic_state = None
            self.render_authenticated_shell()
            return
        if label == "Students":
            self.load_students()
            return
        if label == "Faculty": self.load_faculty(); return
        if label == "Timetable":self.load_timetable();return
        if label == "Attendance":self.load_admin_attendance();return
        if label == "Face Enrollment":self.load_face_enrollments();return
        if label == "Reports":
            if self.current_screen=="authenticated":self.load_reports()
            else:self.render_authenticated_shell()
            return
        self.load_academic_resource(NAVIGATION_RESOURCES[label])

    def load_reports(self):
        self.reports_loading=True;self.reports_error=None;self.render_authenticated_shell();role=self.current_role or "Admin";query={k:v for k,v in self.reports_filters.items() if k not in {"search"} and v};result=self.api_client.reports_overview(role,**query)
        if not result.connected or not result.data:self.reports_data={};self.reports_error=result.error or "Reports are unavailable."
        else:
            self.reports_data=result.data
            if role in {"Admin","Faculty"}:
                subjects=self.api_client.reports_subjects(role,**query);self.reports_data["subjects"]=(subjects.data or {}).get("items",[]) if subjects.connected else []
                choices=self.api_client.reports_options(role);self.reports_options=choices.data or {} if choices.connected else {}
            if role=="Admin":
                low=self.api_client.reports_low_attendance(**self.reports_filters,page=self.reports_page,pageSize=25);self.reports_low=low.data or {} if low.connected else {}
                trend=self.api_client.reports_trend(dateFrom=query.get("dateFrom"),dateTo=query.get("dateTo"));self.reports_data["trend"]=(trend.data or {}).get("items",[]) if trend.connected else []
        self.reports_loading=False
        self.render_authenticated_shell()

    def filter_reports(self,key,value):
        value=value or "";self.reports_filters[key]=value;self.reports_page=1
        if key=="departmentId":self.reports_filters.update({"programId":"","semesterId":"","classDivisionId":""})
        elif key=="programId":self.reports_filters.update({"semesterId":"","classDivisionId":""})
        elif key=="semesterId":self.reports_filters["classDivisionId"]=""
        self.load_reports()
    def reset_report_filters(self,_=None):self.reports_filters={};self.reports_page=1;self.load_reports()
    def set_report_range(self,days):
        today=date.today();self.reports_filters.update({"dateFrom":(today-timedelta(days=days-1)).isoformat(),"dateTo":today.isoformat()});self.reports_page=1;self.load_reports()
    def set_report_page(self,page):self.reports_page=max(1,page);self.load_reports()
    def search_reports(self,value):self.reports_filters["search"]=value;self.reports_page=1;self.load_reports()
    def open_report_student(self,student_id):
        result=self.api_client.report_student(self.current_role or "Admin",student_id)
        if not result.connected or not result.data:self._face_message("Student report unavailable",result.error or "Unable to load report.",False);return
        self.page.show_dialog(ft.AlertDialog(content=build_student_detail(result.data,self.tokens,lambda _:self.page.pop_dialog()),modal=True))
    def open_report_session(self,session_id):
        result=self.api_client.report_session(self.current_role or "Admin",session_id)
        if not result.connected or not result.data:self._face_message("Session report unavailable",result.error or "Unable to load report.",False);return
        self.page.show_dialog(ft.AlertDialog(content=build_session_detail(result.data,self.tokens,lambda _:self.page.pop_dialog(),self.export_report_csv),modal=True))
    def open_report_class(self,class_id):
        if not class_id:return
        result=self.api_client.report_class(self.current_role or "Admin",class_id)
        if not result.connected or not result.data:self._face_message("Class report unavailable",result.error or "Unable to load report.",False);return
        self.page.show_dialog(ft.AlertDialog(content=build_class_detail(result.data,self.tokens,lambda _:self.page.pop_dialog(),lambda sid:(self.page.pop_dialog(),self.open_report_student(sid)),self.export_report_csv),modal=True))
    async def export_report_csv(self,kind,document_id=None):
        result=self.api_client.download_report_csv(self.current_role or "Admin",kind,document_id)
        if not result.connected or not result.data:self._face_message("Export failed",result.error or "CSV export is unavailable.",False);return
        picker=ft.FilePicker();self.page.services.append(picker);path=await picker.save_file(dialog_title="Save AttendAI report",file_name=result.data["filename"],file_type=ft.FilePickerFileType.CUSTOM,allowed_extensions=["csv"],src_bytes=result.data["content"])
        self._face_message("Export complete" if path else "Export cancelled",f"CSV saved to {path}" if path else "No file was saved.",bool(path))

    def load_face_enrollments(self,search=None,status=None):
        previous=self.face_enrollment_state or FaceEnrollmentState();state=FaceEnrollmentState(search=previous.search if search is None else search,status=previous.status if status is None else status,loading=True);self.face_enrollment_state=state;self.render_authenticated_shell()
        result=self.api_client.list_students(page=1,pageSize=100,search=state.search)
        if not result.connected or not result.data:state.loading=False;state.error=result.error or "Students are unavailable.";self.render_authenticated_shell();return
        items=[]
        for student in result.data.get("items",[]):
            face=self.api_client.face_status(student["_id"]);record={**student,"face":face.data if face.connected and face.data else {"enrolled":False,"status":"unavailable"}}
            if state.status=="enrolled" and not record["face"].get("enrolled"):continue
            if state.status=="not_enrolled" and record["face"].get("enrolled"):continue
            items.append(record)
        state.items=items;state.loading=False;self.render_authenticated_shell()
    def filter_face_enrollments(self,status):self.load_face_enrollments(status=status)
    async def select_face_frames(self,student):
        log_ui_event("file picker requested",student_id=student.get("_id"))
        picker=ft.FilePicker();self.page.services.append(picker);selected=await picker.pick_files(dialog_title="Select exactly 3 distinct face frames",file_type=ft.FilePickerFileType.CUSTOM,allowed_extensions=["jpg","jpeg","png","webp"],allow_multiple=True,with_data=True)
        log_ui_event("file picker returned",files=len(selected or []))
        if not selected:return
        if len(selected)!=3:self._face_message("Three frames required","Select exactly three distinct consecutive photos.",False);return
        files=[];quality=[]
        for index,chosen in enumerate(selected,1):
            content=chosen.bytes
            if content is None and chosen.path:
                try:
                    with open(chosen.path,"rb") as stream:content=stream.read(5*1024*1024+1)
                except OSError:content=None
            if content is None:self._face_message("Frame unavailable",f"Capture {index}/3 could not be read.",False);return
            suffix=(chosen.name.rsplit(".",1)[-1] if "." in chosen.name else "jpg").casefold();mime={"jpg":"image/jpeg","jpeg":"image/jpeg","png":"image/png","webp":"image/webp"}.get(suffix,"application/octet-stream");analysis=self.api_client.analyze_face(student["_id"],chosen.name,content,mime)
            if not analysis.connected:log_ui_event("face analysis failed",frame=index,status=analysis.status_code);self._face_message(f"Capture {index}/3 rejected",analysis.error or "Quality validation failed.",False);return
            log_ui_event("face analysis succeeded",frame=index)
            quality.append(analysis.data);files.append((chosen.name,content,mime))
        def confirm(_):
            result=self.api_client.enroll_face(student["_id"],files);self.page.pop_dialog()
            if result.connected:self._face_message("Enrollment complete","Three stable frames were averaged and the encrypted template was stored.",True);self.load_face_enrollments()
            else:self._face_message("Enrollment failed",result.error or "The template was not stored.",False)
        self.page.show_dialog(ft.AlertDialog(title=ft.Text("Quality passed · 3/3"),content=ft.Column([ft.Text(f"Capture {i}/3 · confidence {item.get('detectionConfidence','—')} · blur/lighting/size accepted") for i,item in enumerate(quality,1)],tight=True),actions=[ft.TextButton("Cancel",on_click=lambda _:self.page.pop_dialog()),ft.FilledButton("Complete Enrollment",on_click=confirm)]))
    def enroll_face_profile(self,student):
        result=self.api_client.enroll_face_from_profile(student["_id"]);self.page.pop_dialog()
        if result.connected:self._face_message("Enrollment complete","The managed profile photo passed quality checks and the encrypted template was stored.",True);self.load_face_enrollments()
        else:self._face_message("Profile enrollment failed",result.error or "Profile photo was not accepted.",False)
    def remove_face_enrollment(self,student):
        result=self.api_client.remove_face(student["_id"]);self.page.pop_dialog();self._face_message("Template removed" if result.connected else "Removal failed","The encrypted biometric template was deleted." if result.connected else result.error or "Template was not removed.",result.connected);self.load_face_enrollments()
    def _face_message(self,title,message,success):self.page.show_dialog(ft.AlertDialog(title=ft.Text(title),content=ft.Text(message),icon=ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE if success else ft.Icons.ERROR_OUTLINE,color=self.tokens["success"] if success else self.tokens["danger"]),actions=[ft.FilledButton("Close",on_click=lambda _:self.page.pop_dialog())]))
    def open_face_enrollment(self,student):
        log_ui_event("enrollment dialog opened",student_id=student.get("_id"))
        if (student.get("face") or {}).get("enrolled"):
            reference=self.api_client.face_reference(student["_id"])
            if reference.connected:(student.setdefault("face",{}))["referenceImage"]=(reference.data or {}).get("content")
        self.stop_camera();self.camera_context="enrollment";self.camera_student=student;self.camera_consent=False;self.camera_frames=[];self.camera_capture_sequences=[];self._capture_retries=0;self._final_validation_retries=0;self._enrollment_finalizing=False;self.biometric_pipeline=self._new_biometric_pipeline();self.camera_panel_state=CameraPanelState()
        async def choose_frames(_):await self.select_face_frames(student)
        panel=build_camera_panel(self.camera_panel_state,self.tokens,self.start_camera,self.stop_camera,f"Face Enrollment — {student.get('display_name','Student')}",self.retry_liveness)
        self.page.show_dialog(ft.AlertDialog(content=build_face_enrollment_dialog(student,self.tokens,choose_frames,lambda _:self.enroll_face_profile(student),lambda _:self.remove_face_enrollment(student),lambda _:self.close_face_dialog(),panel,lambda value:setattr(self,"camera_consent",value)),modal=True))

    async def start_camera(self,_=None):
        if self.camera_context=="enrollment" and not self.camera_consent:self.camera_panel_state.message="Confirm consent before starting the camera.";self.camera_panel_state.sync();self.page.update();return
        if self.camera_context=="attendance" and self.face_recognition_mode=="specific" and not self.face_selected_student_id:self.camera_panel_state.message="Select the Student to verify before starting.";self.camera_panel_state.sync();self.page.update();return
        try:
            settings=get_settings()
            if self.blink_detector is None:self.blink_detector=MediaPipeBlinkDetector(settings.face_landmarker_model_path)
            self.camera_service.start()
        except CameraUnavailable as exc:self.camera_panel_state.camera="unavailable";self.camera_panel_state.message=str(exc);self.camera_panel_state.sync();self.page.update();return
        except Exception as exc:self.camera_panel_state.camera="unavailable";self.camera_panel_state.message=f"Blink landmark model unavailable: {exc}";self.camera_panel_state.sync();self.page.update();return
        self._neutral_since=None;self._neutral_anchor=None;self._capture_last_at=0.;self.biometric_pipeline.start();self.liveness_engine=self._new_liveness_engine();self.camera_panel_state.prepare_start();self.camera_panel_state.camera="connected";self.camera_panel_state.message="Position your face inside the guide.";self.camera_panel_state.sync();log_ui_event("enrollment camera opened" if self.camera_context=="enrollment" else "attendance camera opened");self.page.update()
        if not self._camera_loop_running:self.page.run_task(self._camera_preview_loop)
        if not self._camera_analysis_running:self.page.run_task(self._camera_analysis_loop)
        if not self._liveness_loop_running:self.page.run_task(self._camera_liveness_loop)
    def stop_camera(self,_=None):
        if hasattr(self,"camera_service"):self.camera_service.stop()
        if hasattr(self,"camera_panel_state"):self.camera_panel_state.camera="stopped";self.camera_panel_state.message="Camera stopped.";self.camera_panel_state.sync()
        self._camera_loop_running=False;self._camera_analysis_running=False;self._liveness_loop_running=False;self._recognition_running=False
    def close_face_dialog(self):self.stop_camera();self.camera_context=None;self.page.pop_dialog()
    async def _camera_preview_loop(self):
        self._camera_loop_running=True;last_preview=-1;frames=0;started=asyncio.get_running_loop().time();settings=get_settings()
        try:
            while self.camera_service.running and self.camera_context:
                item=self.camera_service.raw_snapshot(last_preview)
                if item:
                    last_preview=item.sequence;encoded=await asyncio.to_thread(self.camera_service.encode_preview,item)
                    if encoded:
                        first=self.camera_panel_state.accept_preview(encoded);ui_started=asyncio.get_running_loop().time();self.camera_panel_state.image.update();frames+=1
                        if first:self.camera_panel_state.placeholder.update();logging.getLogger("CAMERA").info("[CAMERA] first valid preview frame")
                        logging.getLogger("PERF").debug("[PERF] preview_ui_update_ms=%.2f",(asyncio.get_running_loop().time()-ui_started)*1000)
                now=asyncio.get_running_loop().time()
                if now-started>=2:logging.getLogger("PERF").info("[PERF] preview_fps=%.1f",frames/(now-started));frames=0;started=now
                await asyncio.sleep(1/max(1,settings.camera_preview_fps))
        except Exception:log_ui_event("camera preview failed");self.stop_camera();raise
        finally:
            self._camera_loop_running=False
            if self.camera_context and self.camera_panel_state.camera=="connected" and not self.camera_service.running:
                self.camera_panel_state.camera="disconnected";self.camera_panel_state.message="Camera disconnected. Check the device and try again.";self.camera_panel_state.sync()
                for control in (self.camera_panel_state.camera_badge,self.camera_panel_state.instruction_text,self.camera_panel_state.progress_text):
                    try:control.update()
                    except Exception:pass

    async def _camera_analysis_loop(self):
        self._camera_analysis_running=True;last=-1;settings=get_settings()
        try:
            while self.camera_service.running and self.camera_context:
                item=self.camera_service.raw_snapshot(last)
                if not item:await asyncio.sleep(.02);continue
                last=item.sequence;frame=await asyncio.to_thread(self.camera_service.encode_analysis,item,settings.camera_analysis_width)
                if not frame:continue
                started=asyncio.get_running_loop().time()
                if self.camera_context=="enrollment":analysis=await asyncio.to_thread(self.api_client.analyze_face,self.camera_student["_id"],"camera.jpg",frame,"image/jpeg")
                else:analysis=await asyncio.to_thread(self.api_client.analyze_attendance_face,self.current_attendance["_id"],"camera.jpg",frame,"image/jpeg")
                logging.getLogger("PERF").debug("[PERF] analysis_roundtrip_ms=%.2f",(asyncio.get_running_loop().time()-started)*1000)
                await self._handle_camera_analysis(item,frame,analysis)
                await asyncio.sleep(max(0,1/max(1,settings.camera_analysis_fps)-(asyncio.get_running_loop().time()-started)))
        except Exception:log_ui_event("camera analysis failed");self.stop_camera();raise
        finally:self._camera_analysis_running=False

    async def _camera_liveness_loop(self):
        self._liveness_loop_running=True;last=-1;settings=get_settings();tracked=0;started=asyncio.get_running_loop().time()
        try:
            while self.camera_service.running and self.camera_context:
                active={BiometricState.LIVENESS_PROMPT,BiometricState.LIVENESS_CALIBRATING,BiometricState.LIVENESS_TRACKING,BiometricState.RETURN_TO_NEUTRAL,BiometricState.STABILIZING_FOR_CAPTURE,BiometricState.CAPTURING}
                if self.biometric_pipeline.state not in active:
                    await asyncio.sleep(.03);continue
                item=self.camera_service.raw_snapshot(last)
                if not item:await asyncio.sleep(.01);continue
                last=item.sequence;eye=await asyncio.to_thread(self.blink_detector.observe,item.image,int(item.captured_at*1000));now=asyncio.get_running_loop().time();tracked+=1
                if self.biometric_pipeline.state in {BiometricState.RETURN_TO_NEUTRAL,BiometricState.STABILIZING_FOR_CAPTURE,BiometricState.CAPTURING}:
                    threshold=self.biometric_pipeline.blink.reopen_threshold;self._latest_eyes_open=bool(eye.face_count==1 and eye.bilateral is not None and threshold is not None and eye.bilateral<=threshold);self._latest_eye_at=now;await asyncio.sleep(1/max(1,settings.face_liveness_analysis_fps));continue
                if not self.liveness_engine.attempt_id:self.liveness_engine.start(now)
                challenge=self.liveness_engine.observe(eye,now)
                if challenge.passed:self.biometric_pipeline.state=BiometricState.LIVENESS_PASSED
                elif challenge.failed:self.biometric_pipeline.state=BiometricState.ERROR
                elif self.liveness_engine.neutral_yaw is None:self.biometric_pipeline.state=BiometricState.LIVENESS_CALIBRATING
                else:self.biometric_pipeline.state=BiometricState.LIVENESS_TRACKING
                state=self.biometric_pipeline.state
                if settings.face_liveness_debug:
                    logging.getLogger("LIVENESS").info("[LIVENESS] eye_metric_left=%s eye_metric_right=%s analysis_fps=%.1f",f"{eye.left:.4f}" if eye.left is not None else "unavailable",f"{eye.right:.4f}" if eye.right is not None else "unavailable",tracked/max(now-started,.001))
                self.camera_panel_state.blink_count=self.biometric_pipeline.blink.blinks
                if eye.face_count!=1 and state!=BiometricState.ERROR:
                    self.camera_panel_state.message="Keep exactly one face centered."
                elif eye.bilateral is None and state!=BiometricState.ERROR:
                    self.camera_panel_state.message="Eye landmarks unavailable — face the camera directly."
                elif state==BiometricState.LIVENESS_CALIBRATING:
                    count,total=self.biometric_pipeline.blink.calibration_progress;self.camera_panel_state.liveness="in_progress";self.camera_panel_state.message=f"Keep your eyes open and look straight... Calibrating {count} / {total}"
                elif state==BiometricState.LIVENESS_TRACKING:
                    step=self.liveness_engine.index+1;total=len(self.liveness_engine.steps);phase=self.biometric_pipeline.blink.phase
                    self.camera_panel_state.message=f"Step {step} of {total} · Blink detected... open your eyes" if self.liveness_engine.current and self.liveness_engine.current.value=="BLINK" and phase in {"possible_closed","waiting_reopen","reopening"} else f"Step {step} of {total} · {self.liveness_engine.instruction}"
                elif state==BiometricState.ERROR:
                    self.camera_panel_state.liveness="timed_out";self.camera_panel_state.message="That action wasn't detected. Try again." if self.liveness_engine.failure_reason!="LIVENESS_MULTIPLE_FACES" else "Only one person should be visible.";self.camera_panel_state.retry_button.visible=True
                elif state==BiometricState.LIVENESS_PASSED:
                    self.camera_panel_state.liveness="passed";self.camera_panel_state.message="✓ Blink verified";self.camera_panel_state.retry_button.visible=False;self.camera_panel_state.sync();self._update_camera_status();await self._on_liveness_passed(item);continue
                self.camera_panel_state.sync();self._update_camera_status();await asyncio.sleep(1/max(1,settings.face_liveness_analysis_fps))
        except Exception:logging.getLogger("LIVENESS").exception("liveness loop failed");self.stop_camera();raise
        finally:self._liveness_loop_running=False

    async def _on_liveness_passed(self,item):
        if self.camera_context=="enrollment":
            logging.getLogger("FACE").info("[ENROLL] entering neutral stabilization");self.biometric_pipeline.state=BiometricState.RETURN_TO_NEUTRAL;self._neutral_since=None;self._neutral_anchor=None;self.camera_panel_state.message="Liveness verified — look straight and hold still"
        elif self.biometric_pipeline.begin_recognition() and not self._recognition_running:
            self._recognition_running=True;best=self.biometric_pipeline.best_frame.frame if self.biometric_pipeline.best_frame else await asyncio.to_thread(self.camera_service.encode_analysis,item,get_settings().camera_analysis_width);await self._complete_live_attendance(best)
        self.camera_panel_state.sync();self._update_camera_status()

    def retry_liveness(self,_=None):
        if not self.camera_service.running:return
        self.biometric_pipeline.retry_liveness(time.monotonic());self.liveness_engine.retry(time.monotonic());self.camera_panel_state.blink_count=0;self.camera_panel_state.liveness="in_progress";self.camera_panel_state.message="Keep your eyes open and look straight...";self.camera_panel_state.retry_button.visible=False;self.camera_panel_state.sync();self._update_camera_status()

    async def _handle_camera_analysis(self,item,frame,analysis):
        now=asyncio.get_running_loop().time()
        if not analysis.connected:
            code=(((analysis.data or {}).get("error") or {}).get("code"));count=2 if code=="MULTIPLE_FACES_FOUND" else 0
            self.biometric_pipeline.observe(FaceObservation(now,count));self.camera_panel_state.face="multiple_faces" if count>1 else "no_face";self.camera_panel_state.message="Only one person should be visible." if count>1 else "Position your face inside the guide.";self.camera_panel_state.sync();self._update_camera_status();return
        data=analysis.data or {};quality=data.get("quality") or {};box=data.get("faceBox") or {};face_count=1;closed=not (self._latest_eyes_open and now-self._latest_eye_at<.35);quality_ok=all(quality.get(x) for x in ("faceSizeAccepted","lightingAccepted","blurAccepted"));score=float(data.get("detectionConfidence") or 0)+min(float(quality.get("blurVariance") or 0)/1000,.2)
        if self.camera_context=="enrollment" and self.biometric_pipeline.state==BiometricState.IDENTITY_CONSISTENCY:return
        if self.camera_context=="enrollment" and self.biometric_pipeline.state in {BiometricState.RETURN_TO_NEUTRAL,BiometricState.STABILIZING_FOR_CAPTURE,BiometricState.CAPTURING}:
            self._handle_enrollment_capture(now,item.sequence,frame,data,quality,box,closed,quality_ok);self.camera_panel_state.sync();self._update_camera_status();return
        state=self.biometric_pipeline.observe(FaceObservation(now,face_count,(float(box.get("centerX",.5)),float(box.get("centerY",.5))),float(box.get("size",0)),quality_ok,None,item.sequence,frame,score))
        self.camera_panel_state.face="one_face";self.camera_panel_state.face_size="good" if quality.get("faceSizeAccepted") else "adjust";self.camera_panel_state.lighting="good" if quality.get("lightingAccepted") else "adjust";self.camera_panel_state.sharpness="good" if quality.get("blurAccepted") else "adjust";self.camera_panel_state.position="good" if state not in {BiometricState.STABILIZING,BiometricState.QUALITY_CHECK} else "adjust";self.camera_panel_state.blink_count=self.biometric_pipeline.blink.blinks
        if state==BiometricState.STABILIZING:self.camera_panel_state.message="Hold still..."
        elif state in {BiometricState.LIVENESS_PROMPT,BiometricState.LIVENESS_CALIBRATING}:self.camera_panel_state.liveness="in_progress";self.camera_panel_state.message="Keep your eyes open for a moment..."
        self.camera_panel_state.sync();self._update_camera_status()

    def _update_camera_status(self):
        for control in (self.camera_panel_state.status_text,self.camera_panel_state.camera_badge,self.camera_panel_state.camera_label,self.camera_panel_state.instruction_text,self.camera_panel_state.progress_text,self.camera_panel_state.retry_button):control.update()

    def _handle_enrollment_capture(self,now,frame_sequence,frame,data,quality,box,closed,quality_ok):
        center=(float(box.get("centerX",.5)),float(box.get("centerY",.5)));size=float(box.get("size",0));frontal=data.get("pose","center")=="center"
        if not quality_ok or closed or not frontal:
            self._neutral_since=None;self._neutral_anchor=None;self.biometric_pipeline.state=BiometricState.RETURN_TO_NEUTRAL;self.camera_panel_state.message="Look straight with eyes open and hold still...";return
        if self._neutral_anchor is None:self._neutral_anchor=(center,size);self._neutral_since=now;self.biometric_pipeline.state=BiometricState.STABILIZING_FOR_CAPTURE;self.camera_panel_state.message="Look straight and hold still...";return
        anchor_center,anchor_size=self._neutral_anchor;movement=((center[0]-anchor_center[0])**2+(center[1]-anchor_center[1])**2)**.5;size_change=abs(size-anchor_size)/max(anchor_size,1e-6)
        if movement>.035 or size_change>.10:self._neutral_anchor=(center,size);self._neutral_since=now;self.biometric_pipeline.state=BiometricState.STABILIZING_FOR_CAPTURE;self.camera_panel_state.message="Hold still for enrollment capture...";return
        if now-self._neutral_since<.7:self.biometric_pipeline.state=BiometricState.STABILIZING_FOR_CAPTURE;self.camera_panel_state.message="Face stable — preparing capture...";return
        if self.biometric_pipeline.state!=BiometricState.CAPTURING:logging.getLogger("FACE").info("[FACE] neutral stability passed")
        self.biometric_pipeline.state=BiometricState.CAPTURING;settings=get_settings();slot=len(self.camera_frames)+1
        if now-self._capture_last_at<settings.face_enrollment_capture_interval_seconds:self.camera_panel_state.message=f"Getting a fresh image for capture {slot} of 3...";return
        logging.getLogger("FACE").info("[ENROLL] capture_candidate slot=%s frame_seq=%s",slot,frame_sequence)
        duplicate=frame_sequence in self.camera_capture_sequences or frame in self.camera_frames
        if duplicate:
            self._capture_retries+=1;logging.getLogger("FACE").info("[ENROLL] duplicate_candidate_discarded slot=%s frame_seq=%s retry=%s",slot,frame_sequence,self._capture_retries);self.camera_panel_state.message="Getting a fresh frame..."
            if self._capture_retries>=settings.face_enrollment_max_capture_retries:self.stop_camera();self._face_message("Fresh capture unavailable","Could not obtain a new camera frame. Check the camera and retry enrollment.",False)
            return
        self.camera_frames.append(frame);self.camera_capture_sequences.append(frame_sequence);self._capture_last_at=now;self._capture_retries=0;self.camera_panel_state.capture_count=len(self.camera_frames);logging.getLogger("FACE").info("[ENROLL] capture_accepted slot=%s frame_seq=%s",len(self.camera_frames),frame_sequence);self.camera_panel_state.message=f"Capture {len(self.camera_frames)} of 3 ✓"
        if len(self.camera_frames)>=3:
            self.biometric_pipeline.state=BiometricState.IDENTITY_CONSISTENCY;self.camera_panel_state.message="Verifying captures...";logging.getLogger("FACE").info("[ENROLL] independent_capture_check passed");self._enrollment_finalizing=True;self.page.run_task(self._finalize_live_enrollment)

    async def _finalize_live_enrollment(self):
        frames=[(f"frame_{i}.jpg",data,"image/jpeg") for i,data in enumerate(self.camera_frames[:3],1)];student=self.camera_student
        result=await asyncio.to_thread(self.api_client.enroll_face,student["_id"],frames)
        if result.connected:
            logging.getLogger("FACE").info("[ENROLL] enrollment_saved");self.stop_camera();self._enrollment_finalizing=False;self._face_message("✓ Face Enrollment Complete",f"Student: {student.get('display_name','Student')}\nVerified captures: 3\nLiveness: Passed\nBiometric template: Encrypted",True);self.load_face_enrollments();return
        code=(((result.data or {}).get("error") or {}).get("code"))
        if code=="DUPLICATE_FACE_FRAMES" and self.camera_service.running:
            self._final_validation_retries+=1
            if self._final_validation_retries>=get_settings().face_enrollment_max_capture_retries:self.stop_camera();self._enrollment_finalizing=False;self._face_message("Fresh capture unavailable","Repeated frame reuse prevented a safe enrollment. Please retry.",False);return
            discarded_seq=self.camera_capture_sequences.pop();self.camera_frames.pop();self.camera_panel_state.capture_count=len(self.camera_frames);self.biometric_pipeline.state=BiometricState.CAPTURING;self._enrollment_finalizing=False;logging.getLogger("FACE").info("[ENROLL] duplicate_candidate_discarded slot=%s frame_seq=%s retry=%s",len(self.camera_frames)+1,discarded_seq,self._final_validation_retries);self.camera_panel_state.message="Getting a fresh frame...";self.camera_panel_state.sync();self._update_camera_status();return
        self.stop_camera();self._enrollment_finalizing=False;self._face_message("Enrollment failed",result.error or "Enrollment was not stored.",False)
    def load_faculty_attendance(self):
        result=self.api_client.faculty_attendance_sessions();self.attendance_sessions=(result.data or {}).get("items",[]) if result.connected else [];self.attendance_notice=None if result.connected else result.error;self.render_authenticated_shell()
    def start_attendance(self,lecture):
        result=self.api_client.start_attendance({"timetable_entry_id":lecture["timetableEntryId"],"lecture_date":lecture["date"]})
        if result.connected and result.data:self.current_attendance=result.data;self.attendance_notice=None
        else:self.attendance_notice=result.error or "Attendance could not be started."
        self.render_authenticated_shell()
    def open_faculty_attendance(self,session_id):
        self.stop_camera();result=self.api_client.attendance_session(session_id);self.current_attendance=result.data if result.connected else None;self.attendance_notice=None if result.connected else result.error;self.attendance_mode="manual";self.face_attendance_status_data=None;self.face_attendance_result=None;self.face_recognition_mode="all";self.face_selected_student_id=None;self.face_reference_image=None;self.render_authenticated_shell()
    def set_attendance_mode(self,mode):
        self.attendance_mode=mode
        if mode=="face" and self.current_attendance:
            result=self.api_client.face_attendance_status(self.current_attendance["_id"]);self.face_attendance_status_data=result.data if result.connected else {"capability":{"faceAttendance":"unavailable"},"stats":{}};self.attendance_notice=None if result.connected else (result.error or "Face Attendance unavailable; continue manually.");self.camera_context="attendance";self.camera_student=None;self._reset_camera_challenge()
        else:self.stop_camera();self.camera_context=None
        self.render_authenticated_shell()
    def _reset_camera_challenge(self):
        self.stop_camera();self.camera_frames=[];self._neutral_since=None;self._neutral_anchor=None;self._capture_last_at=0.;self.biometric_pipeline=self._new_biometric_pipeline();self.camera_panel_state=CameraPanelState()
    def set_face_recognition_mode(self,mode):
        self.face_recognition_mode=mode;self.face_selected_student_id=None;self.face_reference_image=None;self.face_attendance_result=None;self._reset_camera_challenge();self.camera_context="attendance";self.render_authenticated_shell()
    def set_face_selected_student(self,student_id):
        self.face_selected_student_id=student_id;self.face_reference_image=None
        if student_id and self.current_attendance:
            reference=self.api_client.face_reference(student_id,self.current_attendance["_id"])
            if reference.connected:self.face_reference_image=(reference.data or {}).get("content")
        self.face_attendance_result=None;self._reset_camera_challenge();self.camera_context="attendance";self.render_authenticated_shell()
    async def capture_attendance_face(self,_=None):
        if not self.current_attendance:return
        picker=ft.FilePicker();self.page.services.append(picker);selected=await picker.pick_files(dialog_title="Capture or select one recent face frame",file_type=ft.FilePickerFileType.CUSTOM,allowed_extensions=["jpg","jpeg","png","webp"],allow_multiple=False,with_data=True)
        if not selected:return
        chosen=selected[0];content=chosen.bytes
        if content is None and chosen.path:
            try:
                with open(chosen.path,"rb") as stream:content=stream.read(5*1024*1024+1)
            except OSError:content=None
        if content is None:self.attendance_notice="Captured frame could not be read.";self.render_authenticated_shell();return
        suffix=(chosen.name.rsplit(".",1)[-1] if "." in chosen.name else "jpg").casefold();mime={"jpg":"image/jpeg","jpeg":"image/jpeg","png":"image/png","webp":"image/webp"}.get(suffix,"application/octet-stream");selected=self.face_selected_student_id if self.face_recognition_mode=="specific" else None;result=self.api_client.identify_attendance_face(self.current_attendance["_id"],chosen.name,content,mime,selected)
        self.face_reference_image=None;self.face_attendance_result=result.data if result.connected else {"result":"ai_unavailable"};self.attendance_notice=None if result.connected else result.error
        recognized=(self.face_attendance_result or {}).get("student") or {}
        if recognized.get("id"):
            reference=self.api_client.face_reference(recognized["id"],self.current_attendance["_id"])
            if reference.connected:self.face_reference_image=(reference.data or {}).get("content")
        refreshed=self.api_client.attendance_session(self.current_attendance["_id"]);status=self.api_client.face_attendance_status(self.current_attendance["_id"])
        if refreshed.connected:self.current_attendance=refreshed.data
        if status.connected:self.face_attendance_status_data=status.data
        self.render_authenticated_shell()
    async def _complete_live_attendance(self,frame):
        self.stop_camera()
        selected=self.face_selected_student_id if self.face_recognition_mode=="specific" else None
        result=await asyncio.to_thread(self.api_client.identify_attendance_face,self.current_attendance["_id"],"live.jpg",frame,"image/jpeg",selected,list(self.camera_frames[:3]))
        self.face_reference_image=None;self.face_attendance_result=result.data if result.connected else {"result":"ai_unavailable"};self.attendance_notice=None if result.connected else result.error
        recognized=(self.face_attendance_result or {}).get("student") or {}
        if recognized.get("id"):
            reference=await asyncio.to_thread(self.api_client.face_reference,recognized["id"],self.current_attendance["_id"])
            if reference.connected:self.face_reference_image=(reference.data or {}).get("content")
        refreshed=await asyncio.to_thread(self.api_client.attendance_session,self.current_attendance["_id"]);status=await asyncio.to_thread(self.api_client.face_attendance_status,self.current_attendance["_id"])
        if refreshed.connected:self.current_attendance=refreshed.data
        if status.connected:self.face_attendance_status_data=status.data
        self.biometric_pipeline.finish_recognition((self.face_attendance_result or {}).get("result"));self.biometric_pipeline.cooldown();self.camera_frames=[];self._recognition_running=False;self.camera_panel_state.capture_count=0;self.camera_panel_state.liveness="not_started";self.camera_panel_state.message="Live verification complete. Review it, then start the camera for the next Student.";self.camera_panel_state.sync();self.render_authenticated_shell()
    def mark_attendance(self,student_id,status):
        if not self.current_attendance:return
        for record in self.current_attendance.get("records",[]):
            if str(record.get("student_id"))==str(student_id):record["status"]=status
        from collections import Counter
        counts=Counter(x.get("status") or "unmarked" for x in self.current_attendance.get("records",[]));self.current_attendance["summary"]={**counts,"total":len(self.current_attendance.get("records",[]))};self.render_authenticated_shell()
    def filter_attendance_roster(self,search=None,status=None):
        if search is not None:self.attendance_search=search
        if status is not None:self.attendance_status_filter=status
        self.render_authenticated_shell()
    def save_attendance(self,_=None):
        if not self.current_attendance:return
        payload={"records":[{"student_id":x["student_id"],"status":x["status"],"remark":x.get("remark")} for x in self.current_attendance.get("records",[]) if x.get("status")],"topic":self.current_attendance.get("topic"),"notes":self.current_attendance.get("notes")};result=self.api_client.save_attendance_draft(self.current_attendance["_id"],payload)
        if result.connected:self.current_attendance=result.data;self.attendance_notice="Draft saved."
        else:self.attendance_notice=result.error
        self.render_authenticated_shell()
    def review_attendance(self,_=None):
        if not self.current_attendance:return
        summary=self.current_attendance.get("summary") or {}
        dialog=ft.AlertDialog(modal=True,title=ft.Text("Submit Attendance?"),content=ft.Text(f"Review: {summary.get('present',0)} present, {summary.get('absent',0)} absent, {summary.get('late',0)} late, {summary.get('excused',0)} excused. Submission restricts Faculty editing."),actions=[ft.TextButton("Cancel",on_click=lambda _:self.page.pop_dialog()),ft.FilledButton("Confirm Submit",on_click=self.confirm_attendance)])
        self.page.show_dialog(dialog)
    def confirm_attendance(self,_=None):
        self.page.pop_dialog();self.submit_attendance()
    def submit_attendance(self,_=None):
        if not self.current_attendance:return
        self.save_attendance();result=self.api_client.submit_attendance(self.current_attendance["_id"])
        if result.connected:self.current_attendance=result.data;self.attendance_notice="Attendance submitted."
        else:self.attendance_notice=result.error
        self.render_authenticated_shell()
    def load_admin_attendance(self):
        result=self.api_client.admin_attendance_sessions(pageSize=100,status=None if self.admin_attendance_filter=="all" else self.admin_attendance_filter);self.attendance_sessions=(result.data or {}).get("items",[]) if result.connected else [];self.current_attendance=None;self.attendance_notice=None if result.connected else result.error;self.render_authenticated_shell()
    def filter_admin_attendance(self,status):
        self.admin_attendance_filter=status;self.load_admin_attendance()
    def open_admin_attendance(self,session_id):
        result=self.api_client.attendance_session(session_id,admin=True);self.current_attendance=result.data if result.connected else None;self.attendance_notice=None if result.connected else result.error;self.render_authenticated_shell()
    def admin_attendance_action(self,session_id,action):
        result=self.api_client.admin_attendance_action(session_id,action,f"Administrative {action} from oversight screen")
        if result.connected:self.open_admin_attendance(session_id)
        else:self.attendance_notice=result.error;self.render_authenticated_shell()
    def load_student_attendance(self):
        summary=self.api_client.student_attendance_summary();history=self.api_client.student_attendance_history();self.attendance_data={**(summary.data or {}),"history":((history.data or {}).get("items",[]))} if summary.connected else {"summary":{},"subjects":[],"history":[]};self.render_authenticated_shell()

    def load_timetable(self,page:int=1)->None:
        old=self.timetable_state or TimetablePageState();self.timetable_state=TimetablePageState(loading=True,view=old.view,filters=dict(old.filters),options=dict(old.options),page=page);self.render_authenticated_shell()
        if self.current_screen=="preview":self.timetable_state.loading=False;self.timetable_state.error="Sign in as an Admin to manage the production timetable."
        else:
            result=self.api_client.list_timetable(page=page,pageSize=20,**self.timetable_state.filters);self.timetable_state.loading=False
            if result.connected and result.data:
                self.timetable_state.items=result.data.get("items",[]);pagination=result.data.get("pagination") or {};self.timetable_state.total=pagination.get("total",0);self.timetable_state.pages=pagination.get("pages",0)
                resources={"classes":"classes","departments":"departments","semesters":"semesters"}
                for key,resource in resources.items():
                    listed=self.api_client.list_academic(resource,page=1,pageSize=100,status="active");self.timetable_state.options[key]=listed.data.get("items",[]) if listed.connected and listed.data else []
                faculty=self.api_client.list_faculty(page=1,pageSize=100,status="active");self.timetable_state.options["faculty"]=faculty.data.get("items",[]) if faculty.connected and faculty.data else []
            else:self.timetable_state.error=result.error or "Timetable data is unavailable."
        self.render_authenticated_shell()
    def set_timetable_view(self,view):
        if self.timetable_state:self.timetable_state.view=view
        self.render_authenticated_shell()
    def filter_timetable(self,field,value):
        if not self.timetable_state:return
        if value:self.timetable_state.filters[field]=value
        else:self.timetable_state.filters.pop(field,None)
        self.load_timetable()
    def timetable_assignments(self,faculty_id):
        result=self.api_client.get_faculty(faculty_id);return result.data.get("assignments",[]) if result.connected and result.data else []
    def open_timetable_form(self,record=None):
        if self.current_screen!="authenticated" or not self.timetable_state:return
        def save(payload):
            result=self.api_client.update_timetable(record["_id"],payload) if record else self.api_client.create_timetable(payload);self.page.pop_dialog()
            if result.connected:self.load_timetable(self.timetable_state.page)
            else:self.timetable_state.error=result.error or "Lecture could not be saved.";self.render_authenticated_shell()
        self.page.show_dialog(ft.AlertDialog(content=build_timetable_form(self.tokens,save,lambda _:self.page.pop_dialog(),self.timetable_state.options.get("faculty",[]),self.timetable_assignments,record),modal=True))
    def timetable_action(self,record,action):
        if action=="edit":self.open_timetable_form(record);return
        target="active" if action=="activate" else "inactive";verb="Activate" if target=="active" else "Deactivate"
        self.page.show_dialog(ft.AlertDialog(title=ft.Text(f"{verb} lecture?"),content=ft.Text("The recurring entry is retained and no attendance records are created."),actions=[ft.TextButton("Cancel",on_click=lambda _:self.page.pop_dialog()),ft.FilledButton(verb,on_click=lambda _:(self.page.pop_dialog(),self.api_client.update_timetable_status(record["_id"],target),self.load_timetable()))]))

    def load_faculty(self,search:str|None=None)->None:
        old=self.faculty_state or FacultyPageState(); self.faculty_state=FacultyPageState(loading=True,search=old.search if search is None else search,status=old.status,department_id=old.department_id,department_options=list(old.department_options),active_total=old.active_total,inactive_total=old.inactive_total); self.render_authenticated_shell()
        if self.current_screen=="preview": self.faculty_state.loading=False; self.faculty_state.error="Sign in as an Admin to manage Faculty."
        else:
            result=self.api_client.list_faculty(page=1,pageSize=20,search=self.faculty_state.search,status=self.faculty_state.status,department_id=self.faculty_state.department_id); self.faculty_state.loading=False
            if result.connected and result.data:
                self.faculty_state.items=result.data.get("items",[]); self.faculty_state.total=(result.data.get("pagination") or {}).get("total",0)
                active=self.api_client.list_faculty(page=1,pageSize=1,status="active"); inactive=self.api_client.list_faculty(page=1,pageSize=1,status="inactive")
                self.faculty_state.active_total=((active.data or {}).get("pagination") or {}).get("total",0) if active.connected else 0; self.faculty_state.inactive_total=((inactive.data or {}).get("pagination") or {}).get("total",0) if inactive.connected else 0
                departments=self.api_client.list_academic("departments",page=1,pageSize=100,status="active");self.faculty_state.department_options=departments.data.get("items",[]) if departments.connected and departments.data else []
            else: self.faculty_state.error=result.error or "Faculty data is unavailable."
        self.render_authenticated_shell()
    def filter_faculty(self,status):
        if self.faculty_state:self.faculty_state.status=status
        self.load_faculty()
    def filter_faculty_department(self,department):
        if self.faculty_state:self.faculty_state.department_id=department
        self.load_faculty()
    def open_faculty_form(self,record=None):
        if self.current_screen!="authenticated":return
        def save(payload):
            result=self.api_client.update_faculty(record["_id"],payload) if record else self.api_client.create_faculty(payload); self.page.pop_dialog()
            if result.connected:self.load_faculty()
            elif self.faculty_state:self.faculty_state.error=result.error;self.render_authenticated_shell()
        departments_result=self.api_client.list_academic("departments",page=1,pageSize=100,status="active");departments=departments_result.data.get("items",[]) if departments_result.connected and departments_result.data else []
        self.page.show_dialog(ft.AlertDialog(content=build_faculty_form(self.tokens,save,lambda _:self.page.pop_dialog(),record,departments),modal=True))
    def faculty_action(self,fid,action):
        result=self.api_client.get_faculty(fid)
        if not result.connected or not result.data:
            if self.faculty_state:self.faculty_state.error=result.error
            self.render_authenticated_shell();return
        record=result.data
        if action in {"view","assignments"}:self.page.show_dialog(ft.AlertDialog(content=build_faculty_details(record,self.tokens,lambda _:self.page.pop_dialog()),modal=True));return
        if action=="edit":self.open_faculty_form(record);return
        if action=="assign":
            def save(payload):
                assigned=self.api_client.create_faculty_assignment(fid,payload);self.page.pop_dialog()
                if assigned.connected:self.load_faculty()
                elif self.faculty_state:self.faculty_state.error=assigned.error;self.render_authenticated_shell()
            choices={}
            for key,resource in (("years","academic-years"),("classes","classes"),("subjects","subjects")):
                listed=self.api_client.list_academic(resource,page=1,pageSize=100,status="active");choices[key]=listed.data.get("items",[]) if listed.connected and listed.data else []
            self.page.show_dialog(ft.AlertDialog(content=build_assignment_form(self.tokens,save,lambda _:self.page.pop_dialog(),choices),modal=True));return
        new="inactive" if record.get("status")=="active" else "active"
        self.page.show_dialog(ft.AlertDialog(title=ft.Text(f"{new.title()} Faculty?"),content=ft.Text("Account access and active teaching ownership will be synchronized without deleting history."),actions=[ft.TextButton("Cancel",on_click=lambda _:self.page.pop_dialog()),ft.FilledButton("Confirm",on_click=lambda _:(self.page.pop_dialog(),self.api_client.update_faculty_status(fid,new),self.load_faculty()))]))

    async def open_faculty_import(self,_=None):
        if self.current_screen!="authenticated":return
        picker=ft.FilePicker();self.page.services.append(picker);selected=await picker.pick_files(dialog_title="Select Faculty CSV",file_type=ft.FilePickerFileType.CUSTOM,allowed_extensions=["csv"],with_data=True)
        if not selected:return
        chosen=selected[0];content=chosen.bytes
        if content is None and chosen.path:
            try:
                with open(chosen.path,"rb") as stream:content=stream.read(1_048_577)
            except OSError:content=None
        if content is None:return
        result=self.api_client.preview_faculty_import(chosen.name,content)
        if not result.connected or not result.data:
            if self.faculty_state:self.faculty_state.error=result.error
            self.render_authenticated_shell();return
        report=result.data;errors=[f"Row {x['row']}: {'; '.join(x['errors'])}" for x in report.get("rows",[]) if not x.get("valid")][:8]
        def confirm(_):
            done=self.api_client.confirm_faculty_import(chosen.name,content);self.page.pop_dialog()
            if done.connected:self.load_faculty()
            elif self.faculty_state:self.faculty_state.error=done.error;self.render_authenticated_shell()
        self.page.show_dialog(ft.AlertDialog(title=ft.Text("Faculty import preview"),content=ft.Column([ft.Text(f"Valid: {report.get('valid',0)} · Invalid: {report.get('invalid',0)}"),*[ft.Text(x,color=self.tokens["danger"],size=12) for x in errors],ft.Text("No assignments are inferred from CSV.",size=11)],tight=True),actions=[ft.TextButton("Cancel",on_click=lambda _:self.page.pop_dialog()),ft.FilledButton("Confirm Import",disabled=bool(report.get("invalid")),on_click=confirm)]))

    def load_students(self, search: str | None = None) -> None:
        previous = self.student_state or StudentPageState()
        self.student_state = StudentPageState(loading=True, search=previous.search if search is None else search, status=previous.status, active_total=previous.active_total, inactive_total=previous.inactive_total, filters=dict(previous.filters))
        self.render_authenticated_shell()
        if self.current_screen == "preview":
            self.student_state.loading = False; self.student_state.error = "Sign in as an Admin to manage Students."
        else:
            result = self.api_client.list_students(page=1, pageSize=20, search=self.student_state.search, status=self.student_state.status, **self.student_state.filters)
            self.student_state.loading = False
            if result.connected and result.data:
                self.student_state.items = result.data.get("items", []); self.student_state.total = (result.data.get("pagination") or {}).get("total", 0)
                active = self.api_client.list_students(page=1,pageSize=1,status="active"); inactive = self.api_client.list_students(page=1,pageSize=1,status="inactive")
                self.student_state.active_total = ((active.data or {}).get("pagination") or {}).get("total",0) if active.connected else 0
                self.student_state.inactive_total = ((inactive.data or {}).get("pagination") or {}).get("total",0) if inactive.connected else 0
            else: self.student_state.error = result.error or "Student data is unavailable."
        self.render_authenticated_shell()

    def filter_students(self, status: str | None) -> None:
        if self.student_state: self.student_state.status=status
        self.load_students()

    def filter_students_academic(self, filters: dict) -> None:
        if self.student_state: self.student_state.filters=filters
        self.load_students()

    def open_student_create(self, _: ft.ControlEvent | None = None) -> None:
        if self.current_screen != "authenticated": return
        def submit(payload: dict):
            result = self.api_client.create_student(payload); self.page.pop_dialog()
            if result.connected: self.load_students()
            else:
                if self.student_state: self.student_state.error = result.error or "Student could not be created."
                self.render_authenticated_shell()
        self.page.show_dialog(ft.AlertDialog(content=build_student_create_form(self.tokens, submit, lambda _: self.page.pop_dialog()), modal=True))

    def open_student_details(self, student_id: str) -> None:
        if self.current_screen != "authenticated": return
        result = self.api_client.get_student(student_id)
        if result.connected and result.data:
            self.page.show_dialog(ft.AlertDialog(content=build_student_details(result.data, self.tokens, lambda _: self.page.pop_dialog()), modal=True))
        elif self.student_state:
            self.student_state.error = result.error or "Student details are unavailable."; self.render_authenticated_shell()

    def student_action(self, student_id: str, action: str) -> None:
        record_result = self.api_client.get_student(student_id)
        if not record_result.connected or not record_result.data:
            if self.student_state: self.student_state.error = record_result.error or "Student details are unavailable."
            self.render_authenticated_shell(); return
        record = record_result.data
        if action in {"view", "history"}: self.open_student_details(student_id); return
        if action == "face":
            status=self.api_client.face_status(student_id);self.open_face_enrollment({**record,"face":status.data if status.connected and status.data else {"enrolled":False}});return
        if action == "edit":
            def save(payload):
                result=self.api_client.update_student(student_id,payload); self.page.pop_dialog()
                if result.connected: self.load_students()
                elif self.student_state: self.student_state.error=result.error; self.render_authenticated_shell()
            self.page.show_dialog(ft.AlertDialog(content=build_student_profile_form(record,self.tokens,save,lambda _:self.page.pop_dialog()),modal=True)); return
        if action == "enrollment":
            def change(payload):
                result=self.api_client.change_student_enrollment(student_id,payload); self.page.pop_dialog()
                if result.connected: self.load_students()
                elif self.student_state: self.student_state.error=result.error; self.render_authenticated_shell()
            self.page.show_dialog(ft.AlertDialog(content=build_enrollment_form(self.tokens,change,lambda _:self.page.pop_dialog()),modal=True)); return
        new_status = "inactive" if record.get("status") == "active" else "active"
        self.page.show_dialog(ft.AlertDialog(title=ft.Text(f"{new_status.title()} Student?"),content=ft.Text("Profile and enrollment history will be preserved. Account access will be synchronized."),actions=[ft.TextButton("Cancel",on_click=lambda _:self.page.pop_dialog()),ft.FilledButton("Confirm",on_click=lambda _:(self.page.pop_dialog(),self.api_client.update_student_status(student_id,new_status),self.load_students()))]))

    async def open_student_import(self, _: ft.ControlEvent | None = None) -> None:
        if self.current_screen != "authenticated": return
        picker = ft.FilePicker(); self.page.services.append(picker)
        selected = await picker.pick_files(dialog_title="Select Student CSV", file_type=ft.FilePickerFileType.CUSTOM, allowed_extensions=["csv"], with_data=True)
        if not selected: return
        chosen = selected[0]
        content = chosen.bytes
        if content is None and chosen.path:
            try:
                with open(chosen.path, "rb") as stream: content = stream.read(1_048_577)
            except OSError: content = None
        if content is None: return
        result = self.api_client.preview_student_import(chosen.name, content)
        if not result.connected or not result.data:
            if self.student_state: self.student_state.error = result.error or "CSV preview failed."
            self.render_authenticated_shell(); return
        report = result.data
        errors = [f"Row {row['row']}: {'; '.join(row['errors'])}" for row in report.get("rows", []) if not row.get("valid")][:8]
        def confirm_import(_):
            imported = self.api_client.confirm_student_import(chosen.name, content); self.page.pop_dialog()
            if imported.connected: self.load_students()
            elif self.student_state:
                self.student_state.error = imported.error or "CSV import failed."; self.render_authenticated_shell()
        self.page.show_dialog(ft.AlertDialog(title=ft.Text("Student import preview"), content=ft.Column([ft.Text(f"Valid: {report.get('valid', 0)} · Invalid: {report.get('invalid', 0)}"), *[ft.Text(error, color=self.tokens["danger"], size=12) for error in errors], ft.Text("Preview performed no database writes.", size=11)], tight=True), actions=[ft.TextButton("Cancel", on_click=lambda _: self.page.pop_dialog()), ft.FilledButton("Confirm Import", disabled=bool(report.get("invalid")), on_click=confirm_import)]))

    def select_setup_resource(self, resource: str) -> None:
        label = next((label for label, value in NAVIGATION_RESOURCES.items() if value == resource), "Dashboard")
        self.select_navigation(label)

    def skip_setup_wizard(self, _: ft.ControlEvent | None = None) -> None:
        self.setup_wizard_visible = False
        self.render_authenticated_shell()

    def load_academic_resource(self, resource: str, *, page: int = 1, search: str | None = None, status: str | None = None) -> None:
        previous = self.academic_state if self.academic_state and self.academic_state.resource == resource else AcademicPageState(resource)
        self.academic_state = AcademicPageState(resource, page=page, page_size=previous.page_size, loading=True, search=previous.search if search is None else search, status_filter=previous.status_filter if status is None else status, filters=dict(previous.filters), filter_options=dict(previous.filter_options))
        self.render_authenticated_shell()
        if self.current_screen == "preview":
            self.academic_state.loading = False
            self.academic_state.error = "Sign in as an Admin to use production academic management."
            self.render_authenticated_shell()
            return
        result = self.api_client.academic_institution() if resource == "institution" else self.api_client.list_academic(resource, page=page, pageSize=self.academic_state.page_size, search=self.academic_state.search, status=self.academic_state.status_filter, **self.academic_state.filters)
        self.academic_state.loading = False
        if not result.connected or not result.data:
            self.academic_state.error = result.error or "Academic data is unavailable."
        elif resource == "institution":
            self.academic_state.items = [result.data]
            self.academic_state.total = 1
            self.academic_state.total_pages = 1
        else:
            self.academic_state.items = result.data.get("items", [])
            self.academic_state.page = result.data.get("page", page)
            self.academic_state.total = result.data.get("total", 0)
            self.academic_state.total_pages = result.data.get("totalPages", 0)
            self.academic_state.filter_options = self._reference_options(resource)
            if resource == "subjects":
                self.academic_state.filter_options["type"] = [(value, value.title()) for value in ("theory", "practical", "project", "elective")]
        self.render_authenticated_shell()

    def filter_academic_status(self, value: str | None) -> None:
        if not self.academic_state:
            return
        self.academic_state.status_filter = value
        self.load_academic_resource(self.academic_state.resource)

    def filter_academic_reference(self, field: str, value: str | None) -> None:
        if not self.academic_state:
            return
        if value is None:
            self.academic_state.filters.pop(field, None)
        else:
            self.academic_state.filters[field] = value
        self.load_academic_resource(self.academic_state.resource)

    def _reference_options(self, resource: str) -> dict[str, list[tuple[str, str]]]:
        mapping = {
            "programs": {"department_id": "departments"},
            "semesters": {"academic_year_id": "academic-years", "program_id": "programs"},
            "classes": {"academic_year_id": "academic-years", "department_id": "departments", "program_id": "programs", "semester_id": "semesters"},
            "subjects": {"department_id": "departments", "program_id": "programs", "semester_id": "semesters"},
        }
        options: dict[str, list[tuple[str, str]]] = {}
        for field, reference_resource in mapping.get(resource, {}).items():
            result = self.api_client.list_academic(reference_resource, pageSize=100, status="active")
            items = result.data.get("items", []) if result.connected and result.data else []
            options[field] = [(str(item.get("_id") or item.get("id")), str(item.get("name") or item.get("label") or f"Semester {item.get('semester_number', '')}")) for item in items]
        return options

    def open_academic_form(self, record: dict | None = None) -> None:
        if self.current_screen != "authenticated" or not self.academic_state:
            return
        resource = self.academic_state.resource
        if resource == "institution" and record is None and self.academic_state.items:
            record = self.academic_state.items[0]

        def close(_: ft.ControlEvent | None = None) -> None:
            self.page.pop_dialog()

        def execute(payload: dict) -> None:
            if resource == "institution":
                result = self.api_client.update_academic_institution(payload)
            elif record:
                result = self.api_client.update_academic(resource, str(record.get("_id") or record.get("id")), payload)
            else:
                result = self.api_client.create_academic(resource, payload)
            self.page.pop_dialog()
            if result.connected:
                self.load_academic_resource(resource, page=self.academic_state.page)
                status_result = self.api_client.academic_setup_status()
                self.setup_status_data = status_result.data if status_result.connected else self.setup_status_data
            else:
                self.academic_state.error = result.error or "The academic record could not be saved."
                self.render_authenticated_shell()

        def submit(payload: dict) -> None:
            if record and record.get("status") == "active" and payload.get("status") == "inactive":
                self.page.pop_dialog()
                self.page.show_dialog(build_confirmation_dialog("Deactivate academic record?", "Active dependent records may prevent this change. No records will be deleted.", lambda _: (self.page.pop_dialog(), execute(payload)), lambda _: self.page.pop_dialog()))
            else:
                execute(payload)

        form = build_academic_form(resource, self.tokens, submit, close, record=record, references=self._reference_options(resource))
        self.page.show_dialog(ft.AlertDialog(content=form, modal=True))

    def render_public(self) -> None:
        tokens = self.tokens
        if self.current_screen == "splash":
            content = build_splash(self.show_login, tokens)
        else:
            content = build_login(
                self.show_preview,
                tokens,
                api_status_badge(self.api_connected, tokens),
                development_preview_enabled=self.development_preview_enabled,
                on_login=self.handle_login,
                auth_loading=self.auth_state.loading,
                auth_error=self.auth_state.error,
            )
        self.host.content = build_public_shell(
            content,
            tokens,
            api_connected=self.api_connected,
            on_theme_toggle=self.toggle_theme,
            on_api_check=self.check_api,
        )
        self.page.update()

    def render_preview(self) -> None:
        if self.current_role is None:
            raise RuntimeError("Preview role is not selected.")
        self.render_authenticated_shell()

    def render_authenticated_shell(self) -> None:
        if self.current_role is None:
            raise RuntimeError("Authenticated role is not selected.")
        is_preview = self.current_screen == "preview"
        if not is_preview and not self.auth_state.is_authenticated:
            raise RuntimeError("Authenticated shell requires a real session.")
        tokens = self.tokens
        desktop = (self.page.width or 0) >= 900
        sidebar = build_sidebar(
            self.current_role,
            tokens,
            collapsed=self.sidebar_collapsed,
            visible=desktop,
            active_label=self.active_navigation,
            on_select=self.select_navigation if self.current_role in {"Admin","Faculty","Student"} else None,
        )
        self.page.drawer = build_navigation_drawer(self.current_role, tokens, active_label=self.active_navigation, on_select=self.select_navigation if self.current_role in {"Admin","Faculty","Student"} else None)
        developer_strip = ft.Container(
            build_role_switcher(self.current_role, self.show_preview, self.exit_preview, tokens),
            padding=ft.Padding.symmetric(horizontal=12, vertical=6),
            bgcolor=tokens["surface_secondary"],
            border=ft.Border.only(bottom=ft.BorderSide(1, tokens["border"])),
        ) if is_preview else None
        shell_controls: list[ft.Control] = [
            build_authenticated_top_bar(
                self.current_role,
                tokens,
                api_connected=self.api_connected,
                on_sidebar_toggle=self.handle_sidebar_toggle,
                on_theme_toggle=self.toggle_theme,
                on_api_check=self.check_api,
                on_logout=None if is_preview else self.logout,
                view_label=self.active_navigation,
            )
        ]
        if developer_strip:
            shell_controls.append(developer_strip)
        if self.current_role=="Admin" and self.active_navigation=="Timetable" and self.timetable_state is not None:
            content=build_timetable_page(self.timetable_state,tokens,self.set_timetable_view,self.filter_timetable,lambda _:self.open_timetable_form(),self.timetable_action,self.load_timetable)
        elif self.current_role=="Admin" and self.active_navigation=="Attendance":
            content=build_admin_attendance(tokens,self.attendance_sessions,self.current_attendance,self.open_admin_attendance,self.admin_attendance_action,self.attendance_notice,self.admin_attendance_filter,self.filter_admin_attendance)
        elif self.current_role=="Admin" and self.active_navigation=="Face Enrollment" and self.face_enrollment_state is not None:
            content=build_face_enrollment_page(self.face_enrollment_state,tokens,lambda value:self.load_face_enrollments(search=value),self.filter_face_enrollments,self.open_face_enrollment)
        elif self.current_role=="Faculty" and self.active_navigation in {"Take Attendance","Attendance History"}:
            camera_panel=build_camera_panel(self.camera_panel_state,tokens,self.start_camera,self.stop_camera,"Live Attendance Camera") if self.current_attendance and self.attendance_mode=="face" else None
            content=build_take_attendance(tokens,self.schedule_data,self.attendance_sessions,self.current_attendance,self.start_attendance,self.open_faculty_attendance,self.mark_attendance,self.save_attendance,self.review_attendance,self.attendance_notice,self.attendance_search,self.attendance_status_filter,self.filter_attendance_roster,self.attendance_mode,self.face_attendance_status_data,self.face_attendance_result,self.set_attendance_mode,self.capture_attendance_face,self.face_recognition_mode,self.face_selected_student_id,self.set_face_recognition_mode,self.set_face_selected_student,camera_panel,self.face_reference_image)
        elif self.current_role=="Student" and self.active_navigation=="Attendance":
            content=build_reports("Student",tokens,self.reports_data,self.reports_error,lambda _:self.load_reports(),loading=self.reports_loading,on_student=self.open_report_student)
        elif self.active_navigation=="Reports" and self.current_role in {"Admin","Faculty"}:
            content=build_reports(self.current_role,tokens,self.reports_data,self.reports_error,lambda _:self.load_reports(),loading=self.reports_loading,options=self.reports_options,filters=self.reports_filters,low=self.reports_low,on_filter=self.filter_reports,on_reset=self.reset_report_filters,on_range=self.set_report_range,on_page=self.set_report_page,on_search=self.search_reports,on_student=self.open_report_student,on_session=self.open_report_session,on_class=self.open_report_class,on_export=self.export_report_csv)
        elif self.current_role == "Admin" and self.active_navigation == "Faculty" and self.faculty_state is not None:
            content=build_faculty_page(self.faculty_state,tokens,self.load_faculty,self.filter_faculty,self.filter_faculty_department,lambda _:self.load_faculty(),lambda _:self.open_faculty_form(),self.open_faculty_import,self.faculty_action)
        elif self.current_role == "Admin" and self.active_navigation == "Students" and self.student_state is not None:
            content = build_students_page(self.student_state, tokens, self.load_students, self.filter_students, self.filter_students_academic, lambda _: self.load_students(), self.open_student_create, self.open_student_import, self.student_action)
        elif self.current_role == "Admin" and self.academic_state is not None and self.active_navigation != "Dashboard":
            content = build_academic_management_page(
                self.academic_state, tokens,
                on_create=lambda _: self.open_academic_form(),
                on_edit=self.open_academic_form,
                on_search=lambda value: self.load_academic_resource(self.academic_state.resource, search=value),
                on_filter=self.filter_academic_status,
                on_resource_filter=self.filter_academic_reference,
                on_page=lambda value: self.load_academic_resource(self.academic_state.resource, page=value),
            )
        else:
            content = build_dashboard(self.current_role, tokens, self.development_academic_api_enabled, self.setup_status_data, self.select_setup_resource, show_development_structure=is_preview, show_setup_wizard=self.setup_wizard_visible, on_skip_setup=self.skip_setup_wizard, student_profile=None if is_preview else self.student_profile_data, faculty_profile=None if is_preview else self.faculty_profile_data, schedule_data=None if is_preview else self.schedule_data, attendance_data=None if is_preview else self.attendance_data)
        shell_controls.append(ft.Row([sidebar, content], spacing=0, expand=True))
        self.host.content = ft.Column(
            shell_controls,
            spacing=0,
            expand=True,
            key="authenticated-shell",
        )
        self.page.update()

    def render_current(self) -> None:
        if self.current_screen in {"preview", "authenticated"}:
            self.render_authenticated_shell()
        else:
            self.render_public()


# Backward-compatible name used by existing foundation tests.
DevelopmentPreviewController = PremiumUiController


def main(page: ft.Page) -> PremiumUiController:
    settings=get_settings();configure_runtime_logging(settings)
    log_ui_event("Flet startup",api_base_url=settings.api_base_url,ui_event_logging=settings.enable_ui_event_logging)
    configure_page(page)
    page.title = "AI Based Real-Time Face Recognition Attendance System"
    host = ft.Container(expand=True)
    page.add(host)

    controller = PremiumUiController(
        page,
        host,
        development_preview_enabled=settings.development_preview_enabled,
        development_academic_api_enabled=settings.enable_dev_academic_api,
    )
    page.on_disconnect=lambda _:controller.stop_camera()
    page.on_close=lambda _:controller.stop_camera()
    controller.show_splash()
    controller.check_api()
    return controller


if __name__ == "__main__":
    ft.run(main)

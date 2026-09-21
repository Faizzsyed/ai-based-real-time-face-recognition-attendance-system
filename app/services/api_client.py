from dataclasses import dataclass
from typing import Any, Callable
from urllib.parse import urlencode,urlparse
import httpx,logging,time,threading
from uuid import uuid4
from app.core.config import get_settings
from app.state.auth_state import AuthState


@dataclass
class ApiResult:
    connected: bool
    data: dict | None = None
    status_code: int | None = None
    error: str | None = None


class ApiClient:
    def __init__(self, base_url: str | None = None, timeout: float = 3.0, auth_state: AuthState | None = None, on_auth_lost: Callable[[], None] | None = None):
        self.base_url = (base_url or get_settings().api_base_url).rstrip("/")
        self.timeout = timeout
        self.auth_state = auth_state or AuthState()
        self.on_auth_lost = on_auth_lost
        self.logger=logging.getLogger("CLIENT")
        self._refresh_lock=threading.Lock()
        self._auth_loss_lock=threading.Lock();self._auth_loss_notified=False
    def set_base_url(self, base_url: str) -> bool:
        """Apply a user-selected development server only after conservative validation."""
        value=base_url.strip().rstrip("/");parsed=urlparse(value)
        if parsed.scheme not in {"http","https"} or not parsed.netloc:return False
        if parsed.scheme=="http" and not get_settings().allow_insecure_dev_api:return False
        self.base_url=value;return True
    def _log(self,message,*args):
        if get_settings().enable_api_request_logging:self.logger.info(message,*args)
    def _trace_headers(self,authenticated=False):
        request_id=uuid4().hex;headers={"X-Request-ID":request_id}
        if authenticated and self.auth_state.access_token:headers["Authorization"]=f"Bearer {self.auth_state.access_token}"
        return request_id,headers

    def _get(self, path: str) -> ApiResult:
        request_id,headers=self._trace_headers();started=time.perf_counter();self._log("[req=%s] GET %s attempt=1",request_id,path)
        try:
            response = httpx.get(f"{self.base_url}{path}",headers=headers, timeout=self.timeout)
            data = response.json()
            self._log("[req=%s] response=%s duration_ms=%.2f",request_id,response.status_code,(time.perf_counter()-started)*1000)
            return ApiResult(response.is_success and isinstance(data, dict), data if isinstance(data, dict) else None, response.status_code)
        except (httpx.HTTPError, ValueError):
            return ApiResult(False)

    def health_check(self) -> ApiResult:
        return self._get("/api/v1/health")

    def system_info(self) -> ApiResult:
        return self._get("/api/v1/system/info")

    @staticmethod
    def _error_message(data: Any) -> str:
        if isinstance(data, dict):
            error = data.get("error")
            if isinstance(error, dict) and isinstance(error.get("message"), str):
                return error["message"]
            if isinstance(data.get("message"), str):
                return data["message"]
        return "The request could not be completed."

    def _request(self, method: str, path: str, *, payload: dict | None = None, authenticated: bool = False, allow_refresh: bool = True) -> ApiResult:
        response=self._send(method,path,json=payload,authenticated=authenticated,allow_refresh=allow_refresh)
        if response is None:return ApiResult(False,error="The authentication service is unavailable.")
        try:data=response.json()
        except ValueError:data=None
        return ApiResult(response.is_success and isinstance(data,dict),data if isinstance(data,dict) else None,response.status_code,None if response.is_success else self._error_message(data))

    @staticmethod
    def _auth_error_code(response):
        try:
            data=response.json();error=data.get("error") if isinstance(data,dict) else None
            if isinstance(error,dict):
                code=error.get("code")
                if isinstance(code,str):return code
                message=str(error.get("message","")).casefold()
                if "expired" in message:return "AUTH_TOKEN_EXPIRED"
        except ValueError:pass
        return None

    def _send(self,method,path,*,authenticated=False,allow_refresh=True,timeout=None,**kwargs):
        request_id,headers=self._trace_headers(authenticated);used_token=self.auth_state.access_token if authenticated else None;headers.update(kwargs.pop("headers",{}) or {});started=time.perf_counter();self._log("[req=%s] %s %s attempt=1",request_id,method,path)
        try:response=httpx.request(method,f"{self.base_url}{path}",headers=headers,timeout=timeout or self.timeout,**kwargs)
        except httpx.HTTPError:return None
        self._log("[req=%s] response=%s duration_ms=%.2f",request_id,response.status_code,(time.perf_counter()-started)*1000)
        code=self._auth_error_code(response) if response.status_code==401 else None
        if response.status_code==401 and authenticated and allow_refresh and code=="AUTH_TOKEN_EXPIRED":
            self._log("[CLIENT] access token expired")
            if self._refresh_for_token(used_token):
                self._log("[CLIENT] retrying original request")
                retried=self._send(method,path,authenticated=True,allow_refresh=False,timeout=timeout,**kwargs)
                if retried is not None and retried.is_success:self._log("[CLIENT] retry succeeded")
                return retried
            self._lose_authentication()
        elif response.status_code==401 and authenticated and code in {"AUTH_TOKEN_INVALID","AUTH_REQUIRED"}:
            self._log("[AUTH] credentials invalid; authentication cleared");self._lose_authentication()
        return response

    def _refresh_for_token(self,used_token):
        if not self._refresh_lock.acquire(blocking=False):
            self._log("[AUTH] refresh already in progress; waiting");self._refresh_lock.acquire()
            try:return bool(self.auth_state.access_token and self.auth_state.access_token!=used_token)
            finally:self._refresh_lock.release()
        try:
            if self.auth_state.access_token and self.auth_state.access_token!=used_token:return True
            self._log("[AUTH] refresh requested")
            if self._refresh_once():self._log("[AUTH] refresh succeeded");return True
            self._log("[AUTH] refresh failed; authentication cleared");return False
        finally:self._refresh_lock.release()

    def _refresh_once(self) -> bool:
        refresh_token = self.auth_state.refresh_token
        if not refresh_token:
            return False
        result = self._request("POST", "/api/v1/auth/refresh", payload={"refreshToken": refresh_token}, authenticated=False, allow_refresh=False)
        if result.connected and result.data and isinstance(result.data.get("data"), dict):
            self.auth_state.update_tokens(result.data["data"])
            return True
        return False

    def _lose_authentication(self) -> None:
        with self._auth_loss_lock:
            if self._auth_loss_notified:return
            self._auth_loss_notified=True;self.auth_state.clear()
            if self.on_auth_lost:self.on_auth_lost()

    def login(self, identifier: str, password: str) -> ApiResult:
        result = self._request("POST", "/api/v1/auth/login", payload={"identifier": identifier, "password": password})
        if result.connected and result.data and isinstance(result.data.get("data"), dict):
            self.auth_state.authenticate(result.data["data"])
            self._auth_loss_notified=False
        else:
            self.auth_state.fail(result.error or "Login failed.")
        return result

    def refresh(self) -> bool:
        if self._refresh_once():
            return True
        self._lose_authentication()
        return False

    def logout(self) -> ApiResult:
        refresh_token = self.auth_state.refresh_token
        result = self._request("POST", "/api/v1/auth/logout", payload={"refreshToken": refresh_token}, authenticated=True, allow_refresh=False) if refresh_token else ApiResult(True, {"success": True})
        self.auth_state.clear()
        return result

    def logout_all(self) -> ApiResult:
        result = self._request("POST", "/api/v1/auth/logout-all", authenticated=True)
        self.auth_state.clear()
        return result

    def get_me(self) -> ApiResult:
        return self._request("GET", "/api/v1/auth/me", authenticated=True)

    def authenticated_request(self, method: str, path: str, payload: dict | None = None) -> ApiResult:
        return self._request(method, path, payload=payload, authenticated=True)

    def academic_institution(self) -> ApiResult:
        return self.authenticated_request("GET", "/api/v1/admin/academic/institution")

    def update_academic_institution(self, payload: dict) -> ApiResult:
        return self.authenticated_request("PATCH", "/api/v1/admin/academic/institution", payload)

    def academic_setup_status(self) -> ApiResult:
        return self.authenticated_request("GET", "/api/v1/admin/academic/setup-status")

    def list_academic(self, resource: str, **filters: Any) -> ApiResult:
        query = urlencode({key: value for key, value in filters.items() if value is not None and value != ""})
        return self.authenticated_request("GET", f"/api/v1/admin/academic/{resource}{'?' + query if query else ''}")

    def create_academic(self, resource: str, payload: dict) -> ApiResult:
        return self.authenticated_request("POST", f"/api/v1/admin/academic/{resource}", payload)

    def update_academic(self, resource: str, document_id: str, payload: dict) -> ApiResult:
        return self.authenticated_request("PATCH", f"/api/v1/admin/academic/{resource}/{document_id}", payload)

    def list_students(self, **filters: Any) -> ApiResult:
        query = urlencode({key: value for key, value in filters.items() if value not in (None, "")})
        return self.authenticated_request("GET", f"/api/v1/admin/students{'?' + query if query else ''}")

    def create_student(self, payload: dict) -> ApiResult:
        return self.authenticated_request("POST", "/api/v1/admin/students", payload)

    def get_student(self, student_id: str) -> ApiResult:
        return self.authenticated_request("GET", f"/api/v1/admin/students/{student_id}")

    def update_student(self, student_id: str, payload: dict) -> ApiResult:
        return self.authenticated_request("PATCH", f"/api/v1/admin/students/{student_id}", payload)

    def update_student_status(self, student_id: str, status: str) -> ApiResult:
        return self.authenticated_request("PATCH", f"/api/v1/admin/students/{student_id}/status", {"status": status})

    def change_student_enrollment(self, student_id: str, payload: dict) -> ApiResult:
        return self.authenticated_request("POST", f"/api/v1/admin/students/{student_id}/enrollments", payload)

    def student_profile(self) -> ApiResult:
        return self.authenticated_request("GET", "/api/v1/student/profile")

    def _upload_csv(self, path: str, filename: str, content: bytes, *, confirm: bool = False) -> ApiResult:
        return self._multipart(path,params={"confirm":"true"} if confirm else None,files={"file":(filename,content,"text/csv")},unavailable="The import service is unavailable.",timeout=max(self.timeout,30))

    def preview_student_import(self, filename: str, content: bytes) -> ApiResult:
        return self._upload_csv("/api/v1/admin/students/import/preview", filename, content)

    def confirm_student_import(self, filename: str, content: bytes) -> ApiResult:
        return self._upload_csv("/api/v1/admin/students/import/confirm", filename, content, confirm=True)

    def list_faculty(self, **filters: Any) -> ApiResult:
        query=urlencode({k:v for k,v in filters.items() if v not in (None,"")}); return self.authenticated_request("GET",f"/api/v1/admin/faculty{'?'+query if query else ''}")
    def create_faculty(self,payload:dict)->ApiResult: return self.authenticated_request("POST","/api/v1/admin/faculty",payload)
    def get_faculty(self,faculty_id:str)->ApiResult: return self.authenticated_request("GET",f"/api/v1/admin/faculty/{faculty_id}")
    def update_faculty(self,faculty_id:str,payload:dict)->ApiResult: return self.authenticated_request("PATCH",f"/api/v1/admin/faculty/{faculty_id}",payload)
    def update_faculty_status(self,faculty_id:str,status:str)->ApiResult: return self.authenticated_request("PATCH",f"/api/v1/admin/faculty/{faculty_id}/status",{"status":status})
    def create_faculty_assignment(self,faculty_id:str,payload:dict)->ApiResult: return self.authenticated_request("POST",f"/api/v1/admin/faculty/{faculty_id}/assignments",payload)
    def faculty_profile(self)->ApiResult: return self.authenticated_request("GET","/api/v1/faculty/profile")
    def faculty_assignments(self)->ApiResult: return self.authenticated_request("GET","/api/v1/faculty/assignments")
    def preview_faculty_import(self,filename:str,content:bytes)->ApiResult: return self._upload_csv("/api/v1/admin/faculty/import/preview",filename,content)
    def confirm_faculty_import(self,filename:str,content:bytes)->ApiResult: return self._upload_csv("/api/v1/admin/faculty/import/confirm",filename,content,confirm=True)

    def list_timetable(self,**filters:Any)->ApiResult:
        query=urlencode({k:v for k,v in filters.items() if v not in (None,"")});return self.authenticated_request("GET",f"/api/v1/admin/timetable{'?'+query if query else ''}")
    def create_timetable(self,payload:dict)->ApiResult:return self.authenticated_request("POST","/api/v1/admin/timetable",payload)
    def update_timetable(self,entry_id:str,payload:dict)->ApiResult:return self.authenticated_request("PATCH",f"/api/v1/admin/timetable/{entry_id}",payload)
    def update_timetable_status(self,entry_id:str,status:str)->ApiResult:return self.authenticated_request("PATCH",f"/api/v1/admin/timetable/{entry_id}/status",{"status":status})
    def faculty_timetable(self)->ApiResult:return self.authenticated_request("GET","/api/v1/faculty/timetable")
    def student_timetable(self)->ApiResult:return self.authenticated_request("GET","/api/v1/student/timetable")
    def start_attendance(self,payload:dict)->ApiResult:return self.authenticated_request("POST","/api/v1/faculty/attendance/sessions",payload)
    def faculty_attendance_sessions(self,status:str|None=None)->ApiResult:
        query=f"?status={status}" if status else "";return self.authenticated_request("GET",f"/api/v1/faculty/attendance/sessions{query}")
    def attendance_session(self,session_id:str,admin:bool=False)->ApiResult:return self.authenticated_request("GET",f"/api/v1/{'admin' if admin else 'faculty'}/attendance/sessions/{session_id}")
    def save_attendance_draft(self,session_id:str,payload:dict)->ApiResult:return self.authenticated_request("PUT",f"/api/v1/faculty/attendance/sessions/{session_id}/draft",payload)
    def submit_attendance(self,session_id:str)->ApiResult:return self.authenticated_request("POST",f"/api/v1/faculty/attendance/sessions/{session_id}/submit")
    def face_attendance_status(self,session_id:str)->ApiResult:return self.authenticated_request("GET",f"/api/v1/faculty/attendance/sessions/{session_id}/face/status")
    def face_attendance_recognized(self,session_id:str)->ApiResult:return self.authenticated_request("GET",f"/api/v1/faculty/attendance/sessions/{session_id}/face/recognized")
    def face_reference(self,student_id:str,session_id:str|None=None)->ApiResult:
        path=f"/api/v1/faculty/attendance/sessions/{session_id}/face/students/{student_id}/reference" if session_id else f"/api/v1/admin/students/{student_id}/face/reference";response=self._send("GET",path,authenticated=True)
        return ApiResult(bool(response and response.is_success),{"content":response.content} if response and response.is_success else None,response.status_code if response else None,None if response and response.is_success else "Enrollment reference is unavailable.")
    def analyze_attendance_face(self,session_id:str,name:str,data:bytes,mime:str)->ApiResult:
        return self._multipart(f"/api/v1/faculty/attendance/sessions/{session_id}/face/analyze",files={"image":(name,data,mime)},unavailable="Live face analysis is unavailable; continue manually.")
    def identify_attendance_face(self,session_id:str,name:str,data:bytes,mime:str,student_id:str|None=None,liveness_frames:list[bytes]|None=None)->ApiResult:
        files=[("image",(name,data,mime))]+[("livenessImages",(f"liveness_{index}.jpg",frame,"image/jpeg")) for index,frame in enumerate(liveness_frames or [],1)];return self._multipart(f"/api/v1/faculty/attendance/sessions/{session_id}/face/identify",files=files,data={"studentId":student_id} if student_id else {},unavailable="Face Attendance is unavailable; continue manually.")
    def admin_attendance_sessions(self,**filters:Any)->ApiResult:
        query=urlencode({k:v for k,v in filters.items() if v not in (None,"")});return self.authenticated_request("GET",f"/api/v1/admin/attendance/sessions{'?'+query if query else ''}")
    def admin_attendance_action(self,session_id:str,action:str,reason:str)->ApiResult:return self.authenticated_request("POST",f"/api/v1/admin/attendance/sessions/{session_id}/{action}",{"reason":reason})
    def student_attendance_summary(self)->ApiResult:return self.authenticated_request("GET","/api/v1/student/attendance/summary")
    def student_attendance_history(self)->ApiResult:return self.authenticated_request("GET","/api/v1/student/attendance/history")
    def create_attendance_request(self,payload:dict)->ApiResult:return self.authenticated_request("POST","/api/v1/requests/attendance",payload)
    def my_attendance_requests(self,**filters:Any)->ApiResult:
        query=urlencode({k:v for k,v in filters.items() if v not in (None,"")});return self.authenticated_request("GET",f"/api/v1/requests/mine{'?'+query if query else ''}")
    def attendance_request_queue(self,**filters:Any)->ApiResult:
        query=urlencode({k:v for k,v in filters.items() if v not in (None,"")});return self.authenticated_request("GET",f"/api/v1/requests/attendance{'?'+query if query else ''}")
    def attendance_request(self,request_id:str)->ApiResult:return self.authenticated_request("GET",f"/api/v1/requests/{request_id}")
    def cancel_attendance_request(self,request_id:str)->ApiResult:return self.authenticated_request("POST",f"/api/v1/requests/{request_id}/cancel")
    def resolve_attendance_request(self,request_id:str,decision:str,note:str|None=None)->ApiResult:return self.authenticated_request("POST",f"/api/v1/requests/{request_id}/{decision}",{"resolutionNote":note} if note else {})
    def notifications(self,**filters:Any)->ApiResult:
        query=urlencode({k:v for k,v in filters.items() if v not in (None,"")});return self.authenticated_request("GET",f"/api/v1/notifications{'?'+query if query else ''}")
    def notification_unread_count(self)->ApiResult:return self.authenticated_request("GET","/api/v1/notifications/unread-count")
    def mark_notification_read(self,notification_id:str)->ApiResult:return self.authenticated_request("POST",f"/api/v1/notifications/{notification_id}/read")
    def mark_all_notifications_read(self)->ApiResult:return self.authenticated_request("POST","/api/v1/notifications/read-all")
    def audit_events(self,**filters:Any)->ApiResult:
        query=urlencode({k:v for k,v in filters.items() if v not in (None,"")});return self.authenticated_request("GET",f"/api/v1/audit{'?'+query if query else ''}")
    def reports_overview(self,role:str,**filters:Any)->ApiResult:
        query=urlencode({k:v for k,v in filters.items() if v not in (None,"")});return self.authenticated_request("GET",f"/api/v1/{role.casefold()}/reports/{'attendance' if role.casefold()=='student' else 'overview'}{'?'+query if query else ''}")
    def reports_subjects(self,role:str,**filters:Any)->ApiResult:
        query=urlencode({k:v for k,v in filters.items() if v not in (None,"")});return self.authenticated_request("GET",f"/api/v1/{role.casefold()}/reports/subjects{'?'+query if query else ''}")
    def reports_trend(self,**filters:Any)->ApiResult:
        query=urlencode({k:v for k,v in filters.items() if v not in (None,"")});return self.authenticated_request("GET",f"/api/v1/admin/reports/trend{'?'+query if query else ''}")
    def reports_departments(self)->ApiResult:return self.authenticated_request("GET","/api/v1/admin/reports/departments")
    def reports_options(self,role:str)->ApiResult:return self.authenticated_request("GET",f"/api/v1/{role.casefold()}/reports/options")
    def reports_low_attendance(self,**filters:Any)->ApiResult:
        query=urlencode({k:v for k,v in filters.items() if v not in (None,"")});return self.authenticated_request("GET",f"/api/v1/admin/reports/students/low-attendance{'?'+query if query else ''}")
    def report_class(self,role:str,class_id:str,page:int=1,page_size:int=25)->ApiResult:return self.authenticated_request("GET",f"/api/v1/{role.casefold()}/reports/classes/{class_id}?page={page}&pageSize={page_size}")
    def report_student(self,role:str,student_id:str)->ApiResult:return self.authenticated_request("GET",f"/api/v1/{role.casefold()}/reports/students/{student_id}")
    def report_session(self,role:str,session_id:str)->ApiResult:return self.authenticated_request("GET",f"/api/v1/{role.casefold()}/reports/sessions/{session_id}")
    def download_report_csv(self,role:str,kind:str,document_id:str|None=None)->ApiResult:
        suffix=f"/{document_id}.csv" if document_id else ".csv";response=self._send("GET",f"/api/v1/{role.casefold()}/reports/exports/{kind}{suffix}",authenticated=True)
        if response is None:return ApiResult(False,error="CSV export is unavailable.")
        disposition=response.headers.get("content-disposition","");filename=disposition.split("filename=",1)[-1].strip(' "') if "filename=" in disposition else "AttendAI_Report.csv"
        return ApiResult(response.is_success,{"content":response.content,"filename":filename} if response.is_success else None,response.status_code,None if response.is_success else "CSV export failed.")
    def face_status(self,student_id:str)->ApiResult:return self.authenticated_request("GET",f"/api/v1/admin/students/{student_id}/face/status")
    def _face_upload(self,path:str,files:list[tuple[str,bytes,str]],fields:dict[str,str]|None=None)->ApiResult:
        payload=[("images",(name,data,mime)) for name,data,mime in files];return self._multipart(path,files=payload,data=fields or {},unavailable="The face enrollment service is unavailable.")
    def analyze_face(self,student_id:str,name:str,data:bytes,mime:str)->ApiResult:
        return self._multipart(f"/api/v1/admin/students/{student_id}/face/analyze",files={"image":(name,data,mime)},unavailable="Face quality analysis is unavailable.")
    def enroll_face(self,student_id:str,files:list[tuple[str,bytes,str]],method:str="camera")->ApiResult:return self._face_upload(f"/api/v1/admin/students/{student_id}/face/enroll",files,{"consent_confirmed":"true","enrollment_method":method})
    def enroll_face_from_profile(self,student_id:str)->ApiResult:
        return self._multipart(f"/api/v1/admin/students/{student_id}/face/enroll-from-profile",data={"consent_confirmed":"true"},unavailable="Profile-photo enrollment is unavailable.")
    def remove_face(self,student_id:str)->ApiResult:return self.authenticated_request("DELETE",f"/api/v1/admin/students/{student_id}/face")

    def _multipart(self,path,*,files=None,data=None,params=None,unavailable="The request is unavailable.",timeout=None):
        response=self._send("POST",path,authenticated=True,files=files,data=data,params=params,timeout=timeout or max(self.timeout,60))
        if response is None:return ApiResult(False,error=unavailable)
        try:body=response.json()
        except ValueError:return ApiResult(False,status_code=response.status_code,error=unavailable)
        return ApiResult(response.is_success and isinstance(body,dict),body if isinstance(body,dict) else None,response.status_code,None if response.is_success else self._error_message(body))

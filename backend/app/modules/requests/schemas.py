from enum import Enum
from pydantic import BaseModel,ConfigDict,Field
from app.modules.attendance.schemas import AttendanceStatus

class RequestStatus(str,Enum): pending="pending";approved="approved";rejected="rejected";cancelled="cancelled"
class AttendanceRequestCreate(BaseModel):
    attendance_session_id:str=Field(alias="attendanceSessionId")
    requested_status:AttendanceStatus=Field(alias="requestedStatus")
    reason:str=Field(min_length=3,max_length=1000)
    model_config=ConfigDict(extra="forbid",str_strip_whitespace=True,populate_by_name=True,use_enum_values=True)
class Resolution(BaseModel):
    resolution_note:str|None=Field(default=None,alias="resolutionNote",max_length=1000)
    model_config=ConfigDict(extra="forbid",str_strip_whitespace=True,populate_by_name=True)

"""Validated contracts for manual attendance sessions and roster records."""
from datetime import date
from enum import Enum
from pydantic import BaseModel,ConfigDict,Field

class AttendanceStatus(str,Enum):
    present="present";absent="absent";late="late";excused="excused"

class SessionStatus(str,Enum):
    draft="draft";submitted="submitted";locked="locked";reopened="reopened"

class SessionCreate(BaseModel):
    timetable_entry_id:str
    lecture_date:date
    topic:str|None=Field(default=None,max_length=240)
    notes:str|None=Field(default=None,max_length=2000)
    model_config=ConfigDict(extra="forbid",str_strip_whitespace=True)

class RecordMark(BaseModel):
    student_id:str
    status:AttendanceStatus
    remark:str|None=Field(default=None,max_length=500)
    model_config=ConfigDict(extra="forbid",str_strip_whitespace=True,use_enum_values=True)

class DraftSave(BaseModel):
    records:list[RecordMark]=Field(min_length=1,max_length=500)
    topic:str|None=Field(default=None,max_length=240)
    notes:str|None=Field(default=None,max_length=2000)
    model_config=ConfigDict(extra="forbid",str_strip_whitespace=True)

class AdministrativeEdit(BaseModel):
    records:list[RecordMark]=Field(min_length=1,max_length=500)
    reason:str=Field(min_length=3,max_length=500)
    model_config=ConfigDict(extra="forbid",str_strip_whitespace=True)

class AdministrativeAction(BaseModel):
    reason:str=Field(min_length=3,max_length=500)
    model_config=ConfigDict(extra="forbid",str_strip_whitespace=True)

"""Recurring timetable contracts; lecture instances are computed, never persisted."""
from datetime import date, time
from enum import Enum
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

class Weekday(str, Enum):
    monday="monday"; tuesday="tuesday"; wednesday="wednesday"; thursday="thursday"; friday="friday"; saturday="saturday"; sunday="sunday"
class LectureType(str, Enum):
    theory="theory"; practical="practical"; project="project"; tutorial="tutorial"
class TimetableStatus(str, Enum): active="active"; inactive="inactive"

class TimetableEntryCreate(BaseModel):
    faculty_assignment_id:str
    day_of_week:Weekday
    start_time:time
    end_time:time
    room:str|None=Field(None,max_length=80)
    lecture_type:LectureType=LectureType.theory
    effective_from:date
    effective_until:date|None=None
    status:TimetableStatus=TimetableStatus.active
    model_config=ConfigDict(extra="forbid",str_strip_whitespace=True,use_enum_values=True)
    @field_validator("room",mode="before")
    @classmethod
    def room_normalized(cls,value): return value.strip().upper() if isinstance(value,str) and value.strip() else None
    @model_validator(mode="after")
    def valid_range(self):
        if self.start_time>=self.end_time: raise ValueError("start_time must precede end_time")
        if self.effective_until and self.effective_until<self.effective_from: raise ValueError("effective_until cannot precede effective_from")
        return self

class TimetableEntryUpdate(BaseModel):
    faculty_assignment_id:str|None=None
    day_of_week:Weekday|None=None
    start_time:time|None=None
    end_time:time|None=None
    room:str|None=Field(None,max_length=80)
    lecture_type:LectureType|None=None
    effective_from:date|None=None
    effective_until:date|None=None
    status:TimetableStatus|None=None
    model_config=ConfigDict(extra="forbid",str_strip_whitespace=True,use_enum_values=True)
    @field_validator("room",mode="before")
    @classmethod
    def room_normalized(cls,value): return value.strip().upper() if isinstance(value,str) and value.strip() else None

class TimetableStatusUpdate(BaseModel):
    status:TimetableStatus
    model_config=ConfigDict(extra="forbid",use_enum_values=True)

"""Faculty identity and teaching-assignment contracts."""
from datetime import date
from enum import Enum
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

class FacultyStatus(str, Enum):
    active="active"; inactive="inactive"; suspended="suspended"; resigned="resigned"; archived="archived"
class AssignmentType(str, Enum):
    primary="primary"; co_faculty="co_faculty"; practical="practical"; project_guide="project_guide"
class AssignmentStatus(str, Enum):
    active="active"; inactive="inactive"

class AssignmentCreate(BaseModel):
    academic_year_id:str; subject_id:str; class_division_id:str
    assignment_type:AssignmentType=AssignmentType.primary
    status:AssignmentStatus=AssignmentStatus.active
    start_date:date|None=None; end_date:date|None=None
    model_config=ConfigDict(extra="forbid",str_strip_whitespace=True,use_enum_values=True)
    @model_validator(mode="after")
    def dates(self):
        if self.start_date and self.end_date and self.end_date < self.start_date: raise ValueError("end_date cannot precede start_date")
        return self

class AssignmentUpdate(BaseModel):
    academic_year_id:str|None=None; subject_id:str|None=None; class_division_id:str|None=None
    assignment_type:AssignmentType|None=None; status:AssignmentStatus|None=None
    start_date:date|None=None; end_date:date|None=None
    model_config=ConfigDict(extra="forbid",use_enum_values=True)

class FacultyCreate(BaseModel):
    display_name:str=Field(min_length=2,max_length=160); employee_id:str=Field(min_length=1,max_length=50,pattern=r"^[A-Z0-9_/-]+$")
    email:str=Field(max_length=254,pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$"); username:str=Field(min_length=2,max_length=80,pattern=r"^[a-z0-9_.-]+$")
    temporary_password:str=Field(min_length=8,max_length=1024); department_id:str
    first_name:str|None=Field(None,max_length=80); middle_name:str|None=Field(None,max_length=80); last_name:str|None=Field(None,max_length=80)
    phone:str|None=Field(None,max_length=30); designation:str|None=Field(None,max_length=120); joining_date:date|None=None
    profile_photo_url:str|None=Field(None,max_length=500); assignments:list[AssignmentCreate]=Field(default_factory=list,max_length=50)
    model_config=ConfigDict(extra="forbid",str_strip_whitespace=True)
    @field_validator("employee_id",mode="before")
    @classmethod
    def employee(cls,v): return v.strip().upper() if isinstance(v,str) else v
    @field_validator("email","username",mode="before")
    @classmethod
    def normalized(cls,v): return v.strip().casefold() if isinstance(v,str) else v

class FacultyUpdate(BaseModel):
    display_name:str|None=Field(None,min_length=2,max_length=160); email:str|None=Field(None,max_length=254,pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    first_name:str|None=Field(None,max_length=80); middle_name:str|None=Field(None,max_length=80); last_name:str|None=Field(None,max_length=80)
    phone:str|None=Field(None,max_length=30); department_id:str|None=None; designation:str|None=Field(None,max_length=120)
    joining_date:date|None=None; profile_photo_url:str|None=Field(None,max_length=500)
    model_config=ConfigDict(extra="forbid",str_strip_whitespace=True)
    @field_validator("email",mode="before")
    @classmethod
    def email_normalized(cls,v): return v.strip().casefold() if isinstance(v,str) else v

class FacultyStatusUpdate(BaseModel):
    status:FacultyStatus
    model_config=ConfigDict(extra="forbid",use_enum_values=True)

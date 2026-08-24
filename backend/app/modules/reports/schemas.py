"""Validated report query contracts and the centralized attendance policy."""
from datetime import date
from pydantic import BaseModel,ConfigDict,Field,model_validator

FINAL_SESSION_STATES=frozenset({"submitted","locked"})
PRESENT_EQUIVALENT=frozenset({"present","late"})
ELIGIBLE_STATUSES=frozenset({"present","late","absent"})
EXCLUDED_STATUSES=frozenset({"excused",None})

class ReportFilters(BaseModel):
    date_from:date|None=None;date_to:date|None=None;academic_year_id:str|None=None;department_id:str|None=None;program_id:str|None=None;semester_id:str|None=None;class_division_id:str|None=None;subject_id:str|None=None;faculty_id:str|None=None
    model_config=ConfigDict(extra="forbid")
    @model_validator(mode="after")
    def ordered_dates(self):
        if self.date_from and self.date_to and self.date_from>self.date_to:raise ValueError("dateFrom must not be after dateTo")
        return self

class Page(BaseModel):
    page:int=Field(1,ge=1);page_size:int=Field(25,ge=1,le=100)

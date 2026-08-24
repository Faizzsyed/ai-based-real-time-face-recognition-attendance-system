from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RecordStatus(str, Enum):
    active = "active"
    inactive = "inactive"


class SubjectType(str, Enum):
    theory = "theory"
    practical = "practical"
    project = "project"
    elective = "elective"


class AcademicModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, use_enum_values=True)

    @field_validator("code", "division", mode="before", check_fields=False)
    @classmethod
    def uppercase_identifiers(cls, value):
        return value.strip().upper() if isinstance(value, str) else value


class TimestampedResponse(AcademicModel):
    id: str
    created_at: datetime
    updated_at: datetime


class Pagination(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, alias="pageSize", ge=1, le=100)

"""Student profile, enrollment, status, and creation contracts."""

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StudentStatus(str, Enum):
    active = "active"
    inactive = "inactive"
    graduated = "graduated"
    suspended = "suspended"
    archived = "archived"


class EnrollmentStatus(str, Enum):
    active = "active"
    completed = "completed"
    transferred = "transferred"
    withdrawn = "withdrawn"


class StudentBase(BaseModel):
    display_name: str = Field(min_length=2, max_length=160)
    admission_number: str = Field(min_length=1, max_length=50, pattern=r"^[A-Z0-9_/-]+$")
    email: str = Field(max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    first_name: str | None = Field(default=None, max_length=80)
    middle_name: str | None = Field(default=None, max_length=80)
    last_name: str | None = Field(default=None, max_length=80)
    phone: str | None = Field(default=None, max_length=30)
    date_of_birth: date | None = None
    gender: str | None = Field(default=None, max_length=30)
    profile_photo_url: str | None = Field(default=None, max_length=500)
    admission_date: date | None = None
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, use_enum_values=True)

    @field_validator("admission_number", mode="before")
    @classmethod
    def normalize_admission(cls, value):
        return value.strip().upper() if isinstance(value, str) else value

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value):
        return value.strip().casefold() if isinstance(value, str) else value


class EnrollmentCreate(BaseModel):
    academic_year_id: str
    department_id: str
    program_id: str
    semester_id: str
    class_division_id: str
    roll_number: str = Field(min_length=1, max_length=30)
    start_date: date
    end_date: date | None = None
    previous_status: EnrollmentStatus = EnrollmentStatus.transferred
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, use_enum_values=True)

    @field_validator("roll_number", mode="before")
    @classmethod
    def normalize_roll(cls, value):
        return value.strip().upper() if isinstance(value, str) else value


class StudentCreate(StudentBase, EnrollmentCreate):
    username: str = Field(min_length=2, max_length=80, pattern=r"^[a-z0-9_.-]+$")
    temporary_password: str = Field(min_length=8, max_length=1024)

    @field_validator("username", mode="before")
    @classmethod
    def normalize_username(cls, value):
        return value.strip().casefold() if isinstance(value, str) else value


class StudentUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=2, max_length=160)
    first_name: str | None = Field(default=None, max_length=80)
    middle_name: str | None = Field(default=None, max_length=80)
    last_name: str | None = Field(default=None, max_length=80)
    email: str | None = Field(default=None, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    phone: str | None = Field(default=None, max_length=30)
    date_of_birth: date | None = None
    gender: str | None = Field(default=None, max_length=30)
    profile_photo_url: str | None = Field(default=None, max_length=500)
    admission_date: date | None = None
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value):
        return value.strip().casefold() if isinstance(value, str) else value


class StudentStatusUpdate(BaseModel):
    status: StudentStatus
    model_config = ConfigDict(extra="forbid", use_enum_values=True)


class CsvConfirm(BaseModel):
    confirm: bool

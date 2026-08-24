from app.modules.academic_common.schemas import AcademicModel, RecordStatus, TimestampedResponse
from pydantic import Field


class InstitutionCreate(AcademicModel):
    name: str = Field(min_length=2, max_length=160)
    code: str = Field(min_length=2, max_length=20, pattern=r"^[A-Z0-9_-]+$")
    short_name: str | None = Field(default=None, max_length=80)
    email: str | None = Field(default=None, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    phone: str | None = Field(default=None, max_length=30)
    address: str | None = Field(default=None, max_length=300)
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=100)
    country: str = Field(min_length=2, max_length=100)
    timezone: str = Field(min_length=3, max_length=80)
    status: RecordStatus = RecordStatus.active


class InstitutionUpdate(AcademicModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    code: str | None = Field(default=None, min_length=2, max_length=20, pattern=r"^[A-Z0-9_-]+$")
    short_name: str | None = Field(default=None, max_length=80)
    email: str | None = Field(default=None, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    phone: str | None = Field(default=None, max_length=30)
    address: str | None = Field(default=None, max_length=300)
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=100)
    country: str | None = Field(default=None, min_length=2, max_length=100)
    timezone: str | None = Field(default=None, min_length=3, max_length=80)
    status: RecordStatus | None = None


class InstitutionResponse(InstitutionCreate, TimestampedResponse):
    pass

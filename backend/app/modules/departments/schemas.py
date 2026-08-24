from pydantic import Field

from app.modules.academic_common.schemas import AcademicModel, RecordStatus, TimestampedResponse


class DepartmentCreate(AcademicModel):
    institution_id: str
    name: str = Field(min_length=2, max_length=140)
    code: str = Field(min_length=2, max_length=20, pattern=r"^[A-Z0-9_-]+$")
    description: str | None = Field(default=None, max_length=500)
    status: RecordStatus = RecordStatus.active


class DepartmentUpdate(AcademicModel):
    name: str | None = Field(default=None, min_length=2, max_length=140)
    code: str | None = Field(default=None, min_length=2, max_length=20, pattern=r"^[A-Z0-9_-]+$")
    description: str | None = Field(default=None, max_length=500)
    status: RecordStatus | None = None


class DepartmentResponse(DepartmentCreate, TimestampedResponse):
    pass

from pydantic import Field

from app.modules.academic_common.schemas import AcademicModel, RecordStatus, SubjectType, TimestampedResponse


class SubjectCreate(AcademicModel):
    institution_id: str
    department_id: str
    program_id: str
    semester_id: str
    name: str = Field(min_length=2, max_length=160)
    code: str = Field(min_length=2, max_length=30, pattern=r"^[A-Z0-9_-]+$")
    subject_type: SubjectType
    credits: float | None = Field(default=None, ge=0, le=30)
    weekly_hours: float | None = Field(default=None, ge=0, le=100)
    status: RecordStatus = RecordStatus.active


class SubjectUpdate(AcademicModel):
    department_id: str | None = None
    program_id: str | None = None
    semester_id: str | None = None
    name: str | None = Field(default=None, min_length=2, max_length=160)
    code: str | None = Field(default=None, min_length=2, max_length=30, pattern=r"^[A-Z0-9_-]+$")
    subject_type: SubjectType | None = None
    credits: float | None = Field(default=None, ge=0, le=30)
    weekly_hours: float | None = Field(default=None, ge=0, le=100)
    status: RecordStatus | None = None


class SubjectResponse(SubjectCreate, TimestampedResponse):
    pass

from pydantic import Field

from app.modules.academic_common.schemas import AcademicModel, RecordStatus, TimestampedResponse


class ProgramCreate(AcademicModel):
    institution_id: str
    department_id: str
    name: str = Field(min_length=2, max_length=140)
    code: str = Field(min_length=1, max_length=20, pattern=r"^[A-Z0-9_-]+$")
    degree_type: str = Field(min_length=2, max_length=80)
    duration_years: float = Field(gt=0, le=10)
    total_semesters: int = Field(gt=0, le=30)
    status: RecordStatus = RecordStatus.active


class ProgramUpdate(AcademicModel):
    department_id: str | None = None
    name: str | None = Field(default=None, min_length=2, max_length=140)
    code: str | None = Field(default=None, min_length=1, max_length=20, pattern=r"^[A-Z0-9_-]+$")
    degree_type: str | None = Field(default=None, min_length=2, max_length=80)
    duration_years: float | None = Field(default=None, gt=0, le=10)
    total_semesters: int | None = Field(default=None, gt=0, le=30)
    status: RecordStatus | None = None


class ProgramResponse(ProgramCreate, TimestampedResponse):
    pass

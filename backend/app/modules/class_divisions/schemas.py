from pydantic import Field

from app.modules.academic_common.schemas import AcademicModel, RecordStatus, TimestampedResponse


class ClassDivisionCreate(AcademicModel):
    institution_id: str
    academic_year_id: str
    department_id: str
    program_id: str
    semester_id: str
    name: str = Field(min_length=2, max_length=140)
    division: str = Field(min_length=1, max_length=10, pattern=r"^[A-Z0-9_-]+$")
    room: str | None = Field(default=None, max_length=40)
    capacity: int | None = Field(default=None, gt=0, le=1000)
    status: RecordStatus = RecordStatus.active


class ClassDivisionUpdate(AcademicModel):
    academic_year_id: str | None = None
    department_id: str | None = None
    program_id: str | None = None
    semester_id: str | None = None
    name: str | None = Field(default=None, min_length=2, max_length=140)
    division: str | None = Field(default=None, min_length=1, max_length=10, pattern=r"^[A-Z0-9_-]+$")
    room: str | None = Field(default=None, max_length=40)
    capacity: int | None = Field(default=None, gt=0, le=1000)
    status: RecordStatus | None = None


class ClassDivisionResponse(ClassDivisionCreate, TimestampedResponse):
    pass

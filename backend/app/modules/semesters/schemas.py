from datetime import date

from pydantic import Field, model_validator

from app.modules.academic_common.schemas import AcademicModel, RecordStatus, TimestampedResponse


class SemesterCreate(AcademicModel):
    institution_id: str
    academic_year_id: str
    program_id: str
    semester_number: int = Field(gt=0, le=30)
    label: str | None = Field(default=None, max_length=80)
    start_date: date | None = None
    end_date: date | None = None
    status: RecordStatus = RecordStatus.active

    @model_validator(mode="after")
    def valid_dates(self):
        if self.start_date and self.end_date and self.end_date <= self.start_date:
            raise ValueError("end_date must be after start_date")
        return self


class SemesterUpdate(AcademicModel):
    academic_year_id: str | None = None
    program_id: str | None = None
    semester_number: int | None = Field(default=None, gt=0, le=30)
    label: str | None = Field(default=None, max_length=80)
    start_date: date | None = None
    end_date: date | None = None
    status: RecordStatus | None = None


class SemesterResponse(SemesterCreate, TimestampedResponse):
    pass

from datetime import date

from pydantic import Field, model_validator

from app.modules.academic_common.schemas import AcademicModel, RecordStatus, TimestampedResponse


class AcademicYearCreate(AcademicModel):
    institution_id: str
    name: str = Field(min_length=4, max_length=30)
    start_date: date
    end_date: date
    is_current: bool = False
    status: RecordStatus = RecordStatus.active

    @model_validator(mode="after")
    def valid_dates(self):
        if self.end_date <= self.start_date:
            raise ValueError("end_date must be after start_date")
        return self


class AcademicYearUpdate(AcademicModel):
    name: str | None = Field(default=None, min_length=4, max_length=30)
    start_date: date | None = None
    end_date: date | None = None
    is_current: bool | None = None
    status: RecordStatus | None = None


class AcademicYearResponse(AcademicYearCreate, TimestampedResponse):
    pass

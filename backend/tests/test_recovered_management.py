"""Identity integrity and scoped curriculum regressions; no real database."""
from unittest.mock import Mock
from bson import ObjectId
from pydantic import ValidationError
import pytest

from app.core.config import get_settings
from app.modules.attendance.service import AttendanceService
from app.modules.faculty.schemas import FacultyUpdate
from app.modules.students.schemas import StudentUpdate
from app.modules.students.service import StudentService


@pytest.mark.parametrize("model,field", [(StudentUpdate,"email"),(StudentUpdate,"display_name"),
                                        (FacultyUpdate,"email"),(FacultyUpdate,"display_name"),(FacultyUpdate,"department_id")])
def test_explicit_null_cannot_erase_required_account_identity(model, field):
    with pytest.raises(ValidationError):model.model_validate({field: None})
    assert model.model_validate({}).model_dump(exclude_unset=True) == {}


def test_student_curriculum_uses_own_active_enrollment_and_tenant():
    user={"_id":ObjectId(),"institution_id":ObjectId()}
    student={"_id":ObjectId()};enrollment={"program_id":ObjectId(),"semester_id":ObjectId(),"enrollment_status":"active"}
    students=Mock();students.find_by_user.return_value=student
    enrollments=Mock();enrollments.current.return_value=enrollment
    subjects=Mock();subjects.list.return_value={"items":[{"name":"Data Structures"}]}
    service=StudentService(students=students,enrollments=enrollments,academics={"subjects":subjects},passwords=Mock())
    result=service.own_subjects(user)
    subjects.list.assert_called_once_with({"institution_id":str(user["institution_id"]),"program_id":str(enrollment["program_id"]),
                                          "semester_id":str(enrollment["semester_id"]),"status":"active"},1,100)
    assert result["items"][0]["name"]=="Data Structures"
    enrollments.current.return_value={**enrollment,"enrollment_status":"completed"}
    subjects.list.reset_mock()
    assert service.own_subjects(user)=={"items":[]}
    subjects.list.assert_not_called()


def test_student_attendance_exposes_configured_threshold(monkeypatch):
    monkeypatch.setenv("ATTENDANCE_LOW_THRESHOLD_PERCENT","80")
    get_settings.cache_clear()
    students=Mock();students.find_by_user.return_value={"_id":ObjectId()}
    sessions=Mock();sessions.list.return_value=([],0)
    records=Mock();records.for_student.return_value=[]
    result=AttendanceService(students=students,sessions=sessions,records=records).student_report({"_id":ObjectId(),"institution_id":ObjectId()})
    assert result["threshold"]==80 and result["summary"]["total"]==0

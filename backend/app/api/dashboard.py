from typing import Annotated
from fastapi import APIRouter, Depends
from app.db.mongo import mongo
from app.modules.auth.dependencies import require_role
from datetime import date, datetime, time, timezone

router = APIRouter(tags=["dashboard"])

@router.get("/admin/dashboard")
def get_admin_dashboard(user: Annotated[dict, Depends(require_role("admin"))]):
    db = mongo.require_database()
    institution_id = user["institution_id"]

    total_students = db.students.count_documents({"institution_id": institution_id, "status": "active"})
    total_faculty = db.faculty.count_documents({"institution_id": institution_id, "status": "active"})

    # AttendanceService stores lecture dates as UTC-midnight BSON datetimes.
    today = datetime.combine(date.today(), time.min, tzinfo=timezone.utc)

    # We can calculate attendance today by checking sessions created/scheduled for today
    sessions_today = db.attendance_sessions.count_documents({"institution_id": institution_id, "lecture_date": today})
    attendance_today = f"{sessions_today} Sessions"
    if not sessions_today:
        attendance_today = "No lectures today"

    pending_requests = db.attendance_requests.count_documents({"institution_id": institution_id, "status": "pending"})

    return {
        "success": True,
        "totalStudents": total_students,
        "totalFaculty": total_faculty,
        "attendanceToday": attendance_today,
        "pendingRequests": pending_requests
    }

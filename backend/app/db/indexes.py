"""Phase 2 indexes, initialized once after a successful connection."""

from pymongo import ASCENDING
from pymongo.database import Database


def initialize_phase2_indexes(database: Database) -> None:
    database.institutions.create_index([("code", ASCENDING)], unique=True, name="uq_institution_code")
    database.academic_years.create_index([("institution_id", ASCENDING), ("name", ASCENDING)], unique=True, name="uq_academic_year_name")
    database.academic_years.create_index(
        [("institution_id", ASCENDING), ("is_current", ASCENDING)],
        unique=True,
        partialFilterExpression={"is_current": True},
        name="uq_current_academic_year",
    )
    database.departments.create_index([("institution_id", ASCENDING), ("code", ASCENDING)], unique=True, name="uq_department_code")
    database.programs.create_index([("institution_id", ASCENDING), ("department_id", ASCENDING), ("code", ASCENDING)], unique=True, name="uq_program_code")
    database.semesters.create_index([("institution_id", ASCENDING), ("program_id", ASCENDING), ("academic_year_id", ASCENDING), ("semester_number", ASCENDING)], unique=True, name="uq_semester_number")
    database.class_divisions.create_index([("institution_id", ASCENDING), ("academic_year_id", ASCENDING), ("program_id", ASCENDING), ("semester_id", ASCENDING), ("division", ASCENDING)], unique=True, name="uq_class_division")
    database.subjects.create_index([("institution_id", ASCENDING), ("program_id", ASCENDING), ("semester_id", ASCENDING), ("code", ASCENDING)], unique=True, name="uq_subject_code")
    initialize_auth_indexes(database)
    initialize_student_indexes(database)
    initialize_faculty_indexes(database)
    initialize_timetable_indexes(database)
    initialize_attendance_indexes(database)
    initialize_face_enrollment_indexes(database)
    initialize_phase13_indexes(database)


def initialize_auth_indexes(database: Database) -> None:
    database.users.create_index([("institution_id", ASCENDING), ("email", ASCENDING)], unique=True, name="uq_user_email")
    database.users.create_index([("institution_id", ASCENDING), ("username", ASCENDING)], unique=True, name="uq_user_username")
    database.users.create_index([("institution_id", ASCENDING), ("role", ASCENDING)], name="ix_user_role")
    database.users.create_index([("institution_id", ASCENDING), ("status", ASCENDING)], name="ix_user_status")
    database.users.create_index([("email", ASCENDING)], name="ix_user_login_email")
    database.users.create_index([("username", ASCENDING)], name="ix_user_login_username")
    database.auth_sessions.create_index([("user_id", ASCENDING)], name="ix_auth_session_user")
    database.auth_sessions.create_index([("token_family_id", ASCENDING)], name="ix_auth_session_family")
    database.auth_sessions.create_index([("expires_at", ASCENDING)], expireAfterSeconds=0, name="ttl_auth_session_expiry")
    database.auth_sessions.create_index([("revoked_at", ASCENDING)], name="ix_auth_session_revoked")


def initialize_student_indexes(database: Database) -> None:
    database.students.create_index([("institution_id", ASCENDING), ("admission_number", ASCENDING)], unique=True, name="uq_student_admission")
    database.students.create_index([("institution_id", ASCENDING), ("user_id", ASCENDING)], unique=True, name="uq_student_user")
    database.students.create_index([("institution_id", ASCENDING), ("status", ASCENDING)], name="ix_student_status")
    database.students.create_index([("institution_id", ASCENDING), ("display_name", ASCENDING)], name="ix_student_name")
    database.student_academic_enrollments.create_index([("institution_id", ASCENDING), ("student_id", ASCENDING)], name="ix_enrollment_student")
    database.student_academic_enrollments.create_index([("institution_id", ASCENDING), ("class_division_id", ASCENDING)], name="ix_enrollment_class")
    database.student_academic_enrollments.create_index([("institution_id", ASCENDING), ("academic_year_id", ASCENDING)], name="ix_enrollment_year")
    database.student_academic_enrollments.create_index([("student_id", ASCENDING), ("is_current", ASCENDING)], unique=True, partialFilterExpression={"is_current": True}, name="uq_student_current_enrollment")
    database.student_academic_enrollments.create_index(
        [("institution_id", ASCENDING), ("academic_year_id", ASCENDING), ("class_division_id", ASCENDING), ("roll_number", ASCENDING)],
        unique=True, partialFilterExpression={"is_current": True, "enrollment_status": "active"}, name="uq_current_class_roll",
    )

def initialize_faculty_indexes(database: Database) -> None:
    database.faculty.create_index([("institution_id",ASCENDING),("employee_id",ASCENDING)],unique=True,name="uq_faculty_employee")
    database.faculty.create_index([("institution_id",ASCENDING),("user_id",ASCENDING)],unique=True,name="uq_faculty_user")
    database.faculty.create_index([("institution_id",ASCENDING),("department_id",ASCENDING)],name="ix_faculty_department")
    database.faculty.create_index([("institution_id",ASCENDING),("status",ASCENDING)],name="ix_faculty_status")
    database.faculty_assignments.create_index([("institution_id",ASCENDING),("faculty_id",ASCENDING)],name="ix_assignment_faculty")
    database.faculty_assignments.create_index([("institution_id",ASCENDING),("academic_year_id",ASCENDING)],name="ix_assignment_year")
    database.faculty_assignments.create_index([("institution_id",ASCENDING),("class_division_id",ASCENDING)],name="ix_assignment_class")
    database.faculty_assignments.create_index([("institution_id",ASCENDING),("subject_id",ASCENDING)],name="ix_assignment_subject")
    database.faculty_assignments.create_index([("institution_id",ASCENDING),("faculty_id",ASCENDING),("academic_year_id",ASCENDING),("subject_id",ASCENDING),("class_division_id",ASCENDING),("assignment_type",ASCENDING)],unique=True,partialFilterExpression={"status":"active"},name="uq_active_faculty_assignment")

def initialize_timetable_indexes(database: Database) -> None:
    entries=database.timetable_entries
    entries.create_index([("institution_id",ASCENDING),("academic_year_id",ASCENDING),("status",ASCENDING)],name="ix_timetable_year_status")
    entries.create_index([("institution_id",ASCENDING),("faculty_id",ASCENDING),("day_of_week",ASCENDING),("start_time",ASCENDING)],name="ix_timetable_faculty_day")
    entries.create_index([("institution_id",ASCENDING),("class_division_id",ASCENDING),("day_of_week",ASCENDING),("start_time",ASCENDING)],name="ix_timetable_class_day")
    entries.create_index([("institution_id",ASCENDING),("subject_id",ASCENDING)],name="ix_timetable_subject")
    entries.create_index([("institution_id",ASCENDING),("room",ASCENDING),("day_of_week",ASCENDING),("start_time",ASCENDING)],name="ix_timetable_room_day")
    entries.create_index([("institution_id",ASCENDING),("faculty_assignment_id",ASCENDING)],name="ix_timetable_assignment")

def initialize_attendance_indexes(database: Database) -> None:
    sessions=database.attendance_sessions
    sessions.create_index([("institution_id",ASCENDING),("timetable_entry_id",ASCENDING),("lecture_date",ASCENDING)],unique=True,partialFilterExpression={"timetable_entry_id":{"$exists":True}},name="uq_scheduled_attendance_session")
    sessions.create_index([("institution_id",ASCENDING),("faculty_id",ASCENDING),("lecture_date",ASCENDING)],name="ix_attendance_faculty_date")
    sessions.create_index([("institution_id",ASCENDING),("class_division_id",ASCENDING),("lecture_date",ASCENDING)],name="ix_attendance_class_date")
    sessions.create_index([("institution_id",ASCENDING),("subject_id",ASCENDING),("status",ASCENDING)],name="ix_attendance_subject_status")
    sessions.create_index([("institution_id",ASCENDING),("status",ASCENDING),("lecture_date",ASCENDING)],name="ix_attendance_reports_date")
    records=database.attendance_records
    records.create_index([("session_id",ASCENDING),("student_id",ASCENDING)],unique=True,name="uq_attendance_session_student")
    records.create_index([("institution_id",ASCENDING),("student_id",ASCENDING),("marked_at",ASCENDING)],name="ix_attendance_student_history")
    records.create_index([("institution_id",ASCENDING),("session_id",ASCENDING),("status",ASCENDING)],name="ix_attendance_session_status")

def initialize_face_enrollment_indexes(database: Database) -> None:
    enrollments=database.face_enrollments
    enrollments.create_index([("institution_id",ASCENDING),("student_id",ASCENDING)],unique=True,name="uq_face_enrollment_student")
    enrollments.create_index([("institution_id",ASCENDING),("status",ASCENDING),("updated_at",ASCENDING)],name="ix_face_enrollment_status")
    enrollments.create_index([("institution_id",ASCENDING),("model_version",ASCENDING)],name="ix_face_enrollment_model")

def initialize_phase13_indexes(database: Database) -> None:
    requests=database.attendance_requests
    requests.create_index([("institution_id",ASCENDING),("status",ASCENDING),("created_at",ASCENDING)],name="ix_request_status_created")
    requests.create_index([("institution_id",ASCENDING),("student_id",ASCENDING),("created_at",ASCENDING)],name="ix_request_student_created")
    requests.create_index([("institution_id",ASCENDING),("attendance_session_id",ASCENDING)],name="ix_request_session")
    requests.create_index([("institution_id",ASCENDING),("student_id",ASCENDING),("attendance_session_id",ASCENDING)],unique=True,partialFilterExpression={"status":"pending"},name="uq_pending_request_per_student_session")
    notifications=database.notifications
    notifications.create_index([("institution_id",ASCENDING),("recipient_user_id",ASCENDING),("created_at",ASCENDING)],name="ix_notification_recipient_created")
    notifications.create_index([("institution_id",ASCENDING),("recipient_user_id",ASCENDING),("read_at",ASCENDING)],name="ix_notification_recipient_read")
    audit=database.audit_events
    audit.create_index([("institution_id",ASCENDING),("created_at",ASCENDING)],name="ix_audit_created")
    audit.create_index([("institution_id",ASCENDING),("actor_user_id",ASCENDING),("created_at",ASCENDING)],name="ix_audit_actor_created")
    audit.create_index([("institution_id",ASCENDING),("entity_type",ASCENDING),("entity_id",ASCENDING)],name="ix_audit_entity")
    audit.create_index([("institution_id",ASCENDING),("action",ASCENDING),("created_at",ASCENDING)],name="ix_audit_action_created")

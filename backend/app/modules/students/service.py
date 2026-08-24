"""Tenant-scoped Student lifecycle orchestration."""

from datetime import date, datetime, timezone
from typing import Any

from bson import ObjectId

from app.core.errors import AppError, not_found
from app.core.security import PasswordService
from app.db.object_id import parse_object_id, serialize_document
from app.modules.academic_common.services import build_services
from app.modules.auth.repositories import UserRepository
from app.modules.students.repositories import EnrollmentRepository, StudentRepository
from app.modules.students.schemas import EnrollmentCreate, StudentCreate, StudentStatusUpdate, StudentUpdate
import logging
from app.core.logging import safe_log
logger=logging.getLogger("STUDENTS")

def _student_not_found(): return AppError("STUDENT_NOT_FOUND", "Student was not found.", 404)


def _dt(value):
    return datetime.combine(value, datetime.min.time(), tzinfo=timezone.utc) if isinstance(value, date) and not isinstance(value, datetime) else value


class StudentService:
    def __init__(self, students=None, enrollments=None, users=None, academics=None, passwords=None):
        self.students = students or StudentRepository()
        self.enrollments = enrollments or EnrollmentRepository()
        self.users = users or UserRepository()
        self.academics = academics or build_services()
        self.passwords = passwords or PasswordService()

    def _academic(self, resource, value, institution_id):
        document = self.academics[resource].repository.find_by_id(value)
        if document is None or str(document.get("institution_id")) != str(institution_id):
            raise AppError("CROSS_INSTITUTION_REFERENCE", f"Selected {resource.rstrip('s')} is unavailable for this Institution.", 422)
        if document.get("status", "active") != "active":
            raise AppError("INACTIVE_ACADEMIC_REFERENCE", f"Selected {resource.rstrip('s')} is inactive.", 422)
        return document

    def validate_enrollment(self, model, institution_id, *, student_id=None):
        year = self._academic("academic-years", model.academic_year_id, institution_id)
        department = self._academic("departments", model.department_id, institution_id)
        program = self._academic("programs", model.program_id, institution_id)
        semester = self._academic("semesters", model.semester_id, institution_id)
        division = self._academic("classes", model.class_division_id, institution_id)
        links = ((program, "department_id", department), (semester, "program_id", program),
                 (semester, "academic_year_id", year), (division, "program_id", program),
                 (division, "semester_id", semester), (division, "academic_year_id", year))
        if any(str(child.get(field)) != str(parent.get("_id")) for child, field, parent in links):
            raise AppError("INVALID_ACADEMIC_ENROLLMENT", "Academic selections do not form one valid hierarchy.", 422)
        if model.end_date and model.end_date < model.start_date:
            raise AppError("VALIDATION_ERROR", "end_date cannot precede start_date.", 422)
        if self.enrollments.roll_exists(institution_id, model.academic_year_id, model.class_division_id, model.roll_number):
            current = self.enrollments.current(student_id, institution_id) if student_id else None
            if current is None or current.get("roll_number") != model.roll_number or str(current.get("class_division_id")) != model.class_division_id:
                raise AppError("DUPLICATE_ROLL_NUMBER", "Roll number already exists in this class.", 409)

    def validate_create(self, model: StudentCreate, institution_id):
        if self.students.find_by_admission(institution_id, model.admission_number):
            raise AppError("DUPLICATE_ADMISSION_NUMBER", "Admission number already exists.", 409)
        duplicate = self.users.find_scoped_duplicate(institution_id, model.email, model.username)
        if duplicate:
            code = "USER_EMAIL_ALREADY_EXISTS" if duplicate.get("email") == model.email else "USER_USERNAME_ALREADY_EXISTS"
            raise AppError(code, "Student email or username already exists.", 409)
        self.validate_enrollment(model, institution_id)

    def create(self, model: StudentCreate, institution_id, actor_id):
        self.validate_create(model, institution_id)
        now = datetime.now(timezone.utc); iid = parse_object_id(institution_id, "institution_id")
        user = student = enrollment = None
        try:
            user = self.users.insert({"institution_id": iid, "role": "student", "username": model.username,
                "email": model.email, "display_name": model.display_name, "password_hash": self.passwords.hash_password(model.temporary_password),
                "status": "active", "must_change_password": True, "token_version": 0, "failed_login_attempts": 0,
                "locked_until": None, "last_login_at": None, "created_at": now, "updated_at": now, "created_by": parse_object_id(actor_id, "actor_id")})
            profile = model.model_dump(exclude={"username", "temporary_password", "academic_year_id", "department_id", "program_id", "semester_id", "class_division_id", "roll_number", "start_date", "end_date", "previous_status"})
            profile.update({"institution_id": iid, "user_id": user["_id"], "status": "active", "created_at": now, "updated_at": now, "created_by": parse_object_id(actor_id, "actor_id")})
            for key in ("date_of_birth", "admission_date"): profile[key] = _dt(profile.get(key))
            student = self.students.insert(profile)
            enrollment = self.enrollments.insert(self._enrollment_document(model, iid, student["_id"], now, actor_id))
            self.users.update(user["_id"], {"student_id": student["_id"]})
            safe_log(logger,logging.INFO,"Student created",student_id=str(student["_id"]));return self.get(str(student["_id"]), institution_id)
        except Exception:
            if enrollment: self.enrollments.delete_created(enrollment["_id"])
            if student: self.students.delete_created(student["_id"])
            if user: self.users.delete_created(user["_id"])
            raise

    def _enrollment_document(self, model, iid, student_id, now, actor_id=None):
        return {"institution_id": iid, "student_id": parse_object_id(student_id, "student_id"),
            **{key: parse_object_id(getattr(model, key), key) for key in ("academic_year_id", "department_id", "program_id", "semester_id", "class_division_id")},
            "roll_number": model.roll_number, "start_date": _dt(model.start_date), "end_date": _dt(model.end_date),
            "enrollment_status": "active", "is_current": True, "created_at": now, "updated_at": now,
            "created_by": parse_object_id(actor_id, "actor_id") if actor_id else None}

    def list(self, institution_id, filters, search, page, page_size):
        items, total = self.students.list(institution_id, filters, search, page, page_size)
        return {"items": [serialize_document(x) for x in items], "pagination": {"page": page, "pageSize": page_size, "total": total, "pages": (total + page_size - 1) // page_size}}

    def get(self, student_id, institution_id):
        student = self.students.find_by_id(student_id, institution_id)
        if not student: raise _student_not_found()
        user = self.users.find_by_id(student["user_id"])
        safe_user = {k: user.get(k) for k in ("_id", "username", "email", "display_name", "status", "must_change_password", "last_login_at")} if user else None
        return serialize_document({**student, "account": safe_user, "current_enrollment": self.enrollments.current(student_id, institution_id), "enrollment_history": self.enrollments.list_for_student(student_id, institution_id)})

    def update(self, student_id, model: StudentUpdate, institution_id, actor_id=None):
        current = self.students.find_by_id(student_id, institution_id)
        if not current: raise _student_not_found()
        changes = model.model_dump(exclude_unset=True)
        if actor_id: changes["updated_by"] = parse_object_id(actor_id, "actor_id")
        if changes.get("email") and changes["email"] != current.get("email") and self.users.find_by_email(institution_id, changes["email"]):
            raise AppError("USER_EMAIL_ALREADY_EXISTS", "Student email already exists.", 409)
        for key in ("date_of_birth", "admission_date"):
            if key in changes: changes[key] = _dt(changes[key])
        updated = self.students.update(student_id, institution_id, changes)
        user_changes = {k: changes[k] for k in ("display_name", "email") if k in changes}
        if user_changes: self.users.update(current["user_id"], user_changes)
        safe_log(logger,logging.INFO,"Student updated",student_id=str(student_id))
        return self.get(student_id, institution_id)

    def set_status(self, student_id, model: StudentStatusUpdate, institution_id, actor_id=None):
        student = self.students.find_by_id(student_id, institution_id)
        if not student: raise _student_not_found()
        domain_changes = {"status": model.status}
        if actor_id: domain_changes["updated_by"] = parse_object_id(actor_id, "actor_id")
        updated = self.students.update(student_id, institution_id, domain_changes)
        account_status = "active" if model.status in ("active", "graduated") else "suspended" if model.status == "suspended" else "inactive"
        user = self.users.find_by_id(student["user_id"])
        changes = {"status": account_status}
        if user and account_status != "active": changes["token_version"] = int(user.get("token_version", 0)) + 1
        self.users.update(student["user_id"], changes)
        return self.get(student_id, institution_id)

    def change_enrollment(self, student_id, model: EnrollmentCreate, institution_id, actor_id=None):
        if not self.students.find_by_id(student_id, institution_id): raise _student_not_found()
        self.validate_enrollment(model, institution_id, student_id=student_id)
        old = self.enrollments.current(student_id, institution_id)
        if not old: raise AppError("CURRENT_ENROLLMENT_NOT_FOUND", "Student has no current enrollment.", 409)
        self.enrollments.close_current(old["_id"], model.previous_status, _dt(model.start_date))
        try:
            self.enrollments.insert(self._enrollment_document(model, parse_object_id(institution_id), parse_object_id(student_id), datetime.now(timezone.utc), actor_id))
        except Exception:
            self.enrollments.restore_current(old["_id"]); raise
        return self.get(student_id, institution_id)

    def self_profile(self, user):
        student = self.students.find_by_user(user["_id"], user["institution_id"])
        if not student: raise not_found("Student profile")
        return self.get(str(student["_id"]), str(user["institution_id"]))

"""Production Student management and Student self-service endpoints."""

import csv
import io
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import PlainTextResponse

from app.core.config import get_settings
from app.core.errors import AppError
from app.modules.auth.dependencies import require_role
from app.modules.students.schemas import EnrollmentCreate, StudentCreate, StudentStatusUpdate, StudentUpdate
from app.modules.students.service import StudentService

router = APIRouter(tags=["students"])
CSV_FIELDS = ["admission_number", "name", "email", "username", "phone", "academic_year", "department_code", "program_code", "semester_number", "division", "roll_number", "temporary_password", "start_date"]
CSV_REQUIRED = [field for field in CSV_FIELDS if field != "phone"]


def get_student_service(): return StudentService()


async def _csv_rows(file: UploadFile):
    if not (file.filename or "").lower().endswith(".csv"):
        raise AppError("INVALID_FILE_TYPE", "Only .csv files are accepted.", 422)
    if file.content_type and file.content_type.casefold() not in {"text/csv", "application/csv", "application/vnd.ms-excel", "text/plain", "application/octet-stream"}:
        raise AppError("INVALID_FILE_TYPE", "The uploaded MIME type is not accepted for CSV import.", 422)
    data = await file.read(1_048_577)
    if len(data) > 1_048_576: raise AppError("FILE_TOO_LARGE", "CSV must not exceed 1 MB.", 413)
    try: text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc: raise AppError("INVALID_CSV_ENCODING", "CSV must use UTF-8 encoding.", 422) from exc
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames or any(field not in reader.fieldnames for field in CSV_REQUIRED):
        raise AppError("INVALID_CSV_HEADERS", "CSV is missing one or more required headers.", 422)
    rows = list(reader)
    if len(rows) > 500: raise AppError("TOO_MANY_ROWS", "CSV is limited to 500 data rows.", 422)
    return rows


def _csv_payload(row, service, institution_id):
    """Resolve human-readable academic CSV values within the Admin's Institution."""
    iid = institution_id
    def find(resource, filters, label):
        document = service.academics[resource].repository.find_one({"institution_id": iid, **filters})
        if not document: raise AppError("CSV_IMPORT_INVALID", f"Unknown {label}.", 422)
        return document
    year_value = row.get("academic_year", "").strip()
    year = find("academic-years", {"$or": [{"name": year_value}, {"code": year_value}]}, "academic year")
    department = find("departments", {"code": row.get("department_code", "").strip().upper()}, "department code")
    program = find("programs", {"code": row.get("program_code", "").strip().upper(), "department_id": department["_id"]}, "program code")
    try: semester_number = int(row.get("semester_number", ""))
    except ValueError as exc: raise AppError("CSV_IMPORT_INVALID", "Invalid semester number.", 422) from exc
    semester = find("semesters", {"semester_number": semester_number, "program_id": program["_id"], "academic_year_id": year["_id"]}, "semester")
    division = find("classes", {"division": row.get("division", "").strip().upper(), "program_id": program["_id"], "semester_id": semester["_id"], "academic_year_id": year["_id"]}, "class division")
    return {"display_name": row.get("name"), "admission_number": row.get("admission_number"), "email": row.get("email"), "username": row.get("username"), "temporary_password": row.get("temporary_password"), "phone": row.get("phone") or None,
        "academic_year_id": str(year["_id"]), "department_id": str(department["_id"]), "program_id": str(program["_id"]), "semester_id": str(semester["_id"]), "class_division_id": str(division["_id"]), "roll_number": row.get("roll_number"), "start_date": row.get("start_date")}


def _validate_rows(rows, service, institution_id):
    results = []; seen = set()
    for number, row in enumerate(rows, 2):
        errors = []
        if any(str(value).lstrip().startswith(("=", "+", "-", "@")) for key, value in row.items() if key not in ("start_date", "end_date")):
            errors.append("Spreadsheet formulas are not permitted.")
        signature = (row.get("admission_number", "").upper(), row.get("email", "").casefold(), row.get("username", "").casefold())
        if any(value in seen for value in signature if value): errors.append("Duplicate identifier within CSV.")
        seen.update(value for value in signature if value)
        try:
            model = StudentCreate.model_validate(_csv_payload(row, service, institution_id))
            if not errors: service.validate_create(model, institution_id)
        except Exception as exc:
            errors.append(getattr(exc, "message", str(exc)))
        results.append({"row": number, "valid": not errors, "errors": errors})
    return results


@router.get("/admin/students/import/template", response_class=PlainTextResponse)
def import_template(admin: Annotated[dict, Depends(require_role("admin"))]):
    output = io.StringIO(); writer = csv.writer(output); writer.writerow(CSV_FIELDS)
    return output.getvalue()


@router.post("/admin/students/import/preview")
async def import_preview(file: Annotated[UploadFile, File(...)], admin: Annotated[dict, Depends(require_role("admin"))], service: Annotated[StudentService, Depends(get_student_service)]):
    rows = await _csv_rows(file); report = _validate_rows(rows, service, str(admin["institution_id"]))
    duplicate_count = sum(any("Duplicate" in error for error in row["errors"]) for row in report)
    return {"total": len(report), "valid": sum(x["valid"] for x in report), "invalid": sum(not x["valid"] for x in report), "duplicates": duplicate_count, "rows": report, "writesPerformed": False}


@router.post("/admin/students/import/confirm")
async def import_confirm(file: Annotated[UploadFile, File(...)], confirm: bool, admin: Annotated[dict, Depends(require_role("admin"))], service: Annotated[StudentService, Depends(get_student_service)]):
    if not confirm: raise AppError("IMPORT_CONFIRMATION_REQUIRED", "Explicit import confirmation is required.", 422)
    rows = await _csv_rows(file); report = _validate_rows(rows, service, str(admin["institution_id"]))
    if any(not x["valid"] for x in report): return {"imported": 0, "rejected": len(report), "rows": report}
    created = []
    for number, row in enumerate(rows, 2):
        try:
            payload = _csv_payload(row, service, str(admin["institution_id"]))
            result = service.create(StudentCreate.model_validate(payload), str(admin["institution_id"]), str(admin["_id"]))
            created.append({"row": number, "studentId": result["_id"], "username": row["username"], "temporaryPassword": row["temporary_password"]})
        except Exception as exc:
            report.append({"row": number, "valid": False, "errors": [getattr(exc, "message", str(exc))]})
    return {"imported": len(created), "rejected": len(rows) - len(created), "credentials": created, "rows": report}


@router.get("/admin/students")
def list_students(admin: Annotated[dict, Depends(require_role("admin"))], service: Annotated[StudentService, Depends(get_student_service)], page: int = Query(1, ge=1), page_size: int = Query(20, alias="pageSize", ge=1), search: str | None = Query(None, max_length=100), status: str | None = None, account_status: str | None = None, academic_year_id: str | None = None, department_id: str | None = None, program_id: str | None = None, semester_id: str | None = None, class_division_id: str | None = None):
    if page_size > get_settings().max_page_size: raise AppError("VALIDATION_ERROR", "pageSize exceeds the configured limit.", 422)
    filters = {k: v for k, v in locals().items() if k in {"status", "account_status", "academic_year_id", "department_id", "program_id", "semester_id", "class_division_id"} and v}
    return service.list(str(admin["institution_id"]), filters, search, page, page_size)


@router.post("/admin/students", status_code=201)
def create_student(payload: StudentCreate, admin: Annotated[dict, Depends(require_role("admin"))], service: Annotated[StudentService, Depends(get_student_service)]): return service.create(payload, str(admin["institution_id"]), str(admin["_id"]))

@router.get("/admin/students/{student_id}")
def get_student(student_id: str, admin: Annotated[dict, Depends(require_role("admin"))], service: Annotated[StudentService, Depends(get_student_service)]): return service.get(student_id, str(admin["institution_id"]))

@router.patch("/admin/students/{student_id}")
def update_student(student_id: str, payload: StudentUpdate, admin: Annotated[dict, Depends(require_role("admin"))], service: Annotated[StudentService, Depends(get_student_service)]): return service.update(student_id, payload, str(admin["institution_id"]), str(admin["_id"]))

@router.patch("/admin/students/{student_id}/status")
def update_status(student_id: str, payload: StudentStatusUpdate, admin: Annotated[dict, Depends(require_role("admin"))], service: Annotated[StudentService, Depends(get_student_service)]): return service.set_status(student_id, payload, str(admin["institution_id"]), str(admin["_id"]))

@router.get("/admin/students/{student_id}/enrollments")
def enrollment_history(student_id: str, admin: Annotated[dict, Depends(require_role("admin"))], service: Annotated[StudentService, Depends(get_student_service)]): return service.get(student_id, str(admin["institution_id"]))["enrollment_history"]

@router.post("/admin/students/{student_id}/enrollments", status_code=201)
def change_enrollment(student_id: str, payload: EnrollmentCreate, admin: Annotated[dict, Depends(require_role("admin"))], service: Annotated[StudentService, Depends(get_student_service)]): return service.change_enrollment(student_id, payload, str(admin["institution_id"]), str(admin["_id"]))

@router.get("/student/profile")
def student_profile(student: Annotated[dict, Depends(require_role("student"))], service: Annotated[StudentService, Depends(get_student_service)]): return service.self_profile(student)

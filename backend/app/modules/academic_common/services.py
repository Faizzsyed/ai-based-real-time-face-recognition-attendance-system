"""Phase 2 hierarchy, ownership, duplicate, and deactivation rules."""

from math import ceil
from typing import Any
from datetime import date, datetime, time, timezone
from enum import Enum
import re
import logging
from app.core.logging import safe_log
logger=logging.getLogger("ACADEMIC")

from pydantic import BaseModel

from app.core.errors import AppError, not_found
from app.db.object_id import parse_object_id, serialize_document
from app.modules.academic_common.repositories import BaseRepository, build_repositories
from app.modules.academic_years.schemas import AcademicYearCreate, AcademicYearUpdate
from app.modules.class_divisions.schemas import ClassDivisionCreate, ClassDivisionUpdate
from app.modules.departments.schemas import DepartmentCreate, DepartmentUpdate
from app.modules.institutions.schemas import InstitutionCreate, InstitutionUpdate
from app.modules.programs.schemas import ProgramCreate, ProgramUpdate
from app.modules.semesters.schemas import SemesterCreate, SemesterUpdate
from app.modules.subjects.schemas import SubjectCreate, SubjectUpdate


SCHEMA_MAP = {
    "institutions": (InstitutionCreate, InstitutionUpdate),
    "academic-years": (AcademicYearCreate, AcademicYearUpdate),
    "departments": (DepartmentCreate, DepartmentUpdate),
    "programs": (ProgramCreate, ProgramUpdate),
    "semesters": (SemesterCreate, SemesterUpdate),
    "classes": (ClassDivisionCreate, ClassDivisionUpdate),
    "subjects": (SubjectCreate, SubjectUpdate),
}


class AcademicService:
    resource = ""
    entity_name = "Resource"

    def __init__(self, repositories: dict[str, BaseRepository]) -> None:
        self.repositories = repositories
        self.repository = repositories[self.resource]
        self.create_schema, self.update_schema = SCHEMA_MAP[self.resource]

    def get(self, document_id: str, institution_id: str | None = None) -> dict:
        document = self.repository.find_by_id(document_id, institution_id)
        if document is None:
            raise not_found(self.entity_name)
        return serialize_document(document)

    def list(self, filters: dict[str, Any], page: int, page_size: int) -> dict:
        filters = dict(filters)
        search = filters.pop("search", None)
        if search and self.resource in {"academic-years", "departments", "programs", "classes", "subjects"}:
            pattern = {"$regex": re.escape(search.strip()), "$options": "i"}
            fields = ("name",) if self.resource in {"academic-years", "classes"} else ("name", "code")
            filters["$or"] = [{field: pattern} for field in fields]
        items, total = self.repository.list(filters, page, page_size)
        return {
            "items": [serialize_document(item) for item in items],
            "page": page,
            "pageSize": page_size,
            "total": total,
            "totalPages": ceil(total / page_size) if total else 0,
        }

    def create(self, payload: BaseModel, actor_id: str | None = None) -> dict:
        data = payload.model_dump(exclude_none=True)
        self.validate(data)
        prepared = self._prepare_ids(data)
        if actor_id:
            prepared["created_by"] = parse_object_id(actor_id, "created_by")
            prepared["updated_by"] = parse_object_id(actor_id, "updated_by")
        document = self.repository.insert(prepared)
        safe_log(logger,logging.INFO,"academic resource created",resource=self.resource,document_id=str(document.get("_id")))
        return serialize_document(document)

    def update(self, document_id: str, payload: BaseModel, institution_id: str | None = None, actor_id: str | None = None) -> dict:
        existing = self.repository.find_by_id(document_id, institution_id)
        if existing is None:
            raise not_found(self.entity_name)
        changes = payload.model_dump(exclude_unset=True, exclude_none=True)
        if not changes:
            raise AppError("VALIDATION_ERROR", "At least one update field is required.", 422)
        existing_api = serialize_document(existing)
        candidate = {
            key: value
            for key, value in existing_api.items()
            if key not in {"_id", "id", "created_at", "updated_at", "created_by", "updated_by"}
        }
        candidate.update(changes)
        validated = self.create_schema.model_validate(candidate).model_dump(exclude_none=True)
        self.validate(validated, exclude_id=document_id)
        self.validate_deactivation(existing, validated)
        prepared = self._prepare_ids(changes)
        if actor_id:
            prepared["updated_by"] = parse_object_id(actor_id, "updated_by")
        updated = self.repository.update(document_id, prepared, institution_id)
        safe_log(logger,logging.INFO,"academic resource updated",resource=self.resource,document_id=str(document_id))
        return serialize_document(updated)

    def validate(self, data: dict[str, Any], exclude_id: str | None = None) -> None:
        del data, exclude_id

    def validate_deactivation(self, existing: dict, candidate: dict) -> None:
        if existing.get("status") == "active" and candidate.get("status") == "inactive":
            self._ensure_not_in_use(str(existing["_id"]))

    def _ensure_not_in_use(self, document_id: str) -> None:
        dependencies = {
            "institutions": (("academic-years", "institution_id"), ("departments", "institution_id")),
            "academic-years": (("semesters", "academic_year_id"), ("classes", "academic_year_id")),
            "departments": (("programs", "department_id"),),
            "programs": (("semesters", "program_id"), ("classes", "program_id"), ("subjects", "program_id")),
            "semesters": (("classes", "semester_id"), ("subjects", "semester_id")),
        }
        for child_resource, field in dependencies.get(self.resource, ()):
            if self.repositories[child_resource].count({field: document_id, "status": "active"}) > 0:
                raise AppError("RESOURCE_IN_USE", f"{self.entity_name} has active dependent records.", 409)

    @staticmethod
    def _prepare_ids(data: dict[str, Any]) -> dict[str, Any]:
        prepared: dict[str, Any] = {}
        for key, value in data.items():
            if key.endswith("_id"):
                prepared[key] = parse_object_id(value, key)
            elif isinstance(value, date) and not isinstance(value, datetime):
                prepared[key] = datetime.combine(value, time.min, tzinfo=timezone.utc)
            elif isinstance(value, Enum):
                prepared[key] = value.value
            else:
                prepared[key] = value
        return prepared

    def _unique(self, filters: dict[str, Any], exclude_id: str | None, code: str = "DUPLICATE_CODE") -> None:
        found = self.repository.find_one(filters)
        if found is not None and (exclude_id is None or str(found["_id"]) != exclude_id):
            raise AppError(code, "A record with the same scoped identifier already exists.", 409)

    def _institution(self, institution_id: str) -> dict:
        document = self.repositories["institutions"].find_by_id(institution_id)
        if document is None:
            raise AppError("INVALID_REFERENCE", "Institution does not exist.", 422)
        return document

    def _owned_reference(self, resource: str, document_id: str, institution_id: str, label: str) -> dict:
        scoped = self.repositories[resource].find_by_id(document_id, institution_id)
        if scoped is not None:
            return scoped
        unscoped = self.repositories[resource].find_by_id(document_id)
        if unscoped is not None:
            raise AppError("CROSS_INSTITUTION_REFERENCE", f"{label} belongs to another institution.", 422)
        raise AppError("INVALID_REFERENCE", f"{label} does not exist.", 422)


class InstitutionService(AcademicService):
    resource = "institutions"
    entity_name = "Institution"

    def validate(self, data, exclude_id=None):
        self._unique({"code": data["code"]}, exclude_id)


class AcademicYearService(AcademicService):
    resource = "academic-years"
    entity_name = "Academic year"

    def validate(self, data, exclude_id=None):
        self._institution(data["institution_id"])
        self._unique({"institution_id": data["institution_id"], "name": data["name"]}, exclude_id, "DUPLICATE_CODE")

    def create(self, payload: BaseModel, actor_id: str | None = None) -> dict:
        data = payload.model_dump(exclude_none=True)
        self.validate(data)
        if data.get("is_current"):
            self.repository.unset_current(data["institution_id"])
        prepared = self._prepare_ids(data)
        if actor_id:
            prepared.update(created_by=parse_object_id(actor_id, "created_by"), updated_by=parse_object_id(actor_id, "updated_by"))
        return serialize_document(self.repository.insert(prepared))

    def update(self, document_id: str, payload: BaseModel, institution_id: str | None = None, actor_id: str | None = None) -> dict:
        existing = self.repository.find_by_id(document_id, institution_id)
        if existing is None:
            raise not_found(self.entity_name)
        changes = payload.model_dump(exclude_unset=True, exclude_none=True)
        if not changes:
            raise AppError("VALIDATION_ERROR", "At least one update field is required.", 422)
        if changes.get("status") == "inactive" and existing.get("is_current"):
            changes["is_current"] = False
        candidate = {key: value for key, value in serialize_document(existing).items() if key not in {"_id", "id", "created_at", "updated_at", "created_by", "updated_by"}}
        candidate.update(changes)
        validated = self.create_schema.model_validate(candidate).model_dump(exclude_none=True)
        self.validate(validated, exclude_id=document_id)
        self.validate_deactivation(existing, validated)
        if changes.get("is_current") and institution_id:
            self.repository.unset_current(institution_id, document_id)
        prepared = self._prepare_ids(changes)
        if actor_id:
            prepared["updated_by"] = parse_object_id(actor_id, "updated_by")
        return serialize_document(self.repository.update(document_id, prepared, institution_id))


class DepartmentService(AcademicService):
    resource = "departments"
    entity_name = "Department"

    def validate(self, data, exclude_id=None):
        self._institution(data["institution_id"])
        self._unique({"institution_id": data["institution_id"], "code": data["code"]}, exclude_id)


class ProgramService(AcademicService):
    resource = "programs"
    entity_name = "Program"

    def validate(self, data, exclude_id=None):
        institution_id = data["institution_id"]
        self._institution(institution_id)
        department = self._owned_reference("departments", data["department_id"], institution_id, "Department")
        if department.get("status") != "active":
            raise AppError("INVALID_REFERENCE", "Department must be active before adding a Program.", 422)
        self._unique({"institution_id": institution_id, "department_id": data["department_id"], "code": data["code"]}, exclude_id)


class SemesterService(AcademicService):
    resource = "semesters"
    entity_name = "Semester"

    def validate(self, data, exclude_id=None):
        institution_id = data["institution_id"]
        program = self._owned_reference("programs", data["program_id"], institution_id, "Program")
        self._owned_reference("academic-years", data["academic_year_id"], institution_id, "Academic year")
        if data["semester_number"] > program["total_semesters"]:
            raise AppError("VALIDATION_ERROR", "semester_number exceeds the Program total_semesters.", 422)
        self._unique({"institution_id": institution_id, "program_id": data["program_id"], "academic_year_id": data["academic_year_id"], "semester_number": data["semester_number"]}, exclude_id)


class ClassDivisionService(AcademicService):
    resource = "classes"
    entity_name = "Class division"

    def validate(self, data, exclude_id=None):
        institution_id = data["institution_id"]
        department = self._owned_reference("departments", data["department_id"], institution_id, "Department")
        program = self._owned_reference("programs", data["program_id"], institution_id, "Program")
        semester = self._owned_reference("semesters", data["semester_id"], institution_id, "Semester")
        year = self._owned_reference("academic-years", data["academic_year_id"], institution_id, "Academic year")
        del department, year
        if program["department_id"] != parse_object_id(data["department_id"]):
            raise AppError("INVALID_REFERENCE", "Program does not belong to the selected Department.", 422)
        if semester["program_id"] != parse_object_id(data["program_id"]) or semester["academic_year_id"] != parse_object_id(data["academic_year_id"]):
            raise AppError("INVALID_REFERENCE", "Semester hierarchy does not match the selected Program and Academic Year.", 422)
        self._unique({"institution_id": institution_id, "academic_year_id": data["academic_year_id"], "program_id": data["program_id"], "semester_id": data["semester_id"], "division": data["division"]}, exclude_id)


class SubjectService(AcademicService):
    resource = "subjects"
    entity_name = "Subject"

    def validate(self, data, exclude_id=None):
        institution_id = data["institution_id"]
        program = self._owned_reference("programs", data["program_id"], institution_id, "Program")
        semester = self._owned_reference("semesters", data["semester_id"], institution_id, "Semester")
        self._owned_reference("departments", data["department_id"], institution_id, "Department")
        if program["department_id"] != parse_object_id(data["department_id"]):
            raise AppError("INVALID_REFERENCE", "Program does not belong to the selected Department.", 422)
        if semester["program_id"] != parse_object_id(data["program_id"]):
            raise AppError("INVALID_REFERENCE", "Semester does not belong to the selected Program.", 422)
        self._unique({"institution_id": institution_id, "program_id": data["program_id"], "semester_id": data["semester_id"], "code": data["code"]}, exclude_id)


SERVICE_CLASSES = {
    "institutions": InstitutionService,
    "academic-years": AcademicYearService,
    "departments": DepartmentService,
    "programs": ProgramService,
    "semesters": SemesterService,
    "classes": ClassDivisionService,
    "subjects": SubjectService,
}


def build_services(repositories: dict[str, BaseRepository] | None = None) -> dict[str, AcademicService]:
    repositories = repositories or build_repositories()
    return {name: service_type(repositories) for name, service_type in SERVICE_CLASSES.items()}

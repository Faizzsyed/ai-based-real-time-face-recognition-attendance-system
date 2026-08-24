"""Production Admin academic management scoped to the authenticated Institution."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, Query
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.core.config import get_settings
from app.core.errors import AppError, not_found
from app.db.object_id import serialize_document
from app.modules.academic_common.services import SCHEMA_MAP, AcademicService, build_services
from app.modules.auth.dependencies import require_role

router = APIRouter(prefix="/admin/academic", tags=["admin-academic"])
MANAGED_RESOURCES = {"academic-years", "departments", "programs", "semesters", "classes", "subjects"}


class InstitutionAdminUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    short_name: str | None = Field(default=None, max_length=80)
    email: str | None = Field(default=None, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    phone: str | None = Field(default=None, max_length=30)
    address: str | None = Field(default=None, max_length=300)
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=100)
    country: str | None = Field(default=None, min_length=2, max_length=100)
    timezone: str | None = Field(default=None, min_length=3, max_length=80)
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


def get_admin_services() -> dict[str, AcademicService]:
    return build_services()


def _service(resource: str, services: dict[str, AcademicService]) -> AcademicService:
    if resource not in MANAGED_RESOURCES:
        raise not_found("Academic resource")
    return services[resource]


def _model(resource: str, payload: dict[str, Any], institution_id: str, update: bool = False):
    if "institution_id" in payload:
        raise AppError("IMMUTABLE_FIELD", "institution_id is derived from the authenticated Admin.", 422)
    data = dict(payload)
    if not update:
        data["institution_id"] = institution_id
    try:
        return SCHEMA_MAP[resource][1 if update else 0].model_validate(data)
    except ValidationError as exc:
        first = exc.errors(include_url=False)[0]
        field = ".".join(str(item) for item in first.get("loc", ())) or "payload"
        raise AppError("VALIDATION_ERROR", f"Invalid {field}: {first['msg']}", 422) from exc


@router.get("/institution")
def get_institution(
    admin: Annotated[dict[str, Any], Depends(require_role("admin"))],
    services: Annotated[dict[str, AcademicService], Depends(get_admin_services)],
) -> dict:
    return services["institutions"].get(str(admin["institution_id"]))


@router.patch("/institution")
def update_institution(
    payload: InstitutionAdminUpdate,
    admin: Annotated[dict[str, Any], Depends(require_role("admin"))],
    services: Annotated[dict[str, AcademicService], Depends(get_admin_services)],
) -> dict:
    return services["institutions"].update(
        str(admin["institution_id"]), payload, actor_id=str(admin["_id"])
    )


@router.get("/setup-status")
def setup_status(
    admin: Annotated[dict[str, Any], Depends(require_role("admin"))],
    services: Annotated[dict[str, AcademicService], Depends(get_admin_services)],
) -> dict[str, Any]:
    institution_id = str(admin["institution_id"])
    checks = {
        "institution": services["institutions"].repository.find_by_id(institution_id) is not None,
        "academicYear": services["academic-years"].repository.count({"institution_id": institution_id, "is_current": True, "status": "active"}) > 0,
        "department": services["departments"].repository.count({"institution_id": institution_id, "status": "active"}) > 0,
        "program": services["programs"].repository.count({"institution_id": institution_id, "status": "active"}) > 0,
        "semester": services["semesters"].repository.count({"institution_id": institution_id, "status": "active"}) > 0,
        "class": services["classes"].repository.count({"institution_id": institution_id, "status": "active"}) > 0,
        "subject": services["subjects"].repository.count({"institution_id": institution_id, "status": "active"}) > 0,
    }
    completed = sum(checks.values())
    state = "Ready" if completed == len(checks) else "Incomplete" if completed <= 1 else "Partially Configured"
    return {"state": state, "completed": completed, "total": len(checks), "checks": checks}


@router.get("/{resource}")
def list_resources(
    resource: str,
    admin: Annotated[dict[str, Any], Depends(require_role("admin"))],
    services: Annotated[dict[str, AcademicService], Depends(get_admin_services)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, alias="pageSize", ge=1),
    search: str | None = Query(default=None, max_length=100),
    academic_year_id: str | None = None,
    department_id: str | None = None,
    program_id: str | None = None,
    semester_id: str | None = None,
    status: str | None = Query(default=None, pattern="^(active|inactive)$"),
    subject_type: str | None = Query(default=None, alias="type", pattern="^(theory|practical|project|elective)$"),
    division: str | None = None,
    is_current: bool | None = Query(default=None, alias="current"),
) -> dict:
    if page_size > get_settings().max_page_size:
        raise AppError("VALIDATION_ERROR", f"pageSize cannot exceed {get_settings().max_page_size}.", 422)
    filters = {
        "institution_id": str(admin["institution_id"]), "academic_year_id": academic_year_id,
        "department_id": department_id, "program_id": program_id, "semester_id": semester_id,
        "status": status, "subject_type": subject_type, "division": division.upper() if division else None,
        "is_current": is_current, "search": search,
    }
    return _service(resource, services).list(filters, page, page_size)


@router.get("/{resource}/{document_id}")
def get_resource(
    resource: str,
    document_id: str,
    admin: Annotated[dict[str, Any], Depends(require_role("admin"))],
    services: Annotated[dict[str, AcademicService], Depends(get_admin_services)],
) -> dict:
    return _service(resource, services).get(document_id, str(admin["institution_id"]))


@router.post("/{resource}", status_code=201)
def create_resource(
    resource: str,
    admin: Annotated[dict[str, Any], Depends(require_role("admin"))],
    services: Annotated[dict[str, AcademicService], Depends(get_admin_services)],
    payload: dict[str, Any] = Body(...),
) -> dict:
    service = _service(resource, services)
    model = _model(resource, payload, str(admin["institution_id"]))
    return service.create(model, actor_id=str(admin["_id"]))


@router.patch("/{resource}/{document_id}")
def update_resource(
    resource: str,
    document_id: str,
    admin: Annotated[dict[str, Any], Depends(require_role("admin"))],
    services: Annotated[dict[str, AcademicService], Depends(get_admin_services)],
    payload: dict[str, Any] = Body(...),
) -> dict:
    service = _service(resource, services)
    model = _model(resource, payload, str(admin["institution_id"]), update=True)
    return service.update(document_id, model, str(admin["institution_id"]), actor_id=str(admin["_id"]))

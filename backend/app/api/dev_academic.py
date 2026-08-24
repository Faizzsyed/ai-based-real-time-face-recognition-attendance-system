"""Temporary Phase 2 academic tooling, disabled unless explicitly enabled."""

from typing import Any

from fastapi import APIRouter, Body, Depends, Query
from pydantic import ValidationError

from app.core.config import get_settings
from app.core.errors import AppError
from app.modules.academic_common.services import SCHEMA_MAP, build_services


def require_dev_academic_api() -> None:
    if not get_settings().enable_dev_academic_api:
        raise AppError("DEV_API_DISABLED", "Development academic API is disabled.", 404)


router = APIRouter(
    prefix="/dev",
    tags=["development-academic"],
    dependencies=[Depends(require_dev_academic_api)],
)
services = build_services()


def _service(resource: str):
    try:
        return services[resource]
    except KeyError as exc:
        raise AppError("RESOURCE_NOT_FOUND", "Development academic resource was not found.", 404) from exc


def _model(resource: str, payload: dict[str, Any], update: bool = False):
    try:
        schema = SCHEMA_MAP[resource][1 if update else 0]
        return schema.model_validate(payload)
    except KeyError as exc:
        raise AppError("RESOURCE_NOT_FOUND", "Development academic resource was not found.", 404) from exc
    except ValidationError as exc:
        first = exc.errors(include_url=False)[0]
        field = ".".join(str(item) for item in first.get("loc", ())) or "payload"
        raise AppError("VALIDATION_ERROR", f"Invalid {field}: {first['msg']}", 422) from exc


def _require_scope(resource: str, institution_id: str | None) -> str | None:
    if resource != "institutions" and not institution_id:
        raise AppError("VALIDATION_ERROR", "institution_id is required for tenant-owned resources.", 422)
    return institution_id


@router.get("/{resource}")
def list_resources(
    resource: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, alias="pageSize", ge=1),
    institution_id: str | None = None,
    academic_year_id: str | None = None,
    department_id: str | None = None,
    program_id: str | None = None,
    semester_id: str | None = None,
    status: str | None = None,
    subject_type: str | None = None,
    division: str | None = None,
) -> dict:
    _require_scope(resource, institution_id)
    if page_size > get_settings().max_page_size:
        raise AppError("VALIDATION_ERROR", f"pageSize cannot exceed {get_settings().max_page_size}.", 422)
    filters = {
        "institution_id": institution_id,
        "academic_year_id": academic_year_id,
        "department_id": department_id,
        "program_id": program_id,
        "semester_id": semester_id,
        "status": status,
        "subject_type": subject_type,
        "division": division.upper() if division else None,
    }
    return _service(resource).list(filters, page, page_size)


@router.get("/{resource}/{document_id}")
def get_resource(
    resource: str,
    document_id: str,
    institution_id: str | None = None,
) -> dict:
    return _service(resource).get(document_id, _require_scope(resource, institution_id))


@router.post("/{resource}", status_code=201)
def create_resource(resource: str, payload: dict[str, Any] = Body(...)) -> dict:
    return _service(resource).create(_model(resource, payload))


@router.patch("/{resource}/{document_id}")
def update_resource(
    resource: str,
    document_id: str,
    payload: dict[str, Any] = Body(...),
    institution_id: str | None = None,
) -> dict:
    scope = _require_scope(resource, institution_id)
    return _service(resource).update(document_id, _model(resource, payload, update=True), scope)

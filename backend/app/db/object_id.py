"""Central MongoDB ObjectId parsing and serialization helpers."""

from typing import Any

from bson import ObjectId

from app.core.errors import AppError


def parse_object_id(value: str | ObjectId, field: str = "id") -> ObjectId:
    if isinstance(value, ObjectId):
        return value
    if not ObjectId.is_valid(value):
        raise AppError("VALIDATION_ERROR", f"{field} must be a valid ObjectId.", 422)
    return ObjectId(value)


def serialize_document(document: dict[str, Any] | None) -> dict[str, Any] | None:
    if document is None:
        return None
    return {key: _serialize_value(value) for key, value in document.items()}


def _serialize_value(value: Any) -> Any:
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, list):
        return [_serialize_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _serialize_value(item) for key, item in value.items()}
    return value

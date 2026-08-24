"""MongoDB persistence only; business rules live in services."""

from datetime import datetime, timezone
from typing import Any

from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from app.core.errors import AppError
from app.db.mongo import mongo
from app.db.object_id import parse_object_id


class BaseRepository:
    collection_name = ""

    def __init__(self, database: Database | None = None) -> None:
        self._database = database

    @property
    def collection(self) -> Collection:
        database = self._database or mongo.require_database()
        return database[self.collection_name]

    def find_by_id(self, document_id: str, institution_id: str | None = None) -> dict | None:
        query: dict[str, Any] = {"_id": parse_object_id(document_id)}
        if institution_id is not None:
            query["institution_id"] = parse_object_id(institution_id, "institution_id")
        return self.collection.find_one(query)

    def find_one(self, filters: dict[str, Any]) -> dict | None:
        return self.collection.find_one(self._normalize_filters(filters))

    def list(self, filters: dict[str, Any], page: int, page_size: int) -> tuple[list[dict], int]:
        query = self._normalize_filters(filters)
        total = self.collection.count_documents(query)
        items = list(
            self.collection.find(query)
            .sort("created_at", -1)
            .skip((page - 1) * page_size)
            .limit(page_size)
        )
        return items, total

    def insert(self, document: dict[str, Any]) -> dict:
        now = datetime.now(timezone.utc)
        document = {**document, "created_at": now, "updated_at": now}
        try:
            result = self.collection.insert_one(document)
        except DuplicateKeyError as exc:
            raise AppError("DUPLICATE_CODE", "A record with the same scoped identifier already exists.", 409) from exc
        return self.collection.find_one({"_id": result.inserted_id})

    def update(self, document_id: str, changes: dict[str, Any], institution_id: str | None = None) -> dict | None:
        query: dict[str, Any] = {"_id": parse_object_id(document_id)}
        if institution_id is not None:
            query["institution_id"] = parse_object_id(institution_id, "institution_id")
        changes = {**changes, "updated_at": datetime.now(timezone.utc)}
        try:
            self.collection.update_one(query, {"$set": changes})
        except DuplicateKeyError as exc:
            raise AppError("DUPLICATE_CODE", "A record with the same scoped identifier already exists.", 409) from exc
        return self.collection.find_one(query)

    def count(self, filters: dict[str, Any]) -> int:
        return self.collection.count_documents(self._normalize_filters(filters))

    def unset_current(self, institution_id: str, exclude_id: str | None = None) -> None:
        query: dict[str, Any] = {
            "institution_id": parse_object_id(institution_id, "institution_id"),
            "is_current": True,
        }
        if exclude_id:
            query["_id"] = {"$ne": parse_object_id(exclude_id)}
        self.collection.update_many(
            query,
            {"$set": {"is_current": False, "updated_at": datetime.now(timezone.utc)}},
        )

    @staticmethod
    def _normalize_filters(filters: dict[str, Any]) -> dict[str, Any]:
        normalized: dict[str, Any] = {}
        for key, value in filters.items():
            if value is None:
                continue
            if key == "$or" and isinstance(value, list):
                normalized[key] = [BaseRepository._normalize_filters(item) for item in value]
            elif key.endswith("_id") and not isinstance(value, dict):
                normalized[key] = parse_object_id(value, key)
            else:
                normalized[key] = value
        return normalized


class InstitutionRepository(BaseRepository):
    collection_name = "institutions"


class AcademicYearRepository(BaseRepository):
    collection_name = "academic_years"


class DepartmentRepository(BaseRepository):
    collection_name = "departments"


class ProgramRepository(BaseRepository):
    collection_name = "programs"


class SemesterRepository(BaseRepository):
    collection_name = "semesters"


class ClassDivisionRepository(BaseRepository):
    collection_name = "class_divisions"


class SubjectRepository(BaseRepository):
    collection_name = "subjects"


def build_repositories(database: Database | None = None) -> dict[str, BaseRepository]:
    return {
        "institutions": InstitutionRepository(database),
        "academic-years": AcademicYearRepository(database),
        "departments": DepartmentRepository(database),
        "programs": ProgramRepository(database),
        "semesters": SemesterRepository(database),
        "classes": ClassDivisionRepository(database),
        "subjects": SubjectRepository(database),
    }

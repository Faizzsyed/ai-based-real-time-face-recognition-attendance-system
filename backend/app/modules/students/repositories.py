"""MongoDB repositories for Student profiles and immutable enrollment history."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from app.core.errors import AppError
from app.db.mongo import mongo
from app.db.object_id import parse_object_id


def _duplicate(exc: DuplicateKeyError) -> AppError:
    text = str(exc)
    if "admission" in text:
        return AppError("DUPLICATE_ADMISSION_NUMBER", "Admission number already exists.", 409)
    if "roll" in text:
        return AppError("DUPLICATE_ROLL_NUMBER", "Roll number already exists in this class.", 409)
    if "current" in text:
        return AppError("CURRENT_ENROLLMENT_ALREADY_EXISTS", "Student already has a current enrollment.", 409)
    return AppError("DUPLICATE_RESOURCE", "A Student record with the same scoped identifier already exists.", 409)


class StudentRepository:
    def __init__(self, database=None): self._database = database
    @property
    def collection(self): return (self._database or mongo.require_database()).students

    def insert(self, document):
        try: result = self.collection.insert_one(document)
        except DuplicateKeyError as exc: raise _duplicate(exc) from exc
        return {**document, "_id": result.inserted_id}

    def find_by_id(self, student_id, institution_id):
        return self.collection.find_one({"_id": parse_object_id(student_id), "institution_id": parse_object_id(institution_id)})

    def find_by_user(self, user_id, institution_id):
        return self.collection.find_one({"user_id": parse_object_id(user_id), "institution_id": parse_object_id(institution_id)})

    def find_by_admission(self, institution_id, admission_number):
        return self.collection.find_one({"institution_id": parse_object_id(institution_id), "admission_number": admission_number})

    def update(self, student_id, institution_id, changes):
        query = {"_id": parse_object_id(student_id), "institution_id": parse_object_id(institution_id)}
        try: self.collection.update_one(query, {"$set": {**changes, "updated_at": datetime.now(timezone.utc)}})
        except DuplicateKeyError as exc: raise _duplicate(exc) from exc
        return self.collection.find_one(query)

    def delete_created(self, student_id): self.collection.delete_one({"_id": parse_object_id(student_id)})

    def list(self, institution_id, filters, search, page, page_size):
        match: dict[str, Any] = {"institution_id": parse_object_id(institution_id)}
        if filters.get("status"): match["status"] = filters["status"]
        pipeline: list[dict] = [{"$match": match}, {"$lookup": {"from": "student_academic_enrollments", "let": {"sid": "$_id"}, "pipeline": [{"$match": {"$expr": {"$and": [{"$eq": ["$student_id", "$$sid"]}, {"$eq": ["$is_current", True]}]}}}], "as": "current_enrollments"}}, {"$set": {"current_enrollment": {"$first": "$current_enrollments"}}}, {"$lookup": {"from": "users", "localField": "user_id", "foreignField": "_id", "as": "accounts"}}, {"$set": {"account": {"$first": "$accounts"}}}]
        enrollment_map = {"academic_year_id": "academic_year_id", "department_id": "department_id", "program_id": "program_id", "semester_id": "semester_id", "class_division_id": "class_division_id", "roll_number": "roll_number"}
        enrollment_match = {f"current_enrollment.{target}": parse_object_id(value, key) if key.endswith("_id") else value for key, target in enrollment_map.items() if (value := filters.get(key))}
        if enrollment_match: pipeline.append({"$match": enrollment_match})
        if filters.get("account_status"): pipeline.append({"$match": {"account.status": filters["account_status"]}})
        if search:
            import re
            escaped = re.escape(search[:100])
            pipeline.append({"$match": {"$or": [{field: {"$regex": escaped, "$options": "i"}} for field in ("display_name", "admission_number", "email", "current_enrollment.roll_number")]}})
        pipeline.extend([{"$facet": {"items": [{"$sort": {"created_at": -1}}, {"$skip": (page-1)*page_size}, {"$limit": page_size}], "count": [{"$count": "total"}]}}])
        result = next(iter(self.collection.aggregate(pipeline)), {"items": [], "count": []})
        return result["items"], result["count"][0]["total"] if result["count"] else 0

    def count(self, institution_id, status=None):
        query = {"institution_id": parse_object_id(institution_id)}
        if status: query["status"] = status
        return self.collection.count_documents(query)


class EnrollmentRepository:
    def __init__(self, database=None): self._database = database
    @property
    def collection(self): return (self._database or mongo.require_database()).student_academic_enrollments
    def insert(self, document):
        try: result = self.collection.insert_one(document)
        except DuplicateKeyError as exc: raise _duplicate(exc) from exc
        return {**document, "_id": result.inserted_id}
    def current(self, student_id, institution_id): return self.collection.find_one({"student_id": parse_object_id(student_id), "institution_id": parse_object_id(institution_id), "is_current": True})
    def list_for_student(self, student_id, institution_id): return list(self.collection.find({"student_id": parse_object_id(student_id), "institution_id": parse_object_id(institution_id)}).sort("start_date", -1))
    def roll_exists(self, institution_id, academic_year_id, class_id, roll): return self.collection.find_one({"institution_id": parse_object_id(institution_id), "academic_year_id": parse_object_id(academic_year_id), "class_division_id": parse_object_id(class_id), "roll_number": roll, "is_current": True, "enrollment_status": "active"}) is not None
    def close_current(self, enrollment_id, status, end_date): self.collection.update_one({"_id": parse_object_id(enrollment_id), "is_current": True}, {"$set": {"is_current": False, "enrollment_status": status, "end_date": end_date, "updated_at": datetime.now(timezone.utc)}})
    def restore_current(self, enrollment_id): self.collection.update_one({"_id": parse_object_id(enrollment_id)}, {"$set": {"is_current": True, "enrollment_status": "active", "end_date": None}})
    def delete_created(self, enrollment_id): self.collection.delete_one({"_id": parse_object_id(enrollment_id)})

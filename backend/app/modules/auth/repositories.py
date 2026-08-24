"""MongoDB repositories for users and revocable authentication sessions."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.db.mongo import mongo
from app.db.object_id import parse_object_id
from app.core.errors import AppError


class UserRepository:
    @property
    def collection(self):
        return mongo.require_database().users

    def find_by_identifier(self, identifier: str) -> dict[str, Any] | None:
        matches = list(self.collection.find({"$or": [{"email": identifier}, {"username": identifier}]}).limit(2))
        return matches[0] if len(matches) == 1 else None

    def find_by_id(self, user_id: str | ObjectId) -> dict[str, Any] | None:
        return self.collection.find_one({"_id": parse_object_id(user_id, "user_id")})

    def record_failed_login(self, user_id: str | ObjectId, attempts: int, locked_until: datetime | None) -> None:
        self.collection.update_one(
            {"_id": parse_object_id(user_id, "user_id")},
            {"$set": {"failed_login_attempts": attempts, "locked_until": locked_until, "updated_at": datetime.now(timezone.utc)}},
        )

    def record_login(self, user_id: str | ObjectId, at: datetime) -> None:
        self.collection.update_one(
            {"_id": parse_object_id(user_id, "user_id")},
            {"$set": {"last_login_at": at, "failed_login_attempts": 0, "locked_until": None, "updated_at": at}},
        )

    def increment_token_version(self, user_id: str | ObjectId) -> None:
        self.collection.update_one(
            {"_id": parse_object_id(user_id, "user_id")},
            {"$inc": {"token_version": 1}, "$set": {"updated_at": datetime.now(timezone.utc)}},
        )

    def insert(self, document: dict[str, Any]) -> dict[str, Any]:
        try:
            result = self.collection.insert_one(document)
        except DuplicateKeyError as exc:
            keys = (exc.details or {}).get("keyPattern", {})
            code = "USER_EMAIL_ALREADY_EXISTS" if "email" in keys or "email" in str(exc) else "USER_USERNAME_ALREADY_EXISTS"
            raise AppError(code, "A User account with this email or username already exists.", 409) from exc
        return {**document, "_id": result.inserted_id}

    def find_scoped_duplicate(self, institution_id: str | ObjectId, email: str, username: str) -> dict[str, Any] | None:
        return self.collection.find_one({"institution_id": parse_object_id(institution_id, "institution_id"), "$or": [{"email": email}, {"username": username}]})

    def find_by_email(self, institution_id: str | ObjectId, email: str) -> dict[str, Any] | None:
        return self.collection.find_one({"institution_id": parse_object_id(institution_id, "institution_id"), "email": email})

    def find_by_username(self, institution_id: str | ObjectId, username: str) -> dict[str, Any] | None:
        return self.collection.find_one({"institution_id": parse_object_id(institution_id, "institution_id"), "username": username})

    def update(self, user_id: str | ObjectId, changes: dict[str, Any]) -> dict[str, Any] | None:
        oid = parse_object_id(user_id, "user_id")
        self.collection.update_one({"_id": oid}, {"$set": {**changes, "updated_at": datetime.now(timezone.utc)}})
        return self.collection.find_one({"_id": oid})

    def delete_created(self, user_id: str | ObjectId) -> None:
        self.collection.delete_one({"_id": parse_object_id(user_id, "user_id"), "last_login_at": None})


class AuthSessionRepository:
    @property
    def collection(self):
        return mongo.require_database().auth_sessions

    def create(self, document: dict[str, Any]) -> dict[str, Any]:
        self.collection.insert_one(document)
        return document

    def find_by_id(self, session_id: ObjectId) -> dict[str, Any] | None:
        return self.collection.find_one({"_id": session_id})

    def claim_for_rotation(self, session_id: ObjectId, now: datetime) -> dict[str, Any] | None:
        return self.collection.find_one_and_update(
            {"_id": session_id, "revoked_at": None, "expires_at": {"$gt": now}},
            {"$set": {"revoked_at": now, "last_used_at": now}},
            return_document=ReturnDocument.BEFORE,
        )

    def revoke_session(self, session_id: ObjectId, now: datetime) -> None:
        self.collection.update_one({"_id": session_id, "revoked_at": None}, {"$set": {"revoked_at": now}})

    def revoke_family(self, family_id: str, now: datetime) -> None:
        self.collection.update_many({"token_family_id": family_id, "revoked_at": None}, {"$set": {"revoked_at": now}})

    def revoke_all(self, user_id: str | ObjectId, now: datetime) -> None:
        self.collection.update_many({"user_id": parse_object_id(user_id, "user_id"), "revoked_at": None}, {"$set": {"revoked_at": now}})

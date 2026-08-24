"""Explicitly bootstrap the first Institution and Admin in the NEW Python database."""

from __future__ import annotations

import getpass
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pymongo.errors import DuplicateKeyError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import get_settings  # noqa: E402
from app.core.errors import AppError  # noqa: E402
from app.core.security import PasswordService  # noqa: E402
from app.db.mongo import mongo  # noqa: E402
from app.modules.institutions.schemas import InstitutionCreate  # noqa: E402

KNOWN_LEGACY_DATABASE_NAMES = {"aiattendance", "attendance", "attendai", "attendance_system"}


def required(prompt: str) -> str:
    value = input(prompt).strip()
    if not value:
        raise ValueError("A required value was empty.")
    return value


def optional(prompt: str) -> str | None:
    return input(prompt).strip() or None


def main() -> int:
    settings = get_settings()
    database_name = settings.mongodb_database.strip()
    if not settings.mongodb_uri:
        print("Refusing to continue: MONGODB_URI is not configured.")
        return 2
    if database_name.casefold() in KNOWN_LEGACY_DATABASE_NAMES or not database_name.casefold().startswith("attendai_python"):
        print("Refusing to continue: target is not an explicitly named AttendAI-Python database.")
        return 2

    print(f"Target NEW Python database: {database_name}")
    try:
        institution = InstitutionCreate(
            name=required("Institution name: "),
            code=required("Institution code: "),
            country=required("Country: "),
            timezone=required("Timezone (for example Asia/Kolkata): "),
            city=optional("City (optional): "),
            state=optional("State (optional): "),
        )
        try:
            ZoneInfo(institution.timezone)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("Timezone is not a recognized IANA timezone.") from exc
        display_name = required("Admin display name: ")
        username = required("Admin username: ").casefold()
        email = required("Admin email: ").casefold()
        if "@" not in email:
            raise ValueError("Admin email is not valid.")
        password = getpass.getpass("Admin password (minimum 8 characters): ")
        if password != getpass.getpass("Confirm Admin password: "):
            raise ValueError("Passwords did not match.")
        password_hash = PasswordService().hash_password(password)
        del password
        if input(f"Type YES to create the Institution and Admin in '{database_name}': ").strip() != "YES":
            print("Confirmation not received. No changes made.")
            return 2

        mongo.configure()
        database = mongo.require_database()
        existing_institution = database.institutions.find_one({"code": institution.code})
        existing_user = database.users.find_one({"$or": [{"email": email}, {"username": username}]})
        if existing_institution and existing_user:
            if existing_user.get("institution_id") != existing_institution["_id"] or existing_user.get("role") != "admin":
                raise ValueError("Existing records conflict with this bootstrap request.")
            print("Institution and Admin are already bootstrapped. No changes made.")
            return 0
        if existing_user and not existing_institution:
            raise ValueError("Admin identifier already exists without the requested Institution.")

        now = datetime.now(timezone.utc)
        created_institution_id = None
        if existing_institution:
            institution_document = existing_institution
        else:
            institution_document = {**institution.model_dump(mode="python"), "created_at": now, "updated_at": now}
            created_institution_id = database.institutions.insert_one(institution_document).inserted_id
            institution_document["_id"] = created_institution_id
        if database.users.find_one({"institution_id": institution_document["_id"], "$or": [{"email": email}, {"username": username}]}):
            raise ValueError("Institution-scoped Admin email or username already exists.")
        try:
            admin_id = database.users.insert_one({
                "institution_id": institution_document["_id"], "email": email, "username": username,
                "password_hash": password_hash, "role": "admin", "status": "active", "display_name": display_name,
                "must_change_password": False, "last_login_at": None, "password_changed_at": now,
                "failed_login_attempts": 0, "locked_until": None, "token_version": 0,
                "created_at": now, "updated_at": now, "created_by": None,
                "faculty_id": None, "student_id": None,
            }).inserted_id
        except Exception:
            if created_institution_id and database.users.count_documents({"institution_id": created_institution_id}) == 0:
                database.institutions.delete_one({"_id": created_institution_id})
            raise
        print(f"Bootstrap complete. Institution ID: {institution_document['_id']}; Admin ID: {admin_id}")
        return 0
    except (ValueError, DuplicateKeyError, AppError) as exc:
        print(f"Bootstrap stopped safely: {exc}")
        return 2
    finally:
        mongo.close()


if __name__ == "__main__":
    raise SystemExit(main())

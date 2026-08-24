"""Manually create the first Admin in an explicitly confirmed Python database.

This script is never imported or run by application startup.
"""

from __future__ import annotations

import argparse
import getpass
import sys
from datetime import datetime, timezone
from pathlib import Path

from bson import ObjectId
from pymongo.errors import DuplicateKeyError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import get_settings  # noqa: E402
from app.core.security import PasswordService  # noqa: E402
from app.db.mongo import mongo  # noqa: E402
from app.db.object_id import parse_object_id  # noqa: E402
from app.modules.auth.repositories import UserRepository  # noqa: E402


def required(prompt: str) -> str:
    value = input(prompt).strip()
    if not value:
        raise ValueError("A required value was empty.")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a development Admin for the AI face attendance system.")
    parser.add_argument("--institution-id", required=True, help="Existing Institution ObjectId in the NEW Python database")
    args = parser.parse_args()
    settings = get_settings()
    if not settings.mongodb_uri:
        print("Refusing to continue: MONGODB_URI is not configured.")
        return 2
    if not settings.mongodb_database.casefold().startswith("attendai_python"):
        print("Refusing to continue: database name is not explicitly scoped to AttendAI-Python.")
        return 2
    confirmation = input(f"Type the exact database name '{settings.mongodb_database}' to confirm the write target: ").strip()
    if confirmation != settings.mongodb_database:
        print("Database confirmation did not match. No changes made.")
        return 2

    try:
        institution_id = parse_object_id(args.institution_id, "institution_id")
        display_name = required("Display name: ")
        username = required("Username: ").casefold()
        email = required("Email: ").casefold()
        if "@" not in email:
            raise ValueError("Email is not valid.")
        password = getpass.getpass("Password (minimum 8 characters): ")
        confirmation_password = getpass.getpass("Confirm password: ")
        if password != confirmation_password:
            raise ValueError("Passwords did not match.")

        mongo.configure()
        database = mongo.require_database()
        if database.institutions.find_one({"_id": institution_id}) is None:
            raise ValueError("Institution does not exist in the confirmed database.")
        users = UserRepository()
        if users.find_scoped_duplicate(institution_id, email, username):
            raise ValueError("An Admin with that institution-scoped email or username already exists.")
        now = datetime.now(timezone.utc)
        created = users.insert({
            "institution_id": ObjectId(institution_id),
            "email": email,
            "username": username,
            "password_hash": PasswordService().hash_password(password),
            "role": "admin",
            "status": "active",
            "display_name": display_name,
            "must_change_password": False,
            "last_login_at": None,
            "password_changed_at": now,
            "failed_login_attempts": 0,
            "locked_until": None,
            "token_version": 0,
            "created_at": now,
            "updated_at": now,
            "created_by": None,
            "faculty_id": None,
            "student_id": None,
        })
        print(f"Development Admin created safely with user ID {created['_id']}.")
        return 0
    except (ValueError, DuplicateKeyError) as exc:
        print(f"No Admin created: {exc}")
        return 2
    finally:
        mongo.close()


if __name__ == "__main__":
    raise SystemExit(main())

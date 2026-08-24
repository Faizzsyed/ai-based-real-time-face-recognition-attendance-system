"""Explicitly reset one User password in the configured NEW AttendAI Python database."""

from __future__ import annotations

import argparse
import getpass
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import get_settings  # noqa: E402
from app.core.errors import AppError  # noqa: E402
from app.core.security import PasswordService  # noqa: E402
from app.db.mongo import mongo  # noqa: E402


KNOWN_LEGACY_DATABASE_NAMES = {
    "aiattendance",
    "attendance",
    "attendai",
    "attendance_system",
}


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Safely reset an AttendAI Python User password by email or username."
    )
    parser.add_argument("identifier", help="Existing User email or username")
    return parser.parse_args()


def _safe_database_name() -> str:
    settings = get_settings()
    database_name = settings.mongodb_database.strip()
    if not settings.mongodb_uri:
        raise RuntimeError("MONGODB_URI is not configured. Refusing to continue.")
    if (
        not database_name
        or database_name.casefold() in KNOWN_LEGACY_DATABASE_NAMES
        or not database_name.casefold().startswith("attendai_python")
    ):
        raise RuntimeError(
            "Configured database is not an explicitly named AttendAI Python database. Refusing to continue."
        )
    return database_name


def main() -> int:
    args = _arguments()
    identifier = args.identifier.strip().casefold()
    if not identifier:
        print("Identifier cannot be empty.", file=sys.stderr)
        return 2

    try:
        database_name = _safe_database_name()
        mongo.configure()
        if mongo.status != "connected" or mongo.database_name != database_name:
            raise RuntimeError("Configured AttendAI Python database is unavailable.")
        database = mongo.require_database()

        matches = list(
            database.users.find(
                {"$or": [{"email": identifier}, {"username": identifier}]},
                {
                    "display_name": 1,
                    "username": 1,
                    "email": 1,
                    "role": 1,
                    "status": 1,
                    "institution_id": 1,
                },
            ).limit(2)
        )
        if not matches:
            print("No User matched that email or username.", file=sys.stderr)
            return 2
        if len(matches) != 1:
            print(
                "The identifier is ambiguous across Institutions. Refusing to reset any account.",
                file=sys.stderr,
            )
            return 2

        user = matches[0]
        institution = database.institutions.find_one(
            {"_id": user["institution_id"]}, {"name": 1}
        )
        if institution is None:
            raise RuntimeError("The matching User has no valid Institution. Refusing to continue.")

        print(f"Target database: {database_name}")
        print(f"Display name: {user.get('display_name', '—')}")
        print(f"Username: {user.get('username', '—')}")
        print(f"Email: {user.get('email', '—')}")
        print(f"Role: {user.get('role', '—')}")
        print(f"Status: {user.get('status', '—')}")
        print(f"Institution: {institution.get('name', '—')}")

        confirmation = input("Type YES to reset this User's password: ").strip()
        if confirmation != "YES":
            print("Confirmation not received. No changes made.")
            return 2

        new_password = getpass.getpass("New password: ")
        confirmation_password = getpass.getpass("Confirm new password: ")
        if new_password != confirmation_password:
            print("Passwords did not match. No changes made.", file=sys.stderr)
            return 2

        password_service = PasswordService()
        password_hash = password_service.hash_password(new_password)
        del new_password, confirmation_password

        now = datetime.now(timezone.utc)
        result = database.users.update_one(
            {"_id": user["_id"], "institution_id": user["institution_id"]},
            {
                "$set": {
                    "password_hash": password_hash,
                    "password_changed_at": now,
                    "failed_login_attempts": 0,
                    "locked_until": None,
                    "updated_at": now,
                },
                "$inc": {"token_version": 1},
            },
        )
        del password_hash
        if result.matched_count != 1 or result.modified_count != 1:
            raise RuntimeError("Password reset did not update exactly one User.")

        database.auth_sessions.update_many(
            {"user_id": user["_id"], "revoked_at": None},
            {"$set": {"revoked_at": now}},
        )
        print("Password reset complete. Existing access and refresh sessions were invalidated.")
        return 0
    except (AppError, RuntimeError) as exc:
        print(f"Password reset stopped safely: {exc}", file=sys.stderr)
        return 2
    except Exception:
        # Database-driver failures may contain connection details; keep CLI output generic.
        print("Password reset stopped safely because the database operation failed.", file=sys.stderr)
        return 2
    finally:
        mongo.close()


if __name__ == "__main__":
    raise SystemExit(main())

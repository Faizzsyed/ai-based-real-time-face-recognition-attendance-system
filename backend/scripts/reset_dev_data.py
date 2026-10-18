"""Explicit, interactive reset of only the local AttendAI development database."""
from datetime import datetime, timezone
from getpass import getpass
import ipaddress
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from bson import ObjectId
from pymongo import MongoClient
from pymongo.uri_parser import parse_uri
from app.core.config import get_settings
from app.core.security import PasswordService
from app.db.indexes import initialize_phase2_indexes
from app.modules.institutions.schemas import InstitutionCreate

EXPECTED_DATABASE = "attendai_python_dev"
CONFIRMATION = "RESET ATTENDAI DEV"


def verify_target(settings):
    if settings.app_env.casefold() != "development" or settings.mongodb_database != EXPECTED_DATABASE:
        raise ValueError("Refusing reset: development environment and exact AttendAI dev database are required.")
    if not settings.mongodb_uri:
        raise ValueError("Refusing reset: database is not configured.")
    try:
        nodes = parse_uri(settings.mongodb_uri)["nodelist"]
        for host, _ in nodes:
            if host == "localhost":
                continue
            if not ipaddress.ip_address(host).is_loopback:
                raise ValueError
    except Exception:
        raise ValueError("Refusing reset: target must be a positively identified local MongoDB instance.") from None


def reset_database(database, institution, admin, confirmation):
    if database.name != EXPECTED_DATABASE or confirmation != CONFIRMATION:
        raise ValueError("Reset confirmation or database did not match. No data changed.")
    collections = [name for name in database.list_collection_names() if not name.startswith("system.")]
    for name in collections:
        database[name].delete_many({})
    database.institutions.insert_one(institution)
    database.users.insert_one(admin)
    initialize_phase2_indexes(database)
    counts = {name: database[name].count_documents({}) for name in database.list_collection_names() if not name.startswith("system.")}
    if counts.get("institutions") != 1 or counts.get("users") != 1 or any(count for name, count in counts.items() if name not in {"institutions", "users"}):
        raise RuntimeError("Reset verification failed. Do not proceed with the demo until inspected locally.")
    return counts


def main():
    settings = get_settings()
    print("Environment:", settings.app_env)
    print("Database:", settings.mongodb_database)
    verify_target(settings)
    client = MongoClient(settings.mongodb_uri, serverSelectionTimeoutMS=3000, tz_aware=True)
    try:
        database = client[EXPECTED_DATABASE]
        client.admin.command("ping")
        print("Affected collections:", ", ".join(sorted(database.list_collection_names())))
        print("All application records and old sessions will be removed; one institution and one NEW Admin will remain.")
        username = input("Admin username: ").strip().casefold()
        email = input("Admin email: ").strip().casefold()
        if not re.fullmatch(r"[a-z0-9_.-]{2,80}", username) or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            raise ValueError("Use a valid username and email. No data changed.")
        password = getpass("Password: ")
        if password != getpass("Confirm password: "):
            raise ValueError("Passwords did not match. No data changed.")
        passwords = PasswordService()
        password_hash = passwords.hash_password(password)
        del password
        existing = database.institutions.find_one({}, sort=[("_id", 1)]) or {
            "name": "AttendAI Institution", "code": "ATTENDAI", "country": "India", "timezone": "Asia/Kolkata"
        }
        institution = InstitutionCreate.model_validate({key: value for key, value in existing.items() if key in InstitutionCreate.model_fields}).model_dump()
        now = datetime.now(timezone.utc)
        institution.update(_id=existing.get("_id", ObjectId()), status="active", created_at=now, updated_at=now)
        admin = dict(_id=ObjectId(), institution_id=institution["_id"], username=username, email=email,
                     display_name=username, role="admin", status="active", password_hash=password_hash,
                     must_change_password=False, token_version=0, failed_login_attempts=0, locked_until=None,
                     last_login_at=None, password_changed_at=now, created_at=now, updated_at=now,
                     faculty_id=None, student_id=None)
        confirmation = input(f"Type {CONFIRMATION} to delete the listed development data: ").strip()
        counts = reset_database(database, institution, admin, confirmation)
        # Verify the freshly entered credential locally; never serialize it.
        stored = database.users.find_one({"_id": admin["_id"], "role": "admin", "status": "active"})
        if not stored or stored["password_hash"] != password_hash:
            raise RuntimeError("Admin verification failed.")
        result = dict(environment=settings.app_env, database=EXPECTED_DATABASE, admin=True, counts=counts,
                      completed_at=now.isoformat(), old_tokens_invalidated=True)
        output = ROOT / "dist/dev-reset-result.json"
        output.parent.mkdir(exist_ok=True)
        output.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print("Reset verified: Institution=1, Admin=1, all other application collections=0.")
        print("Old identities and sessions removed. Sign in using the Admin credentials entered here.")
        print("Private local image files were not deleted; no unrelated database was modified.")
    finally:
        client.close()


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("Reset cancelled.")
        raise SystemExit(2)
    except Exception:
        # Driver/validation exception strings may contain sensitive configuration.
        print("Reset stopped. Verify the development target and inputs locally; no credentials are displayed.")
        raise SystemExit(2)

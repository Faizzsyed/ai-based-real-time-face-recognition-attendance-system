"""Interactively reset the three local development accounts without reseeding data."""

from datetime import datetime, timezone
from getpass import getpass
from pathlib import Path
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.security import PasswordService
from app.db.mongo import mongo

ACCOUNTS = (
    ("admin", "admin"),
    ("faculty", "faculty_demo"),
    ("student", "student_one"),
)


def _prompt_password(role: str, password_service: PasswordService) -> str:
    while True:
        password = getpass(f"New password for {role}: ")
        confirmation = getpass(f"Confirm password for {role}: ")
        if password != confirmation:
            print("Passwords did not match. Try again.")
            continue
        try:
            password_service.hash_password(password)
        except Exception as exc:
            print(f"Password rejected: {exc}")
            continue
        return password


def main() -> None:
    mongo.configure()
    db = mongo.require_database()
    if db.name != "attendai_python_dev":
        raise SystemExit(f"Refusing to modify unexpected database: {db.name}")

    accounts = []
    for role, username in ACCOUNTS:
        user = db.users.find_one({"username": username, "role": role})
        if user is None:
            raise SystemExit(f"Expected {role} development account was not found.")
        accounts.append((role, user))

    passwords = PasswordService()
    updates = [(user, _prompt_password(role, passwords)) for role, user in accounts]
    now = datetime.now(timezone.utc)
    for user, password in updates:
        db.users.update_one(
            {"_id": user["_id"]},
            {
                "$set": {
                    "password_hash": passwords.hash_password(password),
                    "failed_login_attempts": 0,
                    "locked_until": None,
                    "updated_at": now,
                },
                "$inc": {"token_version": 1},
            },
        )
        db.auth_sessions.update_many(
            {"user_id": user["_id"], "revoked_at": None},
            {"$set": {"revoked_at": now}},
        )

    print("Development account passwords were reset; no password values were displayed.")


if __name__ == "__main__":
    main()

"""Print a safe, read-only summary of the local AttendAI development database."""

from pathlib import Path
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

import json
from pymongo import MongoClient
from app.core.config import get_settings
from scripts.reset_dev_data import verify_target


def main() -> None:
    settings = get_settings()
    verify_target(settings)
    # Do not call mongo.configure(): it initializes indexes. This audit only reads.
    with MongoClient(settings.mongodb_uri, serverSelectionTimeoutMS=3000, tz_aware=True) as client:
        db = client["attendai_python_dev"]
        counts = {name: db[name].count_documents({}) for name in sorted(db.list_collection_names())
                  if not name.startswith("system.")}
        admins = []
        for user in db.users.find({"role": "admin"}):
            institution = db.institutions.find_one({"_id": user.get("institution_id")})
            admins.append({"username": user.get("username"), "role": user.get("role"),
                           "status": user.get("status"), "institution_exists": bool(institution),
                           "argon2id": str(user.get("password_hash", "")).startswith("$argon2id$"),
                           "token_version": user.get("token_version"),
                           "failed_login_attempts": user.get("failed_login_attempts"),
                           "locked": user.get("locked_until") is not None,
                           "has_logged_in": user.get("last_login_at") is not None})
        print(json.dumps({"database": db.name, "environment": settings.app_env,
                          "counts": counts, "admins": admins}, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit("Read-only audit failed. Check local database availability and development settings; credentials are not displayed.") from None

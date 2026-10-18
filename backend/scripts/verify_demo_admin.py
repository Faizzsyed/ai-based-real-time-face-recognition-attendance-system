"""Human-only credential check against the LAN API; output contains no secrets."""
import argparse
from datetime import datetime, timezone
from getpass import getpass
import json
from pathlib import Path
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

import httpx
from pymongo import MongoClient
from app.core.config import get_settings
from app.core.security import PasswordService
from scripts.reset_dev_data import verify_target


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-url", required=True)
    parser.add_argument("--reset-password", action="store_true")
    args = parser.parse_args()
    settings = get_settings()
    verify_target(settings)
    result_path = ROOT / "dist/admin-login-result.json"
    marker = "AttendAI local verification " + str(uuid4())
    result = {"success": False, "database": settings.mongodb_database,
              "api_url": args.api_url, "checked_at": datetime.now(timezone.utc).isoformat()}
    with MongoClient(settings.mongodb_uri, serverSelectionTimeoutMS=3000) as mongo:
        db = mongo[settings.mongodb_database]
        admin = db.users.find_one({"role": "admin", "status": "active"})
        if not admin or admin.get("username") != "demo.admin" or db.users.count_documents({}) != 1:
            raise ValueError("Expected exactly one active development Admin.")
        print("Verify Admin:", admin["username"])
        if args.reset_password:
            print("Only demo.admin's password will change. All institution and application records are preserved.")
            while True:
                password = getpass("New Admin password (at least 8 characters): ")
                confirmation = getpass("Confirm new Admin password: ")
                if password != confirmation:
                    print("The two entries did not match. Nothing changed. Please try again.");continue
                if len(password) < PasswordService.minimum_length:
                    print("Use at least 8 characters. Nothing changed. Please try again.");continue
                del confirmation
                break
            password_hash = PasswordService().hash_password(password)
            now = datetime.now(timezone.utc)
            changed = db.users.update_one({"_id": admin["_id"], "role": "admin", "username": "demo.admin"}, {
                "$set": {"password_hash": password_hash, "failed_login_attempts": 0, "locked_until": None,
                         "password_changed_at": now, "updated_at": now, "must_change_password": False},
                "$inc": {"token_version": 1}})
            if changed.matched_count != 1:
                raise ValueError("Admin account changed; no login attempted.")
            db.auth_sessions.update_many({"user_id": admin["_id"], "revoked_at": None}, {"$set": {"revoked_at": now}})
            result["admin_password_reset"] = True
            print("Admin password updated securely. Verifying the LAN login now...")
        else:
            print("Enter the password you chose during reset. It will not be displayed or saved.")
            password = getpass("Admin password: ")
        try:
            with httpx.Client(base_url=args.api_url, timeout=20, trust_env=False) as client:
                response = client.post("/api/v1/auth/login", json={
                    "identifier": admin["username"], "password": password, "device_name": marker})
                del password
                if response.status_code != 200:
                    print("LOGIN: FAILED (HTTP", response.status_code, ")")
                    print("Use the password chosen for demo.admin during the development reset.")
                    result["login_http_status"] = response.status_code
                    raise ValueError("Login failed. Check your password and account locally.")
                pair = response.json()["data"]
                me = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer " + pair["accessToken"]})
                if me.status_code != 200 or me.json()["data"]["user"]["role"] != "admin":
                    raise ValueError("Admin identity verification failed.")
                rotated = client.post("/api/v1/auth/refresh", json={"refresh_token": pair["refreshToken"], "device_name": marker})
                if rotated.status_code != 200:
                    raise ValueError("Refresh verification failed.")
                fresh = rotated.json()["data"]
                logout = client.post("/api/v1/auth/logout", json={"refresh_token": fresh["refreshToken"]},
                                     headers={"Authorization": "Bearer " + fresh["accessToken"]})
                if logout.status_code != 200:
                    raise ValueError("Logout verification failed.")
                result.update(success=True, admin=True, login=True, auth_me=True, refresh=True, logout=True)
                print("LAN ADMIN LOGIN / AUTH ME / REFRESH / LOGOUT: PASS")
        finally:
            # Remove only this verifier's temporary sessions, preserving all other data.
            db.auth_sessions.delete_many({"user_id": admin["_id"], "device_name": marker})
            result["temporary_sessions_removed"] = True
            result_path.parent.mkdir(exist_ok=True)
            result_path.write_text(json.dumps(result, indent=2), encoding="utf-8")


if __name__ == "__main__":
    try:
        main()
    except (Exception, KeyboardInterrupt):
        print("Verification stopped. No credentials or tokens are displayed. Check the password and LAN backend locally.")
        raise SystemExit(2) from None

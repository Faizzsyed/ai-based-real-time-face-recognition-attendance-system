"""Authentication orchestration with account enforcement and refresh rotation."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from bson import ObjectId

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.core.security import PasswordService, TokenService
from app.db.object_id import parse_object_id
from app.modules.auth.repositories import AuthSessionRepository, UserRepository
from app.modules.auth.schemas import safe_user

logger = logging.getLogger(__name__)
INVALID_CREDENTIALS = "Invalid username/email or password."
VALID_ROLES = {"admin", "faculty", "student"}


class AuthService:
    def __init__(self, users=None, sessions=None, settings: Settings | None = None, passwords=None, tokens=None) -> None:
        self.settings = settings or get_settings()
        self.users = users or UserRepository()
        self.sessions = sessions or AuthSessionRepository()
        self.passwords = passwords or PasswordService()
        self.tokens = tokens or TokenService(
            self.settings.jwt_secret,
            self.settings.jwt_algorithm,
            self.settings.jwt_access_token_minutes,
            self.settings.jwt_refresh_token_days,
        )

    def login(self, identifier: str, password: str, *, user_agent: str | None = None, device_name: str | None = None) -> dict[str, Any]:
        logger.info("Authentication login attempt identifier_present=%s",bool(identifier))
        self.tokens.ensure_configured()
        now = datetime.now(timezone.utc)
        user = self.users.find_by_identifier(identifier.strip().casefold())
        if user is None:
            self.passwords.verify_dummy(password)
            logger.warning("Authentication login failure")
            raise AppError("AUTH_INVALID_CREDENTIALS", INVALID_CREDENTIALS, 401)
        if not self.passwords.verify_password(password, user["password_hash"]):
            active_lock = user.get("locked_until") and user["locked_until"] > now
            attempts = int(user.get("failed_login_attempts", 0)) + 1 if not user.get("locked_until") else 1
            locked_until = None
            if user.get("status") == "active" and not active_lock:
                if attempts >= self.settings.auth_max_failed_attempts:
                    locked_until = now + timedelta(minutes=self.settings.auth_lockout_minutes)
                    logger.warning("Authentication account lockout user_id=%s", user["_id"])
                self.users.record_failed_login(user["_id"], attempts, locked_until)
            raise AppError("AUTH_INVALID_CREDENTIALS", INVALID_CREDENTIALS, 401)
        if user.get("locked_until") and user["locked_until"] > now:
            raise AppError("AUTH_ACCOUNT_LOCKED", "The account is temporarily locked.", 423)
        if user.get("status") != "active":
            raise AppError("AUTH_ACCOUNT_INACTIVE", "The account is not active.", 403)
        self.users.record_login(user["_id"], now)
        user = {**user, "failed_login_attempts": 0, "locked_until": None, "last_login_at": now}
        logger.info("Authentication login success user_id=%s", user["_id"])
        return self._issue_pair(user, user_agent=user_agent, device_name=device_name)

    def _issue_pair(self, user: dict[str, Any], *, family_id: str | None = None, user_agent: str | None = None, device_name: str | None = None) -> dict[str, Any]:
        access_token, expires_in = self.tokens.create_access_token(user)
        session_id, refresh_token, token_hash, expires_at = self.tokens.issue_refresh_token()
        now = datetime.now(timezone.utc)
        self.sessions.create({
            "_id": session_id,
            "user_id": parse_object_id(user["_id"], "user_id"),
            "institution_id": parse_object_id(user["institution_id"], "institution_id"),
            "refresh_token_hash": token_hash,
            "token_family_id": family_id or str(uuid4()),
            "created_at": now,
            "expires_at": expires_at,
            "last_used_at": None,
            "revoked_at": None,
            "user_agent": user_agent,
            "device_name": device_name,
        })
        return {"accessToken": access_token, "refreshToken": refresh_token, "tokenType": "bearer", "expiresIn": expires_in, "user": safe_user(user)}

    def refresh(self, refresh_token: str, *, user_agent: str | None = None, device_name: str | None = None) -> dict[str, Any]:
        self.tokens.ensure_configured()
        session_id = self.tokens.refresh_session_id(refresh_token)
        session = self.sessions.find_by_id(session_id)
        if session is None or not self.tokens.refresh_hash_matches(refresh_token, session.get("refresh_token_hash", "")):
            raise AppError("AUTH_REFRESH_INVALID", "The refresh token is invalid.", 401)
        now = datetime.now(timezone.utc)
        if session.get("revoked_at") is not None:
            self.sessions.revoke_family(session["token_family_id"], now)
            logger.warning("Authentication refresh-token reuse family_id=%s", session["token_family_id"])
            raise AppError("AUTH_REFRESH_INVALID", "The refresh token is invalid.", 401)
        if session["expires_at"] <= now:
            raise AppError("AUTH_REFRESH_INVALID", "The refresh token is invalid.", 401)
        user = self.users.find_by_id(session["user_id"])
        self._enforce_active_user(user)
        if str(user["institution_id"]) != str(session["institution_id"]):
            raise AppError("AUTH_REFRESH_INVALID", "The refresh token is invalid.", 401)
        if self.sessions.claim_for_rotation(session_id, now) is None:
            self.sessions.revoke_family(session["token_family_id"], now)
            raise AppError("AUTH_REFRESH_INVALID", "The refresh token is invalid.", 401)
        logger.info("Authentication refresh user_id=%s", user["_id"])
        return self._issue_pair(user, family_id=session["token_family_id"], user_agent=user_agent or session.get("user_agent"), device_name=device_name or session.get("device_name"))

    def authenticate_access(self, access_token: str) -> dict[str, Any]:
        claims = self.tokens.decode_access_token(access_token)
        try:
            parse_object_id(claims["sub"], "user_id")
            parse_object_id(claims["institution_id"], "institution_id")
        except AppError as exc:
            raise AppError("AUTH_TOKEN_INVALID", "The access token is invalid.", 401) from exc
        user = self.users.find_by_id(claims["sub"])
        self._enforce_active_user(user)
        if (
            str(user["institution_id"]) != str(claims["institution_id"])
            or user["role"] != claims["role"]
            or int(user.get("token_version", 0)) != int(claims["token_version"])
        ):
            raise AppError("AUTH_TOKEN_INVALID", "The access token is invalid.", 401)
        return user

    @staticmethod
    def _enforce_active_user(user: dict[str, Any] | None) -> None:
        if user is None:
            raise AppError("AUTH_TOKEN_INVALID", "The access token is invalid.", 401)
        if user.get("status") != "active":
            raise AppError("AUTH_ACCOUNT_INACTIVE", "The account is not active.", 403)
        if user.get("role") not in VALID_ROLES:
            raise AppError("AUTH_TOKEN_INVALID", "The access token is invalid.", 401)

    def logout(self, refresh_token: str, user_id: str | ObjectId) -> None:
        try:
            session_id = self.tokens.refresh_session_id(refresh_token)
            session = self.sessions.find_by_id(session_id)
        except AppError:
            return
        if session and str(session["user_id"]) == str(user_id) and self.tokens.refresh_hash_matches(refresh_token, session.get("refresh_token_hash", "")):
            self.sessions.revoke_session(session_id, datetime.now(timezone.utc))
            logger.info("Authentication logout user_id=%s", user_id)

    def logout_all(self, user_id: str | ObjectId) -> None:
        now = datetime.now(timezone.utc)
        self.sessions.revoke_all(user_id, now)
        self.users.increment_token_version(user_id)
        logger.info("Authentication logout-all user_id=%s", user_id)

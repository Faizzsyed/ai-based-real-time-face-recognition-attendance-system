"""Password, JWT access-token, and opaque refresh-token primitives."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from bson import ObjectId

from app.core.errors import AppError


class PasswordService:
    minimum_length = 8
    _dummy_hash: str | None = None

    def __init__(self) -> None:
        self._hasher = PasswordHasher()
        if PasswordService._dummy_hash is None:
            PasswordService._dummy_hash = self._hasher.hash(secrets.token_urlsafe(32))

    def verify_dummy(self, password: str) -> None:
        """Spend a normal Argon2 verification when no account matched."""
        self.verify_password(password, PasswordService._dummy_hash or "")

    def hash_password(self, password: str) -> str:
        if len(password) < self.minimum_length:
            raise AppError(
                "PASSWORD_POLICY_FAILED",
                f"Password must be at least {self.minimum_length} characters.",
                422,
            )
        return self._hasher.hash(password)

    def verify_password(self, password: str, password_hash: str) -> bool:
        try:
            return self._hasher.verify(password_hash, password)
        except (VerifyMismatchError, InvalidHashError):
            return False


class TokenService:
    def __init__(
        self,
        secret: str,
        algorithm: str = "HS256",
        access_minutes: int = 15,
        refresh_days: int = 7,
    ) -> None:
        self.secret = secret
        self.algorithm = algorithm
        self.access_minutes = access_minutes
        self.refresh_days = refresh_days

    def ensure_configured(self) -> None:
        if len(self.secret.encode("utf-8")) < 32 or self.algorithm not in {"HS256", "HS384", "HS512"}:
            raise AppError(
                "AUTH_NOT_CONFIGURED",
                "Authentication is not configured for this environment.",
                503,
            )

    def create_access_token(self, user: dict[str, Any], now: datetime | None = None) -> tuple[str, int]:
        self.ensure_configured()
        issued_at = now or datetime.now(timezone.utc)
        expires_at = issued_at + timedelta(minutes=self.access_minutes)
        claims = {
            "sub": str(user["_id"]),
            "institution_id": str(user["institution_id"]),
            "role": user["role"],
            "token_type": "access",
            "token_version": user.get("token_version", 0),
            "iat": issued_at,
            "exp": expires_at,
            "jti": str(uuid4()),
        }
        return jwt.encode(claims, self.secret, algorithm=self.algorithm), int((expires_at - issued_at).total_seconds())

    def decode_access_token(self, token: str) -> dict[str, Any]:
        self.ensure_configured()
        try:
            claims = jwt.decode(token, self.secret, algorithms=[self.algorithm])
        except jwt.ExpiredSignatureError as exc:
            raise AppError("AUTH_TOKEN_EXPIRED", "The access token has expired.", 401) from exc
        except jwt.PyJWTError as exc:
            raise AppError("AUTH_TOKEN_INVALID", "The access token is invalid.", 401) from exc
        required = {"sub", "institution_id", "role", "token_type", "token_version", "iat", "exp", "jti"}
        if not required.issubset(claims) or claims.get("token_type") != "access":
            raise AppError("AUTH_TOKEN_INVALID", "The access token is invalid.", 401)
        return claims

    def issue_refresh_token(self, session_id: ObjectId | None = None) -> tuple[ObjectId, str, str, datetime]:
        session_id = session_id or ObjectId()
        raw_token = f"{session_id}.{secrets.token_urlsafe(48)}"
        expires_at = datetime.now(timezone.utc) + timedelta(days=self.refresh_days)
        return session_id, raw_token, self.hash_refresh_token(raw_token), expires_at

    @staticmethod
    def hash_refresh_token(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def refresh_session_id(token: str) -> ObjectId:
        try:
            value, secret = token.split(".", 1)
            if not secret:
                raise ValueError
            return ObjectId(value)
        except (ValueError, TypeError) as exc:
            raise AppError("AUTH_REFRESH_INVALID", "The refresh token is invalid.", 401) from exc

    def refresh_hash_matches(self, token: str, expected_hash: str) -> bool:
        return hmac.compare_digest(self.hash_refresh_token(token), expected_hash)

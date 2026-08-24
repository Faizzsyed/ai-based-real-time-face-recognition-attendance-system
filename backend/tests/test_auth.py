"""Phase 3 authentication and RBAC tests with no real database dependency."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.core.security import PasswordService, TokenService
from app.main import app
from app.modules.auth.dependencies import get_auth_service
from app.modules.auth.schemas import safe_user
from app.modules.auth.service import AuthService, INVALID_CREDENTIALS


class MemoryUsers:
    def __init__(self, users: list[dict[str, Any]]) -> None:
        self.users = users

    def find_by_identifier(self, identifier: str):
        matches = [u for u in self.users if identifier in {u["email"], u["username"]}]
        return matches[0] if len(matches) == 1 else None

    def find_by_id(self, user_id):
        return next((u for u in self.users if str(u["_id"]) == str(user_id)), None)

    def record_failed_login(self, user_id, attempts, locked_until):
        user = self.find_by_id(user_id)
        user["failed_login_attempts"] = attempts
        user["locked_until"] = locked_until

    def record_login(self, user_id, at):
        user = self.find_by_id(user_id)
        user.update(failed_login_attempts=0, locked_until=None, last_login_at=at)

    def increment_token_version(self, user_id):
        user = self.find_by_id(user_id)
        user["token_version"] += 1


class MemorySessions:
    def __init__(self) -> None:
        self.sessions: dict[ObjectId, dict[str, Any]] = {}

    def create(self, document):
        self.sessions[document["_id"]] = document
        return document

    def find_by_id(self, session_id):
        return self.sessions.get(session_id)

    def claim_for_rotation(self, session_id, now):
        session = self.sessions.get(session_id)
        if not session or session["revoked_at"] is not None or session["expires_at"] <= now:
            return None
        previous = deepcopy(session)
        session["revoked_at"] = now
        session["last_used_at"] = now
        return previous

    def revoke_session(self, session_id, now):
        if session_id in self.sessions and self.sessions[session_id]["revoked_at"] is None:
            self.sessions[session_id]["revoked_at"] = now

    def revoke_family(self, family_id, now):
        for session in self.sessions.values():
            if session["token_family_id"] == family_id and session["revoked_at"] is None:
                session["revoked_at"] = now

    def revoke_all(self, user_id, now):
        for session in self.sessions.values():
            if str(session["user_id"]) == str(user_id) and session["revoked_at"] is None:
                session["revoked_at"] = now


@pytest.fixture
def auth_domain():
    password_service = PasswordService()
    institution_id = ObjectId()
    password_hash = password_service.hash_password("Correct123")
    users = [
        {
            "_id": ObjectId(), "institution_id": institution_id, "email": f"{role}@example.edu",
            "username": role, "password_hash": password_hash, "role": role, "status": "active",
            "display_name": role.title(), "must_change_password": False, "failed_login_attempts": 0,
            "locked_until": None, "token_version": 0, "faculty_id": None, "student_id": None,
        }
        for role in ("admin", "faculty", "student")
    ]
    settings = Settings(
        app_env="test", jwt_secret="test-only-secret-with-sufficient-entropy",
        jwt_access_token_minutes=15, jwt_refresh_token_days=7,
        auth_max_failed_attempts=3, auth_lockout_minutes=15,
    )
    user_repo = MemoryUsers(users)
    session_repo = MemorySessions()
    service = AuthService(user_repo, session_repo, settings, password_service)
    return service, user_repo, session_repo, users


def test_password_hashing_uses_argon2id_and_not_plaintext():
    hashed = PasswordService().hash_password("LongEnough1")
    assert hashed.startswith("$argon2id$") and "LongEnough1" not in hashed


def test_correct_and_wrong_password_verification():
    passwords = PasswordService()
    hashed = passwords.hash_password("LongEnough1")
    assert passwords.verify_password("LongEnough1", hashed)
    assert not passwords.verify_password("WrongValue", hashed)


def test_short_password_policy_is_rejected():
    with pytest.raises(AppError) as exc:
        PasswordService().hash_password("short")
    assert exc.value.code == "PASSWORD_POLICY_FAILED"


def test_password_hash_never_serialized(auth_domain):
    user = safe_user(auth_domain[3][0])
    assert "password_hash" not in user and "passwordHash" not in user


def test_login_success_and_normalized_identifier(auth_domain):
    service, _, sessions, _ = auth_domain
    result = service.login(" ADMIN@EXAMPLE.EDU ", "Correct123")
    assert result["user"]["role"] == "admin"
    assert result["tokenType"] == "bearer" and len(sessions.sessions) == 1


def test_invalid_identifier_is_generic(auth_domain):
    with pytest.raises(AppError) as exc:
        auth_domain[0].login("missing", "anything")
    assert exc.value.code == "AUTH_INVALID_CREDENTIALS" and exc.value.message == INVALID_CREDENTIALS


def test_wrong_password_increments_counter_without_leaking(auth_domain):
    service, _, _, users = auth_domain
    with pytest.raises(AppError) as exc:
        service.login("admin", "Incorrect")
    assert exc.value.message == INVALID_CREDENTIALS and users[0]["failed_login_attempts"] == 1


@pytest.mark.parametrize("status", ["inactive", "suspended"])
def test_non_active_accounts_are_rejected(auth_domain, status):
    service, _, _, users = auth_domain
    users[0]["status"] = status
    with pytest.raises(AppError) as exc:
        service.login("admin", "Correct123")
    assert exc.value.code == "AUTH_ACCOUNT_INACTIVE"


def test_account_lockout_and_locked_login(auth_domain):
    service, _, _, users = auth_domain
    for _ in range(3):
        with pytest.raises(AppError):
            service.login("admin", "Incorrect")
    assert users[0]["locked_until"] > datetime.now(timezone.utc)
    with pytest.raises(AppError) as exc:
        service.login("admin", "Correct123")
    assert exc.value.code == "AUTH_ACCOUNT_LOCKED"


def test_access_token_has_minimal_required_claims(auth_domain):
    service, _, _, users = auth_domain
    token, expires = service.tokens.create_access_token(users[0])
    claims = service.tokens.decode_access_token(token)
    assert {"sub", "institution_id", "role", "token_type", "token_version", "iat", "exp", "jti"} <= claims.keys()
    assert "email" not in claims and expires == 900


def test_expired_access_token_is_distinct(auth_domain):
    service, _, _, users = auth_domain
    old = datetime.now(timezone.utc) - timedelta(minutes=16)
    token, _ = service.tokens.create_access_token(users[0], now=old)
    with pytest.raises(AppError) as exc:
        service.tokens.decode_access_token(token)
    assert exc.value.code == "AUTH_TOKEN_EXPIRED"


def test_invalid_signature_is_rejected(auth_domain):
    service, _, _, users = auth_domain
    other = TokenService("different-test-secret-with-32-bytes")
    token, _ = other.create_access_token(users[0])
    with pytest.raises(AppError) as exc:
        service.tokens.decode_access_token(token)
    assert exc.value.code == "AUTH_TOKEN_INVALID"


def test_refresh_token_is_hashed_at_rest(auth_domain):
    service, _, sessions, _ = auth_domain
    result = service.login("admin", "Correct123")
    stored = next(iter(sessions.sessions.values()))
    assert stored["refresh_token_hash"] != result["refreshToken"]
    assert service.tokens.refresh_hash_matches(result["refreshToken"], stored["refresh_token_hash"])


def test_refresh_rotation_revokes_old_and_issues_new(auth_domain):
    service, _, sessions, _ = auth_domain
    first = service.login("faculty", "Correct123")
    old_id = service.tokens.refresh_session_id(first["refreshToken"])
    second = service.refresh(first["refreshToken"])
    assert second["refreshToken"] != first["refreshToken"]
    assert sessions.sessions[old_id]["revoked_at"] is not None
    assert len({s["token_family_id"] for s in sessions.sessions.values()}) == 1


def test_refresh_reuse_revokes_token_family(auth_domain):
    service, _, sessions, _ = auth_domain
    first = service.login("student", "Correct123")
    second = service.refresh(first["refreshToken"])
    with pytest.raises(AppError) as exc:
        service.refresh(first["refreshToken"])
    assert exc.value.code == "AUTH_REFRESH_INVALID"
    new_id = service.tokens.refresh_session_id(second["refreshToken"])
    assert sessions.sessions[new_id]["revoked_at"] is not None


def test_revoked_refresh_is_rejected(auth_domain):
    service, _, sessions, _ = auth_domain
    first = service.login("admin", "Correct123")
    session_id = service.tokens.refresh_session_id(first["refreshToken"])
    sessions.revoke_session(session_id, datetime.now(timezone.utc))
    with pytest.raises(AppError) as exc:
        service.refresh(first["refreshToken"])
    assert exc.value.code == "AUTH_REFRESH_INVALID"


def test_logout_revokes_current_session(auth_domain):
    service, _, sessions, users = auth_domain
    result = service.login("admin", "Correct123")
    service.logout(result["refreshToken"], users[0]["_id"])
    session_id = service.tokens.refresh_session_id(result["refreshToken"])
    assert sessions.sessions[session_id]["revoked_at"] is not None


def test_logout_all_revokes_sessions_and_access_tokens(auth_domain):
    service, _, sessions, users = auth_domain
    result = service.login("admin", "Correct123")
    service.login("admin", "Correct123")
    service.logout_all(users[0]["_id"])
    assert all(session["revoked_at"] is not None for session in sessions.sessions.values())
    with pytest.raises(AppError) as exc:
        service.authenticate_access(result["accessToken"])
    assert exc.value.code == "AUTH_TOKEN_INVALID"


def test_token_version_invalidation(auth_domain):
    service, _, _, users = auth_domain
    token = service.login("faculty", "Correct123")["accessToken"]
    users[1]["token_version"] += 1
    with pytest.raises(AppError) as exc:
        service.authenticate_access(token)
    assert exc.value.code == "AUTH_TOKEN_INVALID"


def test_malformed_object_id_claim_is_rejected(auth_domain):
    service = auth_domain[0]
    now = datetime.now(timezone.utc)
    token = jwt.encode({"sub": "bad", "institution_id": str(ObjectId()), "role": "admin", "token_type": "access", "token_version": 0, "iat": now, "exp": now + timedelta(minutes=5), "jti": "x"}, service.tokens.secret, algorithm="HS256")
    with pytest.raises(AppError) as exc:
        service.authenticate_access(token)
    assert exc.value.code == "AUTH_TOKEN_INVALID"


def test_missing_jwt_secret_fails_safely(auth_domain):
    service, users, sessions, _ = auth_domain
    unconfigured = AuthService(users, sessions, Settings(jwt_secret=""))
    with pytest.raises(AppError) as exc:
        unconfigured.login("admin", "Correct123")
    assert exc.value.code == "AUTH_NOT_CONFIGURED"


def _client_for(service: AuthService):
    app.dependency_overrides[get_auth_service] = lambda: service
    return TestClient(app)


def test_me_returns_safe_user(auth_domain):
    service = auth_domain[0]
    token = service.login("admin", "Correct123")["accessToken"]
    try:
        with _client_for(service) as client:
            response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200 and response.json()["data"]["user"]["role"] == "admin"
        assert "password_hash" not in response.text.casefold() and "passwordHash" not in response.text
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize("role", ["admin", "faculty", "student"])
def test_role_route_allows_matching_role(auth_domain, role):
    service = auth_domain[0]
    token = service.login(role, "Correct123")["accessToken"]
    try:
        with _client_for(service) as client:
            response = client.get(f"/api/v1/auth/test/{role}", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
    finally:
        app.dependency_overrides.clear()


def test_cross_role_access_is_forbidden(auth_domain):
    service = auth_domain[0]
    token = service.login("student", "Correct123")["accessToken"]
    try:
        with _client_for(service) as client:
            response = client.get("/api/v1/auth/test/admin", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 403 and response.json()["error"]["code"] == "FORBIDDEN"
    finally:
        app.dependency_overrides.clear()


def test_protected_route_without_token_returns_401(auth_domain):
    try:
        with _client_for(auth_domain[0]) as client:
            response = client.get("/api/v1/auth/test/authenticated")
        assert response.status_code == 401 and response.json()["error"]["code"] == "AUTH_REQUIRED"
    finally:
        app.dependency_overrides.clear()


def test_login_without_database_returns_safe_configuration_error(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "test-environment-secret-only-32-bytes")
    monkeypatch.setenv("MONGODB_URI", "")
    get_settings.cache_clear()
    try:
        with TestClient(app) as client:
            response = client.post("/api/v1/auth/login", json={"identifier": "admin", "password": "Correct123"})
        assert response.status_code == 503 and response.json()["error"]["code"] == "DATABASE_UNAVAILABLE"
    finally:
        get_settings.cache_clear()

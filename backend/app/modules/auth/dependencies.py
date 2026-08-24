"""Reusable access-token, role, and institution authorization dependencies."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.errors import AppError
from app.modules.auth.service import AuthService
import logging
from app.core.logging import safe_log
logger=logging.getLogger("RBAC")

bearer = HTTPBearer(auto_error=False)


def get_auth_service() -> AuthService:
    return AuthService()


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> dict[str, Any]:
    if credentials is None or credentials.scheme.casefold() != "bearer":
        raise AppError("AUTH_REQUIRED", "Authentication is required.", 401)
    return service.authenticate_access(credentials.credentials)


require_authenticated_user = get_current_user


def require_roles(*roles: str) -> Callable:
    def dependency(user: Annotated[dict[str, Any], Depends(get_current_user)]) -> dict[str, Any]:
        if user.get("role") not in roles:
            safe_log(logger,logging.WARNING,"authorization denied",user_id=str(user.get("_id")),role=user.get("role"),required_roles=roles)
            raise AppError("FORBIDDEN", "You do not have permission to perform this action.", 403)
        safe_log(logger,logging.INFO,"authorization allowed",user_id=str(user.get("_id")),role=user.get("role"),required_roles=roles)
        return user
    return dependency


def require_role(role: str) -> Callable:
    return require_roles(role)


def require_institution_access(institution_id: str, user: Annotated[dict[str, Any], Depends(get_current_user)]) -> dict[str, Any]:
    if str(user["institution_id"]) != institution_id:
        raise AppError("FORBIDDEN", "You do not have permission to access this institution.", 403)
    return user

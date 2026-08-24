"""Authentication lifecycle and development-only RBAC verification routes."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.core.config import get_settings
from app.core.errors import AppError
from app.modules.auth.dependencies import get_auth_service, get_current_user, require_role
from app.modules.auth.schemas import LoginRequest, LogoutRequest, RefreshRequest, safe_user
from app.modules.auth.service import AuthService

router = APIRouter(prefix="/auth", tags=["authentication"])
verification_router = APIRouter()


@router.post("/login")
def login(payload: LoginRequest, service: Annotated[AuthService, Depends(get_auth_service)]) -> dict[str, Any]:
    return {"success": True, "data": service.login(payload.identifier, payload.password, user_agent=payload.user_agent, device_name=payload.device_name)}


@router.post("/refresh")
def refresh(payload: RefreshRequest, service: Annotated[AuthService, Depends(get_auth_service)]) -> dict[str, Any]:
    return {"success": True, "data": service.refresh(payload.refresh_token, user_agent=payload.user_agent, device_name=payload.device_name)}


@router.post("/logout")
def logout(payload: LogoutRequest, user: Annotated[dict[str, Any], Depends(get_current_user)], service: Annotated[AuthService, Depends(get_auth_service)]) -> dict[str, Any]:
    service.logout(payload.refresh_token, user["_id"])
    return {"success": True}


@router.post("/logout-all")
def logout_all(user: Annotated[dict[str, Any], Depends(get_current_user)], service: Annotated[AuthService, Depends(get_auth_service)]) -> dict[str, Any]:
    service.logout_all(user["_id"])
    return {"success": True}


@router.get("/me")
def me(user: Annotated[dict[str, Any], Depends(get_current_user)]) -> dict[str, Any]:
    return {"success": True, "data": {"user": safe_user(user)}}


def _development_only() -> None:
    if get_settings().app_env.casefold() not in {"development", "test"}:
        raise AppError("RESOURCE_NOT_FOUND", "Resource was not found.", 404)


@verification_router.get("/test/authenticated", dependencies=[Depends(_development_only)])
def test_authenticated(user: Annotated[dict[str, Any], Depends(get_current_user)]) -> dict[str, Any]:
    return {"success": True, "role": user["role"]}


def _role_test(role: str, user: dict[str, Any]) -> dict[str, Any]:
    return {"success": True, "role": role, "userId": str(user["_id"])}


@verification_router.get("/test/admin", dependencies=[Depends(_development_only)])
def test_admin(user: Annotated[dict[str, Any], Depends(require_role("admin"))]) -> dict[str, Any]:
    return _role_test("admin", user)


@verification_router.get("/test/faculty", dependencies=[Depends(_development_only)])
def test_faculty(user: Annotated[dict[str, Any], Depends(require_role("faculty"))]) -> dict[str, Any]:
    return _role_test("faculty", user)


@verification_router.get("/test/student", dependencies=[Depends(_development_only)])
def test_student(user: Annotated[dict[str, Any], Depends(require_role("student"))]) -> dict[str, Any]:
    return _role_test("student", user)


if get_settings().app_env.casefold() in {"development", "test"}:
    router.include_router(verification_router)

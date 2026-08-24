"""Validated authentication requests and safe user serialization."""

from __future__ import annotations

from enum import Enum
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class UserRole(str, Enum):
    admin = "admin"
    faculty = "faculty"
    student = "student"


class UserStatus(str, Enum):
    active = "active"
    inactive = "inactive"
    suspended = "suspended"


class UserDocument(BaseModel):
    """Internal persistence model; API routes must use ``safe_user`` instead."""

    id: Any = Field(alias="_id")
    institution_id: Any
    email: str
    username: str
    password_hash: str = Field(repr=False)
    role: UserRole
    status: UserStatus = UserStatus.active
    display_name: str
    must_change_password: bool = False
    last_login_at: datetime | None = None
    password_changed_at: datetime | None = None
    failed_login_attempts: int = 0
    locked_until: datetime | None = None
    token_version: int = 0
    created_at: datetime
    updated_at: datetime
    created_by: Any | None = None
    faculty_id: Any | None = None
    student_id: Any | None = None
    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)

    @field_validator("email", "username")
    @classmethod
    def normalize_login_name(cls, value: str) -> str:
        return value.strip().casefold()


class AuthSessionDocument(BaseModel):
    id: Any = Field(alias="_id")
    user_id: Any
    institution_id: Any
    refresh_token_hash: str = Field(repr=False)
    token_family_id: str
    created_at: datetime
    expires_at: datetime
    last_used_at: datetime | None = None
    revoked_at: datetime | None = None
    user_agent: str | None = None
    device_name: str | None = None
    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)


class LoginRequest(BaseModel):
    identifier: str = Field(min_length=1, max_length=254)
    password: str = Field(min_length=1, max_length=1024)
    user_agent: str | None = Field(default=None, alias="userAgent", max_length=512)
    device_name: str | None = Field(default=None, alias="deviceName", max_length=120)
    model_config = ConfigDict(populate_by_name=True)

    @field_validator("identifier")
    @classmethod
    def normalize_identifier(cls, value: str) -> str:
        return value.strip().casefold()


class RefreshRequest(BaseModel):
    refresh_token: str = Field(alias="refreshToken", min_length=20)
    user_agent: str | None = Field(default=None, alias="userAgent", max_length=512)
    device_name: str | None = Field(default=None, alias="deviceName", max_length=120)
    model_config = ConfigDict(populate_by_name=True)


class LogoutRequest(BaseModel):
    refresh_token: str = Field(alias="refreshToken", min_length=20)
    model_config = ConfigDict(populate_by_name=True)


def safe_user(user: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(user["_id"]),
        "institutionId": str(user["institution_id"]),
        "displayName": user["display_name"],
        "email": user["email"],
        "username": user["username"],
        "role": user["role"],
        "status": user["status"],
        "mustChangePassword": user.get("must_change_password", False),
        "facultyId": str(user["faculty_id"]) if user.get("faculty_id") else None,
        "studentId": str(user["student_id"]) if user.get("student_id") else None,
    }

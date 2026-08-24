"""Central Flet authentication state with deliberately memory-only token storage."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol


class AuthenticationStatus(str, Enum):
    unauthenticated = "unauthenticated"
    authenticating = "authenticating"
    authenticated = "authenticated"


class TokenStorage(Protocol):
    def load(self) -> tuple[str | None, str | None]: ...
    def save(self, access_token: str, refresh_token: str) -> None: ...
    def clear(self) -> None: ...


class MemoryTokenStorage:
    """Safe development fallback: tokens disappear when the process exits."""

    def __init__(self) -> None:
        self._access_token: str | None = None
        self._refresh_token: str | None = None

    def load(self) -> tuple[str | None, str | None]:
        return self._access_token, self._refresh_token

    def save(self, access_token: str, refresh_token: str) -> None:
        self._access_token = access_token
        self._refresh_token = refresh_token

    def clear(self) -> None:
        self._access_token = None
        self._refresh_token = None


@dataclass
class AuthState:
    storage: TokenStorage = field(default_factory=MemoryTokenStorage)
    current_user: dict[str, Any] | None = None
    status: AuthenticationStatus = AuthenticationStatus.unauthenticated
    loading: bool = False
    error: str | None = None

    @property
    def access_token(self) -> str | None:
        return self.storage.load()[0]

    @property
    def refresh_token(self) -> str | None:
        return self.storage.load()[1]

    @property
    def is_authenticated(self) -> bool:
        return self.status == AuthenticationStatus.authenticated and self.current_user is not None

    def begin_login(self) -> None:
        self.loading = True
        self.error = None
        self.status = AuthenticationStatus.authenticating

    def authenticate(self, payload: dict[str, Any]) -> None:
        self.storage.save(payload["accessToken"], payload["refreshToken"])
        self.current_user = payload["user"]
        self.loading = False
        self.error = None
        self.status = AuthenticationStatus.authenticated

    def update_tokens(self, payload: dict[str, Any]) -> None:
        self.storage.save(payload["accessToken"], payload["refreshToken"])
        if payload.get("user"):
            self.current_user = payload["user"]

    def fail(self, message: str) -> None:
        self.loading = False
        self.error = message
        self.status = AuthenticationStatus.unauthenticated

    def clear(self) -> None:
        self.storage.clear()
        self.current_user = None
        self.loading = False
        self.error = None
        self.status = AuthenticationStatus.unauthenticated

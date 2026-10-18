"""Small import-safe checks for the Flet HTTP boundary."""

from unittest.mock import patch

import httpx
import pytest
import socket

from app.services.api_client import ApiClient


def test_unreachable_api_is_safe() -> None:
    with patch("httpx.get", side_effect=httpx.ConnectError("offline")):
        assert ApiClient().health_check().connected is False


def test_timeout_is_safe() -> None:
    with patch("httpx.get", side_effect=httpx.TimeoutException("slow")):
        assert ApiClient().system_info().connected is False


def test_malformed_response_is_safe() -> None:
    response = httpx.Response(200, content=b"not-json")
    with patch("httpx.get", return_value=response):
        assert ApiClient().health_check().connected is False


@pytest.mark.parametrize("status", [401, 404, 503])
def test_http_error_is_reachable_and_not_transport_offline(status):
    with patch("httpx.get", return_value=httpx.Response(status, json={"error": {"message": "Service error"}})):
        result = ApiClient().health_check()
    assert not result.connected and result.reachable
    assert result.status_code == status and result.error_kind == "http"


@pytest.mark.parametrize("exception,kind", [(httpx.ConnectTimeout("secret"), "timeout"), (httpx.ConnectError("secret"), "connection"), (httpx.ReadError("secret"), "network")])
def test_transport_errors_are_distinct_and_sanitized(exception, kind, caplog):
    with patch("httpx.request", side_effect=exception):
        result = ApiClient().login("user", "password-secret")
    assert not result.reachable and result.error_kind == kind and result.error
    assert "secret" not in caplog.text and "failure=" in caplog.text


@pytest.mark.parametrize("cause,kind", [(socket.gaierror(-2, "secret-host"), "dns"), (ConnectionRefusedError(10061, "secret-address"), "connection_refused")])
def test_connection_causes_are_classified(cause, kind, caplog):
    exception = httpx.ConnectError("secret-url")
    exception.__cause__ = cause
    with patch("httpx.get", side_effect=exception):
        result = ApiClient().health_check()
    assert result.error_kind == kind and not result.reachable
    assert "secret" not in caplog.text


def test_login_payload_and_invalid_credentials_are_not_offline(caplog):
    client = ApiClient(base_url="https://example.test/api/v1/")
    with patch("httpx.request", return_value=httpx.Response(401, json={"success": False, "error": {"code": "AUTH_INVALID_CREDENTIALS", "message": "Invalid credentials."}})) as request:
        result = client.login("person@example.test", "password-secret")
    assert request.call_args.args == ("POST", "https://example.test/api/v1/auth/login")
    assert request.call_args.kwargs["json"] == {"identifier": "person@example.test", "password": "password-secret"}
    assert result.reachable and not result.connected and result.error == "Invalid credentials."
    assert not client.auth_state.is_authenticated
    assert "password-secret" not in caplog.text


def test_login_server_error_is_reachable_and_never_authenticates():
    client = ApiClient(base_url="https://example.test")
    with patch("httpx.request", return_value=httpx.Response(500, json={"success": False, "message": "An unexpected server error occurred."})):
        result = client.login("admin", "password-secret")
    assert result.status_code == 500 and result.reachable and not result.connected
    assert result.error_kind == "http" and result.error == "An unexpected server error occurred."
    assert client.auth_state.error == result.error
    assert not client.auth_state.is_authenticated and client.auth_state.access_token is None

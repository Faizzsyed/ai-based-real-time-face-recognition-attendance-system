"""Small import-safe checks for the Flet HTTP boundary."""

from unittest.mock import patch

import httpx

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

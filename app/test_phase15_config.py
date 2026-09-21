import os
from app.core.config import AppSettings

def test_flet_api_url_resolves_gracefully(monkeypatch):
    monkeypatch.setenv("API_BASE_URL", "https://production.example.com")
    settings = AppSettings()
    assert settings.api_base_url == "https://production.example.com"

def test_flet_api_url_defaults_to_localhost_if_not_set(monkeypatch):
    monkeypatch.delenv("API_BASE_URL", raising=False)
    settings = AppSettings()
    assert settings.api_base_url == "http://127.0.0.1:8000"

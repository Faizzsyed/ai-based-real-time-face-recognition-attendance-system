import pytest
import importlib
import sys
import os
from pathlib import Path
import subprocess
from app.core.config import normalize_api_url


@pytest.fixture(autouse=True)
def isolated_client_config(monkeypatch):
    import app.core.config as config
    monkeypatch.setitem(config.AppSettings.model_config, "env_file", None)
    monkeypatch.setattr(config, "ANDROID_API_BASE_URL", None)
    monkeypatch.delenv("API_BASE_URL", raising=False)
    monkeypatch.delenv("FLET_PLATFORM", raising=False)
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("ALLOW_INSECURE_DEV_API", "true")
    config.get_settings.cache_clear()
    yield
    config.get_settings.cache_clear()

def test_desktop_default_api_url(monkeypatch):
    # Ensure no environment variables or build_config override
    monkeypatch.delenv("API_BASE_URL", raising=False)
    import app.core.config

    # Patch module attribute directly to None (simulating absence of override)
    monkeypatch.setattr(app.core.config, "ANDROID_API_BASE_URL", None)

    try:
        app.core.config.get_settings.cache_clear()
        settings = app.core.config.get_settings()
        assert settings.api_base_url == "http://127.0.0.1:8000"
    finally:
        app.core.config.get_settings.cache_clear()


@pytest.mark.parametrize("base", ["http://192.168.1.50:8000", "http://192.168.1.50:8000/", "http://192.168.1.50:8000/api/v1/"])
def test_endpoint_joining_for_origin_and_api_base(base, monkeypatch):
    import httpx
    from app.services.api_client import ApiClient
    client = ApiClient(base_url=base)
    calls = []
    def get(url, **kwargs):
        calls.append(url)
        return httpx.Response(200, json={"success": True, "status": "ok"})
    monkeypatch.setattr(httpx, "get", get)
    assert client.health_check().connected
    assert calls == ["http://192.168.1.50:8000/api/v1/health"]
    assert client._url("api/v1/auth/login") == "http://192.168.1.50:8000/api/v1/auth/login"


@pytest.mark.parametrize("url", ["http://localhost:8000", "http://127.0.0.1:8000", "http://[::1]:8000", "http://0.0.0.0:8000", "http://localhost.:8000", "http://app.localhost.:8000", "http://[::ffff:127.0.0.1]:8000", "http://[::]:8000"])
def test_android_rejects_loopback(url):
    with pytest.raises(ValueError):
        normalize_api_url(url, android=True)


@pytest.mark.parametrize("url", ["", "backend", "ftp://example.test", "https://user:secret@example.test", "https://example.test?token=secret", "https://example.test:bad", "https://[secret", "https://bad host.test", "https://example.test\\secret", "https://example.test:0", "https://example.test:99999", "https://example.test:", "https://example.test\nsecret", "https://127.1", "https://%73ecret.test"])
def test_api_url_rejects_invalid_or_secret_bearing_values(url):
    with pytest.raises(ValueError) as exc:
        normalize_api_url(url)
    assert "secret" not in str(exc.value)


@pytest.mark.parametrize("api_url,mode", [("http://192.168.1.50:8000/api/v1/", "development"), ("https://api.example.test/proxy/api/v1/", "production")])
def test_packaged_build_url_wins_over_environment_in_isolated_runtime(tmp_path, api_url, mode):
    """Exercise the generated module import, rather than mocking its constant."""
    import shutil
    source = Path(__file__).parent
    shutil.copytree(source / "core", tmp_path / "core", ignore=shutil.ignore_patterns("__pycache__", "build_config.py"))
    from scripts.prepare_android_config import write_build_config
    expected = write_build_config(api_url, tmp_path / "core/build_config.py")
    (tmp_path / ".env").write_text("API_BASE_URL=http://localhost:6666\nAPP_ENV=development\nALLOW_INSECURE_DEV_API=true\n", encoding="utf-8")
    code = (
        "import sys, types\n"
        "app=types.ModuleType('app'); app.__path__=[sys.argv[1]]; sys.modules['app']=app\n"
        "from app.core.config import get_settings\n"
        "assert get_settings().api_base_url == sys.argv[2]\n"
        "assert get_settings().app_env == sys.argv[3]\n"
        "assert get_settings().allow_insecure_dev_api == (sys.argv[3] == 'development')\n"
    )
    env = {**os.environ, "API_BASE_URL": "http://127.0.0.1:9999", "APP_ENV": "development", "ALLOW_INSECURE_DEV_API": "true"}
    env.pop("PYTHONPATH", None)
    result = subprocess.run([sys.executable, "-c", code, str(tmp_path), expected, mode], cwd=tmp_path, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_production_rejects_http_even_if_dev_flag_enabled(monkeypatch):
    import app.core.config as config
    monkeypatch.setattr(config, "ANDROID_API_BASE_URL", None)
    monkeypatch.setenv("API_BASE_URL", "http://example.test")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("ALLOW_INSECURE_DEV_API", "true")
    config.get_settings.cache_clear()
    try:
        with pytest.raises(ValueError, match="HTTPS"):
            config.get_settings()
    finally:
        config.get_settings.cache_clear()

def test_android_build_api_url(monkeypatch):
    monkeypatch.delenv("API_BASE_URL", raising=False)

    import app.core.config
    import app.services.api_client
    import httpx

    # Patch module attribute directly
    monkeypatch.setattr(app.core.config, "ANDROID_API_BASE_URL", "http://192.168.1.46:8000")

    try:
        # Clear cache to apply Android override
        app.core.config.get_settings.cache_clear()

        settings = app.core.config.get_settings()
        assert settings.api_base_url == "http://192.168.1.46:8000"

        # Test ApiClient uses the exact same URL
        client = app.services.api_client.ApiClient()
        assert client.base_url == "http://192.168.1.46:8000"

        # Test ApiClient's health endpoint logic
        called_url = None

        class DummyResponse:
            status_code = 200
            is_success = True
            def json(self): return {"status": "ok"}

        def mock_get(url, **kwargs):
            nonlocal called_url
            called_url = url
            return DummyResponse()

        monkeypatch.setattr(httpx, "get", mock_get)

        result = client.health_check()
        assert result.connected is True
        assert called_url == "http://192.168.1.46:8000/api/v1/health"
    finally:
        app.core.config.get_settings.cache_clear()


@pytest.mark.parametrize("url", ["http://127.0.0.1:8000/", "http://192.168.1.50:8000/api/v1/", "https://api.example.test/proxy/api/v1///"])
def test_desktop_environment_and_client_use_resolved_url(monkeypatch, url):
    import httpx
    from app.core.config import get_settings
    from app.services.api_client import ApiClient
    monkeypatch.setenv("API_BASE_URL", url)
    expected = normalize_api_url(url)
    client = ApiClient()
    assert get_settings().api_base_url == client.base_url == expected
    calls = []
    def response(*args, **kwargs):
        calls.append(args[-1])
        return httpx.Response(200, json={"success": True})
    monkeypatch.setattr(httpx, "get", response)
    monkeypatch.setattr(httpx, "request", response)
    client.health_check()
    client.system_info()
    client.login("test-user", "not-logged")
    assert calls == [expected + path for path in ("/api/v1/health", "/api/v1/system/info", "/api/v1/auth/login")]


@pytest.mark.parametrize("build_url", [None, "", "backend", "https://user:secret@example.test", "https://example.test:secret"])
def test_android_missing_or_invalid_build_url_never_uses_environment(monkeypatch, build_url):
    import app.core.config as config
    monkeypatch.setenv("FLET_PLATFORM", "android")
    monkeypatch.setenv("API_BASE_URL", "https://valid-but-not-packaged.example.test")
    monkeypatch.setattr(config, "ANDROID_API_BASE_URL", build_url)
    with pytest.raises(ValueError) as exc:
        config.get_settings()
    assert "secret" not in str(exc.value)
    if not build_url:
        assert "Rebuild" in str(exc.value)


def test_android_native_runtime_detection_requires_packaged_url(monkeypatch):
    from app.core.config import get_settings
    monkeypatch.setattr(sys, "getandroidapilevel", lambda: 35, raising=False)
    with pytest.raises(ValueError, match="Android API URL is missing"):
        get_settings()


@pytest.mark.parametrize("packaged", [False, True])
def test_explicit_client_and_server_settings_cannot_bypass_https(monkeypatch, packaged):
    import app.core.config as config
    from app.services.api_client import ApiClient
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("API_BASE_URL", "https://api.example.test/")
    if packaged:
        monkeypatch.setattr(config, "ANDROID_API_BASE_URL", "https://api.example.test/")
        monkeypatch.setenv("APP_ENV", "development")
    with pytest.raises(ValueError, match="HTTPS"):
        ApiClient(base_url="http://192.168.1.50:8000")
    client = ApiClient()
    assert not client.set_base_url("http://192.168.1.50:8000")
    assert client.base_url == "https://api.example.test"
    assert client.set_base_url("https://other.example.test/api/v1/")
    assert client.base_url == "https://other.example.test"


def test_android_explicit_client_url_rejects_loopback(monkeypatch):
    import app.core.config as config
    from app.services.api_client import ApiClient
    monkeypatch.setattr(config, "ANDROID_API_BASE_URL", "http://192.168.1.50:8000")
    with pytest.raises(ValueError, match="loopback"):
        ApiClient(base_url="http://localhost:8000")
    client = ApiClient()
    assert not client.set_base_url("http://localhost:8000")


def test_generator_rejects_invalid_url_without_overwriting_file(tmp_path):
    from scripts.prepare_android_config import write_build_config
    destination = tmp_path / "build_config.py"
    destination.write_text("previous config", encoding="utf-8")
    with pytest.raises(ValueError):
        write_build_config("https://user:secret@example.test", destination)
    assert destination.read_text(encoding="utf-8") == "previous config"

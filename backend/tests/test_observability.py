"""Safe runtime observability, correlation, and redaction coverage."""
import logging
from fastapi.testclient import TestClient
from app.core.logging import request_id_var,safe_log,sanitize
from app.db.mongo import MongoConnection
from app.main import app,settings

def test_redaction_covers_credentials_tokens_database_and_biometrics():
    payload={"password":"p","password_hash":"h","Authorization":"Bearer secret","access_token":"a","refreshToken":"r","jwt_secret":"j","mongodb_uri":"mongodb://user:pass@host/db","embedding":[1,2],"encrypted_embedding":{"ciphertext":"x"},"image_bytes":b"raw"}
    text=str(sanitize(payload));assert "Bearer secret" not in text and "user:pass" not in text and "[1, 2]" not in text and "b'raw'" not in text and text.count("[REDACTED]")>=8
def test_request_id_generated_propagated_and_request_logs(caplog):
    caplog.set_level(logging.INFO)
    with TestClient(app) as client:
        generated=client.get("/api/v1/health");incoming=client.get("/api/v1/health",headers={"X-Request-ID":"observability-123"})
    assert generated.headers["X-Request-ID"] and incoming.headers["X-Request-ID"]=="observability-123"
    assert "request started" in caplog.text and "request finished" in caplog.text
def test_safe_logger_never_emits_sensitive_values(caplog):
    caplog.set_level(logging.INFO);safe_log(logging.getLogger("TEST"),logging.INFO,"operation",password="NeverLog",refresh_token="TokenValue",face_image=b"bytes",mongodb_uri="mongodb://secret/db")
    assert "NeverLog" not in caplog.text and "TokenValue" not in caplog.text and "bytes" not in caplog.text and "secret/db" not in caplog.text
def test_database_unavailable_is_logged_safely(caplog):
    caplog.set_level(logging.ERROR);connection=MongoConnection()
    try:connection.require_database()
    except Exception:pass
    assert "Database unavailable" in caplog.text
def test_context_request_id_is_local():
    token=request_id_var.set("local-request");assert request_id_var.get()=="local-request";request_id_var.reset(token);assert request_id_var.get()=="-"
def test_api_request_logging_flag_disables_middleware_logs(caplog):
    caplog.set_level(logging.INFO);previous=settings.enable_api_request_logging;settings.enable_api_request_logging=False
    try:
        with TestClient(app) as client:client.get("/api/v1/health")
    finally:settings.enable_api_request_logging=previous
    assert "request started" not in caplog.text and "request finished" not in caplog.text

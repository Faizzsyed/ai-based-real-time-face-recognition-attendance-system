import pytest
from pydantic import ValidationError
from app.core.config import Settings
from fastapi.testclient import TestClient
from app.main import app
from app.db.mongo import mongo

client = TestClient(app)

def test_production_config_rejects_insecure_jwt():
    with pytest.raises(ValidationError) as exc:
        Settings(
            app_env="production",
            mongodb_uri="mongodb://localhost:27017",
            jwt_secret="too_short",
            cors_origins="https://example.com",
            face_ai_enabled=False
        )
    assert "secure JWT_SECRET" in str(exc.value)

def test_production_config_rejects_default_jwt():
    with pytest.raises(ValidationError) as exc:
        Settings(
            app_env="production",
            mongodb_uri="mongodb://localhost:27017",
            jwt_secret="replace_with_at_least_32_random_characters",
            cors_origins="https://example.com",
            face_ai_enabled=False
        )
    assert "secure JWT_SECRET" in str(exc.value)

def test_production_config_rejects_missing_mongo():
    with pytest.raises(ValidationError) as exc:
        Settings(
            app_env="production",
            mongodb_uri="",
            jwt_secret="this_is_a_secure_jwt_secret_that_is_long_enough",
            cors_origins="https://example.com",
            face_ai_enabled=False
        )
    assert "MONGODB_URI is required" in str(exc.value)

def test_production_config_rejects_wildcard_cors():
    with pytest.raises(ValidationError) as exc:
        Settings(
            app_env="production",
            mongodb_uri="mongodb://localhost:27017",
            jwt_secret="this_is_a_secure_jwt_secret_that_is_long_enough",
            cors_origins="*",
            face_ai_enabled=False
        )
    assert "CORS_ORIGINS must be explicitly configured" in str(exc.value)

def test_production_config_rejects_insecure_encryption_key_when_face_ai_enabled():
    with pytest.raises(ValidationError) as exc:
        Settings(
            app_env="production",
            mongodb_uri="mongodb://localhost:27017",
            jwt_secret="this_is_a_secure_jwt_secret_that_is_long_enough",
            cors_origins="https://example.com",
            face_ai_enabled=True,
            face_embedding_encryption_key="too_short"
        )
    assert "secure 32-character FACE_EMBEDDING_ENCRYPTION_KEY" in str(exc.value)

def test_ready_endpoint_returns_503_when_mongo_disconnected():
    original_status = mongo.status
    mongo.status = "disconnected"
    try:
        response = client.get("/api/v1/ready")
        assert response.status_code == 503
        assert response.json()["detail"] == "Database not ready"
    finally:
        mongo.status = original_status

def test_ready_endpoint_returns_200_when_mongo_connected():
    original_status = mongo.status
    mongo.status = "connected"
    try:
        response = client.get("/api/v1/ready")
        assert response.status_code == 200
        assert response.json()["status"] == "ready"
    finally:
        mongo.status = original_status

def test_security_headers_are_present():
    response = client.get("/api/v1/health")
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("X-XSS-Protection") == "1; mode=block"

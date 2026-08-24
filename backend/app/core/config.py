from functools import lru_cache
from pathlib import Path
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    app_name: str = "AI Based Real-Time Face Recognition Attendance System"
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    mongodb_uri: str | None = None
    mongodb_database: str = "attendai_python_dev"
    enable_dev_academic_api: bool = False
    enable_dev_role_preview: bool = True
    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    jwt_access_token_minutes: int = 15
    jwt_refresh_token_days: int = 7
    auth_max_failed_attempts: int = 5
    auth_lockout_minutes: int = 15
    max_page_size: int = 100
    attendance_low_threshold_percent: float = 75.0
    cors_origins: str = ""
    log_level: str = "INFO"
    log_format: str = "console"
    enable_api_request_logging: bool = True
    enable_file_logging: bool = False
    face_ai_enabled: bool = False
    face_embedding_encryption_key: str = ""
    face_detection_model_path: Path = Path(__file__).resolve().parents[3] / "models" / "face_detection_yunet_2023mar.onnx"
    face_recognition_model_path: Path = Path(__file__).resolve().parents[3] / "models" / "face_recognition_sface_2021dec.onnx"
    face_detection_threshold: float = 0.90
    face_match_threshold: float = 0.363
    face_identification_min_margin: float = 0.08
    face_enrollment_consistency_threshold: float = 0.40
    face_recognition_cooldown_seconds: int = 8
    face_liveness_mode: str = "optional"
    face_max_image_bytes: int = 5 * 1024 * 1024

    @field_validator("face_detection_model_path","face_recognition_model_path",mode="before")
    @classmethod
    def resolve_face_model_path(cls,value):
        path=Path(value)
        return path if path.is_absolute() else Path(__file__).resolve().parents[3]/path
    @field_validator("log_level")
    @classmethod
    def valid_log_level(cls,value):
        value=str(value).upper()
        if value not in {"DEBUG","INFO","WARNING","ERROR","CRITICAL"}:raise ValueError("Unsupported log level")
        return value
    @field_validator("face_liveness_mode")
    @classmethod
    def valid_liveness_mode(cls,value):
        value=str(value).casefold()
        if value not in {"required","optional","disabled"}:raise ValueError("Unsupported liveness mode")
        return value
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[3] / ".env", extra="ignore"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()

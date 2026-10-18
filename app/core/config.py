from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
from pydantic import ValidationError
from app.core.api_config import is_android_runtime, normalize_api_url

try:
    from app.core.build_config import ANDROID_API_BASE_URL
except ModuleNotFoundError as exc:
    if exc.name != "app.core.build_config":
        raise
    ANDROID_API_BASE_URL = None


def is_android_client() -> bool:
    return ANDROID_API_BASE_URL is not None or is_android_runtime()


class AppSettings(BaseSettings):
    app_env: str = "development"
    api_base_url: str = "http://127.0.0.1:8000"
    allow_insecure_dev_api: bool = True
    enable_dev_academic_api: bool = False
    enable_dev_role_preview: bool = True
    log_level: str = "INFO"
    enable_ui_event_logging: bool = True
    enable_api_request_logging: bool = True
    camera_preview_fps: int = 24
    camera_analysis_fps: int = 6
    camera_analysis_width: int = 640
    face_stability_seconds: float = 1.0
    face_liveness_required_blinks: int = 1
    face_liveness_timeout_seconds: float = 9.0
    face_liveness_min_open_frames: int = 2
    face_liveness_min_closed_frames: int = 2
    face_liveness_calibration_samples: int = 8
    face_liveness_closure_delta: float = 0.20
    face_liveness_reopen_ratio: float = 0.45
    face_liveness_analysis_fps: int = 15
    face_liveness_debug: bool = False
    face_enrollment_capture_interval_seconds: float = 0.50
    face_enrollment_max_capture_retries: int = 8
    face_liveness_challenge_mode: str = "challenge"
    face_liveness_enrollment_steps: int = 1
    face_liveness_attendance_steps: int = 1
    face_liveness_pose_timeout_seconds: float = 9.0
    face_liveness_pose_delta: float = 0.10
    face_liveness_pose_center_tolerance: float = 0.07
    face_liveness_pose_frames: int = 3
    camera_input_mirrored: bool = False
    face_liveness_face_loss_grace_ms: int = 600
    face_landmarker_model_path: Path = Path(__file__).resolve().parents[2] / "models" / "face_landmarker.task"
    face_detection_model_path: Path = Path(__file__).resolve().parents[2] / "models" / "face_detection_yunet_2023mar.onnx"
    face_detection_threshold: float = 0.90
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def development_preview_enabled(self) -> bool:
        return self.enable_dev_role_preview and self.app_env.casefold() == "development"


@lru_cache
def get_settings() -> AppSettings:
    android = is_android_client()
    overrides = {}
    if android:
        if not ANDROID_API_BASE_URL:
            raise ValueError("Android API URL is missing. Rebuild with scripts/build_android.ps1 -ApiUrl and a LAN or HTTPS backend URL.")
        packaged_url = normalize_api_url(ANDROID_API_BASE_URL, android=True)
        # The build URL determines the packaged mode. Runtime environment or
        # .env files cannot redirect the APK or downgrade an HTTPS build.
        production = packaged_url.startswith("https://")
        overrides = dict(api_base_url=packaged_url, app_env="production" if production else "development",
                         allow_insecure_dev_api=not production, _env_file=None)
    try:
        settings = AppSettings(**overrides)
    except ValidationError:
        raise ValueError("Client configuration is invalid. Check the client environment settings.") from None
    if settings.app_env.casefold() == "production":
        settings.allow_insecure_dev_api = False
    settings.api_base_url = normalize_api_url(settings.api_base_url, android=android,
                                              require_https=not settings.allow_insecure_dev_api)
    return settings


def resolve_api_url(value: str | None = None) -> str:
    """Apply the same policy to the configured URL and explicit client overrides."""
    settings = get_settings()
    return normalize_api_url(settings.api_base_url if value is None else value,
                             android=is_android_client(), require_https=not settings.allow_insecure_dev_api)

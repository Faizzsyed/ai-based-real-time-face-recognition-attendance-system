from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path


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
    face_liveness_timeout_seconds: float = 5.0
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
    face_liveness_enrollment_steps: int = 3
    face_liveness_attendance_steps: int = 1
    face_liveness_pose_timeout_seconds: float = 5.0
    face_liveness_pose_delta: float = 0.16
    face_liveness_pose_center_tolerance: float = 0.07
    face_liveness_pose_frames: int = 2
    face_liveness_face_loss_grace_ms: int = 600
    face_landmarker_model_path: Path = Path(__file__).resolve().parents[2] / "models" / "face_landmarker.task"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def development_preview_enabled(self) -> bool:
        return self.enable_dev_role_preview and self.app_env.casefold() == "development"


@lru_cache
def get_settings() -> AppSettings:
    return AppSettings()

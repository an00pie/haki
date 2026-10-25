from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from urllib.parse import urlparse
import ipaddress
from pathlib import Path

class Settings(BaseSettings):
    app_name: str = "HaKi"
    database_url: str = "sqlite:///./data/haki.db"
    data_dir: Path = Path("data")
    ollama_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "gemma3:4b"
    ollama_text_model: str = "gemma:2b"
    # PROVISIONAL / UN-CALIBRATED: All thresholds, weights, budgets, and timeouts are heuristic baselines.
    max_upload_mb: int = 50  # Provisional upload limit
    max_video_upload_mb: int = 100  # Provisional video upload limit
    max_video_seconds: int = 60  # Provisional video duration limit
    max_video_duration_seconds: int = 60  # Backwards compatibility alias
    max_video_frames: int = 12  # Provisional frame budget
    stage2_threshold: int = 40  # Provisional Stage 2 recommendation threshold (0-100)
    video_verification_threshold: int = 40  # Backwards compatibility alias for stage2_threshold
    max_tool_executions: int = 10  # Provisional step budget
    node_retry_limit: int = 2  # Provisional per-node retry budget
    fetch_max_bytes: int = 5_000_000  # Provisional SSRF fetcher max body size (5MB)
    fetch_timeout_s: float = 10.0  # Provisional SSRF fetcher timeout in seconds
    rdap_enabled: bool = False  # Provisional domain age lookup flag
    complaint_search_provider: str = "none"  # Provisional search provider (none, brave, mock)
    complaint_search_api_key: str = ""
    public_checks_enabled: bool = False
    brave_search_api_key: str = ""
    instagram_max_media_candidates: int = 3
    instagram_max_media_frames: int = 4
    instagram_api_token: str = ""
    cors_origins: str = "http://localhost:3000"
    @field_validator("ollama_url")
    @classmethod
    def ollama_must_be_local(cls, value: str) -> str:
        parsed=urlparse(value)
        if parsed.scheme != "http" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("Ollama must use a local HTTP endpoint")
        if parsed.hostname != "localhost":
            try: loopback=ipaddress.ip_address(parsed.hostname).is_loopback
            except ValueError: loopback=False
            if not loopback: raise ValueError("Ollama must be bound to localhost")
        return value

    @field_validator("video_verification_threshold")
    @classmethod
    def threshold_in_score_range(cls, value: int) -> int:
        if not 0 <= value <= 100: raise ValueError("VIDEO_VERIFICATION_THRESHOLD must be between 0 and 100")
        return value

    @field_validator("max_video_upload_mb")
    @classmethod
    def video_upload_limit_bounded(cls,value:int)->int:
        if not 1<=value<=500:raise ValueError("MAX_VIDEO_UPLOAD_MB must be from 1 to 500")
        return value

    @field_validator("max_video_duration_seconds")
    @classmethod
    def video_duration_bounded(cls,value:int)->int:
        if not 1<=value<=600:raise ValueError("MAX_VIDEO_DURATION_SECONDS must be from 1 to 600")
        return value

    @field_validator("max_video_frames")
    @classmethod
    def video_frames_bounded(cls,value:int)->int:
        if not 1<=value<=24:raise ValueError("MAX_VIDEO_FRAMES must be from 1 to 24")
        return value

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def origins(self): return [x.strip() for x in self.cors_origins.split(",") if x.strip()]

settings = Settings()
settings.data_dir.mkdir(parents=True, exist_ok=True)
(settings.data_dir / "evidence").mkdir(exist_ok=True)
(settings.data_dir / "reports").mkdir(exist_ok=True)

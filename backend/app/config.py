from pathlib import Path
from typing import List, Optional

from pydantic import ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Centralized application configuration, read from environment variables
    (and optionally a local .env file). See root .env.example for the full
    list of supported variables and safe placeholder values.
    """

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Database (required, no insecure fallback) ---
    DATABASE_URL: str

    # --- Auth (required, no insecure fallback) ---
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7

    # --- Storage (non-secret, safe to default) ---
    UPLOAD_DIR: str = "/app/storage/uploads"
    FUSION_UPLOAD_DIR: Optional[str] = None
    FUSION_OUTPUT_DIR: Optional[str] = None
    FUSION_PROCESS_TIMEOUT_SECONDS: int = 3900
    FUSION_MAX_UPLOAD_BYTES: int = 500 * 1024 * 1024

    # --- Phase 3A: per-question answer segments + real local audio
    # analysis (non-secret, safe to default). Deliberately smaller than
    # FUSION_MAX_UPLOAD_BYTES: a segment is one answer to one question,
    # not a whole-interview recording. ---
    ANSWER_SEGMENT_UPLOAD_DIR: Optional[str] = None
    ANSWER_SEGMENT_MAX_UPLOAD_BYTES: int = 150 * 1024 * 1024
    AUDIO_EXTRACTION_TIMEOUT_SECONDS: int = 120
    AUDIO_MODEL_TIMEOUT_SECONDS: int = 300

    # --- CORS (non-secret, safe local-dev default) ---
    CORS_ORIGINS: str = (
        "http://localhost:5173,http://127.0.0.1:5173"
    )

    # --- OpenRouter (preparation only — not integrated in this phase) ---
    OPENROUTER_API_KEY: Optional[str] = None
    OPENROUTER_MODEL: str = "cohere/north-mini-code:free"
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"

    # --- Organization invitations (Phase 2D) ---
    # Fixed server-side default, not client-configurable via the API (a
    # caller could otherwise request an unreasonably long-lived token).
    # 168 hours = 7 days, matching ACCESS_TOKEN_EXPIRE_MINUTES's existing
    # 7-day default for a consistent "how long do links last" mental model.
    INVITATION_EXPIRE_HOURS: int = 168
    # Used only to build the locally-displayed one-time acceptance URL
    # (e.g. "{FRONTEND_PUBLIC_URL}/invitations/accept?token=..."). No real
    # email is sent in this phase — the URL is returned in the API
    # response and shown in the System Admin / company invitation UI for
    # manual delivery.
    FRONTEND_PUBLIC_URL: str = "https://localhost"

    @property
    def cors_origins_list(self) -> List[str]:
        """CORS_ORIGINS parsed from a comma-separated string into a list."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def project_root(self) -> Path:
        return PROJECT_ROOT

    @property
    def fusion_dir(self) -> Path:
        return self.project_root / "InterviewIQ_AI" / "fusion"

    @property
    def fusion_runner(self) -> Path:
        return self.fusion_dir / "fusion_pipeline.py"

    @property
    def fusion_reference_json(self) -> Path:
        return (
            self.project_root
            / "InterviewIQ_AI"
            / "nlp"
            / "interview-iq-fusion-handoff"
            / "data"
            / "refdocs"
            / "reference_docs_250_FINAL_v1.json"
        )

    @property
    def fusion_upload_path(self) -> Path:
        return (
            Path(self.FUSION_UPLOAD_DIR).expanduser()
            if self.FUSION_UPLOAD_DIR
            else self.project_root / "backend" / "storage" / "fusion_uploads"
        ).resolve()

    @property
    def fusion_output_path(self) -> Path:
        return (
            Path(self.FUSION_OUTPUT_DIR).expanduser()
            if self.FUSION_OUTPUT_DIR
            else self.fusion_dir / "outputs" / "website"
        ).resolve()

    @property
    def interviewiq_ai_dir(self) -> Path:
        return self.project_root / "InterviewIQ_AI"

    @property
    def answer_segment_upload_path(self) -> Path:
        return (
            Path(self.ANSWER_SEGMENT_UPLOAD_DIR).expanduser()
            if self.ANSWER_SEGMENT_UPLOAD_DIR
            else self.project_root / "backend" / "storage" / "answer_segments"
        ).resolve()

    @property
    def audio_emotion_package_dir(self) -> Path:
        return self.interviewiq_ai_dir / "audio" / "audio_emotion_package"

    @property
    def audio_emotion_python(self) -> Path:
        return self.audio_emotion_package_dir / ".venv_audio" / "Scripts" / "python.exe"

    @property
    def audio_emotion_checkpoint(self) -> Path:
        return self.audio_emotion_package_dir / "audio_model.pt"

    @property
    def audio_emotion_runner(self) -> Path:
        return self.interviewiq_ai_dir / "fusion" / "runners" / "run_audio_json.py"


def _load_settings() -> Settings:
    try:
        return Settings()
    except ValidationError as exc:
        missing = sorted(
            {str(err["loc"][0]) for err in exc.errors() if err.get("type") == "missing"}
        )
        if missing:
            raise RuntimeError(
                "InterviewIQ backend failed to start: missing required environment "
                f"variable(s): {', '.join(missing)}. "
                "Copy .env.example to .env at the project root, fill in real values, "
                "and restart. Refusing to start with an insecure default secret."
            ) from exc
        raise


settings = _load_settings()

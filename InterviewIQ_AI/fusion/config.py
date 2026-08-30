"""Paths and runtime settings for the local Fusion demo."""
from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

FUSION_DIR = Path(__file__).resolve().parent
PROJECT_DIR = FUSION_DIR.parent
VISION_DIR = PROJECT_DIR / "vision"
AUDIO_DIR = PROJECT_DIR / "audio" / "audio_emotion_package"
NLP_DIR = PROJECT_DIR / "nlp" / "interview-iq-fusion-handoff"


def _venv_python(venv_dir: Path) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def _path_setting(name: str, default: Path) -> Path:
    configured = os.environ.get(name)
    if not configured:
        return default
    path = Path(configured).expanduser()
    return (path if path.is_absolute() else PROJECT_DIR.parent / path).resolve()


@dataclass(frozen=True)
class Settings:
    host_python: Path = Path(sys.executable)
    vision_python: Path = _path_setting(
        "INTERVIEWIQ_VISION_PYTHON", _venv_python(VISION_DIR / ".venv_vision")
    )
    audio_python: Path = _path_setting(
        "INTERVIEWIQ_AUDIO_PYTHON", _venv_python(AUDIO_DIR / ".venv_audio")
    )
    nlp_python: Path = _path_setting(
        "INTERVIEWIQ_NLP_PYTHON", _venv_python(NLP_DIR / ".venv_nlp")
    )
    ffmpeg: str = shutil.which("ffmpeg") or "ffmpeg"
    reference_json: Path = NLP_DIR / "data" / "refdocs" / "reference_docs_250_FINAL_v1.json"
    vision_checkpoint: Path = _path_setting(
        "INTERVIEWIQ_VISION_CHECKPOINT",
        VISION_DIR / "vsc_ravdess_test73_deployment (1)" / "vsc_ravdess_lora_r16_test73_24.pt",
    )
    audio_checkpoint: Path = _path_setting(
        "INTERVIEWIQ_AUDIO_CHECKPOINT", AUDIO_DIR / "audio_model.pt"
    )
    nlp_env_file: Path = NLP_DIR / ".env"
    vision_runner: Path = FUSION_DIR / "runners" / "run_vision_json.py"
    audio_runner: Path = FUSION_DIR / "runners" / "run_audio_json.py"
    nlp_runner: Path = FUSION_DIR / "runners" / "run_nlp_json.py"
    component_timeout_seconds: int = int(os.environ.get("FUSION_COMPONENT_TIMEOUT", "1200"))
    ffmpeg_timeout_seconds: int = int(os.environ.get("FUSION_FFMPEG_TIMEOUT", "180"))

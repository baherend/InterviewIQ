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


@dataclass(frozen=True)
class Settings:
    host_python: Path = Path(sys.executable)
    vision_python: Path = VISION_DIR / ".venv_vision" / "Scripts" / "python.exe"
    audio_python: Path = AUDIO_DIR / ".venv_audio" / "Scripts" / "python.exe"
    nlp_python: Path = NLP_DIR / ".venv_nlp" / "Scripts" / "python.exe"
    ffmpeg: str = shutil.which("ffmpeg") or "ffmpeg"
    reference_json: Path = NLP_DIR / "data" / "refdocs" / "reference_docs_250_FINAL_v1.json"
    vision_checkpoint: Path = VISION_DIR / "vsc_ravdess_test73_deployment (1)" / "vsc_ravdess_lora_r16_test73_24.pt"
    audio_checkpoint: Path = AUDIO_DIR / "audio_model.pt"
    nlp_env_file: Path = NLP_DIR / ".env"
    vision_runner: Path = FUSION_DIR / "runners" / "run_vision_json.py"
    audio_runner: Path = FUSION_DIR / "runners" / "run_audio_json.py"
    nlp_runner: Path = FUSION_DIR / "runners" / "run_nlp_json.py"
    component_timeout_seconds: int = int(os.environ.get("FUSION_COMPONENT_TIMEOUT", "1200"))
    ffmpeg_timeout_seconds: int = int(os.environ.get("FUSION_FFMPEG_TIMEOUT", "180"))


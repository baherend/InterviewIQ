from pathlib import Path
import os
from adapters.base import run_json_component
from config import Settings, AUDIO_DIR


def run_audio(audio: Path, settings: Settings):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(AUDIO_DIR)
    env["PYTHONIOENCODING"] = "utf-8"
    return run_json_component(
        [str(settings.audio_python), str(settings.audio_runner), "--audio", str(audio)],
        AUDIO_DIR, env, settings.component_timeout_seconds)

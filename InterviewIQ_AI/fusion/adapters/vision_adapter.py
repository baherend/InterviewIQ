from pathlib import Path
import os
from adapters.base import run_json_component
from config import Settings, VISION_DIR


def run_vision(video: Path, settings: Settings):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(VISION_DIR)
    env["PYTHONIOENCODING"] = "utf-8"
    return run_json_component(
        [str(settings.vision_python), str(settings.vision_runner), "--video", str(video)],
        VISION_DIR, env, settings.component_timeout_seconds)

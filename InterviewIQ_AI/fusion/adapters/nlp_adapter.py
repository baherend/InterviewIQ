from pathlib import Path
import os
from adapters.base import run_json_component
from config import Settings, NLP_DIR


def run_nlp(audio: Path, question_id: str, settings: Settings):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(NLP_DIR / "src")
    env["PYTHONIOENCODING"] = "utf-8"
    return run_json_component(
        [str(settings.nlp_python), str(settings.nlp_runner), "--audio", str(audio),
         "--question-id", question_id, "--reference-json", str(settings.reference_json)],
        NLP_DIR, env, settings.component_timeout_seconds)

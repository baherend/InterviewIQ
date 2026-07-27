"""Local multimodal Fusion orchestrator."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from adapters.audio_adapter import run_audio
from adapters.nlp_adapter import run_nlp
from adapters.vision_adapter import run_vision
from config import Settings
from schemas import assess_question_answer_match, mapped_audio, mapped_nlp, mapped_vision


def load_question(reference_json: Path, question_id: str) -> dict[str, Any]:
    with reference_json.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    documents = data.get("documents") if isinstance(data, dict) else None
    if not isinstance(documents, list):
        raise ValueError("Reference JSON must contain a documents list")
    for doc in documents:
        if isinstance(doc, dict) and doc.get("question_id") == question_id:
            return doc
    raise KeyError(f"Unknown question_id: {question_id}")


def _env_has_key(path: Path, name: str) -> bool:
    if not path.is_file():
        return False
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key, value = stripped.split("=", 1)
            if key.strip() == name and value.strip().strip("'\""):
                return True
    return False


def preflight(video: Path, question_id: str, settings: Settings) -> tuple[dict[str, Any], dict[str, Any] | None]:
    checks: dict[str, Any] = {}
    paths = {
        "host_python": settings.host_python, "vision_python": settings.vision_python,
        "audio_python": settings.audio_python, "nlp_python": settings.nlp_python,
        "input_video": video, "reference_json": settings.reference_json,
        "vision_checkpoint": settings.vision_checkpoint, "audio_checkpoint": settings.audio_checkpoint,
        "nlp_env": settings.nlp_env_file, "vision_runner": settings.vision_runner,
        "audio_runner": settings.audio_runner, "nlp_runner": settings.nlp_runner,
    }
    for name, path in paths.items():
        checks[name] = {"ok": path.is_file(), "path": str(path)}
    checks["ffmpeg"] = {"ok": Path(settings.ffmpeg).is_file() or bool(os.path.dirname(settings.ffmpeg) == "" and settings.ffmpeg),
                        "path": settings.ffmpeg}
    checks["groq_api_key"] = {"ok": _env_has_key(settings.nlp_env_file, "GROQ_API_KEY"),
                              "detail": "present" if _env_has_key(settings.nlp_env_file, "GROQ_API_KEY") else "missing"}
    question = None
    try:
        question = load_question(settings.reference_json, question_id)
        checks["question_id"] = {"ok": True, "value": question_id}
        checks["reference_json_valid"] = {"ok": True}
    except Exception as exc:
        checks["question_id"] = {"ok": False, "value": question_id}
        checks["reference_json_valid"] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    return checks, question


def extract_audio(video: Path, destination: Path, settings: Settings) -> dict[str, Any]:
    command = [settings.ffmpeg, "-y", "-i", str(video), "-vn", "-ac", "1", "-ar", "16000",
               "-c:a", "pcm_s16le", str(destination)]
    started = time.monotonic()
    try:
        cp = subprocess.run(command, capture_output=True, text=True, encoding="utf-8",
                            errors="replace", timeout=settings.ffmpeg_timeout_seconds,
                            check=False, shell=False)
        return {"status": "completed" if cp.returncode == 0 and destination.is_file() else "failed",
                "command": command, "return_code": cp.returncode, "stderr": cp.stderr,
                "duration_seconds": round(time.monotonic() - started, 3)}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"status": "failed", "command": command,
                "error": {"type": type(exc).__name__, "message": str(exc)},
                "duration_seconds": round(time.monotonic() - started, 3)}


def _error(execution: dict[str, Any]) -> dict | None:
    return execution.get("error") if execution.get("status") == "failed" else None


def run_fusion(video: Path, question_id: str, output: Path, settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or Settings()
    video = video.expanduser().resolve()
    output = output.expanduser().resolve()
    checks, doc = preflight(video, question_id, settings)
    errors: list[dict[str, Any]] = []
    component_execution: dict[str, Any] = {}
    vision_raw = audio_raw = nlp_raw = None

    output.parent.mkdir(parents=True, exist_ok=True)
    audio_path = output.parent / f"{video.stem}_mono_16khz.wav"

    fatal = [name for name in ("host_python", "input_video", "reference_json")
             if not checks.get(name, {}).get("ok")]
    if doc is None:
        fatal.append("question_id")

    if not fatal:
        if checks["vision_python"]["ok"] and checks["vision_checkpoint"]["ok"]:
            vision_raw, component_execution["vision"] = run_vision(video, settings)
        else:
            component_execution["vision"] = {"status": "failed", "error": {"type": "PreflightError", "message": "Vision executable or checkpoint missing"}}

        component_execution["ffmpeg"] = extract_audio(video, audio_path, settings)
        if component_execution["ffmpeg"]["status"] == "completed":
            if checks["audio_python"]["ok"] and checks["audio_checkpoint"]["ok"]:
                audio_raw, component_execution["audio"] = run_audio(audio_path, settings)
            else:
                component_execution["audio"] = {"status": "failed", "error": {"type": "PreflightError", "message": "Audio executable or checkpoint missing"}}
            if checks["nlp_python"]["ok"] and checks["nlp_env"]["ok"] and checks["groq_api_key"]["ok"]:
                nlp_raw, component_execution["nlp"] = run_nlp(audio_path, question_id, settings)
            else:
                component_execution["nlp"] = {"status": "failed", "error": {"type": "PreflightError", "message": "NLP executable, .env, or GROQ_API_KEY missing"}}
        else:
            for name in ("audio", "nlp"):
                component_execution[name] = {"status": "failed", "error": {"type": "AudioExtractionError", "message": "ffmpeg audio extraction failed"}}
    else:
        for name in ("vision", "audio", "nlp"):
            component_execution[name] = {"status": "failed", "error": {"type": "PreflightError", "message": f"Fatal preflight failure: {', '.join(fatal)}"}}

    for name in ("vision", "audio", "nlp"):
        if component_execution[name].get("status") == "failed":
            detail = component_execution[name].get("error", {})
            if not isinstance(detail, dict):
                detail = {"type": "ComponentFailure", "message": str(detail)}
            errors.append({"component": name, **detail})

    visual = mapped_vision(vision_raw, _error(component_execution["vision"]))
    vocal = mapped_audio(audio_raw, _error(component_execution["audio"]))
    technical = mapped_nlp(nlp_raw, _error(component_execution["nlp"]))
    transcript = ((nlp_raw or {}).get("asr") or {}).get("normalized_transcript")
    match = assess_question_answer_match(doc["question"], transcript) if doc else {
        "valid": None, "reason": "Question record was not loaded."}
    successes = sum(x["status"] == "success" for x in (visual, vocal, technical))
    status = "success" if successes == 3 else ("partial" if successes else "failed")
    limitations = [
        "Visual analysis requires enough valid face-visible windows.",
        "Audio emotion output is a model-estimated vocal pattern, not a competence measure.",
        "Technical score is valid only when the spoken answer corresponds to the selected question.",
        "Automated outputs require human review.",
    ]
    if match["valid"] is not True and technical["status"] == "success":
        limitations.append("The NLP pipeline executed, but its technical score is withheld because question-answer matching was not validated.")
    result = {
        "status": status,
        "input": {"video_path": str(video), "question_id": question_id,
                  "question": doc.get("question") if doc else None},
        "preflight": checks,
        "question_answer_match": match,
        "technical_evaluation": technical,
        "visual_analysis": visual,
        "vocal_analysis": vocal,
        "fusion_summary": {
            "final_technical_score": technical["score"] if technical["status"] == "success" and match["valid"] is True else None,
            "technical_interpretation": "NLP technical correctness score; not combined with behavioral model confidence." if technical["status"] == "success" else None,
            "visual_observation": ("Insufficient visual evidence." if visual.get("sufficient_evidence") is False else
                                   visual.get("predicted_emotion")),
            "vocal_observation": vocal.get("dominant_emotion"),
            "limitations": limitations,
        },
        "artifacts": {"extracted_audio_path": str(audio_path), "output_json_path": str(output)},
        "component_execution": component_execution,
        "errors": errors,
    }
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Run InterviewIQ multimodal Fusion")
    parser.add_argument("--video", required=True)
    parser.add_argument("--question-id", required=True)
    parser.add_argument("--output", default="outputs/fusion_result.json")
    args = parser.parse_args()
    result = run_fusion(Path(args.video), args.question_id, Path(args.output))
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] in {"success", "partial"} else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Thin ASR-only subprocess wrapper — sibling to run_audio_json.py /
run_vision_json.py / run_nlp_json.py, following the exact same pattern
(parse args, redirect any library stdout noise to stderr, print one JSON
object to stdout, exit 0/1).

Deliberately does NOT reuse run_nlp_json.py's `evaluate_answer` (that also
runs claim decomposition via Groq, BGE-M3 retrieval, and NLI — all out of
scope for Phase 3B). This wrapper calls only
interview_iq.asr.engine.transcribe_audio, i.e. real faster-whisper
transcription, nothing else. interview_iq/ itself is not modified.
"""
from __future__ import annotations
import argparse
import contextlib
import json
import sys


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio", required=True)
    parser.add_argument("--question-id", required=False, default=None)
    args = parser.parse_args()
    try:
        with contextlib.redirect_stdout(sys.stderr):
            from interview_iq.asr.engine import transcribe_audio
            result = transcribe_audio(args.audio, question_id=args.question_id)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(json.dumps({"error": {"type": type(exc).__name__, "message": str(exc)}}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

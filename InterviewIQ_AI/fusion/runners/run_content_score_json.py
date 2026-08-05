"""Thin Answer-Content-Score subprocess wrapper — sibling to
run_asr_only_json.py / run_audio_json.py / run_vision_json.py / the
existing run_nlp_json.py, following the exact same pattern (parse args,
redirect any library stdout noise to stderr, print one JSON object to
stdout, exit 0/1).

Unlike run_nlp_json.py, this wrapper does NOT let evaluate_answer run its
own ASR: Phase 3B already transcribed this exact answer segment once and
persisted the result, so re-running faster-whisper here would be a
duplicate, wasted (and non-idempotent-feeling) second ASR call per
segment. `--input-file` instead supplies that already-persisted
transcript/status as a small UTF-8 JSON file (safer than a raw CLI arg
for Arabic/Unicode text on Windows), and an injected `transcribe_fn`
feeds it straight into interview_iq.pipeline.evaluate_answer, which
still runs the real, unmodified claim decomposition (Groq) -> BGE-M3
retrieval -> NLI -> Precision/Coverage/Score pipeline for real.

interview_iq/ itself is not modified.
"""
from __future__ import annotations
import argparse
import contextlib
import json
import sys


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-file", required=True)
    parser.add_argument("--reference-json", required=True)
    args = parser.parse_args()
    try:
        with open(args.input_file, "r", encoding="utf-8") as fh:
            payload = json.load(fh)
        transcript = payload["transcript"]
        transcript_status = payload["transcript_status"]
        question_id = payload["question_id"]

        with contextlib.redirect_stdout(sys.stderr):
            from interview_iq.pipeline import evaluate_answer
            from interview_iq.refdocs.loader import load_reference_docs

            refs = load_reference_docs(args.reference_json)
            doc = refs.get_document(question_id)
            if doc is None:
                result = {"status": "NO_REFERENCE_DOCUMENT",
                          "error": f"Unknown question_id: {question_id}",
                          "question_id": question_id}
            else:
                def _persisted_transcript(_audio_path, **_kwargs) -> dict:
                    # Mirrors just the two fields interview_iq.pipeline
                    # actually reads off the ASR Format Spec record —
                    # never opens/re-transcribes any audio.
                    return {"status": transcript_status, "normalized_transcript": transcript}

                result = evaluate_answer(
                    "(reused Phase 3B transcript — no audio re-read)",
                    doc.question, doc.chunks, doc.key_points,
                    question_id=doc.question_id,
                    transcribe_fn=_persisted_transcript,
                )
        print(json.dumps(result, ensure_ascii=False))
        # Every branch above always sets a typed `status` — that alone
        # (not "status == SUCCESS") is what makes this a clean run; a
        # DECOMPOSITION_FAILED/NLI_FAILED result is still a real, valid,
        # non-crash outcome the caller should persist as-is.
        return 0 if result.get("status") is not None else 1
    except Exception as exc:
        print(json.dumps({"error": {"type": type(exc).__name__, "message": str(exc)}}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

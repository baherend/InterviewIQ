from __future__ import annotations
import argparse
import contextlib
import json
import sys


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio", required=True)
    parser.add_argument("--question-id", required=True)
    parser.add_argument("--reference-json", required=True)
    args = parser.parse_args()
    try:
        with contextlib.redirect_stdout(sys.stderr):
            from interview_iq.pipeline import evaluate_answer
            from interview_iq.refdocs.loader import load_reference_docs
            refs = load_reference_docs(args.reference_json)
            doc = refs.get_document(args.question_id)
            if doc is None:
                raise KeyError(f"Unknown question_id: {args.question_id}")
            result = evaluate_answer(args.audio, doc.question, doc.chunks, doc.key_points,
                                     question_id=doc.question_id)
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result.get("status") == "SUCCESS" else 1
    except Exception as exc:
        print(json.dumps({"error": {"type": type(exc).__name__, "message": str(exc)}}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

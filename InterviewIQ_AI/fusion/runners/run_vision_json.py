from __future__ import annotations
import argparse
import contextlib
import json
import sys


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", required=True)
    args = parser.parse_args()
    try:
        with contextlib.redirect_stdout(sys.stderr):
            from vision_module import analyze_visual_confidence
            result = analyze_visual_confidence(args.video)
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result.get("status") in {"ok", "insufficient_evidence"} else 1
    except Exception as exc:
        print(json.dumps({"error": {"type": type(exc).__name__, "message": str(exc)}}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())


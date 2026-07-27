"""
CLI smoke test for vision_module.analyze_visual_confidence.

Usage:
    python test_vision.py --video "path/to/video.mp4"
"""

from __future__ import annotations

import argparse
import json
import sys

from vision_module import analyze_visual_confidence


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the VSC visual-confidence pipeline on a local video file."
    )
    parser.add_argument(
        "--video",
        required=True,
        help="Path to a local video file (e.g. .mp4).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        result = analyze_visual_confidence(args.video)
    except Exception as error:  # top-level safety net for the CLI itself
        print(f"Unhandled exception: {type(error).__name__}: {error}", file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2, ensure_ascii=False))

    if result.get("status") == "failed":
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())

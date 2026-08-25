"""
cli/run_asr.py — Phase 7 ASR CLI: transcribe one answer-segment audio (or
video, extracted first) into a Format Spec v1.1 JSON file.

Usage:
    python -m interview_iq.cli.run_asr \\
        --audio-path tests/fixtures/audio/DA-001.wav \\
        --question-id DA-001 \\
        --output-path out/asr_DA-001.json

    python -m interview_iq.cli.run_asr \\
        --video-path recordings/DA-001.mp4 \\
        --question-id DA-001 \\
        --output-path out/asr_DA-001.json
        # extracts audio via ffmpeg first (audio.segmentation.extract_audio),
        # writing the intermediate WAV next to --output-path.

--device/--compute-type override configs/asr.yaml's baseline (CPU/int8) for
this call only — the config file itself is not modified (see
asr/engine.py's module docstring).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from interview_iq.asr.engine import ASRError, transcribe_audio
from interview_iq.audio.segmentation import AudioSegmentationError, extract_audio
from interview_iq.config import Config


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Phase 7: ASR transcription -> Format Spec v1.1 JSON (configs/asr.yaml)."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--audio-path", type=Path, help="Path to an existing mono 16kHz WAV.")
    source.add_argument("--video-path", type=Path, help="Path to a video file; audio is extracted via ffmpeg first.")
    parser.add_argument("--question-id", type=str, default=None)
    parser.add_argument("--output-path", type=Path, required=True, help="Where to write the Format Spec v1.1 JSON.")
    parser.add_argument(
        "--device", type=str, default=None,
        help="Override configs/asr.yaml's model.device for this call only (e.g. 'cuda' on Kaggle).",
    )
    parser.add_argument(
        "--compute-type", type=str, default=None,
        help="Override configs/asr.yaml's model.compute_type for this call only (e.g. 'float16' on GPU).",
    )
    parser.add_argument("--configs-dir", type=Path, default=None)
    args = parser.parse_args(argv)

    cfg = Config(configs_dir=args.configs_dir)

    audio_path = args.audio_path
    if args.video_path is not None:
        extracted_path = args.output_path.with_name(args.output_path.stem + "_audio.wav")
        print(f"[run_asr] Extracting audio: {args.video_path} -> {extracted_path}")
        try:
            audio_path = extract_audio(args.video_path, extracted_path)
        except AudioSegmentationError as exc:
            print(f"[run_asr] Audio extraction failed: {exc}", file=sys.stderr)
            return 1

    try:
        record = transcribe_audio(
            audio_path,
            config=cfg,
            device_override=args.device,
            compute_type_override=args.compute_type,
            question_id=args.question_id,
        )
    except ASRError as exc:
        print(f"[run_asr] ASR failed: {exc}", file=sys.stderr)
        return 1

    args.output_path.parent.mkdir(parents=True, exist_ok=True)
    with args.output_path.open("w", encoding="utf-8") as fh:
        json.dump(record, fh, ensure_ascii=False, indent=2)

    print(f"[run_asr] status={record['status']!r} -> wrote {args.output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

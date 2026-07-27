"""
audio/segmentation.py — Phase 7 audio extraction + VAD gating for the ASR module.

Two independent responsibilities:
  1. extract_audio: ffmpeg video -> mono 16kHz WAV (the format asr/engine.py
     and Silero VAD both expect, per configs/asr.yaml).
  2. run_vad: Silero VAD (loaded via torch.hub, per configs/asr.yaml's
     `vad.source: "silero_vad"`) gates each answer segment into
     ok/no_speech/too_short BEFORE asr/engine.py runs faster-whisper on it —
     "status ... decided by VAD, before the ASR" (configs/asr.yaml).

Model loading is lazy and injectable, matching retrieval/chunk_cap.py's
BgeM3Embedder convention: SileroVad does not call torch.hub.load until
.get_speech_timestamps() is first invoked, and run_vad() accepts a
`backend: VadBackend` for tests to inject a fake implementation — no test in
this repo ever downloads a real Silero VAD model or touches the network.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from interview_iq.config import Config

_DEFAULT_SAMPLING_RATE = 16000


class AudioSegmentationError(RuntimeError):
    """Raised when ffmpeg audio extraction fails (missing input, missing
    ffmpeg executable, non-zero exit, or no output file produced)."""


def extract_audio(video_path: Path, output_path: Path) -> Path:
    """Extract mono 16kHz PCM WAV audio from a video file via ffmpeg.

    Runs ffmpeg as an explicit argv list (no shell=True — no shell-injection
    surface from a caller-supplied path). Raises AudioSegmentationError on
    any failure instead of returning a partial/invalid file silently.
    """
    video_path = Path(video_path)
    output_path = Path(output_path)

    if not video_path.is_file():
        raise AudioSegmentationError(f"Video file not found: {video_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg",
        "-y",  # overwrite output_path without an interactive prompt
        "-i", str(video_path),
        "-vn",  # no video stream in the output
        "-ac", "1",  # mono
        "-ar", str(_DEFAULT_SAMPLING_RATE),  # 16kHz
        "-acodec", "pcm_s16le",  # uncompressed 16-bit PCM WAV
        str(output_path),
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except FileNotFoundError as exc:
        raise AudioSegmentationError(
            "ffmpeg executable not found on PATH — install ffmpeg to extract audio."
        ) from exc

    if result.returncode != 0:
        raise AudioSegmentationError(
            f"ffmpeg extraction failed (exit {result.returncode}) for {video_path} -> {output_path}: "
            f"{result.stderr[-2000:]}"
        )
    if not output_path.is_file():
        raise AudioSegmentationError(
            f"ffmpeg reported success but produced no output file: {output_path}"
        )
    return output_path


class VadBackend(Protocol):
    """Anything with a `.get_speech_timestamps(...)` method returning a list
    of {"start": <sample index>, "end": <sample index>} dicts at the given
    sampling_rate — the real Silero VAD utils.get_speech_timestamps return
    shape. Tests inject a fake implementation; production uses SileroVad."""

    def get_speech_timestamps(
        self,
        audio_path: Path,
        sampling_rate: int,
        threshold: float,
        max_speech_duration_s: float,
    ) -> list[dict[str, int]]: ...


class SileroVad:
    """Lazy, real Silero VAD backend (production path), loaded via
    torch.hub per configs/asr.yaml's `vad.source: "silero_vad"`.

    Not loaded until `.get_speech_timestamps()` is first called, so this
    class can be default-constructed anywhere (e.g. as run_vad's default
    argument) without ever downloading anything unless real VAD actually
    runs — same laziness convention as retrieval/chunk_cap.py's
    BgeM3Embedder and asr/engine.py's FasterWhisperBackend.
    """

    def __init__(self) -> None:
        self._model: Any = None
        self._utils: Any = None

    def _ensure_loaded(self) -> None:
        if self._model is None:
            import torch  # heavy import deferred to first use

            print("[audio.segmentation] Loading Silero VAD via torch.hub ...")
            self._model, self._utils = torch.hub.load(
                repo_or_dir="snakers4/silero-vad", model="silero_vad"
            )

    def get_speech_timestamps(
        self,
        audio_path: Path,
        sampling_rate: int = _DEFAULT_SAMPLING_RATE,
        threshold: float = 0.5,
        max_speech_duration_s: float = 30.0,
    ) -> list[dict[str, int]]:
        self._ensure_loaded()
        get_speech_timestamps_fn, _save_audio, read_audio, _vad_iterator, _collect_chunks = self._utils
        waveform = read_audio(str(audio_path), sampling_rate=sampling_rate)
        return get_speech_timestamps_fn(
            waveform,
            self._model,
            sampling_rate=sampling_rate,
            threshold=threshold,
            max_speech_duration_s=max_speech_duration_s,
        )


@dataclass(frozen=True)
class VadResult:
    status: str  # "ok" | "no_speech" | "too_short" — configs/asr.yaml's status enum
    vad_features: dict[str, Any]


def run_vad(
    audio_path: Path,
    config: Config | None = None,
    backend: VadBackend | None = None,
) -> VadResult:
    """Runs Silero VAD on the raw waveform and classifies the segment per
    configs/asr.yaml's vad thresholds:
      - no speech segments detected at all -> status="no_speech"
      - total speech duration < vad.min_speech_duration_ms -> status="too_short"
      - otherwise -> status="ok"

    vad_features carries the raw segment list (start/end in ms) and the
    total speech duration, straight from Silero's own output — NOT derived
    from faster-whisper's timestamps (configs/asr.yaml: "Silero VAD on raw
    waveform — NOT from Whisper timestamps").
    """
    cfg = config or Config()
    vad_cfg = cfg.asr["vad"]
    backend = backend or SileroVad()

    timestamps = backend.get_speech_timestamps(
        Path(audio_path),
        sampling_rate=_DEFAULT_SAMPLING_RATE,
        threshold=float(vad_cfg["threshold"]),
        max_speech_duration_s=float(vad_cfg["max_speech_duration_s"]),
    )

    segments_ms = [
        {
            "start_ms": round(seg["start"] / _DEFAULT_SAMPLING_RATE * 1000, 3),
            "end_ms": round(seg["end"] / _DEFAULT_SAMPLING_RATE * 1000, 3),
        }
        for seg in timestamps
    ]
    total_speech_ms = sum(s["end_ms"] - s["start_ms"] for s in segments_ms)

    vad_features: dict[str, Any] = {
        "segments": segments_ms,
        "total_speech_duration_ms": round(total_speech_ms, 3),
        "threshold": vad_cfg["threshold"],
    }

    if not segments_ms:
        return VadResult(status="no_speech", vad_features=vad_features)
    if total_speech_ms < float(vad_cfg["min_speech_duration_ms"]):
        return VadResult(status="too_short", vad_features=vad_features)
    return VadResult(status="ok", vad_features=vad_features)

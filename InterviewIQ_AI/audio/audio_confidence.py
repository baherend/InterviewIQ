"""Deterministic vocal-delivery features; no emotion inference is performed."""
from __future__ import annotations

import math
import re
import wave
from pathlib import Path
from typing import Any

import numpy as np

from fusion.confidence_config import AUDIO_CONFIDENCE_CONFIG, AudioConfidenceConfig


def _clamp(value: float) -> float:
    return float(max(0.0, min(1.0, value)))


def _range_score(value: float, acceptable_low: float, ideal_low: float,
                 ideal_high: float, acceptable_high: float) -> float:
    if ideal_low <= value <= ideal_high:
        return 1.0
    if value < ideal_low:
        return _clamp((value - acceptable_low) / (ideal_low - acceptable_low))
    return _clamp((acceptable_high - value) / (acceptable_high - ideal_high))


def _read_wav(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as wav:
        rate, channels, width = wav.getframerate(), wav.getnchannels(), wav.getsampwidth()
        raw = wav.readframes(wav.getnframes())
    if width != 2:
        raise ValueError("Confidence extraction supports PCM 16-bit WAV audio.")
    samples = np.frombuffer(raw, dtype="<i2").astype(np.float64) / 32768.0
    if channels > 1:
        samples = samples.reshape(-1, channels).mean(axis=1)
    return samples, rate


def calculate_audio_confidence(
    audio_path: str | Path,
    transcript: str | None = None,
    *,
    config: AudioConfidenceConfig = AUDIO_CONFIDENCE_CONFIG,
) -> dict[str, Any]:
    warnings: list[str] = []
    empty = {
        "speaking_rate_wpm": None, "speaking_rate_score": None,
        "pause_ratio": None, "pause_control_score": None,
        "volume_stability_score": None, "speech_continuity_score": None,
        "vocal_confidence_score": None, "sufficient_evidence": False,
        "warnings": warnings,
    }
    try:
        samples, rate = _read_wav(Path(audio_path))
        duration = len(samples) / rate if rate > 0 else 0.0
        if duration <= 0:
            warnings.append("Audio duration is zero.")
            return empty
        if duration < config.minimum_duration_seconds:
            warnings.append("Audio is too short for reliable vocal delivery scoring.")

        frame = max(1, round(rate * config.frame_ms / 1000))
        hop = max(1, round(rate * config.hop_ms / 1000))
        starts = range(0, max(len(samples) - frame + 1, 1), hop)
        rms = np.asarray([
            math.sqrt(float(np.mean(np.square(samples[s:s + frame]))))
            for s in starts if len(samples[s:s + frame])
        ])
        peak = float(np.percentile(rms, 90)) if rms.size else 0.0
        if peak <= 1e-9:
            warnings.append("Audio contains no measurable speech energy.")
            return empty
        threshold = max(config.silence_absolute_rms, peak * config.silence_relative_rms)
        speech = rms > threshold
        if not speech.any():
            warnings.append("No frames exceeded the configured speech-energy threshold.")
        pause_ratio = float(1.0 - speech.mean())
        pause_score = _range_score(
            pause_ratio, 0.0, config.ideal_pause_ratio_low,
            config.ideal_pause_ratio_high, config.maximum_pause_ratio,
        )
        voiced_rms = rms[speech]
        mean_voiced = float(voiced_rms.mean()) if voiced_rms.size else 0.0
        cv = float(voiced_rms.std() / mean_voiced) if mean_voiced > 1e-12 else math.inf
        volume_score = _clamp(
            (config.volume_cv_poor - cv) /
            (config.volume_cv_poor - config.volume_cv_good)
        )
        transitions = np.diff(np.r_[False, speech, False].astype(np.int8))
        starts_i, ends_i = np.flatnonzero(transitions == 1), np.flatnonzero(transitions == -1)
        segment_durations = (ends_i - starts_i) * config.hop_ms / 1000
        voiced_ratio = float(speech.mean())
        mean_segment = float(segment_durations.mean()) if segment_durations.size else 0.0
        continuity = _clamp(
            0.5 * voiced_ratio +
            0.5 * min(mean_segment / config.continuity_target_segment_seconds, 1.0)
        )

        words = re.findall(r"\b[\w'-]+\b", transcript or "", re.UNICODE)
        wpm = len(words) / (duration / 60.0) if words else None
        rate_score = (
            _range_score(wpm, config.acceptable_wpm_low, config.ideal_wpm_low,
                         config.ideal_wpm_high, config.acceptable_wpm_high)
            if wpm is not None else None
        )
        if not words:
            warnings.append("Transcript is missing; speaking rate cannot be scored.")

        sufficient = (
            duration >= config.minimum_duration_seconds
            and len(words) >= config.minimum_words and bool(speech.any())
        )
        score = None
        if sufficient:
            score = 100.0 * (
                config.weights["speaking_rate"] * rate_score
                + config.weights["pause_control"] * pause_score
                + config.weights["volume_stability"] * volume_score
                + config.weights["speech_continuity"] * continuity
            )
        return {
            "speaking_rate_wpm": round(wpm, 3) if wpm is not None else None,
            "speaking_rate_score": round(rate_score, 4) if rate_score is not None else None,
            "pause_ratio": round(pause_ratio, 4),
            "pause_control_score": round(pause_score, 4),
            "volume_stability_score": round(volume_score, 4),
            "speech_continuity_score": round(continuity, 4),
            "vocal_confidence_score": round(score, 3) if score is not None else None,
            "sufficient_evidence": sufficient, "warnings": warnings,
        }
    except Exception as exc:
        warnings.append(f"Audio confidence extraction failed: {type(exc).__name__}: {exc}")
        return empty

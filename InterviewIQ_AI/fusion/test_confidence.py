from __future__ import annotations

import sys
import tempfile
import unittest
import wave
from pathlib import Path

import numpy as np

FUSION_DIR = Path(__file__).resolve().parent
AI_DIR = FUSION_DIR.parent
for path in (FUSION_DIR, AI_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from audio.audio_confidence import calculate_audio_confidence
from confidence_fusion import fuse_confidence


def _wav(path: Path, seconds: float, *, silent: bool = False) -> None:
    rate = 16000
    count = int(rate * seconds)
    t = np.arange(count) / rate
    signal = np.zeros(count) if silent else 0.2 * np.sin(2 * np.pi * 220 * t)
    pcm = (signal * 32767).astype("<i2")
    with wave.open(str(path), "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(rate)
        target.writeframes(pcm.tobytes())


class AudioConfidenceTests(unittest.TestCase):
    def test_normal_audio_and_score_range(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "normal.wav"
            _wav(path, 10)
            result = calculate_audio_confidence(path, " ".join(["word"] * 22))
        self.assertTrue(result["sufficient_evidence"])
        self.assertGreaterEqual(result["vocal_confidence_score"], 0)
        self.assertLessEqual(result["vocal_confidence_score"], 100)

    def test_silent_audio(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "silent.wav"
            _wav(path, 2, silent=True)
            result = calculate_audio_confidence(path, "some words")
        self.assertFalse(result["sufficient_evidence"])
        self.assertIsNone(result["vocal_confidence_score"])

    def test_very_short_audio(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "short.wav"
            _wav(path, 0.2)
            result = calculate_audio_confidence(path, "word")
        self.assertFalse(result["sufficient_evidence"])

    def test_missing_transcript(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "normal.wav"
            _wav(path, 2)
            result = calculate_audio_confidence(path, None)
        self.assertIsNone(result["speaking_rate_wpm"])
        self.assertIsNone(result["vocal_confidence_score"])

    def test_zero_duration(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "zero.wav"
            _wav(path, 0)
            result = calculate_audio_confidence(path, "word")
        self.assertFalse(result["sufficient_evidence"])
        self.assertIsNone(result["vocal_confidence_score"])


class FusionConfidenceTests(unittest.TestCase):
    def test_both(self):
        self.assertEqual(fuse_confidence(80, 50)["final_confidence_score"], 68)

    def test_only_audio(self):
        result = fuse_confidence(80, 55, visual_sufficient_evidence=False)
        self.assertEqual(result["final_confidence_score"], 80)
        self.assertEqual(result["confidence_evidence_status"], "partial")
        self.assertEqual(result["effective_weights"], {"vocal": 1.0, "visual": 0.0})
        self.assertIn(
            "Visual confidence was excluded because visual evidence was insufficient.",
            result["warnings"],
        )

    def test_only_vision(self):
        result = fuse_confidence(75, 70, vocal_sufficient_evidence=False)
        self.assertEqual(result["final_confidence_score"], 70)
        self.assertEqual(result["effective_weights"], {"vocal": 0.0, "visual": 1.0})

    def test_neither(self):
        result = fuse_confidence(
            80, 70, vocal_sufficient_evidence=False,
            visual_sufficient_evidence=False,
        )
        self.assertIsNone(result["final_confidence_score"])
        self.assertEqual(result["confidence_evidence_status"], "insufficient")

    def test_model_and_technical_confidence_are_ignored(self):
        baseline = fuse_confidence(80, 50)
        injected = fuse_confidence(
            80, 50, model_confidence=0.01, technical_score=100
        )
        self.assertEqual(baseline["final_confidence_score"], injected["final_confidence_score"])


if __name__ == "__main__":
    unittest.main()

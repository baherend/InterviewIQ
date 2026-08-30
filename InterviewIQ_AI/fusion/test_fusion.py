from __future__ import annotations
import json
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from adapters.base import run_json_component
from config import Settings
from fusion_pipeline import load_question, run_fusion


class FusionSmokeTests(unittest.TestCase):
    def test_reference_question_loading(self):
        doc = load_question(Settings().reference_json, "SE-028")
        self.assertEqual(doc["question_id"], "SE-028")
        self.assertTrue(doc["chunks"])

    def test_missing_question_id(self):
        with self.assertRaises(KeyError):
            load_question(Settings().reference_json, "DOES-NOT-EXIST")

    def test_invalid_component_json(self):
        with tempfile.TemporaryDirectory() as td:
            raw, execution = run_json_component(
                [sys.executable, "-c", "print('not-json')"], Path(td),
                dict(), 10)
        self.assertIsNone(raw)
        self.assertEqual(execution["error"]["type"], "InvalidComponentJSON")

    def test_missing_component_executable(self):
        with tempfile.TemporaryDirectory() as td:
            raw, execution = run_json_component(
                [str(Path(td) / "missing-python.exe")], Path(td), dict(), 10)
        self.assertIsNone(raw)
        self.assertEqual(execution["status"], "failed")

    @patch("fusion_pipeline.run_nlp")
    @patch("fusion_pipeline.run_audio")
    @patch("fusion_pipeline.run_vision")
    @patch("fusion_pipeline.extract_audio")
    def test_partial_status_and_output_creation(self, extract, vision, audio, nlp):
        extract.return_value = {"status": "completed"}
        vision.return_value = ({"status": "insufficient_evidence", "sufficient_evidence": False}, {"status": "completed"})
        audio.return_value = (None, {"status": "failed", "error": {"type": "Test", "message": "failure"}})
        nlp.return_value = ({"status": "SUCCESS", "score": 12.0, "asr": {"normalized_transcript": "unrelated"}},
                            {"status": "completed"})
        with tempfile.TemporaryDirectory() as td:
            temp_dir = Path(td)
            output = temp_dir / "result.json"
            placeholder_checkpoint = temp_dir / "placeholder.pt"
            placeholder_checkpoint.write_bytes(b"test-only-placeholder")
            nlp_env = temp_dir / ".env"
            nlp_env.write_text("GROQ_API_KEY=test-only-placeholder\n", encoding="utf-8")
            settings = replace(
                Settings(),
                vision_python=Path(sys.executable),
                audio_python=Path(sys.executable),
                nlp_python=Path(sys.executable),
                vision_checkpoint=placeholder_checkpoint,
                audio_checkpoint=placeholder_checkpoint,
                nlp_env_file=nlp_env,
            )

            result = run_fusion(temp_dir / "not-video.mp4", "SE-028", output, settings)
            # Replace the input-video preflight for a genuine temporary file.
            self.assertEqual(result["status"], "failed")
            video = temp_dir / "video.mp4"
            video.write_bytes(b"x")
            result = run_fusion(video, "SE-028", output, settings)
            self.assertEqual(result["status"], "partial")
            self.assertTrue(output.is_file())
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["status"], "partial")


if __name__ == "__main__":
    unittest.main()

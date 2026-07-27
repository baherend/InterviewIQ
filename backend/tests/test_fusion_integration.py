import unittest

from app.fusion_response import clean_fusion_response


class FusionResponseTests(unittest.TestCase):
    def test_negative_nlp_values_are_not_presented_as_percentages(self):
        raw = {
            "status": "success",
            "question_answer_match": {"valid": False, "reason": "Mismatch."},
            "technical_evaluation": {
                "status": "success",
                "score": -92.0,
                "precision": -0.92,
                "coverage": 0.01,
                "raw": {"asr": {"normalized_transcript": "unrelated answer"}},
            },
            "visual_analysis": {
                "status": "success",
                "predicted_emotion": "calm",
                "sufficient_evidence": False,
                "raw": {"confidence": 0.96},
            },
            "vocal_analysis": {
                "status": "success",
                "dominant_emotion": "Neutral Emotion",
                "model_confidence": 0.93,
            },
            "fusion_summary": {
                "final_technical_score": None,
                "technical_interpretation": "Technical score only.",
                "limitations": ["Human review required."],
            },
            "errors": [],
        }

        result = clean_fusion_response(raw, "SE-028")

        self.assertIsNone(result["nlp"]["technical_score"])
        self.assertIsNone(result["nlp"]["precision"])
        self.assertEqual(result["nlp"]["coverage"], 0.01)
        self.assertTrue(result["nlp"]["raw_values_withheld"])
        self.assertIsNone(result["fusion_summary"]["final_technical_score"])
        self.assertEqual(result["transcript"], "unrelated answer")
        self.assertEqual(result["vision"]["model_confidence"], 0.96)

    def test_missing_required_fusion_section_is_rejected(self):
        with self.assertRaises(ValueError):
            clean_fusion_response({"status": "success"}, "SE-028")


if __name__ == "__main__":
    unittest.main()

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
        self.assertIsNone(result["confidence"]["final_confidence_score"])

    def test_candidate_confidence_is_mapped_separately(self):
        raw = {
            "status": "success",
            "question_answer_match": {"valid": True, "reason": "Match."},
            "technical_evaluation": {"status": "success", "score": 91, "raw": {}},
            "visual_analysis": {"status": "success", "raw": {"confidence": .99}},
            "vocal_analysis": {"status": "success", "model_confidence": .98},
            "fusion_summary": {"final_technical_score": 91, "limitations": []},
            "confidence": {
                "vocal": {"vocal_confidence_score": 70},
                "visual": {"visual_confidence_score": 50},
                "final_confidence_score": 62,
                "confidence_evidence_status": "complete",
                "weights": {"vocal": .6, "visual": .4},
                "warnings": [],
            },
        }
        result = clean_fusion_response(raw, "SE-028")
        self.assertEqual(result["fusion_summary"]["final_technical_score"], 91)
        self.assertEqual(result["confidence"]["final_confidence_score"], 62)
        self.assertNotEqual(result["confidence"]["final_confidence_score"],
                            result["audio"]["model_confidence"])

    def test_missing_required_fusion_section_is_rejected(self):
        with self.assertRaises(ValueError):
            clean_fusion_response({"status": "success"}, "SE-028")

    def test_insufficient_visual_raw_score_and_details_are_preserved(self):
        raw = {
            "status": "partial",
            "question_answer_match": {"valid": True, "reason": "Match."},
            "technical_evaluation": {"status": "success", "score": 80, "raw": {}},
            "visual_analysis": {"status": "success", "raw": {"confidence": .9}},
            "vocal_analysis": {"status": "success", "model_confidence": .8},
            "fusion_summary": {"final_technical_score": 80, "limitations": []},
            "confidence": {
                "vocal": {"vocal_confidence_score": 70, "sufficient_evidence": True},
                "visual": {
                    "visual_behavioral_confidence_score": 25.85,
                    "visual_confidence_score": 25.85,
                    "visual_confidence_level": "insufficient_evidence",
                    "sufficient_evidence": False,
                    "number_of_windows": 1,
                    "confidence_margin": 2.0,
                    "score_range": {"low": 23.85, "high": 27.85},
                    "visual_reliability": .8667,
                },
                "final_confidence_score": 70,
                "confidence_evidence_status": "partial",
                "effective_weights": {"vocal": 1.0, "visual": 0.0},
                "warnings": [
                    "Visual confidence was excluded because visual evidence was insufficient."
                ],
            },
        }
        result = clean_fusion_response(raw, "SE-028")
        self.assertEqual(result["visual_behavioral_confidence_score"], 25.85)
        self.assertEqual(
            result["confidence"]["visual"]["visual_confidence_level"],
            "insufficient_evidence",
        )
        self.assertEqual(result["final_confidence_score"], 70)
        self.assertEqual(
            result["confidence"]["effective_weights"],
            {"vocal": 1.0, "visual": 0.0},
        )


if __name__ == "__main__":
    unittest.main()

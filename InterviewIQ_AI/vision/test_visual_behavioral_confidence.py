from __future__ import annotations

import unittest

import numpy as np

from visual_behavioral_confidence import (
    VisualConfidenceConfig,
    calculate_calm_recovery,
    calculate_comfort_signal,
    calculate_emotion_stability,
    calculate_negative_affect,
    calculate_negative_affect_persistence,
    calculate_visual_confidence_summary,
    calculate_visual_reliability,
    visual_confidence_level,
)


def window(
    *,
    neutral=.10, calm=.10, happy=.10, sad=.10,
    angry=.10, fearful=.10, disgust=.10, surprised=.30,
    face=1.0,
):
    return {
        "prob_neutral": neutral, "prob_calm": calm, "prob_happy": happy,
        "prob_sad": sad, "prob_angry": angry, "prob_fearful": fearful,
        "prob_disgust": disgust, "prob_surprised": surprised,
        "face_detection_ratio": face,
    }


class VisualBehavioralConfidenceTests(unittest.TestCase):
    def test_comfort_is_raw_sum(self):
        result = calculate_comfort_signal([window(calm=.2, neutral=.3, happy=.1)])
        self.assertAlmostEqual(result["comfort_signal"], .6)

    def test_negative_affect_is_raw_sum(self):
        result = calculate_negative_affect([
            window(sad=.1, disgust=.2, fearful=.3, angry=.1)
        ])
        self.assertAlmostEqual(float(result[0]), .7)

    def test_stability_uses_total_variation(self):
        first = window(neutral=1, calm=0, happy=0, sad=0, angry=0,
                       fearful=0, disgust=0, surprised=0)
        second = window(neutral=0, calm=1, happy=0, sad=0, angry=0,
                        fearful=0, disgust=0, surprised=0)
        result = calculate_emotion_stability([first, second])
        self.assertAlmostEqual(result["mean_transition_distance"], 1.0)
        self.assertAlmostEqual(result["emotion_stability"], 0.0)

    def test_one_window_stable_but_insufficient(self):
        summary = calculate_visual_confidence_summary([window()])
        self.assertEqual(summary["metrics"]["emotion_stability"], 1.0)
        self.assertFalse(summary["sufficient_evidence"])

    def test_persistence_formula_and_longest_streak(self):
        rows = [
            window(sad=.3, angry=0, fearful=0, disgust=0),
            window(sad=.3, angry=0, fearful=0, disgust=0),
            window(sad=.1, angry=0, fearful=0, disgust=0),
        ]
        result = calculate_negative_affect_persistence(rows)
        expected = .5 * (.7 / 3) + .25 * (2 / 3) + .25 * (2 / 3)
        self.assertAlmostEqual(result["negative_affect_persistence"], expected)
        self.assertEqual(result["longest_negative_affect_streak_windows"], 2)

    def test_recovery_no_episode(self):
        result = calculate_calm_recovery([
            window(sad=.1, angry=0, fearful=0, disgust=0)
        ])
        self.assertEqual(result["calm_recovery"], 1.0)

    def test_recovery_success_and_failure(self):
        episode = window(calm=.05, neutral=.05, sad=.5, angry=0,
                         fearful=0, disgust=0)
        recovered = window(calm=.5, neutral=.1, sad=.1, angry=0,
                           fearful=0, disgust=0)
        failed = window(calm=.1, neutral=.1, sad=.4, angry=0,
                        fearful=0, disgust=0)
        self.assertEqual(calculate_calm_recovery([episode, recovered])["calm_recovery"], 1)
        self.assertEqual(calculate_calm_recovery([episode, failed])["calm_recovery"], 0)

    def test_reliability_formula(self):
        result = calculate_visual_reliability([window(face=.5), window(face=.5)])
        self.assertAlmostEqual(result["visual_reliability"], .8 * .5 + .2 * (2 / 3))

    def test_base_score_margin_evidence_and_level(self):
        rows = [window(face=1.0) for _ in range(3)]
        result = calculate_visual_confidence_summary(rows)
        metrics = result["metrics"]
        expected = 100 * (
            .35 * metrics["comfort_signal"]
            + .25 * metrics["emotion_stability"]
            + .20 * metrics["calm_recovery"]
            + .20 * (1 - metrics["negative_affect_persistence"])
        )
        self.assertAlmostEqual(result["visual_behavioral_confidence_score"], expected)
        self.assertAlmostEqual(result["confidence_margin"], 0.0)
        self.assertTrue(result["sufficient_evidence"])

        low_faces = calculate_visual_confidence_summary(
            [window(face=.59) for _ in range(3)]
        )
        self.assertFalse(low_faces["sufficient_evidence"])
        self.assertFalse(low_faces["evidence_checks"]["enough_faces"])
        self.assertEqual(low_faces["visual_confidence_level"], "insufficient_evidence")

    def test_confidence_margin(self):
        config = VisualConfidenceConfig()
        rows = [window(face=.5) for _ in range(3)]
        reliability = calculate_visual_reliability(rows, config)["visual_reliability"]
        result = calculate_visual_confidence_summary(rows, config=config)
        self.assertAlmostEqual(result["confidence_margin"], (1 - reliability) * 15)

    def test_levels(self):
        self.assertEqual(visual_confidence_level(99, False), "insufficient_evidence")
        self.assertEqual(visual_confidence_level(75, True), "high")
        self.assertEqual(visual_confidence_level(50, True), "moderate")
        self.assertEqual(visual_confidence_level(49.99, True), "low")

    def test_config_validation(self):
        with self.assertRaises(ValueError):
            VisualConfidenceConfig(minimum_windows_for_decision=0).validate()
        with self.assertRaises(ValueError):
            VisualConfidenceConfig(minimum_face_detection_ratio=1.1).validate()


if __name__ == "__main__":
    unittest.main()

import unittest
from backend.services.prediction_presenter import prediction_presenter


class TestNoUncertainPresentation(unittest.TestCase):
    def test_low_margin_does_not_return_uncertain_label(self):
        # Even with tight margin (e.g. 1% difference)
        analysis = {
            "predicted_skin_type": "Normal",
            "confidence_percentage": 36.0,
            "confidence_level": "calibrated_best_match",
            "top_two_margin_percentage": 1.5,
            "probabilities": [
                {"skin_type": "Normal", "percentage": 36.0},
                {"skin_type": "Combination", "percentage": 34.5},
            ],
            "uncertainty_flag": False,
        }
        presentation = prediction_presenter.present_skin_type(analysis)
        self.assertEqual(presentation["label"], "Normal")
        self.assertNotEqual(presentation["label"], "Uncertain")
        self.assertIn("Normal", presentation["headline"])

    def test_complete_presentation_build_has_no_uncertain_label(self):
        skin_type = {
            "predicted_skin_type": "Dry",
            "confidence_percentage": 42.0,
            "confidence_level": "calibrated_best_match",
            "top_two_margin_percentage": 4.0,
            "probabilities": [
                {"skin_type": "Dry", "percentage": 42.0},
                {"skin_type": "Normal", "percentage": 38.0},
            ],
            "uncertainty_flag": False,
        }
        concerns = {
            "concerns": [
                {"id": "acne", "name": "Acne / Blemishes", "score": 0.35, "threshold": 0.40, "status": "not_detected"},
                {"id": "redness", "name": "Redness", "score": 0.52, "threshold": 0.45, "status": "detected"},
            ]
        }
        skin_tone = {
            "complexion": "Medium Light",
            "fitzpatrick_scale": "Type III",
            "undertone": "Warm",
            "display_label": "Medium Light (Warm Undertone)",
            "representative_hex": "#d4a373",
        }
        result = prediction_presenter.build(skin_type, concerns, skin_tone)
        self.assertEqual(result["skin_type"]["label"], "Dry")
        self.assertEqual(result["skin_tone"]["complexion"], "Medium Light")
        self.assertEqual(len(result["needs_recheck"]), 0)
        self.assertIn("Dry", result["summary"])
        self.assertNotIn("Uncertain", result["summary"])


if __name__ == "__main__":
    unittest.main()

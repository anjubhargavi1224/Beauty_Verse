import unittest

from backend.services.prediction_presenter import PredictionPresenter
from ml.evaluation.evaluate_selfies import LABELS, summarize


class PredictionReportingTests(unittest.TestCase):
    def test_uncertain_skin_type_is_not_presented_as_combination(self):
        result = PredictionPresenter().build({
            "predicted_skin_type": "Combination", "uncertainty_flag": True,
            "confidence_level": "uncertain", "probabilities": [],
        }, {"concerns": []})
        self.assertEqual(result["skin_type"]["label"], "Uncertain")
        self.assertNotIn("matches Uncertain skin", result["summary"])
        self.assertNotIn("Combination skin", result["skin_type"]["headline"])

    def test_empty_evaluation_does_not_claim_perfect_accuracy(self):
        result = summarize([])
        self.assertIsNone(result["skin_type"]["top1_accuracy"])
        self.assertIsNone(result["concerns"]["acne"]["precision"])

    def test_unknown_labels_and_abstentions_are_not_negative_labels(self):
        records = []
        for truth, status in [("1", "detected"), ("0", "detected"), ("1", "uncertain"), ("", "detected")]:
            records.append({
                "status": "analyzed", "truth": {"acne": truth},
                "concerns": {label: {"status": status} for label in LABELS},
            })
        result = summarize(records)["concerns"]["acne"]
        self.assertEqual(result["known"], 3)
        self.assertEqual(result["precision"], 0.5)
        self.assertEqual(result["detection_recall"], 0.5)
        self.assertEqual(result["false_positive_rate"], 1.0)
        self.assertEqual(result["uncertain"], 1)


if __name__ == "__main__":
    unittest.main()

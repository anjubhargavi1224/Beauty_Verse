import unittest
from backend.services.skin_concern_classifier import SkinConcernClassifierService


class TestSkinConcernRegionalValidation(unittest.TestCase):
    def setUp(self):
        self.service = SkinConcernClassifierService()

    def test_blush_suppression_for_redness(self):
        # Simulated cheek blush: left/right cheeks have high erythema, but forehead & chin have near zero
        regions_data = {
            "regions": {
                "forehead": {"metrics": {"erythema_index": 0.04}},
                "chin": {"metrics": {"erythema_index": 0.03}},
                "left_cheek": {"metrics": {"erythema_index": 0.35}},
                "right_cheek": {"metrics": {"erythema_index": 0.32}},
            },
            "regional_summary": {"average_erythema_index": 0.12},
        }
        # Raw score near threshold
        status, calibrated_score, rationale = self.service.validate_concern_with_regions(
            "redness", raw_score=0.48, threshold=0.45, regions_data=regions_data
        )
        self.assertEqual(status, "not_detected")
        self.assertLess(calibrated_score, 0.45)
        self.assertIn("blush", rationale.lower())

    def test_true_redness_confirmation(self):
        # Widespread erythema across forehead, chin, and cheeks
        regions_data = {
            "regions": {
                "forehead": {"metrics": {"erythema_index": 0.25}},
                "chin": {"metrics": {"erythema_index": 0.22}},
                "left_cheek": {"metrics": {"erythema_index": 0.30}},
                "right_cheek": {"metrics": {"erythema_index": 0.28}},
            },
            "regional_summary": {"average_erythema_index": 0.26},
        }
        status, calibrated_score, rationale = self.service.validate_concern_with_regions(
            "redness", raw_score=0.42, threshold=0.45, regions_data=regions_data
        )
        self.assertEqual(status, "detected")
        self.assertGreaterEqual(calibrated_score, 0.45)
        self.assertIn("elevated regional erythema", rationale.lower())

    def test_smooth_skin_suppresses_false_wrinkles(self):
        # Smooth skin under-eye and forehead (camera noise or jpeg edge artifact in raw model)
        regions_data = {
            "regions": {
                "under_eye": {"metrics": {"texture_roughness": 0.12}},
                "forehead": {"metrics": {"texture_roughness": 0.14}},
            },
            "regional_summary": {},
        }
        status, calibrated_score, rationale = self.service.validate_concern_with_regions(
            "wrinkles", raw_score=0.48, threshold=0.45, regions_data=regions_data
        )
        self.assertEqual(status, "not_detected")
        self.assertIn("smooth", rationale.lower())

    def test_binary_status_no_uncertain_string(self):
        regions_data = {
            "regions": {
                "nose": {"metrics": {"texture_roughness": 0.38}},
            },
            "regional_summary": {},
        }
        for score in [0.44, 0.45, 0.46, 0.48]:
            status, _, _ = self.service.validate_concern_with_regions(
                "pores", raw_score=score, threshold=0.45, regions_data=regions_data
            )
            self.assertIn(status, ["detected", "not_detected"])
            self.assertNotEqual(status, "uncertain")


if __name__ == "__main__":
    unittest.main()

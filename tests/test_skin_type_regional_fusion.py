import unittest
from backend.services.skin_type_classifier import SkinTypeClassifierService


class TestSkinTypeRegionalFusion(unittest.TestCase):
    def setUp(self):
        self.service = SkinTypeClassifierService()

    def test_oily_regional_calibration(self):
        raw_probs = {"Combination": 0.45, "Oily": 0.35, "Dry": 0.10, "Normal": 0.10}
        # Elevated shine in BOTH T-Zone and Cheeks
        regional_summary = {
            "tzone_shine_index": 0.42,
            "uzone_shine_index": 0.38,
            "shine_divergence": 0.04,
            "average_texture_roughness": 0.18,
        }
        calibrated = self.service.calibrate_with_regional_evidence(raw_probs, regional_summary)
        self.assertGreater(calibrated["Oily"], calibrated["Combination"])

    def test_combination_regional_calibration(self):
        raw_probs = {"Combination": 0.35, "Normal": 0.35, "Oily": 0.20, "Dry": 0.10}
        # High shine in T-Zone, but matte cheeks -> divergence > 0.12
        regional_summary = {
            "tzone_shine_index": 0.35,
            "uzone_shine_index": 0.14,
            "shine_divergence": 0.21,
            "average_texture_roughness": 0.20,
        }
        calibrated = self.service.calibrate_with_regional_evidence(raw_probs, regional_summary)
        self.assertGreater(calibrated["Combination"], calibrated["Normal"])
        self.assertGreater(calibrated["Combination"], calibrated["Oily"])

    def test_dry_regional_calibration(self):
        raw_probs = {"Combination": 0.40, "Dry": 0.30, "Normal": 0.20, "Oily": 0.10}
        # Very low shine everywhere, high surface roughness/texture
        regional_summary = {
            "tzone_shine_index": 0.10,
            "uzone_shine_index": 0.08,
            "shine_divergence": 0.02,
            "average_texture_roughness": 0.45,
        }
        calibrated = self.service.calibrate_with_regional_evidence(raw_probs, regional_summary)
        self.assertGreater(calibrated["Dry"], calibrated["Combination"])

    def test_normal_regional_calibration(self):
        raw_probs = {"Combination": 0.35, "Normal": 0.35, "Dry": 0.15, "Oily": 0.15}
        # Balanced, moderate shine, smooth texture
        regional_summary = {
            "tzone_shine_index": 0.22,
            "uzone_shine_index": 0.20,
            "shine_divergence": 0.02,
            "average_texture_roughness": 0.15,
        }
        calibrated = self.service.calibrate_with_regional_evidence(raw_probs, regional_summary)
        self.assertGreater(calibrated["Normal"], calibrated["Combination"])


if __name__ == "__main__":
    unittest.main()

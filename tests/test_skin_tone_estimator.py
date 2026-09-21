import unittest
import numpy as np
from backend.services.skin_tone_estimator import SkinToneEstimatorService, skin_tone_estimator


class TestSkinToneEstimator(unittest.TestCase):
    def setUp(self):
        self.service = SkinToneEstimatorService()

    def test_fair_skin_tone_estimation(self):
        # Create a synthetic fair/light skin patch (BGR: light peachy tone)
        # High L*, low to moderate b* -> Type I or II
        fair_bgr = np.full((100, 100, 3), [190, 215, 245], dtype=np.uint8)
        result = self.service.estimate(fair_bgr, landmarks=[])
        self.assertIn(result["fitzpatrick_scale"], ["Type I", "Type II"])
        self.assertIn(result["complexion"], ["Very Fair", "Fair"])
        self.assertGreater(result["ita_degrees"], 40.0)
        self.assertIn("color_metrics", result)
        self.assertTrue(result["color_metrics"]["representative_hex"].startswith("#"))

    def test_medium_olive_skin_tone_estimation(self):
        # Medium skin patch (BGR: [100, 150, 190])
        med_bgr = np.full((100, 100, 3), [100, 150, 190], dtype=np.uint8)
        result = self.service.estimate(med_bgr, landmarks=[])
        self.assertIn(result["fitzpatrick_scale"], ["Type III", "Type IV"])
        self.assertIn(result["complexion"], ["Medium Light", "Medium"])
        self.assertGreaterEqual(result["ita_degrees"], 10.0)

    def test_deep_skin_tone_estimation(self):
        # Deep skin patch (BGR: [40, 55, 80])
        deep_bgr = np.full((100, 100, 3), [40, 55, 80], dtype=np.uint8)
        result = self.service.estimate(deep_bgr, landmarks=[])
        self.assertIn(result["fitzpatrick_scale"], ["Type V", "Type VI"])
        self.assertIn(result["complexion"], ["Tan / Deep Medium", "Deep / Rich"])
        self.assertLess(result["ita_degrees"], 10.0)

    def test_safe_landmark_sampling(self):
        # Mock image and landmarks
        img = np.full((200, 200, 3), [120, 160, 200], dtype=np.uint8)
        class DummyLM:
            def __init__(self, x, y):
                self.x = x
                self.y = y

        landmarks = [DummyLM(0.5, 0.5) for _ in range(468)]
        patches = self.service.sample_skin_patches(img, landmarks)
        self.assertGreater(len(patches), 0)

    def test_empty_or_invalid_image_fallback(self):
        # Should not crash on empty image
        empty_img = np.zeros((0, 0, 3), dtype=np.uint8)
        result = self.service.estimate(empty_img, landmarks=[])
        self.assertIn("complexion", result)
        self.assertIn("fitzpatrick_scale", result)


if __name__ == "__main__":
    unittest.main()

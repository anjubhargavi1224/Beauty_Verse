import unittest
from backend.services.ai_skincare_planner import ai_skincare_planner
from backend.services.recommendation_engine import recommendation_engine


class TestSkincarePlannerDynamic(unittest.TestCase):
    def test_dry_skin_routine_and_ingredients(self):
        skin_type = {"predicted_skin_type": "Dry", "confidence_percentage": 70.0}
        concerns = {"concerns": [{"id": "acne", "status": "not_detected"}]}
        tone = {"complexion": "Fair", "fitzpatrick_scale": "Type II", "undertone": "Cool"}
        plan = ai_skincare_planner.generate(skin_type, concerns, tone)

        self.assertIn("dry", plan["skin_profile"].lower())
        # Dry skin should prioritize hydrating ingredients (Ceramides, Hyaluronic acid)
        ingredient_names = [i["name"] for i in plan["recommended_ingredients"]]
        self.assertTrue(any("ceramide" in n.lower() or "hyaluronic" in n.lower() for n in ingredient_names))
        # Routine steps exist
        self.assertGreaterEqual(len(plan["routine"]["morning"]), 3)
        self.assertGreaterEqual(len(plan["routine"]["evening"]), 2)

    def test_oily_skin_routine_and_ingredients(self):
        skin_type = {"predicted_skin_type": "Oily", "confidence_percentage": 75.0}
        concerns = {"concerns": [{"id": "acne", "status": "detected"}]}
        tone = {"complexion": "Medium", "fitzpatrick_scale": "Type III", "undertone": "Neutral"}
        plan = ai_skincare_planner.generate(skin_type, concerns, tone)

        self.assertIn("oily", plan["skin_profile"].lower())
        ingredient_names = [i["name"] for i in plan["recommended_ingredients"]]
        self.assertTrue(any("niacinamide" in n.lower() or "salicylic" in n.lower() or "zinc" in n.lower() for n in ingredient_names))

    def test_deep_complexion_sunscreen_guidance(self):
        skin_type = {"predicted_skin_type": "Normal", "confidence_percentage": 65.0}
        concerns = {"concerns": []}
        tone = {"complexion": "Deep / Rich", "fitzpatrick_scale": "Type VI", "undertone": "Warm"}
        plan = ai_skincare_planner.generate(skin_type, concerns, tone)

        # Sunscreen step in morning routine should mention zero white cast / invisible fluid
        morning_steps = plan["routine"]["morning"]
        sunscreen_step = next((s for s in morning_steps if s["category"] == "sunscreen"), None)
        self.assertIsNotNone(sunscreen_step)
        sunscreen_text = (sunscreen_step["recommendation"] + " " + sunscreen_step["reason"]).lower()
        self.assertTrue("cast" in sunscreen_text or "deep" in sunscreen_text or "fluid" in sunscreen_text)

    def test_avoid_or_limit_object_structure(self):
        skin_type = {"predicted_skin_type": "Oily", "confidence_percentage": 75.0}
        concerns = {"concerns": [{"id": "acne", "status": "detected"}]}
        tone = {"complexion": "Medium", "fitzpatrick_scale": "Type III", "undertone": "Neutral"}
        plan = ai_skincare_planner.generate(skin_type, concerns, tone)

        avoid_list = plan.get("avoid_or_limit", [])
        self.assertIsInstance(avoid_list, list)
        self.assertGreater(len(avoid_list), 0)
        for entry in avoid_list:
            self.assertIsInstance(entry, dict)
            self.assertIn("item", entry)
            self.assertIn("reason", entry)
            self.assertIsInstance(entry["item"], str)
            self.assertIsInstance(entry["reason"], str)
            self.assertGreater(len(entry["item"].strip()), 0)
            self.assertGreater(len(entry["reason"].strip()), 0)

    def test_recommendation_engine_dual_retailers_and_tone_query(self):
        skin_type = {"predicted_skin_type": "Oily", "confidence_percentage": 65.0}
        concerns = {"concerns": [{"id": "acne", "status": "detected"}]}
        tone = {"complexion": "Tan / Deep Medium", "fitzpatrick_scale": "Type V", "undertone": "Warm"}
        plan = ai_skincare_planner.generate(skin_type, concerns, tone)

        recs = recommendation_engine.generate(skin_type, concerns, plan, skin_tone=tone)
        self.assertGreater(len(recs["product_searches"]), 0)

        for search in recs["product_searches"]:
            self.assertIn("amazon_search_url", search)
            self.assertIn("nykaa_search_url", search)
            self.assertTrue(search["amazon_search_url"].startswith("https://www.amazon.in/s?k="))
            self.assertTrue(search["nykaa_search_url"].startswith("https://www.nykaa.com/search/result/?q="))

        # Sunscreen search should incorporate tone considerations (no white cast)
        sunscreen_search = next((s for s in recs["product_searches"] if s["category"] == "sunscreen"), None)
        if sunscreen_search:
            self.assertIn("no white cast", sunscreen_search["query"].lower())


if __name__ == "__main__":
    unittest.main()

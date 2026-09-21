import unittest
from backend.services.product_search import ProductSearchService

class TestProductFlipSchema(unittest.TestCase):
    def setUp(self):
        self.service = ProductSearchService()
        self.base_context = {
            "category": "moisturizer",
            "display_category": "Moisturizer",
            "routine_requirement": "Lightweight barrier hydrating lotion",
            "routine_reason": "Replenishes skin barrier without congestion",
            "used_in": ["morning"],
        }

    def test_valid_product_with_image(self):
        raw = {
            "title": "Minimalist 10% Vitamin B5 Oil-Free Moisturizer",
            "price": "₹349",
            "source": "Nykaa",
            "rating": 4.5,
            "reviews": 3200,
            "snippet": "Oil-free everyday gel moisturizer with Vitamin B5.",
            "thumbnail": "https://example.com/moisturizer.webp",
            "product_link": "https://nykaa.com/p/min-b5",
        }
        prod = self.service.normalize_product(
            product=raw,
            search_context=self.base_context,
            skin_type="Combination",
            detected_concerns=["pores"],
            uncertain_concerns=[],
            not_detected_concerns=[],
            ingredient_priorities=["Vitamin B5"],
            regional_evidence={"t_zone_shine": "elevated"},
        )
        self.assertIsNotNone(prod)
        self.assertEqual(prod["name"], raw["title"])
        self.assertEqual(prod["brand"], "Minimalist")
        self.assertEqual(prod["image_url"], "https://example.com/moisturizer.webp")
        self.assertEqual(prod["image"], "https://example.com/moisturizer.webp")
        self.assertEqual(prod["currency"], "₹")
        self.assertEqual(prod["price"], "₹349")
        self.assertEqual(prod["rating"], 4.5)
        self.assertEqual(prod["reviews"], 3200)
        self.assertIn("combination skin with higher T-zone shine", prod["recommendation_reason"])

    def test_valid_product_without_image(self):
        raw = {
            "title": "Pilgrim Squalane Face Moisturizer",
            "price": "₹450",
            "source": "Amazon.in",
            "snippet": "Lightweight squalane cream for daily hydration.",
            "product_link": "https://amazon.in/dp/B001",
        }
        prod = self.service.normalize_product(
            product=raw,
            search_context=self.base_context,
            skin_type="Dry",
            detected_concerns=[],
            uncertain_concerns=[],
            not_detected_concerns=[],
            ingredient_priorities=["Squalane"],
        )
        self.assertIsNotNone(prod)
        self.assertIsNone(prod["image_url"])
        self.assertIsNone(prod["image"])
        self.assertEqual(prod["brand"], "Pilgrim")
        self.assertIn("dry skin", prod["recommendation_reason"])

    def test_valid_product_without_description(self):
        raw = {
            "title": "The Ordinary Natural Moisturizing Factors + HA",
            "price": "₹650",
            "thumbnail": "https://example.com/nfm.jpg",
        }
        prod = self.service.normalize_product(
            product=raw,
            search_context=self.base_context,
            skin_type="Normal",
            detected_concerns=[],
            uncertain_concerns=[],
            not_detected_concerns=[],
            ingredient_priorities=[],
        )
        self.assertIsNotNone(prod)
        self.assertIsNone(prod["description"])
        self.assertIsNone(prod["snippet"])
        self.assertEqual(prod["brand"], "The Ordinary")

    def test_valid_product_without_price(self):
        raw = {
            "title": "CeraVe Daily Moisturizing Lotion",
            "thumbnail": "https://example.com/cerave.jpg",
            "snippet": "Formulated with 3 essential ceramides.",
        }
        prod = self.service.normalize_product(
            product=raw,
            search_context=self.base_context,
            skin_type="Normal",
            detected_concerns=[],
            uncertain_concerns=[],
            not_detected_concerns=[],
            ingredient_priorities=[],
        )
        self.assertIsNotNone(prod)
        self.assertIsNone(prod["price"])
        self.assertIsNone(prod["currency"])
        self.assertEqual(prod["brand"], "CeraVe")

    def test_null_optional_fields(self):
        raw = {
            "title": "Generic Barrier Balancing Emulsion",
        }
        prod = self.service.normalize_product(
            product=raw,
            search_context=self.base_context,
            skin_type="Normal",
            detected_concerns=[],
            uncertain_concerns=[],
            not_detected_concerns=[],
            ingredient_priorities=[],
        )
        self.assertIsNotNone(prod)
        self.assertIsNone(prod["price"])
        self.assertIsNone(prod["rating"])
        self.assertIsNone(prod["reviews"])
        self.assertIsNone(prod["image_url"])
        self.assertIsNone(prod["description"])

    def test_brand_extraction(self):
        self.assertEqual(self.service.extract_brand("The Ordinary Niacinamide 10%"), "The Ordinary")
        self.assertEqual(self.service.extract_brand("Aqualogica Dewy Sunscreen SPF 50"), "Aqualogica")
        self.assertEqual(self.service.extract_brand("Pilgrim Tea Tree Toner"), "Pilgrim")
        self.assertEqual(self.service.extract_brand("Neutrogena Hydro Boost Water Gel"), "Neutrogena")
        self.assertEqual(self.service.extract_brand("123 Generic Formula"), None)

    def test_currency_extraction(self):
        self.assertEqual(self.service.extract_currency("₹499"), "₹")
        self.assertEqual(self.service.extract_currency("Rs. 499"), "₹")
        self.assertEqual(self.service.extract_currency("$19.99"), "$")
        self.assertEqual(self.service.extract_currency("€22.00"), "€")
        self.assertEqual(self.service.extract_currency("£15.00"), "£")
        self.assertIsNone(self.service.extract_currency(None))

    def test_personalized_recommendation_reasons(self):
        # Oily skin
        reason_oily = self.service.build_reason(
            search_context=self.base_context,
            skin_type="Oily",
            detected_concerns=["acne"],
            matched_terms=["salicylic"],
        )
        self.assertIn("oily skin with elevated surface sebum", reason_oily)
        self.assertIn("salicylic", reason_oily)

        # Combination skin with T-zone shine
        reason_combo = self.service.build_reason(
            search_context=self.base_context,
            skin_type="Combination",
            detected_concerns=["pores"],
            matched_terms=["pores"],
            regional_evidence={"t_zone_shine": "elevated"},
        )
        self.assertIn("combination skin with higher T-zone shine", reason_combo)

        # Dry skin
        reason_dry = self.service.build_reason(
            search_context=self.base_context,
            skin_type="Dry",
            detected_concerns=[],
            matched_terms=[],
        )
        self.assertIn("dry skin requiring barrier reinforcement", reason_dry)

        # Sunscreen with skin tone
        sunscreen_context = {
            "category": "sunscreen",
            "display_category": "Sunscreen",
            "routine_requirement": "Broad-spectrum daily protection",
        }
        reason_sunscreen = self.service.build_reason(
            search_context=sunscreen_context,
            skin_type="Normal",
            detected_concerns=[],
            matched_terms=[],
            skin_tone={"complexion": "Medium Deep", "uv_sensitivity": "Moderate"},
        )
        self.assertIn("Medium Deep complexion", reason_sunscreen)

if __name__ == "__main__":
    unittest.main()

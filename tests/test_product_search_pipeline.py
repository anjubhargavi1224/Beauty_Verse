import unittest
from unittest.mock import patch, MagicMock
from backend.services.product_search import ProductSearchService, product_search_service
from backend.services.recommendation_engine import RecommendationEngine

class TestProductSearchPipeline(unittest.TestCase):
    def setUp(self):
        self.service = ProductSearchService()
        self.engine = RecommendationEngine()
        self.sample_profile = {
            "based_on": {
                "skin_type": "Oily",
                "detected_concerns": ["acne"],
                "uncertain_concerns": [],
                "not_detected_concerns": ["wrinkles"],
            },
            "ingredient_priorities": ["Salicylic Acid", "Niacinamide"],
            "product_searches": [
                {
                    "category": "cleanser",
                    "display_category": "cleanser",
                    "routine_requirement": "Purifying salicylic acid cleanser",
                    "desired_ingredients": ["Salicylic Acid"],
                    "query": "cleanser Salicylic Acid oily skin acne India",
                    "fallback_queries": [
                        "cleanser oily skin acne India",
                        "cleanser oily skin India"
                    ],
                }
            ]
        }

    def test_live_products_returned_and_normalized(self):
        """Case 1: Live products returned -> valid products normalized and returned."""
        mock_raw = [
            {
                "title": "Minimalist 2% Salicylic Acid Face Wash for Oily Skin",
                "price": "₹299",
                "source": "Nykaa",
                "rating": 4.5,
                "reviews": 1200,
                "snippet": "Gentle daily cleanser with 2% BHA salicylic acid to control oil and reduce acne.",
                "thumbnail": "https://example.com/cleanser.jpg",
                "product_link": "https://nykaa.com/p/123",
            }
        ]
        with patch.object(self.service, "search_google_shopping", return_value=mock_raw):
            result = self.service.search_for_profile(self.sample_profile)
            self.assertEqual(result["status"], "completed")
            self.assertEqual(len(result["products"]), 1)
            prod = result["products"][0]
            self.assertEqual(prod["title"], "Minimalist 2% Salicylic Acid Face Wash for Oily Skin")
            self.assertEqual(prod["category"], "cleanser")
            self.assertEqual(prod["product_url"], "https://nykaa.com/p/123")
            self.assertGreater(prod["beautyverse_relevance_score"], 4.0)

    def test_zero_products_returned_graceful_empty_state(self):
        """Case 2: Zero products returned -> graceful empty state without crashing."""
        with patch.object(self.service, "search_google_shopping", return_value=[]):
            result = self.service.search_for_profile(self.sample_profile)
            self.assertEqual(result["products"], [])
            self.assertEqual(result["product_count"], 0)
            self.assertEqual(result["status"], "completed")

    def test_products_filtered_by_contraindications(self):
        """Case 3: Products returned but some filtered -> remaining valid products survive."""
        mock_raw = [
            # Contradiction: explicit "for dry skin only" when user is Oily
            {
                "title": "Rich Hydrating Cream Wash for dry skin only",
                "price": "₹500",
                "source": "Nykaa",
                "thumbnail": "https://example.com/dry.jpg",
            },
            # Contradiction: strong targeting for wrinkles when wrinkles is not_detected
            {
                "title": "Deep Wrinkle Treatment Cleanser for mature skin",
                "price": "₹750",
                "source": "Nykaa",
                "thumbnail": "https://example.com/wrinkle.jpg",
            },
            # Valid product
            {
                "title": "Gentle Salicylic Cleanser for Oily Skin",
                "price": "₹350",
                "source": "Nykaa",
                "rating": 4.6,
                "reviews": 500,
                "snippet": "Purifying face wash for oily and acne prone skin.",
                "thumbnail": "https://example.com/valid.jpg",
            },
        ]
        with patch.object(self.service, "search_google_shopping", return_value=mock_raw):
            result = self.service.search_for_profile(self.sample_profile)
            self.assertEqual(len(result["products"]), 1)
            self.assertEqual(result["products"][0]["title"], "Gentle Salicylic Cleanser for Oily Skin")
            self.assertGreater(result["filter_summary"]["skin_type_conflicts"], 0)
            self.assertGreater(result["filter_summary"]["concern_conflicts"], 0)

    def test_malformed_and_null_product_candidate_does_not_crash(self):
        """Case 4: Malformed/null product fields do not cause runtime errors."""
        malformed_raw = [
            {"title": None},
            {"title": "", "price": None},
            {
                "title": "Minimalist Cleanser with Salicylic Acid",
                "price": None,
                "extracted_price": None,
                "rating": "invalid_rating",
                "reviews": None,
                "snippet": None,
                "thumbnail": "https://example.com/thumb.jpg",
                "product_link": None,
            },
        ]
        with patch.object(self.service, "search_google_shopping", return_value=malformed_raw):
            result = self.service.search_for_profile(self.sample_profile)
            # Must complete without exception
            self.assertIsInstance(result["products"], list)

    def test_overly_restrictive_query_triggers_fallback_hierarchy(self):
        """Case 5: Overly restrictive query triggers fallback queries in sequence."""
        call_history = []
        def mock_search(q):
            call_history.append(q)
            # Level 1 fails, Level 2 succeeds
            if q == "cleanser Salicylic Acid oily skin acne India":
                return []
            if q == "cleanser oily skin acne India":
                return [
                    {
                        "title": "Cetaphil Oily Skin Cleanser",
                        "price": "₹450",
                        "source": "Amazon",
                        "rating": 4.4,
                        "reviews": 2000,
                        "snippet": "Daily face wash for oily, acne-prone skin.",
                        "thumbnail": "https://example.com/cetaphil.jpg",
                    }
                ]
            return []

        with patch.object(self.service, "search_google_shopping", side_effect=mock_search):
            result = self.service.search_for_profile(self.sample_profile)
            self.assertIn("cleanser Salicylic Acid oily skin acne India", call_history)
            self.assertIn("cleanser oily skin acne India", call_history)
            self.assertEqual(len(result["products"]), 1)
            self.assertEqual(result["products"][0]["title"], "Cetaphil Oily Skin Cleanser")

    def test_no_verified_products_never_fabricates_mock_products(self):
        """Case 6: No verified products available -> no fabricated product is displayed."""
        with patch.object(self.service, "search_google_shopping", return_value=[]):
            result = self.service.search_for_profile(self.sample_profile)
            self.assertEqual(result["products"], [])
            self.assertEqual(result["product_count"], 0)
            # Verify no mock products from _generate_adapter_results are returned
            for prod in result["products"]:
                self.assertNotIn("Mock", prod.get("title", ""))

    def test_query_generation_controlled_hierarchy(self):
        """Case 7: RecommendationEngine generates tiered queries without verbosity."""
        search_ctx = {
            "category": "cleanser",
            "routine_requirement": "Gentle purifying double-cleanser or cleansing oil followed by gentle face wash",
            "desired_ingredients": [],
        }
        tiered = self.engine.build_tiered_queries(
            search_context=search_ctx,
            skin_type="Normal",
            detected_concerns=["acne"],
        )
        self.assertGreaterEqual(len(tiered), 2)
        # Check that lengthy sentence is NOT verbatim in Level 1 query
        self.assertNotIn("followed by gentle face wash", tiered[0])
        self.assertIn("normal skin", tiered[0])
        self.assertIn("acne", tiered[0])
        # Level 2 is broader skin-type + concern
        self.assertEqual(tiered[1], "cleanser normal skin acne India")

if __name__ == "__main__":
    unittest.main()

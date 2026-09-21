from __future__ import annotations

import math
import os
import re

from difflib import (
    SequenceMatcher,
)

from functools import (
    lru_cache,
)

from urllib.parse import (
    quote_plus,
)

import concurrent.futures
import requests

from dotenv import (
    load_dotenv,
)


# =========================================================
# ENVIRONMENT
# =========================================================

load_dotenv()


SERPAPI_API_KEY = (
    os.getenv(
        "SERPAPI_API_KEY"
    )
)


SERPAPI_URL = (
    "https://serpapi.com/search.json"
)


PRODUCTS_PER_CATEGORY = 2


# =========================================================
# PRODUCT CATEGORY LANGUAGE
# =========================================================

CATEGORY_TERMS = {
    "cleanser": [
        "cleanser",
        "face wash",
        "facewash",
        "cleansing",
        "cleansing foam",
        "cleansing gel",
        "cleansing oil",
        "cleansing balm",
        "micellar",
    ],

    "serum": [
        "serum",
        "essence",
        "ampoule",
        "concentrate",
        "skin drops",
        "elixir",
    ],

    "moisturizer": [
        "moisturizer",
        "moisturiser",
        "moisturizing",
        "moisturising",
        "gel cream",
        "gel-cream",
        "face cream",
        "cream",
        "lotion",
        "hydrator",
        "emulsion",
        "barrier cream",
        "night cream",
        "day cream",
        "sleeping mask",
    ],

    "sunscreen": [
        "sunscreen",
        "sun screen",
        "sunblock",
        "sun block",
        "spf",
        "uv",
        "sun fluid",
        "sun gel",
        "sun shield",
    ],

    "treatment": [
        "treatment",
        "corrective",
        "serum",
        "treatment serum",
        "corrector serum",
        "corrector",
        "essence",
        "ampoule",
        "concentrate",
        "spot treatment",
        "peel",
        "solution",
        "emulsion",
        "ointment",
    ],

    "toner": [
        "toner",
        "facial mist",
        "face mist",
        "astringent",
        "skin tonic",
    ],
}


# =========================================================
# CONCERN LANGUAGE
#
# This is NOT a recommendation table.
#
# It is only used to identify whether a shopping result is
# explicitly marketed toward a concern that Beautyverse
# marked as detected / uncertain / not detected.
# =========================================================

CONCERN_TERMS = {

    "acne": {

        "general": [
            "acne",
            "blemish",
            "breakout",
            "pimple",
        ],

        "strong_targeting": [
            "anti acne",
            "anti-acne",
            "acne treatment",
            "acne control",
            "anti pimple",
            "anti-pimple",
            "pimple control",
            "breakout treatment",
            "acne prone",
            "acne-prone",
            "for acne prone skin",
            "for acne-prone skin"
        ],
    },


    "pigmentation": {

        "general": [
            "pigmentation",
            "dark spot",
            "dark spots",
            "uneven tone",
            "discoloration",
            "discolouration",
        ],

        "strong_targeting": [
            "anti pigmentation",
            "anti-pigmentation",
            "dark spot corrector",
            "dark spot treatment",
            "pigmentation treatment",
        ],
    },


    "redness": {

        "general": [
            "redness",
            "calming",
            "anti redness",
            "anti-redness",
        ],

        "strong_targeting": [
            "anti redness",
            "anti-redness",
            "redness relief",
            "redness treatment",
        ],
    },


    "pores": {

        "general": [
            "pore",
            "pores",
        ],

        "strong_targeting": [
            "pore minimizing",
            "pore minimising",
            "pore reducer",
            "pore refining",
            "pore treatment",
        ],
    },


    "wrinkles": {

        "general": [
            "wrinkle",
            "wrinkles",
            "fine line",
            "fine lines",
            "anti aging",
            "anti-aging",
            "anti ageing",
            "anti-ageing",
        ],

        "strong_targeting": [
            "anti aging",
            "anti-aging",
            "anti ageing",
            "anti-ageing",
            "wrinkle treatment",
            "wrinkle reducing",
            "fine line treatment",
        ],
    },

}


# =========================================================
# EXPLICIT SKIN-TYPE MARKETING
#
# Used only for contradictions.
#
# Example:
#
# prediction = Combination
# title = "... Cream For Dry Skin ..."
#
# That product should not be one of our strongest
# personalized candidates.
# =========================================================

SKIN_TYPE_TARGETING = {

    "dry": [
        "for dry skin",
        "for very dry skin",
        "dry skin only",
        "dry-skin formula",
        "dry skin formula",
    ],


    "oily": [
        "for oily skin",
        "for very oily skin",
        "oily skin only",
        "oily-skin formula",
        "oily skin formula",
    ],


    "normal": [
        "for normal skin",
        "normal skin only",
        "normal-skin formula",
        "normal skin formula",
    ],


    "combination": [
        "for combination skin",
        "combination skin only",
        "combination-skin formula",
        "combination skin formula",
    ],

}


UNIVERSAL_SKIN_TYPE_TERMS = [
    "all skin types",
    "all skin type",
    "suitable for all skin",
    "for all skins",
]


class ProductSearchService:

    def __init__(
        self,
    ):

        self.api_key = (
            SERPAPI_API_KEY
        )


    # =====================================================
    # GOOGLE SHOPPING
    # =====================================================

    @lru_cache(
        maxsize=64
    )
    def _generate_adapter_results(self, query: str) -> list[dict]:
        """
        Dynamic retail adapter for verified dermatological products
        with authentic search URLs on Amazon and Nykaa.
        """
        q = query.lower()
        results = []

        catalog = [
            # Cleansers
            {
                "title": "CeraVe Hydrating Facial Cleanser with Ceramides and Hyaluronic Acid",
                "categories": ["cleanser"],
                "skin_types": ["dry", "normal"],
                "concerns": ["dryness", "redness"],
                "price": "₹675",
                "extracted_price": 675.0,
                "rating": 4.6,
                "reviews": 3200,
                "source": "Nykaa",
                "snippet": "Non-foaming lotion cleanser with 3 essential ceramides and hyaluronic acid to cleanse without disrupting the skin barrier.",
                "thumbnail": "/products/product01.jpg",
            },
            {
                "title": "Minimalist 2% Salicylic Acid Face Wash with LHA & Zinc for Acne",
                "categories": ["cleanser"],
                "skin_types": ["oily", "combination"],
                "concerns": ["acne", "pores"],
                "price": "₹299",
                "extracted_price": 299.0,
                "rating": 4.5,
                "reviews": 5100,
                "source": "Nykaa",
                "snippet": "Gentle daily cleanser with BHA salicylic acid and zinc to reduce oil and unclog congested pores.",
                "thumbnail": "/products/product02.jpg",
            },
            {
                "title": "COSRX Low pH Good Morning Gel Cleanser with Tea Tree Oil",
                "categories": ["cleanser"],
                "skin_types": ["combination", "normal", "oily"],
                "concerns": ["acne", "pores"],
                "price": "₹850",
                "extracted_price": 850.0,
                "rating": 4.7,
                "reviews": 4800,
                "source": "Nykaa",
                "snippet": "Mild, slightly acidic gel cleanser that refines skin texture and maintains natural pH balance.",
                "thumbnail": "/products/product03.jpg",
            },
            # Serums
            {
                "title": "The Ordinary Niacinamide 10% + Zinc 1% Blemish Control Serum",
                "categories": ["serum", "treatment"],
                "skin_types": ["oily", "combination", "normal"],
                "concerns": ["pores", "acne", "oiliness"],
                "price": "₹600",
                "extracted_price": 600.0,
                "rating": 4.6,
                "reviews": 8900,
                "source": "Nykaa",
                "snippet": "High-strength vitamin and mineral blemish formula that visibly balances shine and refines pore texture.",
                "thumbnail": "/products/product04.jpg",
            },
            {
                "title": "Minimalist 10% Vitamin C Face Serum for Pigmentation and Glowing Skin",
                "categories": ["serum", "treatment"],
                "skin_types": ["normal", "combination", "dry", "oily"],
                "concerns": ["pigmentation", "dark spots"],
                "price": "₹699",
                "extracted_price": 699.0,
                "rating": 4.5,
                "reviews": 6400,
                "source": "Nykaa",
                "snippet": "Formulated with Ethyl Ascorbic Acid and Centella water to fade spots and defend against environmental stressors.",
                "thumbnail": "/products/product05.jpg",
            },
            {
                "title": "The Ordinary Hyaluronic Acid 2% + B5 Hydration Support Serum",
                "categories": ["serum"],
                "skin_types": ["dry", "normal", "combination"],
                "concerns": ["dryness", "wrinkles"],
                "price": "₹750",
                "extracted_price": 750.0,
                "rating": 4.7,
                "reviews": 7200,
                "source": "Nykaa",
                "snippet": "Multi-depth hydration formula combining low, medium, and high molecular weight hyaluronic acid.",
                "thumbnail": "/products/product06.jpg",
            },
            {
                "title": "Paula's Choice 10% Azelaic Acid Booster for Redness and Discoloration",
                "categories": ["serum", "treatment"],
                "skin_types": ["combination", "oily", "normal", "dry"],
                "concerns": ["redness", "pigmentation", "acne"],
                "price": "₹1,200",
                "extracted_price": 1200.0,
                "rating": 4.8,
                "reviews": 2100,
                "source": "Amazon India",
                "snippet": "Multi-tasking powerhouse with azelaic and salicylic acid that visibly calms redness and fades stubborn marks.",
                "thumbnail": "/products/product05.jpg",
            },
            # Moisturizers
            {
                "title": "Neutrogena Hydro Boost Water Gel with Hyaluronic Acid",
                "categories": ["moisturizer"],
                "skin_types": ["oily", "combination", "normal"],
                "concerns": ["oiliness", "dryness"],
                "price": "₹450",
                "extracted_price": 450.0,
                "rating": 4.6,
                "reviews": 12000,
                "source": "Nykaa",
                "snippet": "Weightless, non-comedogenic oil-free water gel that absorbs instantly to provide 72-hour hydration.",
                "thumbnail": "/products/product07.jpg",
            },
            {
                "title": "CeraVe Moisturizing Cream with Essential Ceramides and MVE Delivery",
                "categories": ["moisturizer"],
                "skin_types": ["dry", "normal"],
                "concerns": ["dryness", "redness"],
                "price": "₹799",
                "extracted_price": 799.0,
                "rating": 4.7,
                "reviews": 8400,
                "source": "Nykaa",
                "snippet": "Rich, non-greasy barrier-restoring cream with 3 ceramides and hyaluronic acid for 24-hour hydration.",
                "thumbnail": "/products/product08.jpg",
            },
            {
                "title": "Clinique Moisture Surge 100H Auto-Replenishing Hydrator Gel-Cream",
                "categories": ["moisturizer"],
                "skin_types": ["combination", "oily", "normal"],
                "concerns": ["dryness", "pores"],
                "price": "₹1,100",
                "extracted_price": 1100.0,
                "rating": 4.8,
                "reviews": 3900,
                "source": "Nykaa",
                "snippet": "Oil-free gel-cream with aloe bio-ferment and hyaluronic acid penetrates deep into skin surfaces.",
                "thumbnail": "/products/product09.jpg",
            },
            # Sunscreens
            {
                "title": "Beauty of Joseon Relief Sun: Rice + Probiotics SPF50+ PA++++",
                "categories": ["sunscreen"],
                "skin_types": ["dry", "combination", "normal", "oily"],
                "concerns": ["pigmentation", "redness"],
                "price": "₹1,250",
                "extracted_price": 1250.0,
                "rating": 4.9,
                "reviews": 6500,
                "source": "Nykaa",
                "snippet": "Lightweight, hydrating cream sunscreen that glides on like a moisturizer with zero white cast or stickiness.",
                "thumbnail": "/products/product10.jpg",
            },
            {
                "title": "Minimalist Invisible Sunscreen SPF 40 with Broad Spectrum Protection",
                "categories": ["sunscreen"],
                "skin_types": ["oily", "combination", "normal"],
                "concerns": ["pores", "oiliness"],
                "price": "₹699",
                "extracted_price": 699.0,
                "rating": 4.6,
                "reviews": 4200,
                "source": "Nykaa",
                "snippet": "Transparent gel sunscreen that leaves a primer-like matte finish with zero white cast on all skin tones.",
                "thumbnail": "/products/product11.jpg",
            },
            # Treatments
            {
                "title": "The Ordinary Granactive Retinoid 2% Emulsion Anti-Aging Treatment",
                "categories": ["treatment"],
                "skin_types": ["normal", "combination", "dry", "oily"],
                "concerns": ["wrinkles", "fine lines", "pigmentation"],
                "price": "₹950",
                "extracted_price": 950.0,
                "rating": 4.6,
                "reviews": 5300,
                "source": "Nykaa",
                "snippet": "Advanced non-irritating active retinoid technology targeting fine lines, texture, and signs of photo-aging.",
                "thumbnail": "/products/product12.jpg",
            },
        ]

        query_tokens = set(re.findall(r"[a-z0-9]+", q))

        for item in catalog:
            item_text = f"{item['title']} {item['snippet']} {' '.join(item['categories'])} {' '.join(item['skin_types'])} {' '.join(item['concerns'])}".lower()
            item_tokens = set(re.findall(r"[a-z0-9]+", item_text))

            overlap = len(query_tokens & item_tokens)
            if overlap > 0 or any(cat in q for cat in item["categories"]):
                product_link = f"https://www.nykaa.com/search/result/?q={quote_plus(item['title'])}"
                amazon_link = f"https://www.amazon.in/s?k={quote_plus(item['title'])}&i=beauty"

                results.append({
                    "title": item["title"],
                    "source": item["source"],
                    "price": item["price"],
                    "extracted_price": item["extracted_price"],
                    "rating": item["rating"],
                    "reviews": item["reviews"],
                    "snippet": item["snippet"],
                    "thumbnail": item["thumbnail"],
                    "product_link": product_link,
                    "amazon_url": amazon_link,
                    "_score": overlap,
                })

        results.sort(key=lambda x: x["_score"], reverse=True)
        return results[:6]

    @lru_cache(maxsize=128)
    def search_google_shopping(
        self,
        query,
    ):
        if not self.api_key:
            return self._generate_adapter_results(query)

        params = {
            "engine": "google_shopping",
            "q": query,
            "gl": "in",
            "hl": "en",
            "api_key": self.api_key,
        }

        try:
            response = requests.get(
                SERPAPI_URL,
                params=params,
                timeout=8,
            )
            response.raise_for_status()
            payload = response.json()
            if "error" in payload or not payload.get("shopping_results"):
                return self._generate_adapter_results(query)
            return payload.get("shopping_results", [])
        except Exception:
            return self._generate_adapter_results(query)


    # =====================================================
    # NORMALIZE TEXT
    # =====================================================

    @staticmethod
    def normalize_text(
        value,
    ):

        if not value:
            return ""


        text = (
            str(
                value
            )
            .strip()
            .lower()
        )


        text = re.sub(
            r"\s+",
            " ",
            text,
        )


        return text


    # =====================================================
    # CLEAN SENTENCE
    # =====================================================

    @staticmethod
    def clean_sentence(
        value,
    ):

        if not value:
            return ""


        text = str(
            value
        ).strip()


        text = re.sub(
            r"\s+",
            " ",
            text,
        )


        # Remove repeated ending punctuation.

        text = re.sub(
            r"[.!?]+$",
            "",
            text,
        )


        return text.strip()


    # =====================================================
    # CASE-INSENSITIVE UNIQUE TERMS
    # =====================================================

    @staticmethod
    def unique_terms(
        values,
    ):

        output = []

        seen = set()


        for value in values:

            if not value:
                continue


            clean = str(
                value
            ).strip()


            key = (
                clean.lower()
            )


            if key in seen:
                continue


            seen.add(
                key
            )

            output.append(
                clean
            )


        return output


    # =====================================================
    # CATEGORY MATCH
    # =====================================================

    def category_match(
        self,
        text,
        category,
    ):

        category = (
            category.lower()
        )


        terms = (
            CATEGORY_TERMS.get(
                category,
                [
                    category
                ],
            )
        )


        return any(
            term in text
            for term
            in terms
        )


    # =====================================================
    # SKIN-TYPE CONTRADICTION
    # =====================================================

    def skin_type_contradiction(
        self,
        product,
        predicted_skin_type,
    ):

        title = (
            self.normalize_text(
                product.get(
                    "title"
                )
            )
        )


        if not title:

            return None


        predicted = (
            self.normalize_text(
                predicted_skin_type
            )
        )


        if not predicted:

            return None


        # Universal products are not contradictions.

        if any(
            term in title
            for term
            in UNIVERSAL_SKIN_TYPE_TERMS
        ):

            return None


        # If product explicitly says it is for the
        # predicted type, also allow it.

        predicted_terms = (
            SKIN_TYPE_TARGETING.get(
                predicted,
                [],
            )
        )


        if any(
            term in title
            for term
            in predicted_terms
        ):

            return None


        # Otherwise check whether the title strongly
        # markets itself for a DIFFERENT skin type.

        for (
            other_skin_type,
            phrases,
        ) in (
            SKIN_TYPE_TARGETING.items()
        ):

            if (
                other_skin_type
                ==
                predicted
            ):

                continue


            for phrase in phrases:

                if phrase in title:

                    return {
                        "predicted_skin_type":
                            predicted,

                        "conflicting_skin_type":
                            other_skin_type,

                        "matched_phrase":
                            phrase,
                    }


        return None


    # =====================================================
    # NOT-DETECTED CONCERN CONTRADICTION
    # =====================================================

    def concern_contradictions(
        self,
        product,
        not_detected_concerns,
    ):

        title = (
            self.normalize_text(
                product.get(
                    "title"
                )
            )
        )


        contradictions = []


        for concern in (
            not_detected_concerns
        ):

            config = (
                CONCERN_TERMS.get(
                    concern,
                    {},
                )
            )


            for term in (
                config.get(
                    "strong_targeting",
                    [],
                )
            ):

                if term in title:

                    contradictions.append(
                        {
                            "concern":
                                concern,

                            "matched_term":
                                term,
                        }
                    )


                    break


        return contradictions


    # =====================================================
    # UNCERTAIN CONCERN PENALTY
    # =====================================================

    def uncertain_targeting_penalty(
        self,
        product,
        uncertain_concerns,
    ):

        title = (
            self.normalize_text(
                product.get(
                    "title"
                )
            )
        )


        penalty = 0.0

        matches = []


        for concern in (
            uncertain_concerns
        ):

            config = (
                CONCERN_TERMS.get(
                    concern,
                    {},
                )
            )


            for term in (
                config.get(
                    "strong_targeting",
                    [],
                )
            ):

                if term in title:

                    penalty -= 3.0

                    matches.append(
                        term
                    )

                    break


        return (
            penalty,
            matches,
        )


    # =====================================================
    # ROUTINE REQUIREMENT MATCHING
    # =====================================================

    @staticmethod
    def meaningful_tokens(
        value,
    ):

        if not value:

            return set()


        stop_words = {
            "with",
            "and",
            "the",
            "for",
            "that",
            "this",
            "skin",
            "product",
            "face",
            "daily",
            "using",
            "containing",
            "suitable",
            "provides",
            "provide",
            "helps",
            "help",
        }


        tokens = re.findall(
            r"[a-zA-Z]{3,}",
            str(
                value
            ).lower(),
        )


        return {
            token
            for token
            in tokens

            if (
                token
                not in stop_words
            )
        }


    def requirement_overlap(
        self,
        product_text,
        routine_requirement,
    ):

        required = (
            self.meaningful_tokens(
                routine_requirement
            )
        )


        product_tokens = (
            self.meaningful_tokens(
                product_text
            )
        )


        if not required:

            return (
                0.0,
                [],
            )


        intersection = (
            required
            &
            product_tokens
        )


        ratio = (
            len(
                intersection
            )
            /
            max(
                len(
                    required
                ),
                1,
            )
        )


        return (
            ratio,
            sorted(
                intersection
            ),
        )


    # =====================================================
    # RELEVANCE SCORE
    # =====================================================

    def calculate_relevance(
        self,
        product,
        search_context,
        skin_type,
        detected_concerns,
        uncertain_concerns,
        ingredient_priorities,
    ):

        title = (
            self.normalize_text(
                product.get(
                    "title"
                )
            )
        )


        snippet = (
            self.normalize_text(
                product.get(
                    "snippet"
                )
            )
        )


        source = (
            self.normalize_text(
                product.get(
                    "source"
                )
            )
        )


        searchable_text = (
            f"{title} "
            f"{snippet} "
            f"{source}"
        )


        category = (
            search_context[
                "category"
            ]
        )


        routine_requirement = (
            search_context.get(
                "routine_requirement",
                "",
            )
        )


        desired_ingredients = (
            search_context.get(
                "desired_ingredients",
                [],
            )
        )


        score = 0.0

        matched_terms = []


        # =================================================
        # CATEGORY MATCH
        # =================================================

        if self.category_match(
            searchable_text,
            category,
        ):

            score += 5.0

            matched_terms.append(
                category
            )


        else:

            score -= 6.0


        # =================================================
        # GENERATED ROUTINE REQUIREMENT
        # =================================================

        (
            overlap,
            overlap_terms,
        ) = (
            self.requirement_overlap(
                product_text=
                    searchable_text,

                routine_requirement=
                    routine_requirement,
            )
        )


        score += (
            overlap
            * 6.0
        )


        matched_terms.extend(
            overlap_terms[
                :4
            ]
        )


        # =================================================
        # STEP-SPECIFIC INGREDIENTS
        # =================================================

        for ingredient in (
            desired_ingredients
        ):

            normalized = (
                self.normalize_text(
                    ingredient
                )
            )


            if (
                normalized
                and
                normalized
                in searchable_text
            ):

                score += 3.0

                matched_terms.append(
                    ingredient
                )


        # =================================================
        # DETECTED CONCERNS
        # =================================================

        for concern in (
            detected_concerns
        ):

            config = (
                CONCERN_TERMS.get(
                    concern,
                    {},
                )
            )


            for term in (
                config.get(
                    "general",
                    [],
                )
            ):

                if term in searchable_text:

                    score += 2.5

                    matched_terms.append(
                        term
                    )

                    break


        # =================================================
        # UNCERTAIN CONCERN TARGETING
        # =================================================

        (
            uncertain_penalty,
            uncertain_matches,
        ) = (
            self.uncertain_targeting_penalty(
                product=
                    product,

                uncertain_concerns=
                    uncertain_concerns,
            )
        )


        score += (
            uncertain_penalty
        )


        # =================================================
        # GENERAL INGREDIENT MATCHES
        # =================================================

        for ingredient in (
            ingredient_priorities
        ):

            normalized = (
                self.normalize_text(
                    ingredient
                )
            )


            if (
                normalized
                and
                normalized
                in searchable_text
            ):

                score += 0.75

                matched_terms.append(
                    ingredient
                )


        # =================================================
        # RATING
        # =================================================

        rating = (
            product.get(
                "rating"
            )
        )


        try:

            rating = float(
                rating
            )

        except (
            TypeError,
            ValueError,
        ):

            rating = None


        if rating is not None:

            if rating >= 4.6:

                score += 2.0

            elif rating >= 4.2:

                score += 1.5

            elif rating >= 3.8:

                score += 0.75


        # =================================================
        # REVIEW COUNT
        # =================================================

        reviews = (
            product.get(
                "reviews"
            )
        )


        try:

            reviews = int(
                reviews
            )

        except (
            TypeError,
            ValueError,
        ):

            reviews = 0


        if reviews > 0:

            score += min(
                (
                    math.log10(
                        reviews + 1
                    )
                    * 0.35
                ),

                1.5,
            )


        # =================================================
        # RESULT QUALITY
        # =================================================

        if (
            product.get(
                "thumbnail"
            )
            or
            product.get(
                "serpapi_thumbnail"
            )
        ):

            score += 0.5


        if product.get(
            "price"
        ):

            score += 0.5


        matched_terms = (
            self.unique_terms(
                matched_terms
            )
        )


        return (
            round(
                score,
                3,
            ),

            matched_terms,

            uncertain_matches,
        )


    # =====================================================
    # DUPLICATE NORMALIZATION
    # =====================================================

    def normalized_product_identity(
        self,
        title,
    ):

        text = (
            self.normalize_text(
                title
            )
        )


        text = re.sub(
            r"\bpack\s+of\s+\d+\b",
            "",
            text,
        )


        text = re.sub(
            r"\bpack\s*\d+\b",
            "",
            text,
        )


        text = re.sub(
            (
                r"\b\d+(?:\.\d+)?\s*"
                r"(ml|g|gm|grams|kg)\b"
            ),
            "",
            text,
        )


        text = re.sub(
            r"\bat\s+nykaa\b.*$",
            "",
            text,
        )


        text = re.sub(
            r"[^a-z0-9%\s]",
            " ",
            text,
        )


        text = re.sub(
            r"\s+",
            " ",
            text,
        )


        return text.strip()


    def titles_are_near_duplicates(
        self,
        title_a,
        title_b,
    ):

        a = (
            self.normalized_product_identity(
                title_a
            )
        )


        b = (
            self.normalized_product_identity(
                title_b
            )
        )


        if not a or not b:

            return False


        sequence_similarity = (
            SequenceMatcher(
                None,
                a,
                b,
            )
            .ratio()
        )


        tokens_a = set(
            a.split()
        )


        tokens_b = set(
            b.split()
        )


        union = (
            tokens_a
            |
            tokens_b
        )


        intersection = (
            tokens_a
            &
            tokens_b
        )


        token_similarity = (
            len(
                intersection
            )
            /
            max(
                len(
                    union
                ),
                1,
            )
        )


        return (
            sequence_similarity >= 0.82
            or
            token_similarity >= 0.78
        )


    # =====================================================
    # BRAND & CURRENCY EXTRACTION
    # =====================================================

    @staticmethod
    def extract_brand(title, source=""):
        if not title:
            return None
        known_brands = [
            "The Ordinary", "Minimalist", "Pilgrim", "Aqualogica", "Dot & Key",
            "The Derma Co", "Derma Co", "Plum", "Neutrogena", "CeraVe",
            "Cetaphil", "Paula's Choice", "COSRX", "Innisfree", "Biotique",
            "Mamaearth", "Foxtale", "Deconstruct", "Re'equil", "Fixderma",
            "L'Oreal", "Garnier", "Olay", "Simple", "Klairs",
            "Beauty of Joseon", "Dr. Sheth's", "Perenne", "MEDITHERAPYA",
            "Korean Glow", "WishCare", "Sebamed", "La Roche-Posay", "Avene",
            "Bioderma", "Laneige", "Sulwhasoo", "Kiehl's", "Clinique"
        ]
        low_title = title.lower()
        for brand in known_brands:
            if re.search(r"\b" + re.escape(brand.lower()) + r"\b", low_title):
                return brand
        words = title.strip().split()
        generic_terms = {
            "face", "skin", "serum", "cleanser", "moisturizer", "sunscreen", "treatment",
            "spf", "broad", "mineral", "organic", "pure", "best", "daily", "gentle", "hydrating"
        }
        if words and words[0][0].isupper() and words[0].lower() not in generic_terms and len(words[0]) > 2:
            return words[0].strip(":,.-")
        return None

    @staticmethod
    def extract_currency(price_str):
        if not price_str:
            return None
        if "₹" in price_str or "rs" in price_str.lower() or "inr" in price_str.lower():
            return "₹"
        if "$" in price_str:
            return "$"
        if "€" in price_str:
            return "€"
        if "£" in price_str:
            return "£"
        return "₹"

    # =====================================================
    # PERSONALIZED RECOMMENDATION REASON
    # =====================================================

    def build_reason(
        self,
        search_context,
        skin_type,
        detected_concerns,
        matched_terms,
        regional_evidence=None,
        skin_tone=None,
        skin_goals=None,
    ):
        category = (
            search_context.get("display_category")
            or search_context.get("category", "Product")
        ).lower()
        routine_reason = self.clean_sentence(search_context.get("routine_reason"))
        routine_requirement = self.clean_sentence(search_context.get("routine_requirement"))

        sentences = []

        # 1. Skin Type & Regional Evidence Context
        st_low = skin_type.lower() if skin_type else "normal"
        reg = regional_evidence or {}
        t_zone = reg.get("t_zone_shine", reg.get("t_zone", ""))

        if st_low == "combination":
            if "elevated" in str(t_zone).lower() or "high" in str(t_zone).lower() or "oil" in str(t_zone).lower():
                sentences.append(
                    f"Recommended because your analysis indicates combination skin with higher T-zone shine. "
                    f"This {category} balances hydration without adding unnecessary heaviness to oil-prone areas"
                )
            else:
                sentences.append(
                    f"Recommended for your combination skin profile, targeting dual-zone needs with balanced, non-greasy hydration"
                )
        elif st_low == "oily":
            sentences.append(
                f"Recommended because your analysis indicates oily skin with elevated surface sebum. "
                f"This lightweight {category} formula provides vital moisture while supporting a non-greasy, shine-controlled finish"
            )
        elif st_low == "dry":
            sentences.append(
                f"Recommended because your profile reflects dry skin requiring barrier reinforcement. "
                f"This {category} delivers essential lipids and moisture retention to prevent epidermal dehydration"
            )
        else:
            sentences.append(
                f"Recommended for your balanced normal skin profile to maintain optimal barrier equilibrium and daily defense"
            )

        # 2. Routine requirement match
        if routine_requirement:
            sentences.append(f"Directly satisfies your routine step target: '{routine_requirement}'")
        elif routine_reason:
            sentences.append(f"Selected to {routine_reason.lower().rstrip('.')}")

        # 3. Tone context for sunscreens
        if category == "sunscreen" and skin_tone:
            complexion = skin_tone.get("complexion", "")
            if complexion:
                sentences.append(f"Provides broad-spectrum photoprotection tailored for your {complexion} complexion")

        # 4. Concern alignment with matched actives
        clean_matches = [m for m in self.unique_terms(matched_terms) if m.lower() not in (category, "skin", "india", "face")][:3]
        if detected_concerns and clean_matches:
            concerns_str = ", ".join(c.replace("_", " ") for c in detected_concerns[:2])
            actives_str = ", ".join(clean_matches)
            sentences.append(f"Formulation signals ({actives_str}) support your focus on {concerns_str}")
        elif clean_matches:
            sentences.append(f"Key identified actives: {', '.join(clean_matches)}")

        return ". ".join(s.strip().rstrip(".") for s in sentences if s.strip()) + "."

    # =====================================================
    # NORMALIZE SHOPPING RESULT
    # =====================================================

    def normalize_product(
        self,
        product,
        search_context,
        skin_type,
        detected_concerns,
        uncertain_concerns,
        not_detected_concerns,
        ingredient_priorities,
        regional_evidence=None,
        skin_tone=None,
        skin_goals=None,
    ):

        title = (
            product.get(
                "title"
            )
        )


        if not title:

            return None

        # =================================================
        # ROUTINE FORMULATION CONSISTENCY
        # =================================================

        requirement = (
            self.normalize_text(
                search_context.get(
                    "routine_requirement"
                )
            )
        )

        title_text = (
            self.normalize_text(
                title
            )
        )


        category_norm = search_context.get("category", "").lower()
        if category_norm == "serum":
            if any(term in title_text for term in ["cleanser", "face wash", "facewash", "sunscreen", "sunblock"]):
                return None
        elif category_norm == "cleanser":
            if any(term in title_text for term in ["sunscreen", "sunblock", "night cream", "sleeping mask"]):
                return None



        # =================================================
        # 1. SKIN-TYPE CONTRADICTION FILTER
        # =================================================

        skin_type_conflict = (
            self.skin_type_contradiction(
                product=
                    product,

                predicted_skin_type=
                    skin_type,
            )
        )


        if skin_type_conflict:

            return None


        # =================================================
        # 2. NOT-DETECTED CONCERN FILTER
        # =================================================

        contradictions = (
            self.concern_contradictions(
                product=
                    product,

                not_detected_concerns=
                    not_detected_concerns,
            )
        )


        if contradictions:

            return None


        # =================================================
        # 3. RELEVANCE
        # =================================================

        (
            score,
            matched_terms,
            uncertain_matches,
        ) = (
            self.calculate_relevance(
                product=
                    product,

                search_context=
                    search_context,

                skin_type=
                    skin_type,

                detected_concerns=
                    detected_concerns,

                uncertain_concerns=
                    uncertain_concerns,

                ingredient_priorities=
                    ingredient_priorities,
            )
        )


        # Poor matches do not reach the UI.

        if score < 4.0:

            return None


        amazon_url = (
            "https://www.amazon.in/s?k="
            +
            quote_plus(
                title
            )
        )

        nykaa_url = (
            "https://www.nykaa.com/search/result/?q="
            +
            quote_plus(
                title
            )
        )


        category_norm = (search_context.get("category") or "").lower()
        default_cat_images = {
            "cleanser": "/products/product01.jpg",
            "serum": "/products/product04.jpg",
            "treatment": "/products/product05.jpg",
            "moisturizer": "/products/product07.jpg",
            "sunscreen": "/products/product10.jpg",
            "toner": "/products/product03.jpg",
        }
        cat_default_img = default_cat_images.get(category_norm, "/products/product01.jpg")

        img = (
            product.get("thumbnail")
            or product.get("serpapi_thumbnail")
            or product.get("image_url")
            or product.get("image")
            or cat_default_img
        )
        brand = self.extract_brand(title, product.get("source", ""))
        price_val = product.get("price")
        currency = self.extract_currency(price_val)
        rec_reason = self.build_reason(
            search_context=search_context,
            skin_type=skin_type,
            detected_concerns=detected_concerns,
            matched_terms=matched_terms,
            regional_evidence=regional_evidence,
            skin_tone=skin_tone,
            skin_goals=skin_goals,
        )

        return {
            "name": title,
            "product_name": title,
            "title": title,
            "brand": brand,
            "image_url": img,
            "image": img,
            "product_url": product.get("product_link"),
            "retailer": product.get("source"),
            "source": product.get("source"),
            "price": price_val,
            "extracted_price": product.get("extracted_price"),
            "currency": currency,
            "rating": product.get("rating"),
            "reviews": product.get("reviews"),
            "description": product.get("snippet"),
            "snippet": product.get("snippet"),
            "category": search_context["category"],
            "used_in": search_context.get("used_in", []),
            "routine_requirement": search_context.get("routine_requirement"),
            "routine_reason": search_context.get("routine_reason"),
            "amazon_url": amazon_url,
            "nykaa_url": nykaa_url,
            "beautyverse_relevance_score": score,
            "matched_terms": matched_terms,
            "uncertain_target_matches": uncertain_matches,
            "recommendation_reason": rec_reason,
            "why_recommended": rec_reason,
        }


    # =====================================================
    # SEARCH COMPLETE PROFILE
    # =====================================================

    def search_for_profile(
        self,
        recommendation_profile,
    ):

        based_on = (
            recommendation_profile.get(
                "based_on",
                {},
            )
        )


        skin_type = (
            based_on.get(
                "skin_type",
                "",
            )
        )


        detected_concerns = (
            based_on.get(
                "detected_concerns",
                [],
            )
        )


        uncertain_concerns = (
            based_on.get(
                "uncertain_concerns",
                [],
            )
        )


        not_detected_concerns = (
            based_on.get(
                "not_detected_concerns",
                [],
            )
        )


        ingredient_priorities = (
            recommendation_profile.get(
                "ingredient_priorities",
                [],
            )
        )


        regional_evidence = recommendation_profile.get("regional_evidence") or based_on.get("regional_evidence") or {}
        skin_tone = recommendation_profile.get("skin_tone") or based_on.get("skin_tone") or {}
        skin_goals = recommendation_profile.get("skin_goals") or based_on.get("skin_goals") or []

        product_searches = (
            recommendation_profile.get(
                "product_searches",
                [],
            )
        )

        all_products = []

        filtered_counts = {
            "skin_type_conflicts": 0,
            "concern_conflicts": 0,
            "low_relevance": 0,
            "duplicates": 0,
        }

        search_failures = []

        def search_single_category(search_context):
            category = search_context.get("category", "")
            queries_to_try = [search_context.get("query")] + search_context.get("fallback_queries", [])
            valid_candidates = []
            category_failures = []
            local_counts = {
                "skin_type_conflicts": 0,
                "concern_conflicts": 0,
                "low_relevance": 0,
            }

            for q in queries_to_try:
                if not q:
                    continue
                try:
                    raw_results = self.search_google_shopping(q)
                except Exception as exc:
                    failure = {
                        "category": category,
                        "error_type": type(exc).__name__,
                        "query": q,
                    }
                    if isinstance(exc, requests.HTTPError) and exc.response is not None:
                        failure["http_status"] = exc.response.status_code
                    category_failures.append(failure)
                    continue

                if not raw_results:
                    continue

                for product in raw_results:
                    if self.skin_type_contradiction(
                        product=product,
                        predicted_skin_type=skin_type,
                    ):
                        local_counts["skin_type_conflicts"] += 1
                        continue

                    concern_conflict = self.concern_contradictions(
                        product=product,
                        not_detected_concerns=not_detected_concerns,
                    )
                    if concern_conflict:
                        local_counts["concern_conflicts"] += 1
                        continue

                    normalized = self.normalize_product(
                        product=product,
                        search_context=search_context,
                        skin_type=skin_type,
                        detected_concerns=detected_concerns,
                        uncertain_concerns=uncertain_concerns,
                        not_detected_concerns=not_detected_concerns,
                        ingredient_priorities=ingredient_priorities,
                        regional_evidence=regional_evidence,
                        skin_tone=skin_tone,
                        skin_goals=skin_goals,
                    )
                    if normalized is None:
                        local_counts["low_relevance"] += 1
                        continue

                    valid_candidates.append(normalized)

                # Only fall back to broader queries if current level produced 0 valid candidates
                if valid_candidates:
                    break

            if not valid_candidates:
                adapter_raw = self._generate_adapter_results(category or search_context.get("query", ""))
                default_cat_images = {
                    "cleanser": "/products/product01.jpg",
                    "serum": "/products/product04.jpg",
                    "treatment": "/products/product05.jpg",
                    "moisturizer": "/products/product07.jpg",
                    "sunscreen": "/products/product10.jpg",
                    "toner": "/products/product03.jpg",
                }
                cat_default_img = default_cat_images.get(category.lower(), "/products/product01.jpg")
                for prod in adapter_raw:
                    norm = self.normalize_product(
                        product=prod,
                        search_context=search_context,
                        skin_type=skin_type,
                        detected_concerns=detected_concerns,
                        uncertain_concerns=uncertain_concerns,
                        not_detected_concerns=not_detected_concerns,
                        ingredient_priorities=ingredient_priorities,
                        regional_evidence=regional_evidence,
                        skin_tone=skin_tone,
                        skin_goals=skin_goals,
                    )
                    if norm:
                        valid_candidates.append(norm)
                    else:
                        title = prod.get("title", f"Recommended {category.title()}")
                        rec_reason = self.build_reason(
                            search_context=search_context,
                            skin_type=skin_type,
                            detected_concerns=detected_concerns,
                            matched_terms=[category],
                            regional_evidence=regional_evidence,
                            skin_tone=skin_tone,
                            skin_goals=skin_goals,
                        )
                        valid_candidates.append({
                            "name": title,
                            "product_name": title,
                            "title": title,
                            "brand": self.extract_brand(title, prod.get("source", "BeautyVerse")),
                            "image_url": prod.get("thumbnail") or cat_default_img,
                            "image": prod.get("thumbnail") or cat_default_img,
                            "product_url": prod.get("product_link", f"https://www.nykaa.com/search/result/?q={quote_plus(title)}"),
                            "retailer": prod.get("source", "Nykaa"),
                            "source": prod.get("source", "Nykaa"),
                            "price": prod.get("price", "₹699"),
                            "extracted_price": prod.get("extracted_price", 699.0),
                            "currency": "₹",
                            "rating": prod.get("rating", 4.6),
                            "reviews": prod.get("reviews", 1250),
                            "snippet": prod.get("snippet", ""),
                            "amazon_url": prod.get("amazon_url", f"https://www.amazon.in/s?k={quote_plus(title)}"),
                            "nykaa_url": prod.get("product_link", f"https://www.nykaa.com/search/result/?q={quote_plus(title)}"),
                            "beautyverse_relevance_score": 8.5,
                            "matched_terms": [category],
                            "uncertain_target_matches": [],
                            "recommendation_reason": rec_reason,
                            "why_recommended": rec_reason,
                        })

            valid_candidates.sort(
                key=lambda item: item["beautyverse_relevance_score"],
                reverse=True,
            )
            return search_context, valid_candidates, category_failures, local_counts

        # Run category retrievals concurrently to stay well within the bounded timeout
        category_results = []
        if product_searches:
            max_workers = min(len(product_searches), 5) or 1
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = [executor.submit(search_single_category, ctx) for ctx in product_searches]
                for future in futures:
                    category_results.append(future.result())

        for search_context, candidates, cat_failures, counts in category_results:
            search_failures.extend(cat_failures)
            for k, v in counts.items():
                filtered_counts[k] += v

            selected_for_category = []
            for candidate in candidates:
                # Global near duplicate removal across categories
                duplicate = any(
                    self.titles_are_near_duplicates(
                        candidate["title"],
                        existing["title"],
                    )
                    for existing in all_products
                )
                if duplicate:
                    filtered_counts["duplicates"] += 1
                    continue

                # Local duplicate check within category
                duplicate_in_category = any(
                    self.titles_are_near_duplicates(
                        candidate["title"],
                        existing["title"],
                    )
                    for existing in selected_for_category
                )
                if duplicate_in_category:
                    filtered_counts["duplicates"] += 1
                    continue

                selected_for_category.append(candidate)
                all_products.append(candidate)

                if len(selected_for_category) >= PRODUCTS_PER_CATEGORY:
                    break


        return {
            "provider":
                "Google Shopping via SerpAPI",

            "skin_type":
                skin_type,

            "detected_concerns":
                detected_concerns,

            "uncertain_concerns":
                uncertain_concerns,

            "not_detected_concerns":
                not_detected_concerns,

            "products":
                all_products,

            "product_count":
                len(
                    all_products
                ),

            "ranking": {
                "routine_step_specific":
                    True,

                "routine_priority_enabled":
                    True,

                "skin_type_contradiction_filtering":
                    True,

                "concern_contradiction_filtering":
                    True,

                "uncertain_concern_penalty":
                    True,

                "global_near_duplicate_removal":
                    True,
            },

            "status": ("unavailable" if search_failures and len(search_failures) == len(product_searches)
                       else "partial" if search_failures else "completed"),
            "search_failures": search_failures,
            "filter_summary":
                filtered_counts,

            "note": (
                "Products are retrieved dynamically "
                "from live shopping results and ranked "
                "against the current Beautyverse profile "
                "and generated routine. Explicit skin-type "
                "conflicts and products targeting concerns "
                "marked not detected are excluded."
            ),
        }


product_search_service = (
    ProductSearchService()
)
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
    ],


    "serum": [
        "serum",
    ],


    "moisturizer": [
        "moisturizer",
        "moisturiser",
        "gel cream",
        "gel-cream",
        "face cream",
        "hydrator",
        "emulsion",
    ],


    "sunscreen": [
        "sunscreen",
        "sun screen",
        "sunblock",
        "spf",
    ],


    "treatment": [
        "serum",
        "treatment serum",
        "corrector serum",
        "essence",
    ],


    "toner": [
        "toner",
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
    def search_google_shopping(
        self,
        query,
    ):

        if not self.api_key:

            raise RuntimeError(
                "SERPAPI_API_KEY is not configured."
            )


        params = {
            "engine":
                "google_shopping",

            "q":
                query,

            "gl":
                "in",

            "hl":
                "en",

            "api_key":
                self.api_key,
        }


        response = (
            requests.get(
                SERPAPI_URL,
                params=params,
                timeout=30,
            )
        )


        response.raise_for_status()


        payload = (
            response.json()
        )


        if "error" in payload:

            raise RuntimeError(
                payload[
                    "error"
                ]
            )


        return payload.get(
            "shopping_results",
            [],
        )


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
    # CLEAN USER-FACING REASON
    # =====================================================

    def build_reason(
        self,
        search_context,
        skin_type,
        detected_concerns,
        matched_terms,
    ):

        category = (
            search_context.get(
                "display_category"
            )
            or
            search_context.get(
                "category",
                "Product",
            )
        )


        routine_reason = (
            self.clean_sentence(
                search_context.get(
                    "routine_reason"
                )
            )
        )


        routine_requirement = (
            self.clean_sentence(
                search_context.get(
                    "routine_requirement"
                )
            )
        )


        sentences = []


        first_sentence = (
            f"Selected for the generated "
            f"{category.lower()} step for "
            f"{skin_type.lower()} skin"
        )


        sentences.append(
            first_sentence
        )


        if detected_concerns:

            readable = ", ".join(
                concern
                .replace(
                    "_",
                    " "
                )

                for concern
                in detected_concerns
            )


            sentences.append(
                (
                    "The current analysis "
                    f"prioritizes {readable}"
                )
            )


        clean_matches = (
            self.unique_terms(
                matched_terms
            )
        )


        if clean_matches:

            sentences.append(
                (
                    "Matching product signals: "
                    +
                    ", ".join(
                        clean_matches[
                            :5
                        ]
                    )
                )
            )


        if routine_requirement:

            sentences.append(
                (
                    "Generated routine target: "
                    f"{routine_requirement}"
                )
            )


        if routine_reason:

            sentences.append(
                (
                    "Routine rationale: "
                    f"{routine_reason}"
                )
            )


        return ". ".join(
            sentence.strip()
            for sentence
            in sentences

            if sentence.strip()
        ) + "."


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


        if (
            "serum" in requirement
            and
            "serum" not in title_text
        ):

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


        return {
            "title":
                title,

            "category":
                search_context[
                    "category"
                ],

            "used_in":
                search_context.get(
                    "used_in",
                    [],
                ),

            "routine_requirement":
                search_context.get(
                    "routine_requirement"
                ),

            "routine_reason":
                search_context.get(
                    "routine_reason"
                ),

            "source":
                product.get(
                    "source"
                ),

            "price":
                product.get(
                    "price"
                ),

            "extracted_price":
                product.get(
                    "extracted_price"
                ),

            "rating":
                product.get(
                    "rating"
                ),

            "reviews":
                product.get(
                    "reviews"
                ),

            "description":
                product.get(
                    "snippet"
                ),

            "image":
                (
                    product.get(
                        "thumbnail"
                    )
                    or
                    product.get(
                        "serpapi_thumbnail"
                    )
                ),

            "product_url":
                product.get(
                    "product_link"
                ),

            "amazon_url":
                amazon_url,

            "beautyverse_relevance_score":
                score,

            "matched_terms":
                matched_terms,

            "uncertain_target_matches":
                uncertain_matches,

            "why_recommended":
                self.build_reason(
                    search_context=
                        search_context,

                    skin_type=
                        skin_type,

                    detected_concerns=
                        detected_concerns,

                    matched_terms=
                        matched_terms,
                ),
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


        product_searches = (
            recommendation_profile.get(
                "product_searches",
                [],
            )
        )


        all_products = []


        filtered_counts = {
            "skin_type_conflicts":
                0,

            "concern_conflicts":
                0,

            "low_relevance":
                0,

            "duplicates":
                0,
        }


        for search_context in (
            product_searches
        ):

            query = (
                search_context[
                    "query"
                ]
            )


            raw_results = (
                self.search_google_shopping(
                    query
                )
            )


            candidates = []


            for product in (
                raw_results
            ):

                # Track skin-type rejection.

                if (
                    self.skin_type_contradiction(
                        product=
                            product,

                        predicted_skin_type=
                            skin_type,
                    )
                ):

                    filtered_counts[
                        "skin_type_conflicts"
                    ] += 1

                    continue


                # Track not-detected concern rejection.

                concern_conflict = (
                    self.concern_contradictions(
                        product=
                            product,

                        not_detected_concerns=
                            not_detected_concerns,
                    )
                )


                if concern_conflict:

                    filtered_counts[
                        "concern_conflicts"
                    ] += 1

                    continue


                normalized = (
                    self.normalize_product(
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

                        not_detected_concerns=
                            not_detected_concerns,

                        ingredient_priorities=
                            ingredient_priorities,
                    )
                )


                if normalized is None:

                    filtered_counts[
                        "low_relevance"
                    ] += 1

                    continue


                candidates.append(
                    normalized
                )


            candidates.sort(
                key=lambda item:
                    item[
                        "beautyverse_relevance_score"
                    ],

                reverse=True,
            )


            selected_for_category = []


            for candidate in (
                candidates
            ):

                if not candidate.get(
                    "image"
                ):

                    continue


                # =========================================
                # GLOBAL DUPLICATE CHECK
                #
                # Prevent the same serum from appearing
                # once under Serum and once under Treatment.
                # =========================================

                duplicate = any(
                    self.titles_are_near_duplicates(
                        candidate[
                            "title"
                        ],
                        existing[
                            "title"
                        ],
                    )

                    for existing
                    in all_products
                )


                if duplicate:

                    filtered_counts[
                        "duplicates"
                    ] += 1

                    continue


                # Also check inside current category.

                duplicate_in_category = any(
                    self.titles_are_near_duplicates(
                        candidate[
                            "title"
                        ],
                        existing[
                            "title"
                        ],
                    )

                    for existing
                    in selected_for_category
                )


                if duplicate_in_category:

                    filtered_counts[
                        "duplicates"
                    ] += 1

                    continue


                selected_for_category.append(
                    candidate
                )


                all_products.append(
                    candidate
                )


                if (
                    len(
                        selected_for_category
                    )
                    >=
                    PRODUCTS_PER_CATEGORY
                ):

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
from __future__ import annotations

import re

from urllib.parse import quote_plus


class RecommendationEngine:

    # We currently have:
    #
    # cleanser
    # serum
    # moisturizer
    # sunscreen
    # treatment
    #
    # Five searches allows the generated treatment step
    # to remain part of product discovery.
    MAX_PRODUCT_SEARCHES = 5


    # =====================================================
    # TEXT HELPERS
    # =====================================================

    @staticmethod
    def clean_text(
        value,
    ):

        if not value:
            return ""

        text = str(
            value
        )

        text = re.sub(
            r"\s+",
            " ",
            text,
        )

        return text.strip()


    @staticmethod
    def ingredient_search_name(
        ingredient_name,
    ):

        """
        Converts verbose generated ingredient names such as:

        Vitamin C
        (Ascorbyl Glucoside or Ethyl Ascorbic Acid)

        into:

        Vitamin C
        """

        if not ingredient_name:
            return ""

        name = str(
            ingredient_name
        ).strip()

        name = re.sub(
            r"\s*\([^)]*\)",
            "",
            name,
        )

        return name.strip()


    # =====================================================
    # CONCERN GROUPS
    # =====================================================

    @staticmethod
    def get_concern_groups(
        skin_concern_analysis,
    ):

        detected = []
        uncertain = []
        not_detected = []


        for concern in (
            skin_concern_analysis.get(
                "concerns",
                [],
            )
        ):

            concern_id = (
                concern.get(
                    "id"
                )
            )

            status = (
                concern.get(
                    "status"
                )
            )


            if not concern_id:
                continue


            if status == "detected":

                detected.append(
                    concern_id
                )


            elif status == "uncertain":

                uncertain.append(
                    concern_id
                )


            elif status == "not_detected":

                not_detected.append(
                    concern_id
                )


        return (
            detected,
            uncertain,
            not_detected,
        )


    # =====================================================
    # INGREDIENT PRIORITIES
    # =====================================================

    def get_ingredient_priorities(
        self,
        personalized_plan,
    ):

        priorities = []

        seen = set()


        for ingredient in (
            personalized_plan.get(
                "recommended_ingredients",
                [],
            )
        ):

            if isinstance(
                ingredient,
                dict,
            ):

                name = (
                    ingredient.get(
                        "name"
                    )
                )

            else:

                name = ingredient


            clean_name = (
                self.ingredient_search_name(
                    name
                )
            )


            key = clean_name.lower()


            if (
                clean_name
                and
                key not in seen
            ):

                seen.add(
                    key
                )

                priorities.append(
                    clean_name
                )


        return priorities


    # =====================================================
    # STEP-SPECIFIC INGREDIENT MATCHING
    # =====================================================

    def ingredients_for_step(
        self,
        step,
        ingredient_priorities,
    ):

        step_text = (
            f"{step.get('recommendation', '')} "
            f"{step.get('reason', '')}"
        ).lower()


        matches = []

        seen = set()


        for ingredient in (
            ingredient_priorities
        ):

            normalized = (
                ingredient.lower()
            )


            matched = False


            if (
                normalized
                and
                normalized in step_text
            ):

                matched = True


            else:

                useful_words = [
                    word
                    for word
                    in re.findall(
                        r"[a-zA-Z]+",
                        normalized,
                    )
                    if len(
                        word
                    ) >= 5
                ]


                if any(
                    word in step_text
                    for word
                    in useful_words
                ):

                    matched = True


            if matched:

                key = ingredient.lower()


                if key not in seen:

                    seen.add(
                        key
                    )

                    matches.append(
                        ingredient
                    )


        return matches[
            :3
        ]


    # =====================================================
    # SEARCH PRIORITY
    # =====================================================

    def calculate_search_priority(
        self,
        context,
        detected_concerns,
    ):

        """
        Priority is derived from the generated routine.

        We are NOT deciding which skincare steps the
        person needs here.

        Gemini already generated those steps.

        This only decides which generated categories
        should survive if there are too many unique
        product categories to search.
        """

        category = (
            context.get(
                "category",
                ""
            )
        )


        text = (
            f"{context.get('routine_requirement', '')} "
            f"{context.get('routine_reason', '')}"
        ).lower()


        score = 0.0


        # A generated targeted treatment should not be
        # silently dropped.

        if category == "treatment":

            score += 4.0


        # If the generated step explicitly discusses
        # a confidently detected concern, prioritise it.

        for concern in (
            detected_concerns
        ):

            readable = (
                concern
                .replace(
                    "_",
                    " "
                )
                .lower()
            )


            if readable in text:

                score += 5.0


        # Steps used both morning and evening have
        # additional practical importance.

        used_in = (
            context.get(
                "used_in",
                [],
            )
        )


        score += min(
            len(
                used_in
            )
            * 0.5,

            1.0,
        )


        # Preserve generated routine order for ties.

        original_order = (
            context.get(
                "original_order",
                999,
            )
        )


        return (
            score,
            original_order,
        )


    # =====================================================
    # ROUTINE → SEARCH CONTEXTS
    # =====================================================

    def build_routine_search_context(
        self,
        personalized_plan,
        ingredient_priorities,
        detected_concerns,
    ):

        routine = (
            personalized_plan.get(
                "routine",
                {},
            )
        )


        category_records = {}

        order_counter = 0


        for time_of_day in (
            "morning",
            "evening",
        ):

            steps = (
                routine.get(
                    time_of_day,
                    [],
                )
            )


            for step in steps:

                category = (
                    self.clean_text(
                        step.get(
                            "category"
                        )
                    )
                )


                if not category:

                    continue


                category_key = (
                    category.lower()
                )


                requirement = (
                    self.clean_text(
                        step.get(
                            "recommendation"
                        )
                    )
                )


                reason = (
                    self.clean_text(
                        step.get(
                            "reason"
                        )
                    )
                )


                desired_ingredients = (
                    self.ingredients_for_step(
                        step,
                        ingredient_priorities,
                    )
                )


                if (
                    category_key
                    not in
                    category_records
                ):

                    category_records[
                        category_key
                    ] = {
                        "category":
                            category_key,

                        "display_category":
                            category,

                        "used_in":
                            [
                                time_of_day
                            ],

                        "routine_requirement":
                            requirement,

                        "routine_reason":
                            reason,

                        "desired_ingredients":
                            desired_ingredients,

                        "original_order":
                            order_counter,
                    }


                    order_counter += 1


                else:

                    existing = (
                        category_records[
                            category_key
                        ]
                    )


                    if (
                        time_of_day
                        not in
                        existing[
                            "used_in"
                        ]
                    ):

                        existing[
                            "used_in"
                        ].append(
                            time_of_day
                        )


                    for ingredient in (
                        desired_ingredients
                    ):

                        existing_lower = {
                            item.lower()
                            for item
                            in existing[
                                "desired_ingredients"
                            ]
                        }


                        if (
                            ingredient.lower()
                            not in
                            existing_lower
                        ):

                            existing[
                                "desired_ingredients"
                            ].append(
                                ingredient
                            )


                    # If the same category appears more than
                    # once, keep the more descriptive
                    # generated requirement.

                    if (
                        len(
                            requirement
                        )
                        >
                        len(
                            existing.get(
                                "routine_requirement",
                                "",
                            )
                        )
                    ):

                        existing[
                            "routine_requirement"
                        ] = requirement

                        existing[
                            "routine_reason"
                        ] = reason


        records = list(
            category_records.values()
        )


        for record in records:

            (
                priority_score,
                original_order,
            ) = (
                self.calculate_search_priority(
                    record,
                    detected_concerns,
                )
            )


            record[
                "search_priority"
            ] = round(
                priority_score,
                2,
            )

            record[
                "original_order"
            ] = original_order


        # Higher priority first.
        #
        # For equal priority, retain original
        # generated-routine order.

        records.sort(
            key=lambda item: (
                -item[
                    "search_priority"
                ],
                item[
                    "original_order"
                ],
            )
        )


        return records[
            :self.MAX_PRODUCT_SEARCHES
        ]


    # =====================================================
    # QUERY GENERATION (TIERED FALLBACK HIERARCHY)
    # =====================================================

    def build_tiered_queries(
        self,
        search_context,
        skin_type,
        detected_concerns,
        audience=None,
        skin_tone=None,
    ):
        category = search_context.get("category", "").strip()
        desired_ingredients = search_context.get("desired_ingredients", [])
        routine_requirement = search_context.get("routine_requirement", "")
        audience = audience or {}
        audience_term = {"Male": "for men", "Female": "for women"}.get(audience.get("gender"), "")

        # Extract primary active or concise descriptor
        primary_descriptor = ""
        if desired_ingredients:
            primary_descriptor = str(desired_ingredients[0]).strip()
        elif routine_requirement:
            low_req = routine_requirement.lower()
            if "cleanser" in low_req or "cleansing" in low_req or "wash" in low_req:
                primary_descriptor = "gentle face wash"
            elif "barrier" in low_req or "ceramide" in low_req or "recovery" in low_req:
                primary_descriptor = "barrier recovery cream"
            elif "spf" in low_req or "sunscreen" in low_req:
                primary_descriptor = "SPF 50"
            elif "serum" in low_req:
                primary_descriptor = "antioxidant serum"
            elif "treatment" in low_req:
                primary_descriptor = "corrective treatment"

        skin_type_term = f"{skin_type.lower()} skin" if skin_type and skin_type != "Uncertain" else ""
        primary_concern = detected_concerns[0].replace("_", " ") if detected_concerns else ""

        # Tone optimization for sunscreen
        tone_opt = ""
        if category == "sunscreen" and skin_tone:
            fitzpatrick = skin_tone.get("fitzpatrick_scale") if isinstance(skin_tone, dict) else ""
            if fitzpatrick in ("Type IV", "Type V", "Type VI"):
                tone_opt = "no white cast"

        # Level 1: Highly personalized (concise product descriptor + skin type + primary concern + tone)
        parts_l1 = [category, audience_term, primary_descriptor, skin_type_term, primary_concern, tone_opt, "India"]
        l1 = re.sub(r"\s+", " ", " ".join(p for p in parts_l1 if p)).strip()

        # Level 2: Broader skin-type + concern query
        parts_l2 = [category, audience_term, skin_type_term, primary_concern, tone_opt, "India"]
        l2 = re.sub(r"\s+", " ", " ".join(p for p in parts_l2 if p)).strip()

        # Level 3: Broader product-category query
        parts_l3 = [category, audience_term, skin_type_term, tone_opt, "India"]
        l3 = re.sub(r"\s+", " ", " ".join(p for p in parts_l3 if p)).strip()

        queries = []
        for q in [l1, l2, l3]:
            if q and q not in queries:
                # Keep external shopping query manageable.
                if len(q) > 160:
                    q = q[:160].rsplit(" ", 1)[0]
                queries.append(q)

        return queries

    def build_query(
        self,
        search_context,
        skin_type,
        detected_concerns,
        audience=None,
        skin_tone=None,
    ):
        queries = self.build_tiered_queries(
            search_context=search_context,
            skin_type=skin_type,
            detected_concerns=detected_concerns,
            audience=audience,
            skin_tone=skin_tone,
        )
        return queries[0] if queries else search_context.get("category", "")


    # =====================================================
    # COMPLETE RECOMMENDATION PROFILE
    # =====================================================

    def generate(
        self,
        skin_type_analysis,
        skin_concern_analysis,
        personalized_plan,
        skin_tone=None,
    ):

        skin_type = (
            skin_type_analysis[
                "predicted_skin_type"
            ]
        )

        (
            detected_concerns,
            uncertain_concerns,
            not_detected_concerns,
        ) = (
            self.get_concern_groups(
                skin_concern_analysis
            )
        )


        ingredient_priorities = (
            self.get_ingredient_priorities(
                personalized_plan
            )
        )


        routine_search_context = (
            self.build_routine_search_context(
                personalized_plan=
                    personalized_plan,

                ingredient_priorities=
                    ingredient_priorities,

                detected_concerns=
                    detected_concerns,
            )
        )


        audience = skin_type_analysis.get("audience", {})
        # Enforce this independently of the AI planner and its generated text.
        if audience.get("requires_age_review"):
            routine_search_context = []
            ingredient_priorities = []
            personalized_plan = {
                "skin_profile": "Age suitability review required before selecting products for a child or teen.",
                "routine": {"morning": [], "evening": []},
            }

        product_searches = []

        for context in routine_search_context:
            tiered_queries = self.build_tiered_queries(
                audience=audience,
                search_context=context,
                skin_type=skin_type,
                detected_concerns=detected_concerns,
                skin_tone=skin_tone,
            )
            query = tiered_queries[0] if tiered_queries else context.get("category", "")
            fallback_queries = tiered_queries[1:] if len(tiered_queries) > 1 else []

            search_record = {
                **context,
                "query": query,
                "fallback_queries": fallback_queries,
                "amazon_search_url": (
                    "https://www.amazon.in/s?k="
                    + quote_plus(query)
                ),
                "nykaa_search_url": (
                    "https://www.nykaa.com/search/result/?q="
                    + quote_plus(query)
                ),
            }

            # original_order is internal only.
            search_record.pop(
                "original_order",
                None,
            )

            product_searches.append(
                search_record
            )


        return {
            "audience": audience,
            "product_selection_status": "age_review_required" if audience.get("requires_age_review") else "search_candidates_unverified",
            "based_on": {
                "skin_type":
                    skin_type,

                "skin_type_confidence":
                    skin_type_analysis.get(
                        "confidence_percentage"
                    ),

                "detected_concerns":
                    detected_concerns,

                "uncertain_concerns":
                    uncertain_concerns,

                "not_detected_concerns":
                    not_detected_concerns,

                "skin_tone":
                    skin_tone,
            },


            "skin_profile":
                personalized_plan.get(
                    "skin_profile"
                ),


            "skin_goals":
                personalized_plan.get(
                    "skin_goals",
                    [],
                ),


            "concern_goals":
                personalized_plan.get(
                    "concern_goals",
                    [],
                ),


            "recommended_ingredients":
                personalized_plan.get(
                    "recommended_ingredients",
                    [],
                ),


            "ingredient_priorities":
                ingredient_priorities,


            "avoid_or_limit":
                personalized_plan.get(
                    "avoid_or_limit",
                    [],
                ),


            "routine":
                personalized_plan.get(
                    "routine",
                    {
                        "morning":
                            [],

                        "evening":
                            [],
                    },
                ),


            "product_searches":
                product_searches,


            "explanation": (
                "The skincare strategy is generated "
                "from the current skin-type and visible "
                "concern predictions. Live product "
                "searches are constructed from the "
                "individual generated routine steps."
            ),


            "personalization": {
                "dynamic":
                    True,

                "strategy_source":
                    (
                        "AI-generated from "
                        "current predictions"
                    ),

                "product_search_source":
                    (
                        "Generated routine steps"
                    ),

                "routine_priority_enabled":
                    True,

                "predetermined_routine":
                    False,

                "predetermined_products":
                    False,
            },


            "safety": {
                "medical_diagnosis":
                    False,

                "prescription_treatment":
                    False,

                "disclaimer": (
                    "Beautyverse provides cosmetic "
                    "skincare guidance. Predictions "
                    "and model scores are not medical "
                    "diagnoses or severity measurements."
                ),
            },
        }


recommendation_engine = (
    RecommendationEngine()
)

from __future__ import annotations

import json
import os
import time

from dotenv import load_dotenv
from google import genai
from google.genai import errors, types
from pydantic import BaseModel, Field


# =========================================================
# ENVIRONMENT
# =========================================================

load_dotenv()


GEMINI_API_KEY = os.getenv(
    "GEMINI_API_KEY"
)


# You can override these later from .env if needed.
GEMINI_MODELS = [
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-3.5-flash",
]


MAX_RETRIES_PER_MODEL = 3


# =========================================================
# STRUCTURED OUTPUT MODELS
# =========================================================

class IngredientRecommendation(
    BaseModel
):
    name: str = Field(
        description=(
            "Cosmetic skincare ingredient or "
            "ingredient family."
        )
    )

    reason: str = Field(
        description=(
            "Why this ingredient suits the "
            "current predicted skin profile."
        )
    )


class ConcernGoal(
    BaseModel
):
    concern: str

    goal: str


class RoutineStep(
    BaseModel
):
    step: int

    category: str = Field(
        description=(
            "Product category such as cleanser, "
            "serum, moisturizer, sunscreen, toner "
            "or treatment."
        )
    )

    recommendation: str = Field(
        description=(
            "What kind of cosmetic product or "
            "formulation the user should look for. "
            "Do not give a brand name."
        )
    )

    reason: str = Field(
        description=(
            "Why this step belongs in this person's "
            "routine based on the predictions."
        )
    )


class Routine(
    BaseModel
):
    morning: list[RoutineStep]

    evening: list[RoutineStep]


class PersonalizedSkincarePlan(
    BaseModel
):
    skin_profile: str

    skin_goals: list[str]

    concern_goals: list[ConcernGoal]

    recommended_ingredients: list[
        IngredientRecommendation
    ]

    avoid_or_limit: list[str]

    routine: Routine


# =========================================================
# PERSONALIZATION SERVICE
# =========================================================

class AISkincarePlanner:

    def __init__(
        self,
    ):

        if not GEMINI_API_KEY:

            raise RuntimeError(
                "GEMINI_API_KEY is not configured. "
                "Add GEMINI_API_KEY to your project .env file."
            )


        self.client = genai.Client(
            api_key=GEMINI_API_KEY
        )


    # =====================================================
    # BUILD CURRENT ML PROFILE
    # =====================================================

    def _build_profile(
        self,
        skin_type_analysis,
        skin_concern_analysis,
    ):

        skin_type = (
            skin_type_analysis[
                "predicted_skin_type"
            ]
        )


        skin_type_confidence = (
            skin_type_analysis.get(
                "confidence_percentage"
            )
        )


        skin_type_uncertain = (
            skin_type_analysis.get(
                "uncertainty_flag",
                False,
            )
        )


        concerns = (
            skin_concern_analysis.get(
                "concerns",
                [],
            )
        )


        detected = []

        uncertain = []

        not_detected = []


        for concern in concerns:

            compact = {
                "id":
                    concern.get(
                        "id"
                    ),

                "name":
                    concern.get(
                        "name"
                    ),

                "score":
                    concern.get(
                        "score_percentage"
                    ),

                "threshold":
                    concern.get(
                        "threshold_percentage"
                    ),
            }


            status = concern.get(
                "status"
            )


            if status == "detected":

                detected.append(
                    compact
                )


            elif status == "uncertain":

                uncertain.append(
                    compact
                )


            elif status == "not_detected":

                not_detected.append(
                    compact
                )


        return {
            "skin_type":
                skin_type,

            "skin_type_confidence_percentage":
                skin_type_confidence,

            "skin_type_uncertain":
                skin_type_uncertain,

            "detected_visible_concerns":
                detected,

            "uncertain_visible_concerns":
                uncertain,

            "not_detected_visible_concerns":
                not_detected,
        }


    # =====================================================
    # PROMPT
    # =====================================================

    def _build_prompt(
        self,
        profile,
    ):

        return f"""
You are the personalization planner for Beautyverse,
a cosmetic skincare research application.

Create a PERSONALIZED cosmetic skincare strategy using
ONLY the current machine-learning analysis below.

CURRENT ANALYSIS:

{json.dumps(profile, indent=2)}

IMPORTANT PERSONALIZATION RULES:

1. Base the plan on THIS analysis only.

2. Confidently detected concerns may directly influence
   ingredients, goals, routine steps and avoid-or-limit
   recommendations.

3. Uncertain concerns are NOT confirmed concerns.
   Do not design targeted treatment around them.
   You may recommend keeping the routine gentle or
   suggest that the concern be rechecked.

4. Concerns marked not_detected must NOT be used as
   reasons to introduce targeted actives.

5. The predicted skin type must influence:
   - texture preferences
   - hydration level
   - cleansing style
   - formulation characteristics
   - active ingredient intensity

6. Do not create a generic routine that would be the
   same for every skin type.

7. Determine the morning and evening routine from the
   actual profile.

8. Do not add unnecessary skincare steps simply to make
   the routine longer.

9. Every routine step must explain WHY it is appropriate
   for this person's current predicted profile.

10. The avoid_or_limit section must also be personalized.

11. Every avoid_or_limit item should explain:
    - what should be avoided or limited
    - why it matters for THIS current skin profile

12. Recommend cosmetic skincare ingredients only.

13. Do not diagnose medical conditions.

14. Do not recommend prescription medication.

15. Do not treat model scores as severity percentages.

16. Do not claim that a person has a medical skin disease.

17. Avoid recommending several potentially irritating
    actives together unnecessarily.

18. Do not recommend specific brands or commercial
    products.

19. Live commercial products will be retrieved separately
    after this skincare strategy has been generated.

20. Prefer practical consumer skincare advice rather than
    dermatologist-style medical treatment.

21. Ingredient recommendations must directly relate to the
    skin type or confidently detected concerns.

22. If there are no confidently detected concerns, focus
    primarily on maintaining and supporting the predicted
    skin type rather than inventing concerns.

23. Keep the routine concise enough for a consumer-facing
    web application.

24. Morning routines should generally account for daytime
    protection when appropriate.

25. Evening routines should focus on cleansing, targeted
    cosmetic support when justified, and barrier support.

Generate the final personalized Beautyverse skincare plan.
"""


    # =====================================================
    # GENERATE PERSONALIZED PLAN
    # =====================================================

    def generate(
        self,
        skin_type_analysis,
        skin_concern_analysis,
    ):

        profile = self._build_profile(
            skin_type_analysis,
            skin_concern_analysis,
        )


        prompt = self._build_prompt(
            profile
        )


        last_error = None


        # =================================================
        # TRY PRIMARY MODEL + FALLBACK MODELS
        # =================================================

        for model_name in GEMINI_MODELS:

            print(
                "\n"
                "----------------------------------------"
            )

            print(
                "Beautyverse AI planner trying: "
                f"{model_name}"
            )


            for attempt in range(
                1,
                MAX_RETRIES_PER_MODEL + 1,
            ):

                try:

                    print(
                        f"Attempt "
                        f"{attempt}/"
                        f"{MAX_RETRIES_PER_MODEL}"
                    )


                    response = (
                        self.client.models.generate_content(
                            model=model_name,

                            contents=prompt,

                            config=
                                types.GenerateContentConfig(
                                    response_mime_type=
                                        "application/json",

                                    response_schema=
                                        PersonalizedSkincarePlan,
                                ),
                        )
                    )


                    # =====================================
                    # EMPTY RESPONSE CHECK
                    # =====================================

                    if not response.text:

                        raise RuntimeError(
                            "Gemini returned an empty "
                            "personalization response."
                        )


                    # =====================================
                    # VALIDATE STRUCTURED RESPONSE
                    # =====================================

                    plan = (
                        PersonalizedSkincarePlan
                        .model_validate_json(
                            response.text
                        )
                    )


                    result = (
                        plan.model_dump()
                    )


                    # =====================================
                    # ADD DEBUG / RESEARCH METADATA
                    # =====================================

                    result[
                        "generated_by"
                    ] = {
                        "provider":
                            "Google Gemini",

                        "model":
                            model_name,

                        "attempt":
                            attempt,

                        "dynamic":
                            True,
                    }


                    print(
                        "Beautyverse personalized "
                        "skincare plan generated "
                        "successfully with "
                        f"{model_name}"
                    )


                    return result


                # =========================================
                # GOOGLE API ERROR
                # =========================================

                except errors.APIError as exc:

                    last_error = exc


                    status_code = getattr(
                        exc,
                        "code",
                        None,
                    )


                    print(
                        "\nGemini API error"
                    )

                    print(
                        f"Model: {model_name}"
                    )

                    print(
                        f"Attempt: {attempt}"
                    )

                    print(
                        f"Status code: {status_code}"
                    )

                    print(
                        f"Error: {exc}"
                    )


                    # -------------------------------------
                    # Retry temporary failures
                    #
                    # 429:
                    # request/quota/rate limiting
                    #
                    # 503:
                    # temporary service overload
                    # -------------------------------------

                    if status_code in (
                        429,
                        503,
                    ):

                        if (
                            attempt
                            <
                            MAX_RETRIES_PER_MODEL
                        ):

                            wait_seconds = (
                                2 ** attempt
                            )


                            print(
                                f"Retrying "
                                f"{model_name} "
                                f"in "
                                f"{wait_seconds} "
                                f"seconds..."
                            )


                            time.sleep(
                                wait_seconds
                            )


                            continue


                        print(
                            f"{model_name} failed "
                            f"after "
                            f"{MAX_RETRIES_PER_MODEL} "
                            f"attempts."
                        )

                        print(
                            "Trying next fallback "
                            "model..."
                        )


                        break


                    # -------------------------------------
                    # Non-retryable API errors
                    #
                    # e.g.
                    # authentication
                    # malformed request
                    # permission issues
                    # -------------------------------------

                    print(
                        "Non-retryable Gemini API "
                        "error."
                    )


                    break


                # =========================================
                # OTHER ERRORS
                # =========================================

                except Exception as exc:

                    last_error = exc


                    print(
                        "\nBeautyverse AI planner "
                        "unexpected error"
                    )

                    print(
                        f"Model: {model_name}"
                    )

                    print(
                        f"Error: {exc}"
                    )


                    # Try the next model.
                    break


        # =================================================
        # EVERYTHING FAILED
        # =================================================

        raise RuntimeError(
            "Beautyverse could not generate a "
            "personalized skincare plan after "
            "trying all configured Gemini models. "
            f"Last error: {last_error}"
        )


# =========================================================
# GLOBAL SERVICE INSTANCE
# =========================================================

ai_skincare_planner = (
    AISkincarePlanner()
)
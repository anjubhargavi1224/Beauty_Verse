from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

GEMINI_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
]

MAX_RETRIES_PER_MODEL = 1


# =========================================================
# STRUCTURED OUTPUT MODELS
# =========================================================

class IngredientRecommendation(BaseModel):
    name: str = Field(description="Cosmetic skincare active or ingredient family.")
    reason: str = Field(description="Why this ingredient suits the current predicted skin profile.")


class ConcernGoal(BaseModel):
    concern: str
    goal: str


class RoutineStep(BaseModel):
    step: int
    category: str = Field(
        description="Product category: cleanser, serum, moisturizer, sunscreen, toner, or treatment."
    )
    recommendation: str = Field(
        description="Type of cosmetic formulation to seek (do not name brands)."
    )
    reason: str = Field(
        description="Why this step is recommended for this person's skin profile."
    )


class Routine(BaseModel):
    morning: list[RoutineStep]
    evening: list[RoutineStep]


class AvoidOrLimit(BaseModel):
    item: str = Field(description="Ingredient, product type, or skincare habit to limit.")
    reason: str = Field(description="Why it may provoke the detected skin concerns.")


class PersonalizedSkincarePlan(BaseModel):
    skin_profile: str
    skin_goals: list[str]
    concern_goals: list[ConcernGoal]
    recommended_ingredients: list[IngredientRecommendation]
    avoid_or_limit: list[AvoidOrLimit]
    routine: Routine


# =========================================================
# PERSONALIZATION SERVICE
# =========================================================

class AISkincarePlanner:
    def __init__(self):
        self.api_key = GEMINI_API_KEY
        self.client = None

        if self.api_key:
            try:
                from google import genai
                self.client = genai.Client(api_key=self.api_key)
                print("Beautyverse AI planner: Gemini client initialized successfully.")
            except Exception as exc:
                print(f"Beautyverse AI planner: Could not initialize Gemini client ({exc}). Using deterministic planner.")
        else:
            print("Beautyverse AI planner: GEMINI_API_KEY not configured. Using deterministic expert planner.")

    def _build_profile(
        self,
        skin_type_analysis: Dict[str, Any],
        skin_concern_analysis: Dict[str, Any],
        skin_tone_analysis: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        skin_type = skin_type_analysis.get("predicted_skin_type", "Normal")
        skin_type_confidence = skin_type_analysis.get("confidence_percentage", 50.0)

        concerns = skin_concern_analysis.get("concerns", [])
        detected = []
        not_detected = []

        for c in concerns:
            compact = {
                "id": c.get("id"),
                "name": c.get("name"),
                "score": c.get("score_percentage"),
                "threshold": c.get("threshold_percentage"),
            }
            if c.get("status") == "detected":
                detected.append(compact)
            else:
                not_detected.append(compact)

        skin_tone_info = {
            "complexion": skin_tone_analysis.get("complexion", "Medium") if skin_tone_analysis else "Medium",
            "fitzpatrick_scale": skin_tone_analysis.get("fitzpatrick_scale", "Type III") if skin_tone_analysis else "Type III",
            "undertone": skin_tone_analysis.get("undertone", "Neutral") if skin_tone_analysis else "Neutral",
            "uv_sensitivity": skin_tone_analysis.get("uv_sensitivity", "") if skin_tone_analysis else "",
        }

        return {
            "skin_type": skin_type,
            "skin_type_confidence_percentage": skin_type_confidence,
            "skin_tone": skin_tone_info,
            "audience": skin_type_analysis.get("audience", {}),
            "concerns": {
                "detected": detected,
                "not_detected": not_detected,
            },
            "regional_evidence": skin_type_analysis.get("regional_evidence", {}),
        }

    def _generate_deterministic_plan(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        """
        Comprehensive expert cosmetic skincare strategy.
        Tailors formulations, active ingredients, and steps to the exact
        combination of skin type, tone, and concerns.
        """
        raw_st = str(profile.get("skin_type", "Normal")).strip().capitalize()
        skin_type = raw_st if raw_st in ("Oily", "Dry", "Combination", "Normal") else "Normal"
        skin_tone = profile.get("skin_tone", {})
        complexion = skin_tone.get("complexion", "Medium")
        undertone = skin_tone.get("undertone", "Neutral")
        fitzpatrick = skin_tone.get("fitzpatrick_scale", "Type III")

        detected_concerns = [c.get("id") for c in profile.get("concerns", {}).get("detected", [])]

        # 1. Skin Profile Summary
        concerns_summary = ", ".join(detected_concerns) if detected_concerns else "overall skin balance and radiance"
        profile_summary = (
            f"Personalized strategy tailored for {skin_type} skin with a {complexion} ({undertone} undertone) complexion. "
            f"Primary focus: targeted support for {concerns_summary} while preserving epidermal barrier integrity."
        )

        # 2. Recommended Actives based on Skin Type & Detected Concerns
        ingredients = []
        avoid = []
        goals = []
        concern_goals = []

        # Baseline ingredients by skin type
        if skin_type == "Oily":
            ingredients.append({"name": "Niacinamide (3-5%)", "reason": "Regulates excess sebum production and minimizes appearance of pores without stripping."})
            ingredients.append({"name": "Zinc PCA", "reason": "Provides antimicrobial sebum balancing to maintain a matte, calm barrier."})
            avoid.append({"item": "Heavy mineral oils and thick petrolatum balms", "reason": "Can trap sebum and exacerbate comedones on oil-prone skin."})
            goals.append("Balance sebum production while keeping the skin barrier hydrated.")
        elif skin_type == "Dry":
            ingredients.append({"name": "Multi-molecular Hyaluronic Acid", "reason": "Draws moisture into dehydrated skin layers to plump and hydrate."})
            ingredients.append({"name": "Ceramide Complex (NP, AP, EOP)", "reason": "Restores the depleted lipid matrix to prevent trans-epidermal water loss."})
            avoid.append({"item": "Denatured alcohol (Alcohol Denat) and foaming sulfates", "reason": "Strips natural surface lipids, exacerbating tightness and flakiness."})
            goals.append("Deeply hydrate and reinforce lipid barrier to prevent moisture loss.")
        elif skin_type == "Combination":
            ingredients.append({"name": "Niacinamide (4%)", "reason": "Balances shine in the T-zone while maintaining barrier hydration on the cheeks."})
            ingredients.append({"name": "Polyglutamic Acid or Squalane", "reason": "Lightweight weightless hydration suitable for dual-zone balance."})
            avoid.append({"item": "One-size-fits-all heavy pore-clogging butters", "reason": "Can over-saturate the T-zone even if cheeks feel dry."})
            goals.append("Refine and de-shine T-zone while hydrating cheeks.")
        else:  # Normal
            ingredients.append({"name": "Centella Asiatica (Cica)", "reason": "Maintains calm equilibrium and soothes daily environmental stressors."})
            ingredients.append({"name": "Panthenol (Vitamin B5)", "reason": "Maintains natural moisture balance and elasticity."})
            avoid.append({"item": "Overusing aggressive physical scrubs", "reason": "Disrupts an already balanced epidermal barrier."})
            goals.append("Maintain optimal barrier health, protection, and luminosity.")

        # Concern-specific additions
        if "acne" in detected_concerns:
            ingredients.append({"name": "Salicylic Acid (1-2% BHA)", "reason": "Lipophilic BHA penetrates pores to dissolve trapped sebum and clear blemishes."})
            avoid.append({"item": "Fragrance-heavy comedogenic facial oils", "reason": "Can irritate active blemishes and provoke micro-comedones."})
            concern_goals.append({"concern": "Acne / Blemishes", "goal": "Unclog congested pores and reduce microbial proliferation."})

        if "pigmentation" in detected_concerns:
            ingredients.append({"name": "Azelaic Acid (10%) or Alpha Arbutin", "reason": "Inhibits tyrosinase to gently fade dark spots and even tone without hypopigmentation."})
            avoid.append({"item": "Unprotected sun exposure without broad-spectrum SPF", "reason": "UV radiation directly stimulates melanogenesis, darkening existing spots."})
            concern_goals.append({"concern": "Pigmentation", "goal": "Fade localized hyperpigmentation and prevent post-inflammatory discoloration."})

        if "redness" in detected_concerns:
            ingredients.append({"name": "Madecassoside & Green Tea Extract", "reason": "Provides potent antioxidant vascular calming to reduce cutaneous erythema."})
            avoid.append({"item": "High-concentration glycolic acid or essential oils", "reason": "Can trigger reactive flushing and compromise delicate facial capillaries."})
            concern_goals.append({"concern": "Redness", "goal": "Soothe facial flush, reinforce capillary resilience, and calm irritation."})

        if "pores" in detected_concerns:
            if not any(i["name"].startswith("Niacinamide") for i in ingredients):
                ingredients.append({"name": "Niacinamide (5%)", "reason": "Improves pore wall elasticity and texture smoothness."})
            concern_goals.append({"concern": "Visible Pores", "goal": "Tighten pore elasticity and refine central facial texture."})

        if "wrinkles" in detected_concerns:
            ingredients.append({"name": "Copper Peptides or Bakuchiol", "reason": "Stimulates collagen synthesis and cellular turnover without retinoid irritation."})
            avoid.append({"item": "Dehydrating cleansers", "reason": "Exaggerates the visual depth of surface fine lines."})
            concern_goals.append({"concern": "Fine Lines / Wrinkles", "goal": "Improve surface elasticity, plump micro-lines, and promote firm skin texture."})

        # Tone/UV specific sunscreen guidance
        if fitzpatrick in ("Type IV", "Type V", "Type VI"):
            sunscreen_type = "Invisible fluid chemical/hybrid SPF 50+ PA++++ (zero white cast)"
            sunscreen_reason = f"Protects {complexion} skin against UV-induced hyperpigmentation while blending cleanly without ashy white residue."
        else:
            sunscreen_type = "Broad-Spectrum mineral/hybrid SPF 50+ PA++++"
            sunscreen_reason = f"Provides maximum broad-spectrum UV shielding essential for UV-sensitive {complexion} skin."

        # Morning Routine
        morning_steps = [
            RoutineStep(
                step=1,
                category="cleanser",
                recommendation="Low-pH balancing gel cleanser" if skin_type in ("Oily", "Combination") else "Gentle hydrating cream-to-foam cleanser",
                reason="Gently lifts overnight sebum and metabolic residue without disrupting natural barrier lipids.",
            ),
            RoutineStep(
                step=2,
                category="serum",
                recommendation=f"Targeted {ingredients[0]['name'].split('(')[0].strip()} antioxidant serum",
                reason=ingredients[0]["reason"],
            ),
            RoutineStep(
                step=3,
                category="moisturizer",
                recommendation="Oil-free light water gel" if skin_type == "Oily" else "Lightweight barrier lotion" if skin_type == "Combination" else "Ceramide-rich nourishing cream",
                reason="Locks in hydration and maintains optimal moisture barrier throughout the day.",
            ),
            RoutineStep(
                step=4,
                category="sunscreen",
                recommendation=sunscreen_type,
                reason=sunscreen_reason,
            ),
        ]

        # Evening Routine
        evening_steps = [
            RoutineStep(
                step=1,
                category="cleanser",
                recommendation="Gentle purifying double-cleanser or cleansing oil followed by gentle face wash",
                reason="Thoroughly removes daytime sunscreen, pollutants, and sebum build-up.",
            ),
            RoutineStep(
                step=2,
                category="treatment",
                recommendation=f"Restorative {ingredients[min(1, len(ingredients)-1)]['name'].split('(')[0].strip()} corrective treatment",
                reason="Accelerates overnight cellular repair, targeting active concerns during resting phase.",
            ),
            RoutineStep(
                step=3,
                category="moisturizer",
                recommendation="Overnight barrier recovery cream with peptides and ceramides",
                reason="Supports overnight lipid synthesis and prevents nocturnal trans-epidermal water loss.",
            ),
        ]

        return {
            "skin_profile": profile_summary,
            "skin_goals": goals if goals else ["Maintain healthy barrier balance and radiance."],
            "concern_goals": concern_goals,
            "recommended_ingredients": ingredients[:4],
            "avoid_or_limit": avoid[:3],
            "routine": {
                "morning": [s.model_dump() for s in morning_steps],
                "evening": [s.model_dump() for s in evening_steps],
            },
            "generated_by": {
                "provider": "BeautyVerse Expert Skincare Engine",
                "model": "calibrated_profile_synthesis",
                "dynamic": True,
            },
        }

    def generate(
        self,
        skin_type_analysis: Dict[str, Any],
        skin_concern_analysis: Dict[str, Any],
        skin_tone_analysis: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Generate a personalized skincare plan.
        Tries Gemini structured generation first if available,
        falling back cleanly to the deterministic expert engine.
        """
        profile = self._build_profile(
            skin_type_analysis,
            skin_concern_analysis,
            skin_tone_analysis,
        )

        if not self.client:
            return self._generate_deterministic_plan(profile)

        # Attempt Gemini LLM structured plan
        prompt = (
            "You are the BeautyVerse expert cosmetic skincare specialist.\n"
            f"Analyze this verified skin profile including skin type, complexion, undertone, and regional optical evidence:\n{json.dumps(profile, indent=2)}\n\n"
            "Create a personalized, science-backed skincare routine with morning and evening steps, "
            "recommended cosmetic actives, items to avoid, and tone-appropriate sunscreen formulations (e.g. non-white-cast for deeper skin tones). "
            "Recommend formulation types, not brand names."
        )

        for model_name in GEMINI_MODELS:
            for attempt in range(1, MAX_RETRIES_PER_MODEL + 1):
                try:
                    response = self.client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config={
                            "response_mime_type": "application/json",
                            "response_schema": PersonalizedSkincarePlan,
                            "temperature": 0.2,
                        },
                    )
                    data = json.loads(response.text)
                    data["generated_by"] = {
                        "provider": "Google Gemini",
                        "model": model_name,
                        "dynamic": True,
                    }
                    return data
                except Exception as exc:
                    print(f"Gemini {model_name} attempt {attempt} failed: {exc}")
                    err_str = str(exc)
                    if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                        print("Gemini quota exhausted. Immediately falling back to BeautyVerse deterministic planner.")
                        return self._generate_deterministic_plan(profile)
                    time.sleep(1)
                    break

        print("Falling back to BeautyVerse deterministic expert planner.")
        return self._generate_deterministic_plan(profile)


ai_skincare_planner = AISkincarePlanner()

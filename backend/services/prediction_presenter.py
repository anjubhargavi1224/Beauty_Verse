from __future__ import annotations

from typing import Any, Dict, List, Optional


class PredictionPresenter:
    """
    Beautyverse Presentation Layer.
    Translates raw ML outputs and regional metrics into user-friendly,
    transparent, and actionable cosmetic profiles without returning 'Uncertain'.
    """

    # =====================================================
    # SKIN TYPE PRESENTATION
    # =====================================================

    def present_skin_type(
        self,
        skin_type_analysis: Dict[str, Any],
    ) -> Dict[str, Any]:
        predicted = skin_type_analysis.get("predicted_skin_type", "Normal")
        score = skin_type_analysis.get("confidence_percentage", 50.0)
        level = skin_type_analysis.get("confidence_level", "calibrated")
        margin = skin_type_analysis.get("top_two_margin_percentage", 0.0)
        probabilities = skin_type_analysis.get("probabilities", [])

        second_choice = probabilities[1] if len(probabilities) >= 2 else None

        if level == "stronger":
            confidence_label = "High confidence pattern"
        elif level == "moderate":
            confidence_label = "Distinct pattern match"
        else:
            confidence_label = "Calibrated best match"

        if second_choice:
            summary = (
                f"Your selfie most strongly matches {predicted} skin ({score}% match). "
                f"The next closest pattern was {second_choice.get('skin_type')} at {second_choice.get('percentage')}%."
            )
        else:
            summary = f"Your selfie most strongly matches {predicted} skin."

        source = skin_type_analysis.get("source", "image_model")
        if source in ("self_reported", "questionnaire_pattern"):
            confidence_label = "Self-reported" if source == "self_reported" else "Questionnaire profile"
            summary = f"{predicted} is the baseline skin type derived from your questionnaire."

        return {
            "source": source,
            "label": predicted,
            "headline": f"{predicted} Skin Profile",
            "model_score_percentage": score,
            "preference_label": confidence_label,
            "top_two_margin_percentage": margin,
            "summary": summary,
            "score_note": (
                "Skin type reflects balanced optical sebum shine and texture metrics across facial zones."
            ),
        }

    # =====================================================
    # SKIN TONE PRESENTATION
    # =====================================================

    def present_skin_tone(
        self,
        skin_tone_analysis: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        if not skin_tone_analysis:
            return {
                "complexion": "Medium",
                "fitzpatrick_scale": "Type III",
                "undertone": "Neutral",
                "undertone_description": "Balanced warm and cool undertones",
                "display_label": "Medium (Neutral Undertone)",
                "uv_sensitivity": "Moderately sensitive to UV",
                "representative_hex": "#c89d7c",
            }

        return {
            "complexion": skin_tone_analysis.get("complexion", "Medium"),
            "fitzpatrick_scale": skin_tone_analysis.get("fitzpatrick_scale", "Type III"),
            "undertone": skin_tone_analysis.get("undertone", "Neutral"),
            "undertone_description": skin_tone_analysis.get("undertone_description", ""),
            "display_label": skin_tone_analysis.get("display_label", "Medium"),
            "ita_degrees": skin_tone_analysis.get("ita_degrees", 35.0),
            "uv_sensitivity": skin_tone_analysis.get("uv_sensitivity", ""),
            "representative_hex": skin_tone_analysis.get("color_metrics", {}).get("representative_hex", "#c89d7c"),
            "rgb": skin_tone_analysis.get("color_metrics", {}).get("rgb", [200, 157, 124]),
        }

    # =====================================================
    # CONCERN PRESENTATION
    # =====================================================

    def present_concern(
        self,
        concern: Dict[str, Any],
    ) -> Dict[str, Any]:
        concern_id = concern.get("id", "")
        name = concern.get("name", concern_id.title())
        score = float(concern.get("score", 0.0))
        threshold = float(concern.get("threshold", 0.5))
        status = concern.get("status", "not_detected")
        rationale = concern.get("regional_rationale", "")
        distance = score - threshold

        if status == "detected":
            display_status = "Observed concern"
            short_status = "Active signal"
            priority = "confirmed"
            signal_label = "Confirmed with regional evidence" if rationale else "Detected above threshold"
            message = (
                f"Visible characteristics associated with {name.lower()} were identified. "
                + (rationale if rationale else "Features crossed calibrated visual thresholds.")
            )
        else:
            display_status = "Not observed"
            short_status = "Minimal / clear"
            priority = "none"
            signal_label = "Below detection threshold"
            message = (
                f"No significant visual indication of {name.lower()} detected. "
                + (rationale if rationale else "Skin looks calm in this zone.")
            )

        return {
            "id": concern_id,
            "name": name,
            "raw_status": status,
            "display_status": display_status,
            "short_status": short_status,
            "priority": priority,
            "signal_label": signal_label,
            "model_score_percentage": round(score * 100, 1),
            "threshold_percentage": round(threshold * 100, 1),
            "distance_from_threshold": round(distance, 4),
            "message": message,
            "score_note": "Calibrated optical score compared against validation baseline.",
        }

    # =====================================================
    # COMPLETE PRESENTATION BUILDER
    # =====================================================

    def build(
        self,
        skin_type_analysis: Dict[str, Any],
        skin_concern_analysis: Dict[str, Any],
        skin_tone_analysis: Optional[Dict[str, Any]] = None,
        regional_summary: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        skin_type = self.present_skin_type(skin_type_analysis)
        skin_tone = self.present_skin_tone(skin_tone_analysis)

        presented_concerns = [
            self.present_concern(c)
            for c in skin_concern_analysis.get("concerns", [])
        ]

        detected = [
            c["name"]
            for c in presented_concerns
            if c["priority"] == "confirmed"
        ]

        if skin_type.get("source") in ("self_reported", "questionnaire_pattern"):
            overall_summary = skin_type["summary"]
            if detected:
                overall_summary += " Possible image concern signals: " + ", ".join(detected) + "."
        elif detected:
            concerns_text = ", ".join(detected)
            overall_summary = (
                f"Your skin profile matches {skin_type['label']} with a {skin_tone['display_label']} complexion. "
                f"Primary areas of focus identified: {concerns_text}."
            )
        else:
            overall_summary = (
                f"Your skin profile matches {skin_type['label']} with a {skin_tone['display_label']} complexion. "
                f"Skin appears balanced with no severe visible concerns detected."
            )

        return {
            "headline": "Your Beautyverse Skin Profile",
            "skin_type": skin_type,
            "skin_tone": skin_tone,
            "concerns": presented_concerns,
            "confirmed_concerns": detected,
            "needs_recheck": [],  # Deprecated in favor of clear determination
            "summary": overall_summary,
            "regional_summary": regional_summary or {},
            "guidance": {
                "confirmed_results_drive_recommendations": True,
                "scores_represent_severity": False,
            },
            "disclaimer": (
                "Beautyverse provides cosmetic skin and tone analysis for personalized beauty guidance. "
                "It is not a medical or dermatological diagnosis."
            ),
        }


prediction_presenter = PredictionPresenter()

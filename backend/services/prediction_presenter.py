from __future__ import annotations


class PredictionPresenter:

    # =====================================================
    # SKIN TYPE PRESENTATION
    # =====================================================

    def present_skin_type(
        self,
        skin_type_analysis,
    ):

        predicted = (
            skin_type_analysis.get(
                "predicted_skin_type"
            )
        )


        score = (
            skin_type_analysis.get(
                "confidence_percentage"
            )
        )


        level = (
            skin_type_analysis.get(
                "confidence_level",
                "unknown",
            )
        )


        margin = (
            skin_type_analysis.get(
                "top_two_margin_percentage"
            )
        )


        probabilities = (
            skin_type_analysis.get(
                "probabilities",
                [],
            )
        )


        second_choice = None


        if len(
            probabilities
        ) >= 2:

            second_choice = (
                probabilities[1]
            )


        if level == "stronger":

            confidence_label = (
                "Clear model preference"
            )

        elif level == "moderate":

            confidence_label = (
                "Moderate model preference"
            )

        elif level == "uncertain":

            confidence_label = (
                "Low model separation"
            )

        else:

            confidence_label = (
                "Model prediction"
            )


        if second_choice:

            summary = (
                f"The model most strongly matched "
                f"{predicted} skin. The next closest "
                f"pattern was "
                f"{second_choice.get('skin_type')} "
                f"at "
                f"{second_choice.get('percentage')}%."
            )

        else:

            summary = (
                f"The model most strongly matched "
                f"{predicted} skin."
            )


        return {
            "label":
                predicted,

            "headline":
                (
                    f"{predicted} skin pattern"
                ),

            "model_score_percentage":
                score,

            "preference_label":
                confidence_label,

            "top_two_margin_percentage":
                margin,

            "summary":
                summary,

            "score_note": (
                "The percentage is the model's "
                "classification score, not a clinical "
                "measurement of the skin."
            ),
        }


    # =====================================================
    # CONCERN PRESENTATION
    # =====================================================

    def present_concern(
        self,
        concern,
    ):

        concern_id = (
            concern.get(
                "id"
            )
        )


        name = (
            concern.get(
                "name"
            )
        )


        score = float(
            concern.get(
                "score",
                0.0,
            )
        )


        threshold = float(
            concern.get(
                "threshold",
                0.5,
            )
        )


        status = (
            concern.get(
                "status"
            )
        )


        distance = (
            score
            -
            threshold
        )


        if status == "detected":

            display_status = (
                "Detected"
            )

            short_status = (
                "Visible signal found"
            )

            priority = (
                "confirmed"
            )


            if distance >= 0.20:

                signal_label = (
                    "Clear model signal"
                )

            else:

                signal_label = (
                    "Model signal above threshold"
                )


            message = (
                f"Visible features associated with "
                f"{name.lower()} crossed the model's "
                f"validation-derived detection threshold."
            )


        elif status == "uncertain":

            display_status = (
                "Needs another look"
            )

            short_status = (
                "Borderline result"
            )

            priority = (
                "review"
            )

            signal_label = (
                "Close to decision threshold"
            )

            message = (
                "The model score is close to its "
                "decision threshold. Beautyverse will "
                "not use this result as a confirmed "
                "concern when choosing products."
            )


        else:

            display_status = (
                "Not detected"
            )

            short_status = (
                "No strong signal"
            )

            priority = (
                "none"
            )


            if distance <= -0.20:

                signal_label = (
                    "Low model signal"
                )

            else:

                signal_label = (
                    "Below detection threshold"
                )


            message = (
                f"This image did not show a strong "
                f"enough visual signal for "
                f"{name.lower()} to cross the model's "
                f"detection threshold."
            )


        return {
            "id":
                concern_id,

            "name":
                name,

            "raw_status":
                status,

            "display_status":
                display_status,

            "short_status":
                short_status,

            "priority":
                priority,

            "signal_label":
                signal_label,

            "model_score_percentage":
                round(
                    score * 100,
                    2,
                ),

            "threshold_percentage":
                round(
                    threshold * 100,
                    2,
                ),

            "distance_from_threshold":
                round(
                    distance,
                    4,
                ),

            "message":
                message,

            "score_note": (
                "The model score is not a measure "
                "of severity."
            ),
        }


    # =====================================================
    # COMPLETE PRESENTATION
    # =====================================================

    def build(
        self,
        skin_type_analysis,
        skin_concern_analysis,
    ):

        skin_type = (
            self.present_skin_type(
                skin_type_analysis
            )
        )


        presented_concerns = [
            self.present_concern(
                concern
            )

            for concern
            in skin_concern_analysis.get(
                "concerns",
                [],
            )
        ]


        detected = [
            concern[
                "name"
            ]

            for concern
            in presented_concerns

            if concern[
                "priority"
            ]
            == "confirmed"
        ]


        review = [
            concern[
                "name"
            ]

            for concern
            in presented_concerns

            if concern[
                "priority"
            ]
            == "review"
        ]


        if detected:

            detected_text = (
                ", ".join(
                    detected
                )
            )

            overall_summary = (
                f"The current image most strongly "
                f"matches {skin_type['label']} skin. "
                f"Visible concern signals were found "
                f"for {detected_text}."
            )

        else:

            overall_summary = (
                f"The current image most strongly "
                f"matches {skin_type['label']} skin. "
                f"No visible concern passed the "
                f"confirmed detection threshold."
            )


        if review:

            overall_summary += (
                " Some borderline results would "
                "benefit from another well-lit selfie."
            )


        return {
            "headline":
                "Your Beautyverse Skin Profile",

            "skin_type":
                skin_type,

            "concerns":
                presented_concerns,

            "confirmed_concerns":
                detected,

            "needs_recheck":
                review,

            "summary":
                overall_summary,

            "guidance": {
                "confirmed_results_drive_recommendations":
                    True,

                "uncertain_results_drive_recommendations":
                    False,

                "scores_represent_severity":
                    False,
            },

            "disclaimer": (
                "Beautyverse analyses visible cosmetic "
                "skin patterns from an image. It does "
                "not diagnose medical skin conditions."
            ),
        }


prediction_presenter = (
    PredictionPresenter()
)
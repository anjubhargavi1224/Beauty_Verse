from backend.services.bounded_work import bounded_call
from backend.services.questionnaire_profile import parse_answers, reconcile
import cv2

from fastapi import (
    FastAPI,
    File,
    Form,
    HTTPException,
    Response,
    UploadFile,
)

from fastapi.middleware.cors import (
    CORSMiddleware,
)

from backend.services.face_detection import (
    face_detection_service,
)

from backend.services.skin_regions import (
    skin_region_service,
)

from backend.services.skin_type_classifier import (
    skin_type_classifier_service,
)

from backend.services.recommendation_engine import (
    recommendation_engine,
)

from backend.services.skin_concern_classifier import (
    skin_concern_classifier_service,
)

from backend.services.product_search import (
    product_search_service,
)

from backend.services.ai_skincare_planner import (
    ai_skincare_planner,
)

from backend.services.skin_tone_estimator import (
    skin_tone_estimator,
)

from backend.services.prediction_presenter import (
    prediction_presenter,
)

# =========================================================
# FASTAPI APP
# =========================================================

app = FastAPI(
    title="Beautyverse API",
    description=(
        "AI-powered cosmetic skin analysis "
        "backend for Beautyverse"
    ),
    version="1.0.0",
)


# =========================================================
# CORS
# =========================================================

app.add_middleware(
    CORSMiddleware,

    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],

    allow_credentials=True,

    allow_methods=[
        "*"
    ],

    allow_headers=[
        "*"
    ],
)


# =========================================================
# UPLOAD SETTINGS
# =========================================================

ALLOWED_IMAGE_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
}


MAX_IMAGE_SIZE = (
    10
    * 1024
    * 1024
)


# =========================================================
# IMAGE VALIDATION
# =========================================================

async def validate_upload(
    image: UploadFile,
):

    if (
        image.content_type
        not in
        ALLOWED_IMAGE_TYPES
    ):

        raise HTTPException(
            status_code=400,

            detail=(
                "Please upload a JPG, JPEG, "
                "PNG, or WEBP image."
            ),
        )


    image_bytes = (
        await image.read()
    )


    if not image_bytes:

        raise HTTPException(
            status_code=400,

            detail=(
                "Uploaded image is empty."
            ),
        )


    if (
        len(
            image_bytes
        )
        >
        MAX_IMAGE_SIZE
    ):

        raise HTTPException(
            status_code=413,

            detail=(
                "Image must be smaller "
                "than 10 MB."
            ),
        )


    return image_bytes


# =========================================================
# ROOT
# =========================================================

@app.get("/")
def root():

    return {
        "application":
            "Beautyverse API",

        "status":
            "running",

        "message": (
            "Beautyverse AI backend "
            "is running successfully."
        ),
    }


# =========================================================
# HEALTH CHECK
# =========================================================

@app.get("/health")
def health_check():

    return {
        "status":
            "healthy"
    }


# =========================================================
# FACE ANALYSIS
# =========================================================

@app.post(
    "/api/analyze-face"
)
async def analyze_face(
    image: UploadFile = File(...),
):

    try:

        image_bytes = (
            await validate_upload(
                image
            )
        )


        result = (
            face_detection_service
            .analyze(
                image_bytes
            )
        )


        if not result[
            "face_detected"
        ]:

            return {
                "success":
                    False,

                "message": (
                    "No face was detected. "
                    "Please upload a clear "
                    "front-facing selfie."
                ),

                "analysis":
                    result,
            }


        return {
            "success":
                True,

            "message": (
                "Face detected successfully."
            ),

            "analysis":
                result,
        }


    except HTTPException:

        raise


    except ValueError as exc:

        raise HTTPException(
            status_code=400,

            detail=str(
                exc
            ),
        )


    except Exception as exc:

        print(
            f"Face analysis error: "
            f"{type(exc).__name__}"
        )


        raise HTTPException(
            status_code=500,

            detail=(
                "An error occurred while "
                "analysing the image."
            ),
        )


# =========================================================
# SKIN REGIONS
# =========================================================

@app.post(
    "/api/analyze-skin-regions"
)
async def analyze_skin_regions(
    image: UploadFile = File(...),
):

    try:

        image_bytes = (
            await validate_upload(
                image
            )
        )


        cv_image, result = (
            face_detection_service
            .detect(
                image_bytes
            )
        )


        if not result.face_landmarks:

            return {
                "success":
                    False,

                "message": (
                    "No face was detected."
                ),
            }


        landmarks = (
            result.face_landmarks[0]
        )


        region_result = (
            skin_region_service
            .extract(
                cv_image,
                landmarks,
            )
        )


        return {
            "success":
                True,

            "message": (
                "Skin regions extracted "
                "successfully."
            ),

            "region_count":
                len(
                    region_result[
                        "regions"
                    ]
                ),

            "analysis":
                region_result,
        }


    except HTTPException:

        raise


    except ValueError as exc:

        raise HTTPException(
            status_code=400,

            detail=str(
                exc
            ),
        )


    except Exception as exc:

        print(
            "Region extraction error: "
            f"{type(exc).__name__}"
        )


        raise HTTPException(
            status_code=500,

            detail=(
                "An error occurred during "
                "skin region extraction."
            ),
        )


# =========================================================
# DEBUG SKIN REGIONS
# =========================================================

@app.post(
    "/api/debug-skin-regions"
)
async def debug_skin_regions(
    image: UploadFile = File(...),
):

    """
    Development-only endpoint.

    Returns a JPEG showing the regions
    Beautyverse extracted from the face.
    """

    image_bytes = (
        await validate_upload(
            image
        )
    )


    cv_image, result = (
        face_detection_service
        .detect(
            image_bytes
        )
    )


    if not result.face_landmarks:

        raise HTTPException(
            status_code=400,

            detail=(
                "No face detected."
            ),
        )


    landmarks = (
        result.face_landmarks[0]
    )


    region_result = (
        skin_region_service
        .extract(
            cv_image,
            landmarks,
        )
    )


    annotated = (
        skin_region_service
        .annotate(
            cv_image,
            region_result,
        )
    )


    success, encoded = (
        cv2.imencode(
            ".jpg",
            annotated,
        )
    )


    if not success:

        raise HTTPException(
            status_code=500,

            detail=(
                "Could not create "
                "debug image."
            ),
        )


    return Response(
        content=(
            encoded.tobytes()
        ),

        media_type=
            "image/jpeg",
    )


# =========================================================
# SKIN TYPE ANALYSIS
# =========================================================

@app.post(
    "/api/analyze-skin-type"
)
async def analyze_skin_type(
    image: UploadFile = File(...),
):

    """
    Beautyverse skin-type pipeline:

    1. Validate image
    2. Detect face
    3. Extract landmarks
    4. Check image quality
    5. Crop face
    6. Run EfficientNet-B0
    7. Return skin-type probabilities
    """

    try:

        image_bytes = (
            await validate_upload(
                image
            )
        )


        # Run MediaPipe once.

        cv_image, face_result = (
            face_detection_service
            .detect(
                image_bytes
            )
        )


        if not (
            face_result.face_landmarks
        ):

            return {
                "success":
                    False,

                "reason":
                    "no_face_detected",

                "message": (
                    "No face was detected. "
                    "Please upload a clear, "
                    "front-facing selfie."
                ),
            }


        landmarks = (
            face_result
            .face_landmarks[0]
        )


        region_result = (
            skin_region_service
            .extract(
                cv_image,
                landmarks,
            )
        )


        capture_quality = (
            region_result[
                "capture_quality"
            ]
        )


        if not capture_quality[
            "usable"
        ]:

            return {
                "success":
                    False,

                "reason":
                    "image_quality",

                "message": (
                    "The image quality is not "
                    "suitable for reliable "
                    "skin analysis. Please use "
                    "a clear, well-lit selfie."
                ),

                "capture_quality":
                    capture_quality,
            }


        skin_tone_analysis = (
            skin_tone_estimator
            .estimate(
                cv_image,
                landmarks,
            )
        )

        prediction = (
            skin_type_classifier_service
            .predict(
                cv_image,
                landmarks,
                regional_summary=region_result.get("regional_summary"),
            )
        )

        return {
            "success":
                True,

            "message": (
                "Skin type analysis "
                "completed successfully."
            ),

            "capture_quality":
                capture_quality,

            "skin_type_analysis":
                prediction,

            "skin_tone_analysis":
                skin_tone_analysis,

            "skin_regions":
                region_result[
                    "regions"
                ],

            "regional_summary":
                region_result.get("regional_summary"),
        }


    except HTTPException:

        raise


    except ValueError as exc:

        raise HTTPException(
            status_code=400,

            detail=str(
                exc
            ),
        )


    except Exception as exc:

        print(
            "Skin type analysis error: "
            f"{type(exc).__name__}"
        )


        raise HTTPException(
            status_code=500,

            detail=(
                "An error occurred while "
                "analysing skin type."
            ),
        )


# =========================================================
# COMPLETE BEAUTYVERSE ANALYSIS
# =========================================================

@app.post(
    "/api/beautyverse-analysis"
)
async def beautyverse_analysis(
    image: UploadFile = File(...),
    preview_only: bool = False,
    questionnaire: str | None = Form(None),
):

    """
    Complete Beautyverse pipeline.

    Selfie
        ↓
    MediaPipe
        ↓
    Capture-quality validation
        ↓
    EfficientNet skin-type model
        ↓
    EfficientNet skin-concern model
        ↓
    Gemini personalized skincare strategy
        ↓
    Dynamic recommendation generation
        ↓
    Live product retrieval
    """

    try:
        try:
            answers = parse_answers(questionnaire)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        # =================================================
        # 1. VALIDATE IMAGE
        # =================================================

        image_bytes = (
            await validate_upload(
                image
            )
        )


        # =================================================
        # 2. FACE DETECTION
        # =================================================

        cv_image, face_result = (
            face_detection_service
            .detect(
                image_bytes
            )
        )


        if not (
            face_result.face_landmarks
        ):

            return {
                "success":
                    False,

                "reason":
                    "no_face_detected",

                "message": (
                    "No face was detected. "
                    "Please upload a clear "
                    "front-facing selfie."
                ),
            }


        landmarks = (
            face_result
            .face_landmarks[0]
        )


        # =================================================
        # 3. SKIN REGIONS + QUALITY
        # =================================================

        region_result = (
            skin_region_service
            .extract(
                cv_image,
                landmarks,
            )
        )


        capture_quality = (
            region_result[
                "capture_quality"
            ]
        )


        if not capture_quality[
            "usable"
        ]:

            return {
                "success":
                    False,

                "reason":
                    "image_quality",

                "message": (
                    "This image is not suitable "
                    "for reliable analysis. "
                    "Please use a clear selfie "
                    "with even lighting."
                ),

                "capture_quality":
                    capture_quality,
            }


        # =================================================
        # 4. SKIN TONE & COMPLEXION
        # =================================================

        skin_tone_analysis = (
            skin_tone_estimator
            .estimate(
                cv_image,
                landmarks,
            )
        )


        # =================================================
        # 5. SKIN TYPE WITH REGIONAL FUSION
        # =================================================

        skin_type_analysis = (
            skin_type_classifier_service
            .predict(
                cv_image,
                landmarks,
                regional_summary=region_result.get("regional_summary"),
            )
        )


        # =================================================
        # 6. REGION-AWARE SKIN CONCERNS
        # =================================================

        skin_concern_analysis = (
            skin_concern_classifier_service
            .predict(
                cv_image,
                landmarks,
                regions_data=region_result,
            )
        )

        questionnaire_profile, guidance_skin_type = reconcile(answers, skin_type_analysis)

        prediction_presentation = (
            prediction_presenter.build(
                guidance_skin_type,
                skin_concern_analysis,
                skin_tone_analysis=skin_tone_analysis,
                regional_summary=region_result.get("regional_summary"),
            )
        )

        # Live frames run the same ML and quality checks without generating
        # a paid AI plan or making shopping requests for every frame.
        if preview_only:
            return {
                "success": True,
                "analysis": {
                    "questionnaire_profile": questionnaire_profile,
                    "capture_quality": capture_quality,
                    "skin_type": skin_type_analysis,
                    "skin_tone": skin_tone_analysis,
                    "skin_concerns": skin_concern_analysis,
                    "presentation": prediction_presentation,
                    "skin_regions": region_result["regions"],
                    "regional_summary": region_result.get("regional_summary"),
                },
            }


        # =================================================
        # 7. DYNAMIC AI SKINCARE PLAN
        # =================================================

        try:

            personalized_plan = await bounded_call(
                ai_skincare_planner.generate,
                guidance_skin_type,
                skin_concern_analysis,
                skin_tone_analysis,
                timeout=15,
            )


        except Exception as exc:

            print(
                "AI skincare planner unavailable: "
                f"{type(exc).__name__}. Using deterministic expert planner."
            )

            profile = ai_skincare_planner._build_profile(
                guidance_skin_type or {},
                skin_concern_analysis or {},
                skin_tone_analysis or {},
            )
            personalized_plan = ai_skincare_planner._generate_deterministic_plan(profile)


        # =================================================
        # 7. BUILD DYNAMIC RECOMMENDATION PROFILE
        # =================================================

        recommendations = (
            recommendation_engine
            .generate(
                guidance_skin_type,
                skin_concern_analysis,
                personalized_plan,
                skin_tone=skin_tone_analysis,
            )
        )
        recommendations["regional_evidence"] = skin_type_analysis.get("regional_evidence", {})
        recommendations["skin_tone"] = skin_tone_analysis

        # =================================================
        # 8. LIVE PRODUCT SEARCH
        #
        # Shopping search failure must also NOT crash
        # the actual skin analysis.
        # =================================================

        try:

            live_products = await bounded_call(
                product_search_service.search_for_profile, recommendations, timeout=30,
            )


        except Exception as exc:

            print(
                "Live product search error: "
                f"{type(exc).__name__}"
            )


            live_products = {
                "provider":
                    "Google Shopping via SerpAPI",

                "status":
                    "unavailable",

                "products":
                    [],

                "product_count":
                    0,

                "error_type": type(exc).__name__,
                "message": "Product matching failed. See the diagnostic error type.",
            }


        recommendations["plan_status"] = personalized_plan.get("generated_by", {}).get("status", "generated")

        # Attach live search results to
        # the recommendation response.

        recommendations[
            "live_products"
        ] = live_products


        # =================================================
        # 9. FINAL RESPONSE
        # =================================================

        return {
            "success":
                True,

            "message": (
                "Beautyverse analysis "
                "completed successfully."
            ),

            "analysis": {
                "questionnaire_profile": questionnaire_profile,
                "capture_quality":
                    capture_quality,

                "skin_type":
                    skin_type_analysis,

                "skin_tone":
                    skin_tone_analysis,

                "skin_concerns":
                    skin_concern_analysis,

                "presentation":
                    prediction_presentation,

                "skin_regions":
                    region_result[
                        "regions"
                    ],

                "regional_summary":
                    region_result.get("regional_summary"),
            },

            "recommendations":
                recommendations,
        }


    # =====================================================
    # REQUEST ERRORS
    # =====================================================

    except HTTPException:

        raise


    except ValueError as exc:

        raise HTTPException(
            status_code=400,

            detail=str(
                exc
            ),
        )


    # =====================================================
    # UNEXPECTED ERRORS
    # =====================================================

    except Exception as exc:

        print(
            "Beautyverse analysis error: "
            f"{type(exc).__name__}"
        )


        raise HTTPException(
            status_code=500,

            detail=(
                "An error occurred during "
                "Beautyverse analysis."
            ),
        )

# Makeup routes reuse the existing models and shopping credentials.
from backend.makeup_routes import router as makeup_router
app.include_router(makeup_router)

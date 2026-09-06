import cv2

from fastapi import (
    FastAPI,
    File,
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
            f"{exc}"
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
            f"{exc}"
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


        prediction = (
            skin_type_classifier_service
            .predict(
                cv_image,
                landmarks,
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

            "skin_regions":
                region_result[
                    "regions"
                ],
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
            f"{exc}"
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
        # 4. SKIN TYPE
        # =================================================

        skin_type_analysis = (
            skin_type_classifier_service
            .predict(
                cv_image,
                landmarks,
            )
        )


        # =================================================
        # 5. SKIN CONCERNS
        # =================================================

        skin_concern_analysis = (
            skin_concern_classifier_service
            .predict(
                cv_image,
                landmarks,
            )
        )

        prediction_presentation = (
            prediction_presenter.build(
                skin_type_analysis,
                skin_concern_analysis,
            )
        )


        # =================================================
        # 6. DYNAMIC AI SKINCARE PLAN
        #
        # Gemini failure must NOT crash the ML analysis.
        # =================================================

        try:

            personalized_plan = (
                ai_skincare_planner
                .generate(
                    skin_type_analysis,
                    skin_concern_analysis,
                )
            )


        except Exception as exc:

            print(
                "AI skincare planner unavailable: "
                f"{exc}"
            )


            # IMPORTANT:
            # This does NOT invent a static routine.
            #
            # If Gemini is unavailable, the app simply
            # reports that personalization could not
            # currently be generated.

            personalized_plan = {
                "skin_profile": (
                    "Personalized AI skincare "
                    "planning is temporarily "
                    "unavailable."
                ),

                "skin_goals":
                    [],

                "concern_goals":
                    [],

                "recommended_ingredients":
                    [],

                "avoid_or_limit":
                    [],

                "routine": {
                    "morning":
                        [],

                    "evening":
                        [],
                },

                "generated_by": {
                    "provider":
                        "Google Gemini",

                    "status":
                        "temporarily_unavailable",
                },
            }


        # =================================================
        # 7. BUILD DYNAMIC RECOMMENDATION PROFILE
        # =================================================

        recommendations = (
            recommendation_engine
            .generate(
                skin_type_analysis,
                skin_concern_analysis,
                personalized_plan,
            )
        )


        # =================================================
        # 8. LIVE PRODUCT SEARCH
        #
        # Shopping search failure must also NOT crash
        # the actual skin analysis.
        # =================================================

        try:

            live_products = (
                product_search_service
                .search_for_profile(
                    recommendations
                )
            )


        except Exception as exc:

            print(
                "Live product search error: "
                f"{exc}"
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

                "message":
                    str(
                        exc
                    ),
            }


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
                "capture_quality":
                    capture_quality,

                "skin_type":
                    skin_type_analysis,

                "skin_concerns":
                    skin_concern_analysis,

                "presentation":
                    prediction_presentation,

                "skin_regions":
                    region_result[
                        "regions"
                    ],
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
            f"{exc}"
        )


        raise HTTPException(
            status_code=500,

            detail=(
                "An error occurred during "
                "Beautyverse analysis."
            ),
        )
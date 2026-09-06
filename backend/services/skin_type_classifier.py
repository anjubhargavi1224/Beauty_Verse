from pathlib import Path
from threading import Lock

import cv2
import torch

from PIL import Image
from torch import nn

from torchvision.models import (
    EfficientNet_B0_Weights,
    efficientnet_b0,
)

from backend.services.face_detection import (
    face_detection_service,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]

MODEL_PATH = (
    PROJECT_ROOT
    / "ml"
    / "models"
    / "best_skin_type_efficientnet_b0.pt"
)


class SkinTypeClassifierService:
    """
    Beautyverse V1 skin-type classifier.

    Classes:
    - Combination
    - Dry
    - Normal
    - Oily

    This is a research/cosmetic analysis model.
    It is not a medical diagnostic system.
    """

    def __init__(self):
        if not MODEL_PATH.exists():
            raise FileNotFoundError(
                f"Skin type model not found at: {MODEL_PATH}"
            )

        self.device = torch.device(
            "cuda"
            if torch.cuda.is_available()
            else "cpu"
        )

        checkpoint = torch.load(
            MODEL_PATH,
            map_location=self.device,
            weights_only=False,
        )

        self.class_names = checkpoint[
            "class_names"
        ]

        self.model = efficientnet_b0(
            weights=None
        )

        in_features = (
            self.model
            .classifier[1]
            .in_features
        )

        self.model.classifier = nn.Sequential(
            nn.Dropout(
                p=0.40
            ),

            nn.Linear(
                in_features,
                len(self.class_names),
            ),
        )

        self.model.load_state_dict(
            checkpoint["state_dict"]
        )

        self.model = self.model.to(
            self.device
        )

        self.model.eval()

        self.transform = (
            EfficientNet_B0_Weights
            .DEFAULT
            .transforms()
        )

        self.lock = Lock()

        print(
            f"Beautyverse skin-type model loaded "
            f"on {self.device}"
        )

    def crop_face(
        self,
        image,
        landmarks,
    ):
        """
        Crop the facial region before classification.

        A small 5% margin is retained around the
        MediaPipe facial bounding box.
        """

        height, width = image.shape[:2]

        bbox = (
            face_detection_service
            .calculate_face_bbox(
                landmarks,
                width,
                height,
            )
        )

        x = bbox["x"]
        y = bbox["y"]

        box_width = bbox["width"]
        box_height = bbox["height"]

        margin_x = int(
            box_width * 0.05
        )

        margin_y = int(
            box_height * 0.05
        )

        x1 = max(
            0,
            x - margin_x,
        )

        y1 = max(
            0,
            y - margin_y,
        )

        x2 = min(
            width,
            x
            + box_width
            + margin_x,
        )

        y2 = min(
            height,
            y
            + box_height
            + margin_y,
        )

        face_crop = image[
            y1:y2,
            x1:x2,
        ]

        if face_crop.size == 0:
            raise ValueError(
                "Face crop could not be created."
            )

        return (
            face_crop,
            {
                "x": x1,
                "y": y1,
                "width": x2 - x1,
                "height": y2 - y1,
            },
        )

    def predict(
        self,
        image,
        landmarks,
    ):
        """
        Predict cosmetic skin type from
        a detected facial crop.
        """

        (
            face_crop,
            crop_box,
        ) = self.crop_face(
            image,
            landmarks,
        )

        rgb_crop = cv2.cvtColor(
            face_crop,
            cv2.COLOR_BGR2RGB,
        )

        pil_image = Image.fromarray(
            rgb_crop
        )

        tensor = self.transform(
            pil_image
        )

        tensor = tensor.unsqueeze(
            0
        )

        tensor = tensor.to(
            self.device
        )

        with self.lock:
            with torch.no_grad():
                logits = self.model(
                    tensor
                )

                probabilities = (
                    torch.softmax(
                        logits,
                        dim=1,
                    )[0]
                )

        probability_values = (
            probabilities
            .detach()
            .cpu()
            .tolist()
        )

        results = []

        for (
            class_name,
            probability,
        ) in zip(
            self.class_names,
            probability_values,
        ):
            results.append(
                {
                    "skin_type":
                        class_name,

                    "probability":
                        round(
                            float(
                                probability
                            ),
                            6,
                        ),

                    "percentage":
                        round(
                            float(
                                probability
                            )
                            * 100,
                            2,
                        ),
                }
            )

        results.sort(
            key=lambda item:
                item["probability"],
            reverse=True,
        )

        top_prediction = (
            results[0]
        )

        second_prediction = (
            results[1]
            if len(results) > 1
            else None
        )

        top_probability = (
            top_prediction[
                "probability"
            ]
        )

        second_probability = (
            second_prediction[
                "probability"
            ]
            if second_prediction
            else 0.0
        )

        probability_margin = (
            top_probability
            - second_probability
        )

        # Important:
        # This is a UX/research heuristic,
        # NOT a scientifically calibrated
        # probability threshold.
        uncertainty_flag = (
            top_probability < 0.55
            or probability_margin < 0.15
        )

        if uncertainty_flag:
            confidence_level = (
                "uncertain"
            )

        elif top_probability < 0.75:
            confidence_level = (
                "moderate"
            )

        else:
            confidence_level = (
                "stronger"
            )

        return {
            "predicted_skin_type":
                top_prediction[
                    "skin_type"
                ],

            "confidence":
                top_prediction[
                    "probability"
                ],

            "confidence_percentage":
                top_prediction[
                    "percentage"
                ],

            "confidence_level":
                confidence_level,

            "uncertainty_flag":
                uncertainty_flag,

            "top_two_margin":
                round(
                    probability_margin,
                    6,
                ),

            "top_two_margin_percentage":
                round(
                    probability_margin
                    * 100,
                    2,
                ),

            "probabilities":
                results,

            "face_crop":
                crop_box,

            "model": {
                "name":
                    "EfficientNet-B0",

                "version":
                    "beautyverse_skin_type_v1",

                "classes":
                    self.class_names,
            },

            "disclaimer": (
                "Research baseline for "
                "cosmetic skin analysis. "
                "Not a medical diagnosis."
            ),
        }


skin_type_classifier_service = (
    SkinTypeClassifierService()
)
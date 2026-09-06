from pathlib import Path
from threading import Lock

import cv2
import torch

from PIL import Image
from torch import nn
from torchvision import transforms
from torchvision.models import efficientnet_b0

from backend.services.face_detection import (
    face_detection_service,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]

MODEL_PATH = (
    PROJECT_ROOT
    / "ml"
    / "models"
    / "best_skin_concerns.pt"
)


DISPLAY_NAMES = {
    "acne": "Acne / Blemishes",
    "pigmentation": "Pigmentation / Dark Spots",
    "redness": "Redness",
    "pores": "Visible Pores",
    "wrinkles": "Fine Lines / Wrinkles",
}


IMAGENET_MEAN = [
    0.485,
    0.456,
    0.406,
]

IMAGENET_STD = [
    0.229,
    0.224,
    0.225,
]


class SkinConcernClassifierService:

    def __init__(self):

        if not MODEL_PATH.exists():
            raise FileNotFoundError(
                f"Skin concern model not found:\n"
                f"{MODEL_PATH}"
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

        self.thresholds = checkpoint[
            "thresholds"
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
                len(
                    self.class_names
                ),
            ),
        )

        self.model.load_state_dict(
            checkpoint[
                "state_dict"
            ]
        )

        self.model = self.model.to(
            self.device
        )

        self.model.eval()

        self.transform = transforms.Compose(
            [
                transforms.Resize(
                    256
                ),

                transforms.CenterCrop(
                    224
                ),

                transforms.ToTensor(),

                transforms.Normalize(
                    IMAGENET_MEAN,
                    IMAGENET_STD,
                ),
            ]
        )

        self.lock = Lock()

        print(
            "Beautyverse skin-concern model "
            f"loaded on {self.device}"
        )


    def crop_face(
        self,
        image,
        landmarks,
    ):

        height, width = (
            image.shape[:2]
        )

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
            box_width * 0.03
        )

        margin_y = int(
            box_height * 0.03
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
            x + box_width + margin_x,
        )

        y2 = min(
            height,
            y + box_height + margin_y,
        )

        face_crop = image[
            y1:y2,
            x1:x2,
        ]

        if face_crop.size == 0:
            raise ValueError(
                "Skin concern face crop was empty."
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


    def get_status(
        self,
        score,
        threshold,
    ):

        uncertainty_margin = 0.08

        if (
            score
            >= threshold
            + uncertainty_margin
        ):
            return "detected"

        if (
            score
            <= threshold
            - uncertainty_margin
        ):
            return "not_detected"

        return "uncertain"


    def predict(
        self,
        image,
        landmarks,
    ):

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

        tensor = (
            self.transform(
                pil_image
            )
            .unsqueeze(0)
            .to(
                self.device
            )
        )

        with self.lock:

            with torch.no_grad():

                logits = self.model(
                    tensor
                )

                probabilities = (
                    torch.sigmoid(
                        logits
                    )[0]
                )


        concern_results = []

        detected_concerns = []

        uncertain_concerns = []


        for (
            label,
            probability,
        ) in zip(
            self.class_names,
            probabilities,
        ):

            score = float(
                probability
            )

            threshold = float(
                self.thresholds[
                    label
                ]
            )

            status = self.get_status(
                score,
                threshold,
            )

            result = {
                "id":
                    label,

                "name":
                    DISPLAY_NAMES.get(
                        label,
                        label.title(),
                    ),

                "score":
                    round(
                        score,
                        6,
                    ),

                "score_percentage":
                    round(
                        score * 100,
                        2,
                    ),

                "threshold":
                    round(
                        threshold,
                        4,
                    ),

                "threshold_percentage":
                    round(
                        threshold * 100,
                        2,
                    ),

                "status":
                    status,
            }

            concern_results.append(
                result
            )

            if status == "detected":

                detected_concerns.append(
                    label
                )

            elif status == "uncertain":

                uncertain_concerns.append(
                    label
                )


        return {
            "concerns":
                concern_results,

            "detected_concerns":
                detected_concerns,

            "uncertain_concerns":
                uncertain_concerns,

            "face_crop":
                crop_box,

            "model": {
                "name":
                    "EfficientNet-B0",

                "version":
                    "beautyverse_skin_concerns_v1",

                "task":
                    "multi_label_visible_skin_concerns",

                "classes":
                    self.class_names,
            },

            "interpretation_note": (
                "Scores indicate model confidence "
                "relative to validation-derived "
                "thresholds. They do not represent "
                "severity."
            ),

            "disclaimer": (
                "Research baseline for visible "
                "cosmetic skin concerns. "
                "Not a medical diagnosis."
            ),
        }


skin_concern_classifier_service = (
    SkinConcernClassifierService()
)
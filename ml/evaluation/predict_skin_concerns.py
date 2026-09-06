from pathlib import Path
import argparse

import cv2
import torch

from PIL import Image
from torch import nn

from torchvision import transforms
from torchvision.models import (
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
    / "best_skin_concerns.pt"
)


TARGET_LABELS = [
    "acne",
    "pigmentation",
    "redness",
    "pores",
    "wrinkles",
]


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


transform = transforms.Compose(
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


def load_model(
    device,
):
    checkpoint = torch.load(
        MODEL_PATH,
        map_location=device,
        weights_only=False,
    )

    class_names = checkpoint[
        "class_names"
    ]

    thresholds = checkpoint[
        "thresholds"
    ]

    model = efficientnet_b0(
        weights=None
    )

    in_features = (
        model
        .classifier[1]
        .in_features
    )

    model.classifier = nn.Sequential(
        nn.Dropout(
            p=0.40
        ),

        nn.Linear(
            in_features,
            len(
                class_names
            ),
        ),
    )

    model.load_state_dict(
        checkpoint[
            "state_dict"
        ]
    )

    model = model.to(
        device
    )

    model.eval()

    return (
        model,
        class_names,
        thresholds,
    )


def crop_face(
    image_path,
):
    with open(
        image_path,
        "rb",
    ) as file:
        image_bytes = file.read()

    cv_image, result = (
        face_detection_service.detect(
            image_bytes
        )
    )

    if not result.face_landmarks:
        raise RuntimeError(
            "No face detected."
        )

    height, width = (
        cv_image.shape[:2]
    )

    landmarks = (
        result.face_landmarks[0]
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

    # Slightly smaller margin than skin-type model.
    # We want facial skin to dominate the crop.
    margin_x = int(
        box_width * 0.03
    )

    margin_y = int(
        box_height * 0.03
    )

    x1 = max(
        0,
        x - margin_x
    )

    y1 = max(
        0,
        y - margin_y
    )

    x2 = min(
        width,
        x + box_width + margin_x
    )

    y2 = min(
        height,
        y + box_height + margin_y
    )

    face_crop = (
        cv_image[
            y1:y2,
            x1:x2,
        ]
    )

    if face_crop.size == 0:
        raise RuntimeError(
            "Face crop was empty."
        )

    face_rgb = cv2.cvtColor(
        face_crop,
        cv2.COLOR_BGR2RGB,
    )

    return Image.fromarray(
        face_rgb
    )


def get_status(
    score,
    threshold,
):
    """
    Conservative user-facing interpretation.

    The threshold is validation-derived.

    Scores close to the threshold are reported
    as uncertain rather than forcing Yes/No.
    """

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
    image_path,
):
    device = torch.device(
        "cuda"
        if torch.cuda.is_available()
        else "cpu"
    )

    (
        model,
        class_names,
        thresholds,
    ) = load_model(
        device
    )

    face_image = crop_face(
        image_path
    )

    tensor = transform(
        face_image
    )

    tensor = (
        tensor
        .unsqueeze(0)
        .to(
            device
        )
    )

    with torch.no_grad():

        logits = model(
            tensor
        )

        probabilities = (
            torch.sigmoid(
                logits
            )[0]
        )

    print(
        "\n"
        "========================================"
    )

    print(
        "BEAUTYVERSE VISIBLE SKIN CONCERNS"
    )

    print(
        "========================================"
    )

    print(
        "\nImage:",
        image_path,
    )

    print(
        "\nModel outputs:\n"
    )

    results = []

    for (
        label,
        probability,
    ) in zip(
        class_names,
        probabilities,
    ):

        score = float(
            probability
        )

        threshold = float(
            thresholds[
                label
            ]
        )

        status = get_status(
            score,
            threshold,
        )

        results.append(
            {
                "label":
                    label,

                "score":
                    score,

                "threshold":
                    threshold,

                "status":
                    status,
            }
        )

        print(
            f"{DISPLAY_NAMES[label]:<28}"
            f"{score * 100:>6.2f}%   "
            f"threshold="
            f"{threshold:.2f}   "
            f"{status}"
        )

    print(
        "\n----------------------------------------"
    )

    print(
        "Important:"
    )

    print(
        "Percentages are model scores, "
        "not severity percentages."
    )

    print(
        "This is a cosmetic computer-vision "
        "research baseline, not a medical diagnosis."
    )

    return results


if __name__ == "__main__":

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "image",
        type=str,
        help="Path to selfie image",
    )

    args = parser.parse_args()

    predict(
        args.image
    )
    
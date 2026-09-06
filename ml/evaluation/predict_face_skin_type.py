from pathlib import Path
import argparse

import cv2
import numpy as np
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


def load_model(device):
    checkpoint = torch.load(
        MODEL_PATH,
        map_location=device,
        weights_only=False,
    )

    class_names = checkpoint["class_names"]

    model = efficientnet_b0(
        weights=None
    )

    in_features = model.classifier[1].in_features

    model.classifier = nn.Sequential(
        nn.Dropout(p=0.40),
        nn.Linear(
            in_features,
            len(class_names),
        ),
    )

    model.load_state_dict(
        checkpoint["state_dict"]
    )

    model = model.to(device)

    model.eval()

    return model, class_names


def crop_face(image_path):
    with open(image_path, "rb") as file:
        image_bytes = file.read()

    cv_image, result = (
        face_detection_service.detect(
            image_bytes
        )
    )

    if not result.face_landmarks:
        raise RuntimeError(
            "No face detected in the image."
        )

    height, width = cv_image.shape[:2]

    landmarks = result.face_landmarks[0]

    bbox = (
        face_detection_service.calculate_face_bbox(
            landmarks,
            width,
            height,
        )
    )

    x = bbox["x"]
    y = bbox["y"]

    box_width = bbox["width"]
    box_height = bbox["height"]

    # Add a small margin around the detected facial area.
    margin_x = int(box_width * 0.05)
    margin_y = int(box_height * 0.05)

    x1 = max(0, x - margin_x)
    y1 = max(0, y - margin_y)

    x2 = min(
        width,
        x + box_width + margin_x,
    )

    y2 = min(
        height,
        y + box_height + margin_y,
    )

    face_crop = cv_image[
        y1:y2,
        x1:x2,
    ]

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


def predict(image_path):
    device = torch.device(
        "cuda"
        if torch.cuda.is_available()
        else "cpu"
    )

    model, class_names = load_model(
        device
    )

    face_image = crop_face(
        image_path
    )

    weights = (
        EfficientNet_B0_Weights.DEFAULT
    )

    transform = weights.transforms()

    tensor = transform(
        face_image
    ).unsqueeze(0)

    tensor = tensor.to(
        device
    )

    with torch.no_grad():
        logits = model(
            tensor
        )

        probabilities = torch.softmax(
            logits,
            dim=1,
        )[0]

    results = []

    for class_name, probability in zip(
        class_names,
        probabilities,
    ):
        results.append(
            (
                class_name,
                float(probability),
            )
        )

    results.sort(
        key=lambda item: item[1],
        reverse=True,
    )

    print()
    print("=" * 60)
    print(
        "BEAUTYVERSE FACE-CROP SKIN TYPE"
    )
    print("=" * 60)

    print()

    for class_name, probability in results:
        print(
            f"{class_name:<15}"
            f"{probability * 100:>7.2f}%"
        )

    prediction = results[0]

    print()
    print(
        f"Prediction: {prediction[0]}"
    )

    print(
        f"Confidence: "
        f"{prediction[1] * 100:.2f}%"
    )

    print()
    print(
        "Research baseline only — "
        "not a medical diagnosis."
    )
    print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "image",
        type=str,
    )

    args = parser.parse_args()

    predict(
        args.image
    )
    
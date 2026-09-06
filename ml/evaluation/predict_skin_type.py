from pathlib import Path
import argparse

import torch
from PIL import Image

from torch import nn
from torchvision.models import (
    EfficientNet_B0_Weights,
    efficientnet_b0,
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

    in_features = (
        model.classifier[1].in_features
    )

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


def predict(image_path):
    device = torch.device(
        "cuda"
        if torch.cuda.is_available()
        else "cpu"
    )

    model, class_names = load_model(
        device
    )

    weights = (
        EfficientNet_B0_Weights.DEFAULT
    )

    transform = weights.transforms()

    image = Image.open(
        image_path
    ).convert("RGB")

    tensor = transform(
        image
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
    print("BEAUTYVERSE BASELINE SKIN-TYPE PREDICTION")
    print("=" * 60)

    print()
    print(
        f"Image: {image_path}"
    )

    print()

    for class_name, probability in results:
        print(
            f"{class_name:<15}"
            f"{probability * 100:>7.2f}%"
        )

    predicted_class = results[0][0]
    confidence = results[0][1]

    print()
    print(
        f"Prediction: {predicted_class}"
    )

    print(
        f"Confidence: {confidence * 100:.2f}%"
    )

    print()
    print(
        "NOTE: This is the Beautyverse V1 "
        "research baseline and is not a "
        "medical diagnosis."
    )

    print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "image",
        type=str,
        help="Path to an image",
    )

    args = parser.parse_args()

    predict(
        args.image
    )
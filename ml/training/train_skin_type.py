from __future__ import annotations

import copy
import csv
import json
import random
import time
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import torch

from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)

from torch import nn
from torch.optim import AdamW
from torch.optim.lr_scheduler import ReduceLROnPlateau
from torch.utils.data import DataLoader

from torchvision import datasets, transforms
from torchvision.models import (
    EfficientNet_B0_Weights,
    efficientnet_b0,
)


# ==========================================================
# CONFIGURATION
# ==========================================================

SEED = 42

IMAGE_SIZE = 224

BATCH_SIZE = 16

HEAD_EPOCHS = 8

FINE_TUNE_EPOCHS = 12

HEAD_LEARNING_RATE = 1e-3

FINE_TUNE_BACKBONE_LR = 1e-5

FINE_TUNE_CLASSIFIER_LR = 1e-4

WEIGHT_DECAY = 1e-4

EARLY_STOPPING_PATIENCE = 5


PROJECT_ROOT = Path(
    __file__
).resolve().parents[2]


DATA_ROOT = (
    PROJECT_ROOT
    / "ml"
    / "data"
    / "processed"
    / "skin_type_v1"
)


TRAIN_DIR = (
    DATA_ROOT
    / "train"
)


VALIDATION_DIR = (
    DATA_ROOT
    / "validation"
)


TEST_DIR = (
    DATA_ROOT
    / "test"
)


MODEL_DIR = (
    PROJECT_ROOT
    / "ml"
    / "models"
)


RESULTS_DIR = (
    PROJECT_ROOT
    / "ml"
    / "results"
)


BEST_MODEL_PATH = (
    MODEL_DIR
    / "best_skin_type_efficientnet_b0.pt"
)


CLASS_NAMES_PATH = (
    MODEL_DIR
    / "skin_type_classes.json"
)


HISTORY_PATH = (
    RESULTS_DIR
    / "training_history.csv"
)


METRICS_PATH = (
    RESULTS_DIR
    / "skin_type_metrics.json"
)


REPORT_PATH = (
    RESULTS_DIR
    / "classification_report.json"
)


CONFUSION_MATRIX_PATH = (
    RESULTS_DIR
    / "confusion_matrix.png"
)


TRAINING_CURVES_PATH = (
    RESULTS_DIR
    / "training_curves.png"
)


# ==========================================================
# REPRODUCIBILITY
# ==========================================================

def set_seed(seed: int):
    random.seed(seed)

    np.random.seed(seed)

    torch.manual_seed(seed)

    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)

    torch.backends.cudnn.deterministic = True

    torch.backends.cudnn.benchmark = False


# ==========================================================
# TRANSFORMS
# ==========================================================

def build_transforms():
    """
    Training images receive modest augmentation.

    We deliberately avoid strong hue or saturation changes
    because colour may contain useful information for
    cosmetic skin analysis.
    """

    weights = (
        EfficientNet_B0_Weights.DEFAULT
    )

    mean = weights.transforms().mean

    std = weights.transforms().std

    train_transform = transforms.Compose(
        [
            transforms.RandomResizedCrop(
                IMAGE_SIZE,
                scale=(0.85, 1.0),
                ratio=(0.90, 1.10),
            ),

            transforms.RandomHorizontalFlip(
                p=0.5
            ),

            transforms.RandomAffine(
                degrees=5,
                translate=(0.03, 0.03),
                scale=(0.95, 1.05),
            ),

            transforms.ColorJitter(
                brightness=0.08,
                contrast=0.08,
            ),

            transforms.ToTensor(),

            transforms.Normalize(
                mean=mean,
                std=std,
            ),
        ]
    )

    validation_transform = (
        weights.transforms()
    )

    return (
        train_transform,
        validation_transform,
    )


# ==========================================================
# DATA
# ==========================================================

def build_dataloaders():
    (
        train_transform,
        evaluation_transform,
    ) = build_transforms()

    train_dataset = datasets.ImageFolder(
        TRAIN_DIR,
        transform=train_transform,
    )

    validation_dataset = datasets.ImageFolder(
        VALIDATION_DIR,
        transform=evaluation_transform,
    )

    test_dataset = datasets.ImageFolder(
        TEST_DIR,
        transform=evaluation_transform,
    )

    if (
        train_dataset.classes
        != validation_dataset.classes
        or train_dataset.classes
        != test_dataset.classes
    ):
        raise RuntimeError(
            "Class order differs between "
            "train/validation/test datasets."
        )

    class_names = train_dataset.classes

    print()
    print(
        "Detected classes:"
    )

    for index, class_name in enumerate(
        class_names
    ):
        print(
            f"  {index}: {class_name}"
        )

    print()
    print(
        f"Training images:   "
        f"{len(train_dataset)}"
    )

    print(
        f"Validation images: "
        f"{len(validation_dataset)}"
    )

    print(
        f"Test images:       "
        f"{len(test_dataset)}"
    )

    # num_workers=0 is intentionally used for
    # maximum reliability on Windows.
    train_loader = DataLoader(
        train_dataset,
        batch_size=BATCH_SIZE,
        shuffle=True,
        num_workers=0,
        pin_memory=torch.cuda.is_available(),
    )

    validation_loader = DataLoader(
        validation_dataset,
        batch_size=BATCH_SIZE,
        shuffle=False,
        num_workers=0,
        pin_memory=torch.cuda.is_available(),
    )

    test_loader = DataLoader(
        test_dataset,
        batch_size=BATCH_SIZE,
        shuffle=False,
        num_workers=0,
        pin_memory=torch.cuda.is_available(),
    )

    return (
        train_loader,
        validation_loader,
        test_loader,
        class_names,
    )


# ==========================================================
# MODEL
# ==========================================================

def build_model(
    number_of_classes: int,
):
    weights = (
        EfficientNet_B0_Weights.DEFAULT
    )

    model = efficientnet_b0(
        weights=weights
    )

    # Freeze pretrained feature extractor.
    for parameter in (
        model.features.parameters()
    ):
        parameter.requires_grad = False

    in_features = (
        model.classifier[1].in_features
    )

    # Replace ImageNet classifier with
    # Beautyverse's four-class classifier.
    model.classifier = nn.Sequential(
        nn.Dropout(
            p=0.40
        ),

        nn.Linear(
            in_features,
            number_of_classes,
        ),
    )

    return model


def unfreeze_final_blocks(
    model,
):
    """
    Fine-tune only the final two EfficientNet
    feature blocks.

    With our small dataset, unfreezing the entire
    network would increase overfitting risk.
    """

    for parameter in (
        model.features.parameters()
    ):
        parameter.requires_grad = False

    for block in model.features[-2:]:
        for parameter in (
            block.parameters()
        ):
            parameter.requires_grad = True

    for parameter in (
        model.classifier.parameters()
    ):
        parameter.requires_grad = True


# ==========================================================
# TRAINING / VALIDATION
# ==========================================================

def train_one_epoch(
    model,
    loader,
    criterion,
    optimizer,
    device,
):
    model.train()

    running_loss = 0.0

    predictions = []

    targets = []

    for images, labels in loader:
        images = images.to(
            device,
            non_blocking=True,
        )

        labels = labels.to(
            device,
            non_blocking=True,
        )

        optimizer.zero_grad(
            set_to_none=True
        )

        outputs = model(
            images
        )

        loss = criterion(
            outputs,
            labels,
        )

        loss.backward()

        optimizer.step()

        running_loss += (
            loss.item()
            * images.size(0)
        )

        predicted_classes = (
            torch.argmax(
                outputs,
                dim=1,
            )
        )

        predictions.extend(
            predicted_classes
            .detach()
            .cpu()
            .numpy()
            .tolist()
        )

        targets.extend(
            labels
            .detach()
            .cpu()
            .numpy()
            .tolist()
        )

    epoch_loss = (
        running_loss
        / len(loader.dataset)
    )

    epoch_accuracy = accuracy_score(
        targets,
        predictions,
    )

    return (
        epoch_loss,
        epoch_accuracy,
    )


@torch.no_grad()
def evaluate_epoch(
    model,
    loader,
    criterion,
    device,
):
    model.eval()

    running_loss = 0.0

    predictions = []

    targets = []

    probabilities = []

    for images, labels in loader:
        images = images.to(
            device,
            non_blocking=True,
        )

        labels = labels.to(
            device,
            non_blocking=True,
        )

        outputs = model(
            images
        )

        loss = criterion(
            outputs,
            labels,
        )

        running_loss += (
            loss.item()
            * images.size(0)
        )

        probs = torch.softmax(
            outputs,
            dim=1,
        )

        predicted_classes = (
            torch.argmax(
                probs,
                dim=1,
            )
        )

        predictions.extend(
            predicted_classes
            .cpu()
            .numpy()
            .tolist()
        )

        targets.extend(
            labels
            .cpu()
            .numpy()
            .tolist()
        )

        probabilities.extend(
            probs
            .cpu()
            .numpy()
            .tolist()
        )

    epoch_loss = (
        running_loss
        / len(loader.dataset)
    )

    epoch_accuracy = accuracy_score(
        targets,
        predictions,
    )

    return (
        epoch_loss,
        epoch_accuracy,
        targets,
        predictions,
        probabilities,
    )


# ==========================================================
# MODEL CHECKPOINTING
# ==========================================================

def save_checkpoint(
    model,
    class_names,
    best_validation_loss,
):
    checkpoint = {
        "architecture":
            "efficientnet_b0",

        "class_names":
            class_names,

        "number_of_classes":
            len(class_names),

        "image_size":
            IMAGE_SIZE,

        "best_validation_loss":
            best_validation_loss,

        "state_dict":
            model.state_dict(),
    }

    torch.save(
        checkpoint,
        BEST_MODEL_PATH,
    )


# ==========================================================
# TRAINING PHASE
# ==========================================================

def run_training_phase(
    *,
    phase_name,
    model,
    train_loader,
    validation_loader,
    criterion,
    optimizer,
    scheduler,
    device,
    class_names,
    epochs,
    history,
    global_epoch_start,
    best_validation_loss,
    best_model_state,
):
    patience_counter = 0

    for local_epoch in range(
        1,
        epochs + 1,
    ):
        global_epoch = (
            global_epoch_start
            + local_epoch
        )

        start_time = time.time()

        (
            train_loss,
            train_accuracy,
        ) = train_one_epoch(
            model,
            train_loader,
            criterion,
            optimizer,
            device,
        )

        (
            validation_loss,
            validation_accuracy,
            _,
            _,
            _,
        ) = evaluate_epoch(
            model,
            validation_loader,
            criterion,
            device,
        )

        scheduler.step(
            validation_loss
        )

        duration = (
            time.time()
            - start_time
        )

        current_learning_rates = [
            group["lr"]
            for group
            in optimizer.param_groups
        ]

        history.append(
            {
                "epoch": global_epoch,
                "phase": phase_name,

                "train_loss":
                    train_loss,

                "train_accuracy":
                    train_accuracy,

                "validation_loss":
                    validation_loss,

                "validation_accuracy":
                    validation_accuracy,

                "learning_rates":
                    "|".join(
                        f"{lr:.8f}"
                        for lr
                        in current_learning_rates
                    ),
            }
        )

        print()
        print(
            f"[{phase_name}] "
            f"Epoch {local_epoch}/{epochs}"
        )

        print(
            f"  Train Loss:     "
            f"{train_loss:.4f}"
        )

        print(
            f"  Train Accuracy: "
            f"{train_accuracy:.4f}"
        )

        print(
            f"  Val Loss:       "
            f"{validation_loss:.4f}"
        )

        print(
            f"  Val Accuracy:   "
            f"{validation_accuracy:.4f}"
        )

        print(
            f"  Duration:       "
            f"{duration:.1f}s"
        )

        if (
            validation_loss
            < best_validation_loss
        ):
            best_validation_loss = (
                validation_loss
            )

            best_model_state = (
                copy.deepcopy(
                    model.state_dict()
                )
            )

            save_checkpoint(
                model,
                class_names,
                best_validation_loss,
            )

            patience_counter = 0

            print(
                "  ✓ Best model updated"
            )

        else:
            patience_counter += 1

            print(
                "  No improvement "
                f"({patience_counter}/"
                f"{EARLY_STOPPING_PATIENCE})"
            )

        if (
            patience_counter
            >= EARLY_STOPPING_PATIENCE
        ):
            print()
            print(
                f"Early stopping "
                f"{phase_name}."
            )

            break

    return (
        best_validation_loss,
        best_model_state,
        global_epoch,
    )


# ==========================================================
# RESULTS
# ==========================================================

def save_training_history(
    history,
):
    if not history:
        return

    fieldnames = [
        "epoch",
        "phase",
        "train_loss",
        "train_accuracy",
        "validation_loss",
        "validation_accuracy",
        "learning_rates",
    ]

    with HISTORY_PATH.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
        )

        writer.writeheader()

        writer.writerows(
            history
        )


def plot_training_curves(
    history,
):
    epochs = [
        row["epoch"]
        for row
        in history
    ]

    train_loss = [
        row["train_loss"]
        for row
        in history
    ]

    validation_loss = [
        row["validation_loss"]
        for row
        in history
    ]

    train_accuracy = [
        row["train_accuracy"]
        for row
        in history
    ]

    validation_accuracy = [
        row["validation_accuracy"]
        for row
        in history
    ]

    # Loss plot
    plt.figure(
        figsize=(8, 5)
    )

    plt.plot(
        epochs,
        train_loss,
        label="Training Loss",
    )

    plt.plot(
        epochs,
        validation_loss,
        label="Validation Loss",
    )

    plt.xlabel(
        "Epoch"
    )

    plt.ylabel(
        "Loss"
    )

    plt.title(
        "Beautyverse EfficientNet-B0 Loss"
    )

    plt.legend()

    plt.tight_layout()

    plt.savefig(
        TRAINING_CURVES_PATH.with_name(
            "training_loss.png"
        ),
        dpi=200,
    )

    plt.close()

    # Accuracy plot
    plt.figure(
        figsize=(8, 5)
    )

    plt.plot(
        epochs,
        train_accuracy,
        label="Training Accuracy",
    )

    plt.plot(
        epochs,
        validation_accuracy,
        label="Validation Accuracy",
    )

    plt.xlabel(
        "Epoch"
    )

    plt.ylabel(
        "Accuracy"
    )

    plt.title(
        "Beautyverse EfficientNet-B0 Accuracy"
    )

    plt.legend()

    plt.tight_layout()

    plt.savefig(
        TRAINING_CURVES_PATH,
        dpi=200,
    )

    plt.close()


def plot_confusion_matrix(
    matrix,
    class_names,
):
    plt.figure(
        figsize=(7, 6)
    )

    plt.imshow(
        matrix,
        interpolation="nearest",
        cmap="Blues",
    )

    plt.title(
        "Beautyverse Skin Type Confusion Matrix"
    )

    plt.colorbar()

    tick_positions = np.arange(
        len(class_names)
    )

    plt.xticks(
        tick_positions,
        class_names,
        rotation=45,
        ha="right",
    )

    plt.yticks(
        tick_positions,
        class_names,
    )

    threshold = (
        matrix.max() / 2
        if matrix.size
        else 0
    )

    for row_index in range(
        matrix.shape[0]
    ):
        for column_index in range(
            matrix.shape[1]
        ):
            value = matrix[
                row_index,
                column_index,
            ]

            plt.text(
                column_index,
                row_index,
                str(value),
                horizontalalignment="center",
                color=(
                    "white"
                    if value > threshold
                    else "black"
                ),
            )

    plt.ylabel(
        "True label"
    )

    plt.xlabel(
        "Predicted label"
    )

    plt.tight_layout()

    plt.savefig(
        CONFUSION_MATRIX_PATH,
        dpi=200,
    )

    plt.close()


# ==========================================================
# MAIN
# ==========================================================

def main():
    set_seed(
        SEED
    )

    MODEL_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    RESULTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    print()
    print("=" * 70)
    print(
        "BEAUTYVERSE — SKIN TYPE MODEL TRAINING"
    )
    print("=" * 70)

    device = torch.device(
        "cuda"
        if torch.cuda.is_available()
        else "cpu"
    )

    print()
    print(
        f"PyTorch version: "
        f"{torch.__version__}"
    )

    print(
        f"Training device: "
        f"{device}"
    )

    if torch.cuda.is_available():
        print(
            f"GPU: "
            f"{torch.cuda.get_device_name(0)}"
        )

    (
        train_loader,
        validation_loader,
        test_loader,
        class_names,
    ) = build_dataloaders()

    with CLASS_NAMES_PATH.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            {
                "class_names":
                    class_names,

                "class_to_index": {
                    name: index
                    for index, name
                    in enumerate(
                        class_names
                    )
                },
            },
            file,
            indent=2,
        )

    model = build_model(
        len(class_names)
    )

    model = model.to(
        device
    )

    criterion = (
        nn.CrossEntropyLoss(
            label_smoothing=0.05
        )
    )

    history = []

    best_validation_loss = (
        float("inf")
    )

    best_model_state = (
        copy.deepcopy(
            model.state_dict()
        )
    )

    # ======================================================
    # PHASE 1
    # Train classifier head only
    # ======================================================

    print()
    print("=" * 70)
    print(
        "PHASE 1 — CLASSIFIER HEAD"
    )
    print("=" * 70)

    head_optimizer = AdamW(
        model.classifier.parameters(),
        lr=HEAD_LEARNING_RATE,
        weight_decay=WEIGHT_DECAY,
    )

    head_scheduler = (
        ReduceLROnPlateau(
            head_optimizer,
            mode="min",
            factor=0.5,
            patience=2,
        )
    )

    (
        best_validation_loss,
        best_model_state,
        global_epoch,
    ) = run_training_phase(
        phase_name="head",

        model=model,

        train_loader=train_loader,

        validation_loader=
            validation_loader,

        criterion=criterion,

        optimizer=head_optimizer,

        scheduler=head_scheduler,

        device=device,

        class_names=class_names,

        epochs=HEAD_EPOCHS,

        history=history,

        global_epoch_start=0,

        best_validation_loss=
            best_validation_loss,

        best_model_state=
            best_model_state,
    )

    # Restore the best stage-1 parameters before fine tuning.
    model.load_state_dict(
        best_model_state
    )

    # ======================================================
    # PHASE 2
    # Fine tune final EfficientNet blocks
    # ======================================================

    print()
    print("=" * 70)
    print(
        "PHASE 2 — FINE TUNING"
    )
    print("=" * 70)

    unfreeze_final_blocks(
        model
    )

    backbone_parameters = []

    classifier_parameters = list(
        model.classifier.parameters()
    )

    for parameter in (
        model.features.parameters()
    ):
        if parameter.requires_grad:
            backbone_parameters.append(
                parameter
            )

    fine_tune_optimizer = AdamW(
        [
            {
                "params":
                    backbone_parameters,

                "lr":
                    FINE_TUNE_BACKBONE_LR,
            },

            {
                "params":
                    classifier_parameters,

                "lr":
                    FINE_TUNE_CLASSIFIER_LR,
            },
        ],

        weight_decay=WEIGHT_DECAY,
    )

    fine_tune_scheduler = (
        ReduceLROnPlateau(
            fine_tune_optimizer,
            mode="min",
            factor=0.5,
            patience=2,
        )
    )

    (
        best_validation_loss,
        best_model_state,
        global_epoch,
    ) = run_training_phase(
        phase_name="fine_tune",

        model=model,

        train_loader=train_loader,

        validation_loader=
            validation_loader,

        criterion=criterion,

        optimizer=fine_tune_optimizer,

        scheduler=fine_tune_scheduler,

        device=device,

        class_names=class_names,

        epochs=FINE_TUNE_EPOCHS,

        history=history,

        global_epoch_start=
            global_epoch,

        best_validation_loss=
            best_validation_loss,

        best_model_state=
            best_model_state,
    )

    # Use the best validation checkpoint.
    model.load_state_dict(
        best_model_state
    )

    # ======================================================
    # FINAL TEST EVALUATION
    # ======================================================

    print()
    print("=" * 70)
    print(
        "FINAL TEST EVALUATION"
    )
    print("=" * 70)

    (
        test_loss,
        test_accuracy,
        true_labels,
        predicted_labels,
        probabilities,
    ) = evaluate_epoch(
        model,
        test_loader,
        criterion,
        device,
    )

    macro_precision = precision_score(
        true_labels,
        predicted_labels,
        average="macro",
        zero_division=0,
    )

    macro_recall = recall_score(
        true_labels,
        predicted_labels,
        average="macro",
        zero_division=0,
    )

    macro_f1 = f1_score(
        true_labels,
        predicted_labels,
        average="macro",
        zero_division=0,
    )

    weighted_f1 = f1_score(
        true_labels,
        predicted_labels,
        average="weighted",
        zero_division=0,
    )

    report = classification_report(
        true_labels,
        predicted_labels,

        target_names=
            class_names,

        output_dict=True,

        zero_division=0,
    )

    matrix = confusion_matrix(
        true_labels,
        predicted_labels,
    )

    metrics = {
        "model":
            "EfficientNet-B0",

        "classes":
            class_names,

        "test_images":
            len(true_labels),

        "test_loss":
            round(
                float(test_loss),
                6,
            ),

        "accuracy":
            round(
                float(test_accuracy),
                6,
            ),

        "macro_precision":
            round(
                float(macro_precision),
                6,
            ),

        "macro_recall":
            round(
                float(macro_recall),
                6,
            ),

        "macro_f1":
            round(
                float(macro_f1),
                6,
            ),

        "weighted_f1":
            round(
                float(weighted_f1),
                6,
            ),

        "best_validation_loss":
            round(
                float(
                    best_validation_loss
                ),
                6,
            ),

        "dataset_note": (
            "Beautyverse V1 uses one "
            "representative per independent "
            "source family to reduce "
            "augmentation-derived leakage."
        ),
    }

    with METRICS_PATH.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            metrics,
            file,
            indent=2,
        )

    with REPORT_PATH.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            report,
            file,
            indent=2,
        )

    save_training_history(
        history
    )

    plot_training_curves(
        history
    )

    plot_confusion_matrix(
        matrix,
        class_names,
    )

    # Save final best checkpoint again.
    save_checkpoint(
        model,
        class_names,
        best_validation_loss,
    )

    print()
    print(
        f"Test Loss:       "
        f"{test_loss:.4f}"
    )

    print(
        f"Test Accuracy:   "
        f"{test_accuracy:.4f} "
        f"({test_accuracy * 100:.2f}%)"
    )

    print(
        f"Macro Precision: "
        f"{macro_precision:.4f}"
    )

    print(
        f"Macro Recall:    "
        f"{macro_recall:.4f}"
    )

    print(
        f"Macro F1:        "
        f"{macro_f1:.4f}"
    )

    print(
        f"Weighted F1:     "
        f"{weighted_f1:.4f}"
    )

    print()
    print(
        "Classification Report:"
    )

    print(
        classification_report(
            true_labels,
            predicted_labels,

            target_names=
                class_names,

            zero_division=0,
        )
    )

    print()
    print("=" * 70)
    print(
        "TRAINING COMPLETE"
    )
    print("=" * 70)

    print()
    print(
        f"Best model:\n"
        f"{BEST_MODEL_PATH}"
    )

    print()
    print(
        f"Metrics:\n"
        f"{METRICS_PATH}"
    )

    print()
    print(
        f"Classification report:\n"
        f"{REPORT_PATH}"
    )

    print()
    print(
        f"Training history:\n"
        f"{HISTORY_PATH}"
    )

    print()
    print(
        f"Confusion matrix:\n"
        f"{CONFUSION_MATRIX_PATH}"
    )

    print()
    print(
        f"Training curves:\n"
        f"{TRAINING_CURVES_PATH}"
    )

    print()


if __name__ == "__main__":
    main()
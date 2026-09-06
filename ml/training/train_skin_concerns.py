from __future__ import annotations

import copy
import json
import random
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch

from PIL import Image

from sklearn.metrics import (
    average_precision_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

from torch import nn
from torch.utils.data import (
    DataLoader,
    Dataset,
)

from torchvision import transforms

from torchvision.models import (
    EfficientNet_B0_Weights,
    efficientnet_b0,
)


# =========================================================
# CONFIGURATION
# =========================================================

SEED = 42

IMAGE_SIZE = 224

BATCH_SIZE = 16

# Windows-safe
NUM_WORKERS = 0


# ---------------------------------------------------------
# STAGE 1
# Weak concern pretraining
# ---------------------------------------------------------

STAGE1_HEAD_EPOCHS = 3

STAGE1_FINETUNE_EPOCHS = 5


# ---------------------------------------------------------
# STAGE 2
# Gold multi-label fine-tuning
# ---------------------------------------------------------

STAGE2_HEAD_EPOCHS = 2

STAGE2_FINETUNE_EPOCHS = 10

STAGE2_PATIENCE = 4


PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[2]
)


PROCESSED_ROOT = (
    PROJECT_ROOT
    / "ml"
    / "data"
    / "processed"
    / "skin_concerns_v1"
)


MANIFEST_PATH = (
    PROCESSED_ROOT
    / "manifest.csv"
)


GOLD_PATH = (
    PROCESSED_ROOT
    / "gold_annotations.csv"
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


PRETRAINED_MODEL_PATH = (
    MODEL_DIR
    / "skin_concern_pretrained_efficientnet_b0.pt"
)


FINAL_MODEL_PATH = (
    MODEL_DIR
    / "best_skin_concerns.pt"
)


THRESHOLDS_PATH = (
    RESULTS_DIR
    / "concern_thresholds.json"
)


METRICS_PATH = (
    RESULTS_DIR
    / "skin_concern_metrics.json"
)


HISTORY_PATH = (
    RESULTS_DIR
    / "skin_concern_training_history.csv"
)


CURVES_PATH = (
    RESULTS_DIR
    / "skin_concern_training_curves.png"
)


TARGET_LABELS = [
    "acne",
    "pigmentation",
    "redness",
    "pores",
    "wrinkles",
]


# =========================================================
# REPRODUCIBILITY
# =========================================================

def set_seed(
    seed=SEED,
):

    random.seed(
        seed
    )

    np.random.seed(
        seed
    )

    torch.manual_seed(
        seed
    )

    if torch.cuda.is_available():

        torch.cuda.manual_seed_all(
            seed
        )


# =========================================================
# IMAGE TRANSFORMS
# =========================================================

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


# Keep colour transformations VERY mild.
#
# Redness and pigmentation are partly colour-dependent,
# so aggressive colour jitter would damage useful signals.

train_transform = transforms.Compose(
    [
        transforms.RandomResizedCrop(
            IMAGE_SIZE,
            scale=(0.88, 1.0),
            ratio=(0.95, 1.05),
        ),

        transforms.RandomHorizontalFlip(
            p=0.5
        ),

        transforms.RandomAffine(
            degrees=5,
            translate=(
                0.02,
                0.02,
            ),
            scale=(
                0.97,
                1.03,
            ),
        ),

        transforms.ColorJitter(
            brightness=0.05,
            contrast=0.05,
        ),

        transforms.ToTensor(),

        transforms.Normalize(
            IMAGENET_MEAN,
            IMAGENET_STD,
        ),
    ]
)


eval_transform = transforms.Compose(
    [
        transforms.Resize(
            256
        ),

        transforms.CenterCrop(
            IMAGE_SIZE
        ),

        transforms.ToTensor(),

        transforms.Normalize(
            IMAGENET_MEAN,
            IMAGENET_STD,
        ),
    ]
)


# =========================================================
# PATH HELPER
# =========================================================

def resolve_image_path(
    value,
):

    path = Path(
        str(value)
    )

    if path.is_absolute():

        return path

    return (
        PROJECT_ROOT
        / path
    )


# =========================================================
# STAGE 1 DATASET
# =========================================================

class WeakConcernDataset(
    Dataset
):

    """
    Used only for Stage 1.

    Each cleaned source-family image has one
    known primary concern.

    Stage 1 learns useful skin-concern visual
    features.

    It is NOT yet the final multi-label detector.
    """

    def __init__(
        self,
        dataframe,
        transform,
    ):

        self.dataframe = (
            dataframe
            .reset_index(
                drop=True
            )
        )

        self.transform = (
            transform
        )


    def __len__(
        self,
    ):

        return len(
            self.dataframe
        )


    def __getitem__(
        self,
        index,
    ):

        row = (
            self.dataframe
            .iloc[index]
        )

        image_path = (
            resolve_image_path(
                row[
                    "image_path"
                ]
            )
        )

        with Image.open(
            image_path
        ) as image:

            image = (
                image
                .convert(
                    "RGB"
                )
            )

        image = (
            self.transform(
                image
            )
        )

        target = int(
            row[
                "weak_target_index"
            ]
        )

        return (
            image,

            torch.tensor(
                target,
                dtype=torch.long,
            ),
        )


# =========================================================
# STAGE 2 DATASET
# =========================================================

class GoldConcernDataset(
    Dataset
):

    """
    Multi-label dataset.

    Yes:
        target = 1
        mask   = 1

    No:
        target = 0
        mask   = 1

    Unsure:
        target = 0
        mask   = 0

    mask=0 means the label does not contribute
    to training or evaluation.
    """

    def __init__(
        self,
        dataframe,
        transform,
    ):

        self.dataframe = (
            dataframe
            .reset_index(
                drop=True
            )
        )

        self.transform = (
            transform
        )


    def __len__(
        self,
    ):

        return len(
            self.dataframe
        )


    def __getitem__(
        self,
        index,
    ):

        row = (
            self.dataframe
            .iloc[index]
        )

        image_path = (
            resolve_image_path(
                row[
                    "image_path"
                ]
            )
        )

        with Image.open(
            image_path
        ) as image:

            image = (
                image
                .convert(
                    "RGB"
                )
            )

        image = (
            self.transform(
                image
            )
        )

        targets = []

        masks = []


        for label in (
            TARGET_LABELS
        ):

            value = (
                str(
                    row[
                        f"annotation_{label}"
                    ]
                )
                .strip()
                .lower()
            )


            if value == "yes":

                targets.append(
                    1.0
                )

                masks.append(
                    1.0
                )


            elif value == "no":

                targets.append(
                    0.0
                )

                masks.append(
                    1.0
                )


            else:

                # Unsure
                targets.append(
                    0.0
                )

                masks.append(
                    0.0
                )


        return (
            image,

            torch.tensor(
                targets,
                dtype=torch.float32,
            ),

            torch.tensor(
                masks,
                dtype=torch.float32,
            ),
        )


# =========================================================
# LOAD WEAK DATA
# =========================================================

def load_weak_dataframe():

    if not MANIFEST_PATH.exists():

        raise FileNotFoundError(
            f"Manifest not found:\n"
            f"{MANIFEST_PATH}"
        )


    dataframe = pd.read_csv(
        MANIFEST_PATH
    )


    rows = []

    skipped = 0


    for _, row in (
        dataframe.iterrows()
    ):

        positives = []


        for label in (
            TARGET_LABELS
        ):

            mask = row.get(
                f"mask_{label}",
                0,
            )

            value = row.get(
                f"label_{label}",
                0,
            )


            try:

                mask = int(
                    float(
                        mask
                    )
                )

            except (
                ValueError,
                TypeError,
            ):

                mask = 0


            try:

                value = int(
                    float(
                        value
                    )
                )

            except (
                ValueError,
                TypeError,
            ):

                value = 0


            if (
                mask == 1
                and
                value == 1
            ):

                positives.append(
                    label
                )


        if len(
            positives
        ) != 1:

            skipped += 1

            continue


        copied = (
            row.copy()
        )


        copied[
            "weak_target"
        ] = positives[0]


        copied[
            "weak_target_index"
        ] = (
            TARGET_LABELS.index(
                positives[0]
            )
        )


        rows.append(
            copied
        )


    weak_df = pd.DataFrame(
        rows
    )


    weak_df[
        "split"
    ] = (
        weak_df[
            "split"
        ]
        .astype(
            str
        )
        .str.strip()
        .str.lower()
    )


    print(
        "\nStage 1 usable weak-label images:",
        len(
            weak_df
        ),
    )


    if skipped:

        print(
            "Skipped rows without exactly "
            "one known primary concern:",
            skipped,
        )


    return weak_df


# =========================================================
# LOAD GOLD DATA
# =========================================================

def load_gold_dataframe():

    if not GOLD_PATH.exists():

        raise FileNotFoundError(
            f"Gold annotations not found:\n"
            f"{GOLD_PATH}"
        )


    gold = pd.read_csv(
        GOLD_PATH
    )


    required = {
        "image_path",
        "split",
        "completed",
    }


    for label in (
        TARGET_LABELS
    ):

        required.add(
            f"annotation_{label}"
        )


    missing = (
        required
        - set(
            gold.columns
        )
    )


    if missing:

        raise ValueError(
            "gold_annotations.csv is missing:\n"
            + "\n".join(
                sorted(
                    missing
                )
            )
        )


    completed = (
        gold[
            "completed"
        ]
        .astype(
            str
        )
        .str.strip()
        .str.lower()
        .eq(
            "true"
        )
    )


    if not completed.all():

        incomplete = int(
            (
                ~completed
            ).sum()
        )

        raise ValueError(
            f"{incomplete} annotations "
            f"are incomplete."
        )


    gold[
        "split"
    ] = (
        gold[
            "split"
        ]
        .astype(
            str
        )
        .str.strip()
        .str.lower()
    )


    print(
        "\nGold annotation split counts:"
    )


    split_counts = (
        gold[
            "split"
        ]
        .value_counts()
        .to_dict()
    )


    for split in [
        "train",
        "validation",
        "test",
    ]:

        count = int(
            split_counts.get(
                split,
                0,
            )
        )


        print(
            f"  "
            f"{split:<12} "
            f"{count}"
        )


        if count == 0:

            raise ValueError(
                f"No '{split}' rows "
                f"exist in gold_annotations.csv."
            )


    print(
        "\nGold label counts:"
    )


    for label in (
        TARGET_LABELS
    ):

        values = (
            gold[
                f"annotation_{label}"
            ]
            .astype(
                str
            )
            .str.strip()
            .str.lower()
        )


        yes = int(
            (
                values
                == "yes"
            ).sum()
        )


        no = int(
            (
                values
                == "no"
            ).sum()
        )


        unsure = int(
            (
                values
                == "unsure"
            ).sum()
        )


        print(
            f"  {label:<15} "
            f"Yes={yes:<4} "
            f"No={no:<4} "
            f"Unsure={unsure:<4}"
        )


    return gold


# =========================================================
# DATALOADER
# =========================================================

def make_loader(
    dataset,
    shuffle,
):

    generator = (
        torch.Generator()
    )


    generator.manual_seed(
        SEED
    )


    return DataLoader(
        dataset,

        batch_size=
            BATCH_SIZE,

        shuffle=
            shuffle,

        num_workers=
            NUM_WORKERS,

        pin_memory=
            torch.cuda.is_available(),

        generator=(
            generator
            if shuffle
            else None
        ),
    )


# =========================================================
# MODEL
# =========================================================

def build_model(
    imagenet_pretrained=True,
):

    if imagenet_pretrained:

        weights = (
            EfficientNet_B0_Weights
            .DEFAULT
        )

    else:

        weights = None


    model = efficientnet_b0(
        weights=weights
    )


    in_features = (
        model
        .classifier[1]
        .in_features
    )


    model.classifier = (
        nn.Sequential(
            nn.Dropout(
                p=0.40
            ),

            nn.Linear(
                in_features,
                len(
                    TARGET_LABELS
                ),
            ),
        )
    )


    return model


# =========================================================
# FREEZING
# =========================================================

def freeze_backbone(
    model,
):

    for parameter in (
        model
        .features
        .parameters()
    ):

        parameter.requires_grad = (
            False
        )


    for parameter in (
        model
        .classifier
        .parameters()
    ):

        parameter.requires_grad = (
            True
        )


def unfreeze_last_blocks(
    model,
    number_of_blocks,
):

    for parameter in (
        model
        .features
        .parameters()
    ):

        parameter.requires_grad = (
            False
        )


    for block in (
        model
        .features[
            -number_of_blocks:
        ]
    ):

        for parameter in (
            block.parameters()
        ):

            parameter.requires_grad = (
                True
            )


    for parameter in (
        model
        .classifier
        .parameters()
    ):

        parameter.requires_grad = (
            True
        )


# =========================================================
# STAGE 1 TRAINING
# =========================================================

def train_stage1_epoch(
    model,
    loader,
    criterion,
    optimizer,
    device,
):

    model.train()


    total_loss = 0.0

    total_items = 0


    for (
        images,
        targets,
    ) in loader:

        images = images.to(
            device
        )

        targets = targets.to(
            device
        )


        optimizer.zero_grad(
            set_to_none=True
        )


        logits = model(
            images
        )


        loss = criterion(
            logits,
            targets,
        )


        loss.backward()

        optimizer.step()


        batch_size = (
            images.size(
                0
            )
        )


        total_loss += (
            loss.item()
            * batch_size
        )


        total_items += (
            batch_size
        )


    return (
        total_loss
        / max(
            total_items,
            1,
        )
    )


def evaluate_stage1(
    model,
    loader,
    criterion,
    device,
):

    model.eval()


    total_loss = 0.0

    total_items = 0


    true_labels = []

    predictions = []


    with torch.no_grad():

        for (
            images,
            targets,
        ) in loader:

            images = (
                images.to(
                    device
                )
            )

            targets = (
                targets.to(
                    device
                )
            )


            logits = model(
                images
            )


            loss = criterion(
                logits,
                targets,
            )


            batch_size = (
                images.size(
                    0
                )
            )


            total_loss += (
                loss.item()
                * batch_size
            )


            total_items += (
                batch_size
            )


            predicted = (
                torch.argmax(
                    logits,
                    dim=1,
                )
            )


            true_labels.extend(
                targets
                .cpu()
                .numpy()
                .tolist()
            )


            predictions.extend(
                predicted
                .cpu()
                .numpy()
                .tolist()
            )


    average_loss = (
        total_loss
        / max(
            total_items,
            1,
        )
    )


    accuracy = float(
        np.mean(
            np.array(
                true_labels
            )
            ==
            np.array(
                predictions
            )
        )
    )


    macro_f1 = float(
        f1_score(
            true_labels,
            predictions,
            average="macro",
            zero_division=0,
        )
    )


    return {
        "loss":
            average_loss,

        "accuracy":
            accuracy,

        "macro_f1":
            macro_f1,
    }


# =========================================================
# RUN STAGE 1
# =========================================================

def run_stage1(
    weak_df,
    device,
):

    print(
        "\n========================================"
    )

    print(
        "STAGE 1 - WEAK CONCERN PRETRAINING"
    )

    print(
        "========================================"
    )


    train_df = (
        weak_df[
            weak_df[
                "split"
            ]
            == "train"
        ]
        .copy()
    )


    validation_df = (
        weak_df[
            weak_df[
                "split"
            ]
            == "validation"
        ]
        .copy()
    )


    print(
        "\nWeak train:",
        len(
            train_df
        ),
    )


    print(
        "Weak validation:",
        len(
            validation_df
        ),
    )


    print(
        "Weak TEST images are intentionally "
        "not used during Stage 1."
    )


    train_dataset = (
        WeakConcernDataset(
            train_df,
            train_transform,
        )
    )


    validation_dataset = (
        WeakConcernDataset(
            validation_df,
            eval_transform,
        )
    )


    train_loader = (
        make_loader(
            train_dataset,
            True,
        )
    )


    validation_loader = (
        make_loader(
            validation_dataset,
            False,
        )
    )


    model = (
        build_model(
            imagenet_pretrained=True
        )
        .to(
            device
        )
    )


    criterion = (
        nn.CrossEntropyLoss(
            label_smoothing=0.05
        )
    )


    history = []


    best_state = copy.deepcopy(
        model.state_dict()
    )


    best_validation_f1 = (
        -1.0
    )


    stage_epoch = 0


    # -----------------------------------------------------
    # HEAD TRAINING
    # -----------------------------------------------------

    freeze_backbone(
        model
    )


    optimizer = (
        torch.optim.AdamW(
            model
            .classifier
            .parameters(),

            lr=1e-3,

            weight_decay=1e-4,
        )
    )


    for epoch in range(
        1,
        STAGE1_HEAD_EPOCHS + 1,
    ):

        stage_epoch += 1


        train_loss = (
            train_stage1_epoch(
                model,
                train_loader,
                criterion,
                optimizer,
                device,
            )
        )


        validation = (
            evaluate_stage1(
                model,
                validation_loader,
                criterion,
                device,
            )
        )


        print(
            f"[Stage1 Head] "
            f"Epoch {epoch}/"
            f"{STAGE1_HEAD_EPOCHS} | "
            f"train_loss="
            f"{train_loss:.4f} | "
            f"val_loss="
            f"{validation['loss']:.4f} | "
            f"val_acc="
            f"{validation['accuracy']:.4f} | "
            f"val_f1="
            f"{validation['macro_f1']:.4f}"
        )


        history.append(
            {
                "stage":
                    "stage1",

                "phase":
                    "head",

                "epoch":
                    stage_epoch,

                "train_loss":
                    train_loss,

                "val_loss":
                    validation[
                        "loss"
                    ],

                "val_macro_f1":
                    validation[
                        "macro_f1"
                    ],
            }
        )


        if (
            validation[
                "macro_f1"
            ]
            >
            best_validation_f1
        ):

            best_validation_f1 = (
                validation[
                    "macro_f1"
                ]
            )


            best_state = (
                copy.deepcopy(
                    model.state_dict()
                )
            )


    # -----------------------------------------------------
    # FINE-TUNING
    # -----------------------------------------------------

    model.load_state_dict(
        best_state
    )


    unfreeze_last_blocks(
        model,
        number_of_blocks=2,
    )


    backbone_parameters = []

    classifier_parameters = []


    for (
        name,
        parameter,
    ) in (
        model.named_parameters()
    ):

        if not (
            parameter
            .requires_grad
        ):

            continue


        if name.startswith(
            "classifier"
        ):

            classifier_parameters.append(
                parameter
            )

        else:

            backbone_parameters.append(
                parameter
            )


    optimizer = (
        torch.optim.AdamW(
            [
                {
                    "params":
                        backbone_parameters,

                    "lr":
                        1e-5,
                },

                {
                    "params":
                        classifier_parameters,

                    "lr":
                        1e-4,
                },
            ],

            weight_decay=
                1e-4,
        )
    )


    for epoch in range(
        1,
        STAGE1_FINETUNE_EPOCHS + 1,
    ):

        stage_epoch += 1


        train_loss = (
            train_stage1_epoch(
                model,
                train_loader,
                criterion,
                optimizer,
                device,
            )
        )


        validation = (
            evaluate_stage1(
                model,
                validation_loader,
                criterion,
                device,
            )
        )


        print(
            f"[Stage1 Fine] "
            f"Epoch {epoch}/"
            f"{STAGE1_FINETUNE_EPOCHS} | "
            f"train_loss="
            f"{train_loss:.4f} | "
            f"val_loss="
            f"{validation['loss']:.4f} | "
            f"val_acc="
            f"{validation['accuracy']:.4f} | "
            f"val_f1="
            f"{validation['macro_f1']:.4f}"
        )


        history.append(
            {
                "stage":
                    "stage1",

                "phase":
                    "finetune",

                "epoch":
                    stage_epoch,

                "train_loss":
                    train_loss,

                "val_loss":
                    validation[
                        "loss"
                    ],

                "val_macro_f1":
                    validation[
                        "macro_f1"
                    ],
            }
        )


        if (
            validation[
                "macro_f1"
            ]
            >
            best_validation_f1
        ):

            best_validation_f1 = (
                validation[
                    "macro_f1"
                ]
            )


            best_state = (
                copy.deepcopy(
                    model.state_dict()
                )
            )


    model.load_state_dict(
        best_state
    )


    torch.save(
        {
            "state_dict":
                model.state_dict(),

            "class_names":
                TARGET_LABELS,

            "stage":
                "weak_concern_pretraining",

            "best_validation_macro_f1":
                best_validation_f1,

            "image_size":
                IMAGE_SIZE,
        },

        PRETRAINED_MODEL_PATH,
    )


    print(
        "\nStage 1 complete."
    )


    print(
        "Saved:"
    )


    print(
        PRETRAINED_MODEL_PATH
    )


    return (
        model,
        history,
    )


# =========================================================
# CLASS BALANCING
# =========================================================

def compute_positive_weights(
    train_df,
    device,
):

    weights = []


    print(
        "\nTraining-set label balance:"
    )


    for label in (
        TARGET_LABELS
    ):

        values = (
            train_df[
                f"annotation_{label}"
            ]
            .astype(
                str
            )
            .str.strip()
            .str.lower()
        )


        positive_count = int(
            (
                values
                == "yes"
            ).sum()
        )


        negative_count = int(
            (
                values
                == "no"
            ).sum()
        )


        if (
            positive_count == 0
            or
            negative_count == 0
        ):

            raise ValueError(
                f"{label} needs both "
                f"Yes and No examples "
                f"in TRAIN.\n"
                f"Yes={positive_count}, "
                f"No={negative_count}"
            )


        weight = (
            negative_count
            / positive_count
        )


        weight = float(
            np.clip(
                weight,
                0.25,
                4.0,
            )
        )


        weights.append(
            weight
        )


        print(
            f"  {label:<15} "
            f"Yes={positive_count:<4} "
            f"No={negative_count:<4} "
            f"pos_weight="
            f"{weight:.3f}"
        )


    return torch.tensor(
        weights,
        dtype=torch.float32,
        device=device,
    )


# =========================================================
# MASKED BCE
# =========================================================

def masked_bce_loss(
    logits,
    targets,
    masks,
    criterion,
):

    element_losses = (
        criterion(
            logits,
            targets,
        )
    )


    masked_losses = (
        element_losses
        * masks
    )


    denominator = (
        masks
        .sum()
        .clamp_min(
            1.0
        )
    )


    return (
        masked_losses.sum()
        / denominator
    )


# =========================================================
# STAGE 2 TRAINING
# =========================================================

def train_stage2_epoch(
    model,
    loader,
    criterion,
    optimizer,
    device,
):

    model.train()


    total_loss = 0.0

    batches = 0


    for (
        images,
        targets,
        masks,
    ) in loader:

        images = (
            images.to(
                device
            )
        )


        targets = (
            targets.to(
                device
            )
        )


        masks = (
            masks.to(
                device
            )
        )


        optimizer.zero_grad(
            set_to_none=True
        )


        logits = model(
            images
        )


        loss = (
            masked_bce_loss(
                logits,
                targets,
                masks,
                criterion,
            )
        )


        loss.backward()


        optimizer.step()


        total_loss += (
            loss.item()
        )


        batches += 1


    return (
        total_loss
        / max(
            batches,
            1,
        )
    )


# =========================================================
# MULTI-LABEL EVALUATION
# =========================================================

def collect_outputs(
    model,
    loader,
    criterion,
    device,
):

    model.eval()


    all_targets = []

    all_masks = []

    all_probabilities = []


    total_loss = 0.0

    batches = 0


    with torch.no_grad():

        for (
            images,
            targets,
            masks,
        ) in loader:

            images = (
                images.to(
                    device
                )
            )


            targets = (
                targets.to(
                    device
                )
            )


            masks = (
                masks.to(
                    device
                )
            )


            logits = model(
                images
            )


            loss = (
                masked_bce_loss(
                    logits,
                    targets,
                    masks,
                    criterion,
                )
            )


            probabilities = (
                torch.sigmoid(
                    logits
                )
            )


            total_loss += (
                loss.item()
            )


            batches += 1


            all_targets.append(
                targets
                .cpu()
                .numpy()
            )


            all_masks.append(
                masks
                .cpu()
                .numpy()
            )


            all_probabilities.append(
                probabilities
                .cpu()
                .numpy()
            )


    return (
        np.concatenate(
            all_targets,
            axis=0,
        ),

        np.concatenate(
            all_masks,
            axis=0,
        ),

        np.concatenate(
            all_probabilities,
            axis=0,
        ),

        total_loss
        / max(
            batches,
            1,
        ),
    )


# =========================================================
# THRESHOLD TUNING
# =========================================================

def tune_thresholds(
    y_true,
    y_mask,
    y_probability,
):

    thresholds = {}


    for (
        index,
        label,
    ) in enumerate(
        TARGET_LABELS
    ):

        known = (
            y_mask[
                :,
                index
            ]
            == 1
        )


        true_values = (
            y_true[
                known,
                index,
            ]
            .astype(
                int
            )
        )


        probabilities = (
            y_probability[
                known,
                index,
            ]
        )


        if len(
            np.unique(
                true_values
            )
        ) < 2:

            thresholds[
                label
            ] = 0.5

            continue


        best_threshold = (
            0.5
        )


        best_f1 = (
            -1.0
        )


        for threshold in (
            np.arange(
                0.10,
                0.91,
                0.01,
            )
        ):

            predictions = (
                probabilities
                >= threshold
            ).astype(
                int
            )


            score = (
                f1_score(
                    true_values,
                    predictions,
                    zero_division=0,
                )
            )


            if score > best_f1:

                best_f1 = (
                    score
                )


                best_threshold = (
                    float(
                        threshold
                    )
                )


        thresholds[
            label
        ] = round(
            best_threshold,
            4,
        )


    return thresholds


# =========================================================
# METRICS
# =========================================================

def calculate_metrics(
    y_true,
    y_mask,
    y_probability,
    thresholds,
):

    per_label = {}


    precisions = []

    recalls = []

    f1_values = []

    roc_auc_values = []

    pr_auc_values = []


    for (
        index,
        label,
    ) in enumerate(
        TARGET_LABELS
    ):

        known = (
            y_mask[
                :,
                index
            ]
            == 1
        )


        true_values = (
            y_true[
                known,
                index,
            ]
            .astype(
                int
            )
        )


        probabilities = (
            y_probability[
                known,
                index,
            ]
        )


        threshold = float(
            thresholds[
                label
            ]
        )


        predictions = (
            probabilities
            >= threshold
        ).astype(
            int
        )


        precision = float(
            precision_score(
                true_values,
                predictions,
                zero_division=0,
            )
        )


        recall = float(
            recall_score(
                true_values,
                predictions,
                zero_division=0,
            )
        )


        f1 = float(
            f1_score(
                true_values,
                predictions,
                zero_division=0,
            )
        )


        roc_auc = None

        pr_auc = None


        if len(
            np.unique(
                true_values
            )
        ) >= 2:

            roc_auc = float(
                roc_auc_score(
                    true_values,
                    probabilities,
                )
            )


            pr_auc = float(
                average_precision_score(
                    true_values,
                    probabilities,
                )
            )


            roc_auc_values.append(
                roc_auc
            )


            pr_auc_values.append(
                pr_auc
            )


        precisions.append(
            precision
        )


        recalls.append(
            recall
        )


        f1_values.append(
            f1
        )


        per_label[
            label
        ] = {
            "threshold":
                threshold,

            "known_labels":
                int(
                    known.sum()
                ),

            "positives":
                int(
                    true_values.sum()
                ),

            "negatives":
                int(
                    len(
                        true_values
                    )
                    -
                    true_values.sum()
                ),

            "precision":
                precision,

            "recall":
                recall,

            "f1":
                f1,

            "roc_auc":
                roc_auc,

            "pr_auc":
                pr_auc,
        }


    return {
        "macro_precision":
            float(
                np.mean(
                    precisions
                )
            ),

        "macro_recall":
            float(
                np.mean(
                    recalls
                )
            ),

        "macro_f1":
            float(
                np.mean(
                    f1_values
                )
            ),

        "macro_roc_auc":
            (
                float(
                    np.mean(
                        roc_auc_values
                    )
                )
                if roc_auc_values
                else None
            ),

        "macro_pr_auc":
            (
                float(
                    np.mean(
                        pr_auc_values
                    )
                )
                if pr_auc_values
                else None
            ),

        "per_label":
            per_label,
    }


# =========================================================
# TRAIN FINAL GOLD MODEL
# =========================================================

def run_stage2(
    gold_df,
    device,
    stage1_history,
):

    print(
        "\n========================================"
    )

    print(
        "STAGE 2 - GOLD MULTI-LABEL TRAINING"
    )

    print(
        "========================================"
    )


    train_df = (
        gold_df[
            gold_df[
                "split"
            ]
            == "train"
        ]
        .copy()
    )


    validation_df = (
        gold_df[
            gold_df[
                "split"
            ]
            == "validation"
        ]
        .copy()
    )


    test_df = (
        gold_df[
            gold_df[
                "split"
            ]
            == "test"
        ]
        .copy()
    )


    train_dataset = (
        GoldConcernDataset(
            train_df,
            train_transform,
        )
    )


    validation_dataset = (
        GoldConcernDataset(
            validation_df,
            eval_transform,
        )
    )


    test_dataset = (
        GoldConcernDataset(
            test_df,
            eval_transform,
        )
    )


    train_loader = (
        make_loader(
            train_dataset,
            True,
        )
    )


    validation_loader = (
        make_loader(
            validation_dataset,
            False,
        )
    )


    test_loader = (
        make_loader(
            test_dataset,
            False,
        )
    )


    checkpoint = torch.load(
        PRETRAINED_MODEL_PATH,

        map_location=
            device,

        weights_only=
            False,
    )


    model = (
        build_model(
            imagenet_pretrained=False
        )
        .to(
            device
        )
    )


    model.load_state_dict(
        checkpoint[
            "state_dict"
        ]
    )


    positive_weights = (
        compute_positive_weights(
            train_df,
            device,
        )
    )


    criterion = (
        nn.BCEWithLogitsLoss(
            pos_weight=
                positive_weights,

            reduction=
                "none",
        )
    )


    history = list(
        stage1_history
    )


    best_state = copy.deepcopy(
        model.state_dict()
    )


    best_thresholds = {
        label:
            0.5

        for label
        in TARGET_LABELS
    }


    best_validation_metrics = (
        None
    )


    best_validation_f1 = (
        -1.0
    )


    stage2_epoch = 0


    # -----------------------------------------------------
    # HEAD PHASE
    # -----------------------------------------------------

    freeze_backbone(
        model
    )


    optimizer = (
        torch.optim.AdamW(
            model
            .classifier
            .parameters(),

            lr=5e-4,

            weight_decay=
                1e-4,
        )
    )


    for epoch in range(
        1,
        STAGE2_HEAD_EPOCHS + 1,
    ):

        stage2_epoch += 1


        train_loss = (
            train_stage2_epoch(
                model,
                train_loader,
                criterion,
                optimizer,
                device,
            )
        )


        (
            y_true,
            y_mask,
            y_probability,
            validation_loss,
        ) = collect_outputs(
            model,
            validation_loader,
            criterion,
            device,
        )


        thresholds = (
            tune_thresholds(
                y_true,
                y_mask,
                y_probability,
            )
        )


        validation_metrics = (
            calculate_metrics(
                y_true,
                y_mask,
                y_probability,
                thresholds,
            )
        )


        print(
            f"[Stage2 Head] "
            f"Epoch {epoch}/"
            f"{STAGE2_HEAD_EPOCHS} | "
            f"train_loss="
            f"{train_loss:.4f} | "
            f"val_loss="
            f"{validation_loss:.4f} | "
            f"val_macro_f1="
            f"{validation_metrics['macro_f1']:.4f}"
        )


        history.append(
            {
                "stage":
                    "stage2",

                "phase":
                    "head",

                "epoch":
                    stage2_epoch,

                "train_loss":
                    train_loss,

                "val_loss":
                    validation_loss,

                "val_macro_f1":
                    validation_metrics[
                        "macro_f1"
                    ],
            }
        )


        if (
            validation_metrics[
                "macro_f1"
            ]
            >
            best_validation_f1
        ):

            best_validation_f1 = (
                validation_metrics[
                    "macro_f1"
                ]
            )


            best_state = (
                copy.deepcopy(
                    model.state_dict()
                )
            )


            best_thresholds = (
                dict(
                    thresholds
                )
            )


            best_validation_metrics = (
                copy.deepcopy(
                    validation_metrics
                )
            )


    # -----------------------------------------------------
    # FINE-TUNING PHASE
    # -----------------------------------------------------

    model.load_state_dict(
        best_state
    )


    unfreeze_last_blocks(
        model,
        number_of_blocks=3,
    )


    backbone_parameters = []

    classifier_parameters = []


    for (
        name,
        parameter,
    ) in (
        model.named_parameters()
    ):

        if not parameter.requires_grad:

            continue


        if name.startswith(
            "classifier"
        ):

            classifier_parameters.append(
                parameter
            )

        else:

            backbone_parameters.append(
                parameter
            )


    optimizer = (
        torch.optim.AdamW(
            [
                {
                    "params":
                        backbone_parameters,

                    "lr":
                        5e-6,
                },

                {
                    "params":
                        classifier_parameters,

                    "lr":
                        5e-5,
                },
            ],

            weight_decay=
                1e-4,
        )
    )


    epochs_without_improvement = (
        0
    )


    for epoch in range(
        1,
        STAGE2_FINETUNE_EPOCHS + 1,
    ):

        stage2_epoch += 1


        train_loss = (
            train_stage2_epoch(
                model,
                train_loader,
                criterion,
                optimizer,
                device,
            )
        )


        (
            y_true,
            y_mask,
            y_probability,
            validation_loss,
        ) = collect_outputs(
            model,
            validation_loader,
            criterion,
            device,
        )


        thresholds = (
            tune_thresholds(
                y_true,
                y_mask,
                y_probability,
            )
        )


        validation_metrics = (
            calculate_metrics(
                y_true,
                y_mask,
                y_probability,
                thresholds,
            )
        )


        print(
            f"[Stage2 Fine] "
            f"Epoch {epoch}/"
            f"{STAGE2_FINETUNE_EPOCHS} | "
            f"train_loss="
            f"{train_loss:.4f} | "
            f"val_loss="
            f"{validation_loss:.4f} | "
            f"val_macro_f1="
            f"{validation_metrics['macro_f1']:.4f}"
        )


        history.append(
            {
                "stage":
                    "stage2",

                "phase":
                    "finetune",

                "epoch":
                    stage2_epoch,

                "train_loss":
                    train_loss,

                "val_loss":
                    validation_loss,

                "val_macro_f1":
                    validation_metrics[
                        "macro_f1"
                    ],
            }
        )


        if (
            validation_metrics[
                "macro_f1"
            ]
            >
            best_validation_f1
            + 1e-6
        ):

            best_validation_f1 = (
                validation_metrics[
                    "macro_f1"
                ]
            )


            best_state = (
                copy.deepcopy(
                    model.state_dict()
                )
            )


            best_thresholds = (
                dict(
                    thresholds
                )
            )


            best_validation_metrics = (
                copy.deepcopy(
                    validation_metrics
                )
            )


            epochs_without_improvement = (
                0
            )


        else:

            epochs_without_improvement += (
                1
            )


        if (
            epochs_without_improvement
            >=
            STAGE2_PATIENCE
        ):

            print(
                "\nEarly stopping triggered."
            )

            break


    # =====================================================
    # FINAL TEST
    #
    # TEST DATA HAS NOT BEEN USED FOR TRAINING OR
    # THRESHOLD TUNING.
    # =====================================================

    model.load_state_dict(
        best_state
    )


    (
        test_true,
        test_mask,
        test_probability,
        test_loss,
    ) = collect_outputs(
        model,
        test_loader,
        criterion,
        device,
    )


    test_metrics = (
        calculate_metrics(
            test_true,
            test_mask,
            test_probability,
            best_thresholds,
        )
    )


    # =====================================================
    # SAVE FINAL MODEL
    # =====================================================

    torch.save(
        {
            "state_dict":
                model.state_dict(),

            "class_names":
                TARGET_LABELS,

            "thresholds":
                best_thresholds,

            "image_size":
                IMAGE_SIZE,

            "model_name":
                "EfficientNet-B0",

            "task":
                "multi_label_visible_skin_concerns",

            "best_validation_macro_f1":
                best_validation_f1,

            "test_macro_f1":
                test_metrics[
                    "macro_f1"
                ],

            "note":
                (
                    "Visible cosmetic skin "
                    "concern research baseline. "
                    "Not medical diagnosis."
                ),
        },

        FINAL_MODEL_PATH,
    )


    # =====================================================
    # SAVE THRESHOLDS
    # =====================================================

    with open(
        THRESHOLDS_PATH,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            best_thresholds,
            file,
            indent=2,
        )


    # =====================================================
    # SAVE METRICS
    # =====================================================

    metrics_payload = {
        "validation":
            best_validation_metrics,

        "test":
            {
                "loss":
                    test_loss,

                **test_metrics,
            },

        "gold_split_counts":
            {
                "train":
                    len(
                        train_df
                    ),

                "validation":
                    len(
                        validation_df
                    ),

                "test":
                    len(
                        test_df
                    ),
            },

        "labels":
            TARGET_LABELS,

        "limitations":
            [
                (
                    "Gold annotations contain "
                    "500 human-reviewed images."
                ),

                (
                    "Unsure labels are masked "
                    "during training and evaluation."
                ),

                (
                    "The model identifies visible "
                    "cosmetic concerns rather than "
                    "medical skin diseases."
                ),

                (
                    "No mild/moderate/severe "
                    "severity labels are predicted."
                ),
            ],
    }


    with open(
        METRICS_PATH,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            metrics_payload,
            file,
            indent=2,
        )


    # =====================================================
    # SAVE HISTORY
    # =====================================================

    history_df = pd.DataFrame(
        history
    )


    history_df.to_csv(
        HISTORY_PATH,
        index=False,
    )


    plot_history(
        history_df
    )


    # =====================================================
    # PRINT RESULTS
    # =====================================================

    print(
        "\n========================================"
    )

    print(
        "FINAL GOLD TEST RESULTS"
    )

    print(
        "========================================"
    )


    print(
        f"\nTest loss: "
        f"{test_loss:.4f}"
    )


    print(
        f"Macro Precision: "
        f"{test_metrics['macro_precision']:.4f}"
    )


    print(
        f"Macro Recall: "
        f"{test_metrics['macro_recall']:.4f}"
    )


    print(
        f"Macro F1: "
        f"{test_metrics['macro_f1']:.4f}"
    )


    if (
        test_metrics[
            "macro_roc_auc"
        ]
        is not None
    ):

        print(
            f"Macro ROC-AUC: "
            f"{test_metrics['macro_roc_auc']:.4f}"
        )


    if (
        test_metrics[
            "macro_pr_auc"
        ]
        is not None
    ):

        print(
            f"Macro PR-AUC: "
            f"{test_metrics['macro_pr_auc']:.4f}"
        )


    print(
        "\nPer-concern results:"
    )


    for label in (
        TARGET_LABELS
    ):

        result = (
            test_metrics[
                "per_label"
            ][
                label
            ]
        )


        print(
            f"\n  {label.upper()}"
        )


        print(
            f"    threshold : "
            f"{result['threshold']:.2f}"
        )


        print(
            f"    known     : "
            f"{result['known_labels']}"
        )


        print(
            f"    positives : "
            f"{result['positives']}"
        )


        print(
            f"    negatives : "
            f"{result['negatives']}"
        )


        print(
            f"    precision : "
            f"{result['precision']:.4f}"
        )


        print(
            f"    recall    : "
            f"{result['recall']:.4f}"
        )


        print(
            f"    F1        : "
            f"{result['f1']:.4f}"
        )


        if (
            result[
                "roc_auc"
            ]
            is not None
        ):

            print(
                f"    ROC-AUC   : "
                f"{result['roc_auc']:.4f}"
            )


        if (
            result[
                "pr_auc"
            ]
            is not None
        ):

            print(
                f"    PR-AUC    : "
                f"{result['pr_auc']:.4f}"
            )


    print(
        "\nFinal model:"
    )

    print(
        FINAL_MODEL_PATH
    )


    print(
        "\nThresholds:"
    )

    print(
        THRESHOLDS_PATH
    )


    print(
        "\nMetrics:"
    )

    print(
        METRICS_PATH
    )


# =========================================================
# TRAINING PLOT
# =========================================================

def plot_history(
    history_df,
):

    stage2 = (
        history_df[
            history_df[
                "stage"
            ]
            == "stage2"
        ]
        .copy()
    )


    if stage2.empty:

        return


    figure = plt.figure(
        figsize=(
            8,
            5,
        )
    )


    plt.plot(
        stage2[
            "epoch"
        ],

        stage2[
            "train_loss"
        ],

        marker="o",

        label="Train loss",
    )


    plt.plot(
        stage2[
            "epoch"
        ],

        stage2[
            "val_loss"
        ],

        marker="o",

        label="Validation loss",
    )


    plt.xlabel(
        "Epoch"
    )


    plt.ylabel(
        "Loss"
    )


    plt.title(
        "Beautyverse Skin Concern Training"
    )


    plt.legend()


    plt.tight_layout()


    figure.savefig(
        CURVES_PATH,
        dpi=160,
    )


    plt.close(
        figure
    )


# =========================================================
# MAIN
# =========================================================

def main():

    set_seed()


    MODEL_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )


    RESULTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )


    device = torch.device(
        "cuda"
        if torch.cuda.is_available()
        else "cpu"
    )


    print(
        "\n========================================"
    )

    print(
        "BEAUTYVERSE SKIN CONCERN TRAINING"
    )

    print(
        "========================================"
    )


    print(
        "\nDevice:",
        device,
    )


    print(
        "\nVisible cosmetic concern model."
    )


    print(
        "NOT a medical diagnosis model."
    )


    weak_df = (
        load_weak_dataframe()
    )


    gold_df = (
        load_gold_dataframe()
    )


    (
        _,
        stage1_history,
    ) = run_stage1(
        weak_df,
        device,
    )


    run_stage2(
        gold_df,
        device,
        stage1_history,
    )


if __name__ == "__main__":

    main()
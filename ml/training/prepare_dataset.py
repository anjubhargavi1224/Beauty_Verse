from __future__ import annotations

import hashlib
import json
import random
import re
import shutil
from collections import Counter, defaultdict
from pathlib import Path


SEED = 42

V1_CLASSES = [
    "Combination",
    "Dry",
    "Normal",
    "Oily",
]

TRAIN_RATIO = 0.70
VAL_RATIO = 0.15
TEST_RATIO = 0.15

SUPPORTED_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
}


PROJECT_ROOT = Path(__file__).resolve().parents[2]

RAW_ROOT = (
    PROJECT_ROOT
    / "ml"
    / "data"
    / "raw"
    / "skin_type"
)

OUTPUT_ROOT = (
    PROJECT_ROOT
    / "ml"
    / "data"
    / "processed"
    / "skin_type_v1"
)

REPORT_PATH = (
    PROJECT_ROOT
    / "ml"
    / "results"
    / "dataset_report.json"
)


def find_dataset_root() -> Path:
    """
    Automatically find the folder containing:

        Train/
        Validation/
        Test/

    This means the script still works if the ZIP extracted
    with an additional parent folder.
    """

    if not RAW_ROOT.exists():
        raise FileNotFoundError(
            f"Raw dataset folder does not exist:\n{RAW_ROOT}"
        )

    candidates = [
        RAW_ROOT,
        *RAW_ROOT.rglob("*"),
    ]

    for candidate in candidates:
        if not candidate.is_dir():
            continue

        children = {
            child.name.lower()
            for child in candidate.iterdir()
            if child.is_dir()
        }

        required = {
            "train",
            "validation",
            "test",
        }

        if required.issubset(children):
            return candidate

    raise FileNotFoundError(
        "Could not find dataset root containing "
        "Train, Validation and Test folders."
    )


def normalize_family_name(filename: str) -> str:
    """
    Convert augmented filenames back to a source-family ID.

    Example:

        image_397 - Copy_resized_rotated_90_flipped_horizontal.jpg

    becomes:

        image_397

    This lets us keep related augmentations together
    when rebuilding train/validation/test splits.
    """

    stem = Path(filename).stem

    previous = None

    while stem != previous:
        previous = stem

        stem = re.sub(
            r"_(?:"
            r"resized"
            r"|rotated_(?:90|180|270)"
            r"|flipped_(?:horizontal|vertical)"
            r")$",
            "",
            stem,
            flags=re.IGNORECASE,
        )

    stem = re.sub(
        r"\s*-\s*Copy$",
        "",
        stem,
        flags=re.IGNORECASE,
    )

    return stem.strip().lower()


def transformation_score(path: Path) -> int:
    """
    Prefer the least geometrically transformed image
    when selecting one representative per family.

    Lower score = preferred.
    """

    name = path.stem.lower()

    score = 0

    if "rotated_" in name:
        score += 100

    if "flipped_" in name:
        score += 50

    # Resizing is much less problematic than rotation/flipping.
    score += name.count("_resized")

    if " - copy" in name:
        score += 1

    return score


def choose_representative(files: list[Path]) -> Path:
    """
    Choose one stable representative image
    for a source family.
    """

    ordered = sorted(
        files,
        key=lambda path: (
            transformation_score(path),
            len(path.name),
            path.name.lower(),
        ),
    )

    return ordered[0]


def calculate_sha256(path: Path) -> str:
    hasher = hashlib.sha256()

    with path.open("rb") as file:
        while True:
            chunk = file.read(1024 * 1024)

            if not chunk:
                break

            hasher.update(chunk)

    return hasher.hexdigest()


def scan_dataset(dataset_root: Path):
    """
    Merge the supplied Train/Validation/Test folders
    into one collection.

    We will rebuild our own split later.
    """

    class_files = defaultdict(list)

    raw_split_counts = defaultdict(
        lambda: defaultdict(int)
    )

    split_lookup = {
        "train": "Train",
        "validation": "Validation",
        "test": "Test",
    }

    for split_key, split_folder_name in split_lookup.items():
        split_path = dataset_root / split_folder_name

        if not split_path.exists():
            raise FileNotFoundError(
                f"Missing folder: {split_path}"
            )

        for class_dir in split_path.iterdir():
            if not class_dir.is_dir():
                continue

            class_name = class_dir.name

            for image_path in class_dir.rglob("*"):
                if (
                    image_path.is_file()
                    and image_path.suffix.lower()
                    in SUPPORTED_EXTENSIONS
                ):
                    class_files[class_name].append(
                        image_path
                    )

                    raw_split_counts[
                        split_key
                    ][class_name] += 1

    return class_files, raw_split_counts


def group_into_families(
    files: list[Path],
):
    families = defaultdict(list)

    for path in files:
        family_name = normalize_family_name(
            path.name
        )

        families[
            family_name
        ].append(path)

    return dict(families)


def split_families(
    family_names: list[str],
):
    """
    Deterministically create:

        70% train
        15% validation
        15% test

    at the SOURCE FAMILY level.
    """

    names = list(family_names)

    random.Random(SEED).shuffle(names)

    total = len(names)

    train_count = int(
        total * TRAIN_RATIO
    )

    val_count = int(
        total * VAL_RATIO
    )

    # Remaining families go to test.
    test_count = (
        total
        - train_count
        - val_count
    )

    train = names[
        :train_count
    ]

    validation = names[
        train_count:
        train_count + val_count
    ]

    test = names[
        train_count + val_count:
    ]

    assert (
        len(train)
        + len(validation)
        + len(test)
        == total
    )

    return {
        "train": train,
        "validation": validation,
        "test": test,
    }


def reset_output_folder():
    if OUTPUT_ROOT.exists():
        shutil.rmtree(
            OUTPUT_ROOT
        )

    for split in [
        "train",
        "validation",
        "test",
    ]:
        for class_name in V1_CLASSES:
            (
                OUTPUT_ROOT
                / split
                / class_name
            ).mkdir(
                parents=True,
                exist_ok=True,
            )


def copy_representatives(
    class_families,
    selected_families,
):
    """
    Copy ONE representative image for each source family.

    Training-time data augmentation will later be performed
    dynamically in PyTorch rather than storing duplicate
    rotated/flipped files.
    """

    records = []

    for class_name in V1_CLASSES:
        families = class_families[
            class_name
        ]

        for split_name in [
            "train",
            "validation",
            "test",
        ]:
            family_names = (
                selected_families[
                    class_name
                ][split_name]
            )

            for index, family_name in enumerate(
                family_names,
                start=1,
            ):
                representative = (
                    choose_representative(
                        families[
                            family_name
                        ]
                    )
                )

                safe_family = re.sub(
                    r"[^a-zA-Z0-9_-]+",
                    "_",
                    family_name,
                ).strip("_")

                output_filename = (
                    f"{index:03d}_"
                    f"{safe_family}"
                    f"{representative.suffix.lower()}"
                )

                destination = (
                    OUTPUT_ROOT
                    / split_name
                    / class_name
                    / output_filename
                )

                shutil.copy2(
                    representative,
                    destination,
                )

                records.append(
                    {
                        "class": class_name,
                        "split": split_name,
                        "family": family_name,
                        "source_file": str(
                            representative
                        ),
                        "output_file": str(
                            destination
                        ),
                        "family_variant_count": len(
                            families[
                                family_name
                            ]
                        ),
                    }
                )

    return records


def audit_exact_duplicates(
    class_files,
):
    """
    Audit exact byte-for-byte duplicate images.

    This is independent of filename-family grouping.
    """

    hash_groups = defaultdict(list)

    for class_name, files in (
        class_files.items()
    ):
        for path in files:
            file_hash = calculate_sha256(
                path
            )

            hash_groups[
                file_hash
            ].append(
                {
                    "class": class_name,
                    "path": str(path),
                }
            )

    duplicate_groups = {
        file_hash: entries
        for file_hash, entries
        in hash_groups.items()
        if len(entries) > 1
    }

    cross_class_duplicate_groups = []

    for file_hash, entries in (
        duplicate_groups.items()
    ):
        classes = {
            entry["class"]
            for entry in entries
        }

        if len(classes) > 1:
            cross_class_duplicate_groups.append(
                {
                    "sha256": file_hash,
                    "entries": entries,
                }
            )

    return {
        "duplicate_group_count": len(
            duplicate_groups
        ),

        "duplicate_file_count": sum(
            len(entries)
            for entries
            in duplicate_groups.values()
        ),

        "cross_class_duplicate_group_count":
            len(
                cross_class_duplicate_groups
            ),
    }


def count_processed_images():
    counts = defaultdict(
        lambda: defaultdict(int)
    )

    for split in [
        "train",
        "validation",
        "test",
    ]:
        for class_name in V1_CLASSES:
            folder = (
                OUTPUT_ROOT
                / split
                / class_name
            )

            counts[
                split
            ][class_name] = sum(
                1
                for path in folder.iterdir()
                if (
                    path.is_file()
                    and path.suffix.lower()
                    in SUPPORTED_EXTENSIONS
                )
            )

    return {
        split: dict(
            class_counts
        )
        for split, class_counts
        in counts.items()
    }


def main():
    print()
    print("=" * 70)
    print("BEAUTYVERSE DATASET PREPARATION")
    print("=" * 70)

    random.seed(SEED)

    dataset_root = (
        find_dataset_root()
    )

    print()
    print(
        f"Dataset root found:\n"
        f"{dataset_root}"
    )

    class_files, raw_split_counts = (
        scan_dataset(
            dataset_root
        )
    )

    total_raw_images = sum(
        len(files)
        for files
        in class_files.values()
    )

    print()
    print(
        f"Total raw images found: "
        f"{total_raw_images}"
    )

    print()
    print("Raw classes:")

    for class_name in sorted(
        class_files
    ):
        print(
            f"  {class_name:<15}"
            f"{len(class_files[class_name])}"
        )

    print()
    print(
        "Beautyverse V1 classes:"
    )

    for class_name in V1_CLASSES:
        print(
            f"  - {class_name}"
        )

    print()
    print(
        "Sensitive is intentionally "
        "excluded from V1."
    )

    missing_classes = [
        class_name
        for class_name
        in V1_CLASSES
        if class_name
        not in class_files
    ]

    if missing_classes:
        raise RuntimeError(
            "Missing required classes: "
            + ", ".join(
                missing_classes
            )
        )

    class_families = {}

    print()
    print(
        "Source-family audit:"
    )

    for class_name in V1_CLASSES:
        families = group_into_families(
            class_files[
                class_name
            ]
        )

        class_families[
            class_name
        ] = families

        variant_counts = [
            len(files)
            for files
            in families.values()
        ]

        print(
            f"  {class_name:<15}"
            f"{len(families):>4} families "
            f"| {len(class_files[class_name]):>4} files"
        )

        if variant_counts:
            print(
                f"      variants/family: "
                f"min={min(variant_counts)}, "
                f"max={max(variant_counts)}, "
                f"avg="
                f"{sum(variant_counts) / len(variant_counts):.2f}"
            )

    # Balance according to the class containing
    # the fewest independent source families.
    family_limit = min(
        len(
            class_families[
                class_name
            ]
        )
        for class_name
        in V1_CLASSES
    )

    print()
    print(
        "Balancing dataset to:"
    )

    print(
        f"  {family_limit} "
        f"source families per class"
    )

    selected_families = {}

    for class_index, class_name in enumerate(
        V1_CLASSES
    ):
        families = sorted(
            class_families[
                class_name
            ].keys()
        )

        class_random = random.Random(
            SEED + class_index
        )

        class_random.shuffle(
            families
        )

        families = families[
            :family_limit
        ]

        selected_families[
            class_name
        ] = split_families(
            families
        )

    print()
    print(
        "Source-level split:"
    )

    for class_name in V1_CLASSES:
        splits = (
            selected_families[
                class_name
            ]
        )

        print(
            f"  {class_name:<15}"
            f"Train={len(splits['train']):>2}  "
            f"Validation={len(splits['validation']):>2}  "
            f"Test={len(splits['test']):>2}"
        )

    print()
    print(
        "Auditing exact duplicates..."
    )

    duplicate_report = (
        audit_exact_duplicates(
            class_files
        )
    )

    print(
        "  Exact duplicate groups: "
        f"{duplicate_report['duplicate_group_count']}"
    )

    print(
        "  Files involved in exact duplicates: "
        f"{duplicate_report['duplicate_file_count']}"
    )

    print(
        "  Exact duplicate groups "
        "crossing class labels: "
        f"{duplicate_report['cross_class_duplicate_group_count']}"
    )

    reset_output_folder()

    records = copy_representatives(
        class_families,
        selected_families,
    )

    processed_counts = (
        count_processed_images()
    )

    report = {
        "seed": SEED,

        "dataset_root": str(
            dataset_root
        ),

        "total_raw_images": (
            total_raw_images
        ),

        "raw_class_counts": {
            class_name: len(files)
            for class_name, files
            in class_files.items()
        },

        "raw_split_counts": {
            split: dict(
                class_counts
            )
            for split, class_counts
            in raw_split_counts.items()
        },

        "v1_classes": (
            V1_CLASSES
        ),

        "excluded_classes": [
            "Sensitive"
        ],

        "source_family_counts": {
            class_name: len(
                class_families[
                    class_name
                ]
            )
            for class_name
            in V1_CLASSES
        },

        "balanced_family_count_per_class":
            family_limit,

        "processed_counts": (
            processed_counts
        ),

        "duplicate_audit":
            duplicate_report,

        "records": records,
    }

    REPORT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
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

    total_processed = sum(
        sum(
            class_counts.values()
        )
        for class_counts
        in processed_counts.values()
    )

    print()
    print("=" * 70)
    print("DATASET PREPARATION COMPLETE")
    print("=" * 70)

    print()
    print(
        f"Processed images: "
        f"{total_processed}"
    )

    print()
    print(
        f"Output folder:\n"
        f"{OUTPUT_ROOT}"
    )

    print()
    print(
        f"Dataset report:\n"
        f"{REPORT_PATH}"
    )

    print()
    print(
        "Processed split counts:"
    )

    for split, class_counts in (
        processed_counts.items()
    ):
        print()
        print(
            f"  {split.upper()}"
        )

        for class_name, count in (
            class_counts.items()
        ):
            print(
                f"    {class_name:<15}"
                f"{count}"
            )

    print()
    print(
        "IMPORTANT:"
    )

    print(
        "The processed dataset contains "
        "one representative image per "
        "independent source family."
    )

    print(
        "Training augmentation will be "
        "performed dynamically later."
    )

    print()


if __name__ == "__main__":
    main()
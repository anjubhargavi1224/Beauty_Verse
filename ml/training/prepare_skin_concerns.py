from __future__ import annotations

import csv
import hashlib
import json
import random
import re
import shutil
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

from PIL import Image


# =========================================================
# CONFIGURATION
# =========================================================

SEED = 42

TRAIN_RATIO = 0.70
VAL_RATIO = 0.15
TEST_RATIO = 0.15

PROJECT_ROOT = Path(__file__).resolve().parents[2]

RAW_ROOT = (
    PROJECT_ROOT
    / "ml"
    / "data"
    / "raw"
    / "skin_concerns"
)

ZIP_PATH = RAW_ROOT / "archive.zip"

EXTRACTED_ROOT = (
    RAW_ROOT
    / "extracted"
)

PROCESSED_ROOT = (
    PROJECT_ROOT
    / "ml"
    / "data"
    / "processed"
    / "skin_concerns_v1"
)

IMAGE_OUTPUT_ROOT = (
    PROCESSED_ROOT
    / "images"
)

MANIFEST_PATH = (
    PROCESSED_ROOT
    / "manifest.csv"
)

REPORT_PATH = (
    PROCESSED_ROOT
    / "dataset_report.json"
)


VALID_IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".bmp",
}


# =========================================================
# BEAUTYVERSE LABEL MAPPING
# =========================================================

SOURCE_TO_TARGET = {
    "inflammatory acne": "acne",

    "non inflammatory acne black heads":
        "acne",

    "non inflammatory acne white heads":
        "acne",

    "dark spots":
        "pigmentation",

    "pigmentation":
        "pigmentation",

    "redness":
        "redness",

    "pores":
        "pores",

    "wrinkles":
        "wrinkles",
}


TARGET_LABELS = [
    "acne",
    "pigmentation",
    "redness",
    "pores",
    "wrinkles",
]


# =========================================================
# BASIC HELPERS
# =========================================================

def normalize_name(
    value: str,
) -> str:

    return (
        value
        .strip()
        .lower()
        .replace("_", " ")
    )


def sha256_file(
    path: Path,
) -> str:

    digest = hashlib.sha256()

    with open(
        path,
        "rb",
    ) as file:

        while True:

            chunk = file.read(
                1024 * 1024
            )

            if not chunk:
                break

            digest.update(
                chunk
            )

    return digest.hexdigest()


def get_family_name(
    path: Path,
) -> str:

    """
    Recover the likely original image name
    from Roboflow-generated filenames.

    Example:

    face_png_jpg.rf.abc123.jpg

    becomes:

    face
    """

    stem = (
        path
        .stem
        .lower()
    )

    # Remove Roboflow hash
    stem = re.sub(
        r"\.rf\.[0-9a-f]+$",
        "",
        stem,
        flags=re.IGNORECASE,
    )

    # Remove embedded original extensions
    # such as "_png_jpg"
    stem = re.sub(
        r"(?:_(?:jpg|jpeg|png|webp|bmp))+$",
        "",
        stem,
        flags=re.IGNORECASE,
    )

    stem = re.sub(
        r"\s+",
        " ",
        stem,
    )

    return stem.strip()


def image_metadata(
    path: Path,
) -> dict:

    # First verify image integrity
    with Image.open(
        path
    ) as image:

        image.verify()

    # Re-open after verify
    with Image.open(
        path
    ) as image:

        width, height = (
            image.size
        )

        return {
            "width":
                int(width),

            "height":
                int(height),

            "area":
                int(
                    width
                    * height
                ),

            "format":
                image.format
                or "unknown",
        }


def safe_filename(
    value: str,
) -> str:

    value = re.sub(
        r"[^a-zA-Z0-9._-]+",
        "_",
        value,
    )

    return value[:180]


# =========================================================
# LOCATE DATASET
# =========================================================

def prepare_search_root() -> Path:

    """
    Supports BOTH:

    1. Dataset already extracted manually.

    2. archive.zip exists and needs extraction.
    """

    RAW_ROOT.mkdir(
        parents=True,
        exist_ok=True,
    )

    if ZIP_PATH.exists():

        if EXTRACTED_ROOT.exists():

            shutil.rmtree(
                EXTRACTED_ROOT
            )

        EXTRACTED_ROOT.mkdir(
            parents=True,
            exist_ok=True,
        )

        print(
            "\narchive.zip found."
        )

        print(
            "Extracting skin-concern dataset..."
        )

        with zipfile.ZipFile(
            ZIP_PATH,
            "r",
        ) as archive:

            archive.extractall(
                EXTRACTED_ROOT
            )

        print(
            "\nExtracted to:"
        )

        print(
            EXTRACTED_ROOT
        )

        return EXTRACTED_ROOT

    # --------------------------------------------
    # Your current setup comes here.
    # --------------------------------------------

    print(
        "\narchive.zip not found."
    )

    print(
        "Using already-extracted files from:"
    )

    print(
        RAW_ROOT
    )

    return RAW_ROOT


def find_dataset_root(
    search_root: Path,
) -> Path:

    """
    Automatically locate the folder containing:

    Redness/
    dark spots/
    inflammatory acne/
    pigmentation/
    pores/
    wrinkles/
    etc.

    Works for:

    skin_concerns/
        dataset/
            Redness/
            ...

    AND:

    skin_concerns/
        Redness/
        ...
    """

    candidates = []

    paths_to_check = [
        search_root
    ]

    paths_to_check.extend(
        path
        for path
        in search_root.rglob("*")
        if path.is_dir()
    )

    expected_folders = set(
        SOURCE_TO_TARGET.keys()
    )

    for path in paths_to_check:

        try:

            child_names = {
                normalize_name(
                    child.name
                )

                for child
                in path.iterdir()

                if child.is_dir()
            }

        except (
            PermissionError,
            OSError,
        ):

            continue

        recognized = (
            child_names
            & expected_folders
        )

        if len(
            recognized
        ) >= 5:

            candidates.append(
                (
                    len(
                        recognized
                    ),

                    -len(
                        path.parts
                    ),

                    path,
                )
            )

    if not candidates:

        raise RuntimeError(
            "\nCould not locate the "
            "skin-concern folders.\n\n"

            "Expected folders such as:\n"
            "Redness\n"
            "dark spots\n"
            "inflammatory acne\n"
            "non inflammatory acne black heads\n"
            "non inflammatory acne white heads\n"
            "pigmentation\n"
            "pores\n"
            "wrinkles\n"
        )

    candidates.sort(
        key=lambda item: (
            item[0],
            item[1],
        ),
        reverse=True,
    )

    return candidates[0][2]


# =========================================================
# UNION FIND
# =========================================================

class UnionFind:

    def __init__(
        self,
    ):

        self.parent = {}


    def add(
        self,
        item,
    ):

        if item not in self.parent:

            self.parent[
                item
            ] = item


    def find(
        self,
        item,
    ):

        if (
            self.parent[
                item
            ]
            != item
        ):

            self.parent[
                item
            ] = self.find(
                self.parent[
                    item
                ]
            )

        return self.parent[
            item
        ]


    def union(
        self,
        a,
        b,
    ):

        root_a = self.find(
            a
        )

        root_b = self.find(
            b
        )

        if root_a != root_b:

            self.parent[
                root_b
            ] = root_a


# =========================================================
# SCAN DATASET
# =========================================================

def scan_dataset(
    dataset_root: Path,
):

    print(
        "\nScanning dataset..."
    )

    records = []

    source_counts = Counter()

    invalid_files = []

    dimension_counts = Counter()

    index = 0

    for source_folder in sorted(
        dataset_root.iterdir(),
        key=lambda path:
            path.name.lower(),
    ):

        if not source_folder.is_dir():

            continue

        normalized_source = (
            normalize_name(
                source_folder.name
            )
        )

        if (
            normalized_source
            not in
            SOURCE_TO_TARGET
        ):

            print(
                "Skipping unrecognized folder:",
                source_folder.name,
            )

            continue

        target = (
            SOURCE_TO_TARGET[
                normalized_source
            ]
        )

        for path in (
            source_folder
            .rglob("*")
        ):

            if not path.is_file():

                continue

            if (
                path.suffix.lower()
                not in
                VALID_IMAGE_EXTENSIONS
            ):

                continue

            try:

                metadata = (
                    image_metadata(
                        path
                    )
                )

                file_hash = (
                    sha256_file(
                        path
                    )
                )

            except Exception as exc:

                invalid_files.append(
                    {
                        "path":
                            str(path),

                        "error":
                            str(exc),
                    }
                )

                continue

            family_name = (
                get_family_name(
                    path
                )
            )

            dimension_counts[
                (
                    f"{metadata['width']}"
                    f"x"
                    f"{metadata['height']}"
                )
            ] += 1

            records.append(
                {
                    "index":
                        index,

                    "path":
                        path,

                    "source_class":
                        normalized_source,

                    "target":
                        target,

                    "family_name":
                        family_name,

                    "sha256":
                        file_hash,

                    **metadata,
                }
            )

            source_counts[
                normalized_source
            ] += 1

            index += 1

    if not records:

        raise RuntimeError(
            "No valid images were found "
            "inside the recognized folders."
        )

    return (
        records,
        source_counts,
        invalid_files,
        dimension_counts,
    )


# =========================================================
# GROUP SOURCE FAMILIES
# =========================================================

def build_source_groups(
    records,
):

    """
    Merge together:

    1. Roboflow variants belonging to the same
       original source image.

    2. Exact duplicate images anywhere in
       the dataset.

    This prevents train/test leakage.
    """

    union_find = (
        UnionFind()
    )

    for record in records:

        union_find.add(
            record[
                "index"
            ]
        )

    by_family = defaultdict(
        list
    )

    by_hash = defaultdict(
        list
    )

    for record in records:

        family_key = (
            record[
                "target"
            ],

            record[
                "family_name"
            ],
        )

        by_family[
            family_key
        ].append(
            record[
                "index"
            ]
        )

        by_hash[
            record[
                "sha256"
            ]
        ].append(
            record[
                "index"
            ]
        )

    # --------------------------------------------
    # Merge Roboflow variants
    # --------------------------------------------

    for indexes in (
        by_family.values()
    ):

        first = indexes[0]

        for other in indexes[1:]:

            union_find.union(
                first,
                other,
            )

    # --------------------------------------------
    # Merge exact duplicates globally
    # --------------------------------------------

    for indexes in (
        by_hash.values()
    ):

        if len(
            indexes
        ) < 2:

            continue

        first = indexes[0]

        for other in indexes[1:]:

            union_find.union(
                first,
                other,
            )

    grouped = defaultdict(
        list
    )

    for record in records:

        root = (
            union_find.find(
                record[
                    "index"
                ]
            )
        )

        grouped[
            root
        ].append(
            record
        )

    groups = []

    sorted_members = sorted(
        grouped.values(),

        key=lambda members:
            min(
                member[
                    "index"
                ]

                for member
                in members
            ),
    )

    for (
        group_number,
        members,
    ) in enumerate(
        sorted_members
    ):

        targets = sorted(
            {
                member[
                    "target"
                ]

                for member
                in members
            }
        )

        source_classes = sorted(
            {
                member[
                    "source_class"
                ]

                for member
                in members
            }
        )

        # Choose highest-resolution copy
        # as representative.
        representative = max(
            members,

            key=lambda item: (
                item[
                    "area"
                ],

                item[
                    "width"
                ],

                item[
                    "height"
                ],
            ),
        )

        groups.append(
            {
                "group_id":
                    (
                        f"group_"
                        f"{group_number:05d}"
                    ),

                "targets":
                    targets,

                "source_classes":
                    source_classes,

                "members":
                    members,

                "representative":
                    representative,
            }
        )

    return groups


# =========================================================
# TRAIN / VALIDATION / TEST SPLIT
# =========================================================

def split_groups(
    groups,
):

    """
    Split SOURCE FAMILIES, not individual
    augmented images.

    This prevents augmented versions of the
    same original image appearing in different
    splits.
    """

    rng = random.Random(
        SEED
    )

    strata = defaultdict(
        list
    )

    for group in groups:

        signature = tuple(
            group[
                "targets"
            ]
        )

        strata[
            signature
        ].append(
            group
        )

    split_map = {
        "train":
            [],

        "validation":
            [],

        "test":
            [],
    }

    for (
        signature,
        items,
    ) in sorted(
        strata.items(),
        key=lambda item:
            str(
                item[0]
            ),
    ):

        items = list(
            items
        )

        rng.shuffle(
            items
        )

        total = len(
            items
        )

        if total == 1:

            train_count = 1
            val_count = 0

        elif total == 2:

            train_count = 1
            val_count = 0

        else:

            train_count = int(
                total
                * TRAIN_RATIO
            )

            val_count = int(
                total
                * VAL_RATIO
            )

            train_count = max(
                train_count,
                1,
            )

            val_count = max(
                val_count,
                1,
            )

            # Keep at least one test item
            if (
                train_count
                + val_count
                >= total
            ):

                train_count = (
                    total
                    - 2
                )

                val_count = 1

        train_items = (
            items[
                :train_count
            ]
        )

        validation_items = (
            items[
                train_count:
                train_count
                + val_count
            ]
        )

        test_items = (
            items[
                train_count
                + val_count:
            ]
        )

        split_map[
            "train"
        ].extend(
            train_items
        )

        split_map[
            "validation"
        ].extend(
            validation_items
        )

        split_map[
            "test"
        ].extend(
            test_items
        )

        print(
            "\nTarget signature:",
            " + ".join(
                signature
            ),
        )

        print(
            f"  total groups: "
            f"{total}"
        )

        print(
            f"  train: "
            f"{len(train_items)}"
        )

        print(
            f"  validation: "
            f"{len(validation_items)}"
        )

        print(
            f"  test: "
            f"{len(test_items)}"
        )

    return split_map


# =========================================================
# EXPORT DATASET + MANIFEST
# =========================================================

def create_output(
    split_map,
):

    if (
        PROCESSED_ROOT
        .exists()
    ):

        shutil.rmtree(
            PROCESSED_ROOT
        )

    PROCESSED_ROOT.mkdir(
        parents=True,
        exist_ok=True,
    )

    IMAGE_OUTPUT_ROOT.mkdir(
        parents=True,
        exist_ok=True,
    )

    manifest_rows = []

    split_target_counts = {
        split:
            Counter()

        for split
        in split_map
    }

    for (
        split,
        groups,
    ) in split_map.items():

        for group in groups:

            representative = (
                group[
                    "representative"
                ]
            )

            positive_targets = set(
                group[
                    "targets"
                ]
            )

            if len(
                positive_targets
            ) == 1:

                folder_name = next(
                    iter(
                        positive_targets
                    )
                )

            else:

                folder_name = (
                    "multi_concern"
                )

            output_directory = (
                IMAGE_OUTPUT_ROOT
                / split
                / folder_name
            )

            output_directory.mkdir(
                parents=True,
                exist_ok=True,
            )

            extension = (
                representative[
                    "path"
                ]
                .suffix
                .lower()
            )

            destination = (
                output_directory
                /
                (
                    safe_filename(
                        group[
                            "group_id"
                        ]
                    )
                    + extension
                )
            )

            shutil.copy2(
                representative[
                    "path"
                ],
                destination,
            )

            relative_path = (
                destination
                .relative_to(
                    PROJECT_ROOT
                )
                .as_posix()
            )

            row = {
                "image_path":
                    relative_path,

                "split":
                    split,

                "group_id":
                    group[
                        "group_id"
                    ],

                "source_classes":
                    "|".join(
                        group[
                            "source_classes"
                        ]
                    ),

                "original_family":
                    representative[
                        "family_name"
                    ],

                "original_file":
                    representative[
                        "path"
                    ].name,

                "width":
                    representative[
                        "width"
                    ],

                "height":
                    representative[
                        "height"
                    ],

                "source_family_size":
                    len(
                        group[
                            "members"
                        ]
                    ),
            }

            # --------------------------------------------
            # LABEL POLICY
            #
            # label = 1 and mask = 1
            # means confirmed positive.
            #
            # blank label and mask = 0
            # means UNKNOWN.
            #
            # UNKNOWN IS NOT NEGATIVE.
            # --------------------------------------------

            for target in (
                TARGET_LABELS
            ):

                if (
                    target
                    in
                    positive_targets
                ):

                    row[
                        f"label_{target}"
                    ] = 1

                    row[
                        f"mask_{target}"
                    ] = 1

                    split_target_counts[
                        split
                    ][target] += 1

                else:

                    row[
                        f"label_{target}"
                    ] = ""

                    row[
                        f"mask_{target}"
                    ] = 0

            manifest_rows.append(
                row
            )

    fieldnames = [
        "image_path",
        "split",
        "group_id",
        "source_classes",
        "original_family",
        "original_file",
        "width",
        "height",
        "source_family_size",

        "label_acne",
        "mask_acne",

        "label_pigmentation",
        "mask_pigmentation",

        "label_redness",
        "mask_redness",

        "label_pores",
        "mask_pores",

        "label_wrinkles",
        "mask_wrinkles",
    ]

    with open(
        MANIFEST_PATH,
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
            manifest_rows
        )

    return (
        manifest_rows,
        split_target_counts,
    )


# =========================================================
# BUILD DATASET REPORT
# =========================================================

def build_report(
    records,
    groups,
    source_counts,
    invalid_files,
    dimension_counts,
    manifest_rows,
    split_target_counts,
):

    by_hash = defaultdict(
        list
    )

    for record in records:

        by_hash[
            record[
                "sha256"
            ]
        ].append(
            record
        )

    duplicate_groups = [
        items

        for items
        in by_hash.values()

        if len(
            items
        ) > 1
    ]

    files_in_duplicate_groups = sum(
        len(
            items
        )

        for items
        in duplicate_groups
    )

    cross_source_duplicates = []

    for items in (
        duplicate_groups
    ):

        source_classes = {
            item[
                "source_class"
            ]

            for item
            in items
        }

        if len(
            source_classes
        ) > 1:

            cross_source_duplicates.append(
                {
                    "source_classes":
                        sorted(
                            source_classes
                        ),

                    "files":
                        [
                            str(
                                item[
                                    "path"
                                ]
                            )

                            for item
                            in items
                        ],
                }
            )

    merged_image_counts = Counter()

    for record in records:

        merged_image_counts[
            record[
                "target"
            ]
        ] += 1

    merged_family_counts = Counter()

    for group in groups:

        for target in (
            group[
                "targets"
            ]
        ):

            merged_family_counts[
                target
            ] += 1

    split_counts = Counter(
        row[
            "split"
        ]

        for row
        in manifest_rows
    )

    multi_concern_groups = sum(
        1

        for group
        in groups

        if len(
            group[
                "targets"
            ]
        ) > 1
    )

    report = {
        "seed":
            SEED,

        "raw_valid_images":
            len(
                records
            ),

        "invalid_images":
            len(
                invalid_files
            ),

        "invalid_image_examples":
            invalid_files[
                :20
            ],

        "raw_source_class_counts":
            dict(
                source_counts
            ),

        "merged_target_image_counts":
            dict(
                merged_image_counts
            ),

        "source_family_groups_after_deduplication":
            len(
                groups
            ),

        "merged_target_family_counts":
            dict(
                merged_family_counts
            ),

        "multi_concern_groups_from_cross_class_duplicates":
            multi_concern_groups,

        "representative_images_exported":
            len(
                manifest_rows
            ),

        "split_counts":
            dict(
                split_counts
            ),

        "split_target_counts":
            {
                split:
                    dict(
                        counts
                    )

                for (
                    split,
                    counts,
                )
                in
                split_target_counts.items()
            },

        "exact_duplicate_groups":
            len(
                duplicate_groups
            ),

        "files_in_exact_duplicate_groups":
            files_in_duplicate_groups,

        "cross_source_exact_duplicate_groups":
            len(
                cross_source_duplicates
            ),

        "cross_source_duplicate_examples":
            cross_source_duplicates[
                :20
            ],

        "top_image_dimensions":
            dict(
                dimension_counts
                .most_common(
                    25
                )
            ),

        "target_labels":
            TARGET_LABELS,

        "source_to_target_mapping":
            SOURCE_TO_TARGET,

        "label_policy":
            {
                "confirmed_positive":
                    "label=1, mask=1",

                "unknown":
                    "blank label, mask=0",

                "confirmed_negative":
                    (
                        "No automatic negative "
                        "labels are created."
                    ),
            },

        "note":
            (
                "This prepared dataset is not yet "
                "sufficient for ordinary supervised "
                "multi-label BCE training because "
                "it contains confirmed positives "
                "and unknown labels but no validated "
                "negative labels."
            ),
    }

    with open(
        REPORT_PATH,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            report,
            file,
            indent=2,
        )

    return report


# =========================================================
# MAIN
# =========================================================

def main():

    print(
        "\n========================================"
    )

    print(
        "BEAUTYVERSE SKIN CONCERN DATA PREP"
    )

    print(
        "========================================"
    )

    print(
        "\nIMPORTANT:"
    )

    print(
        "This stage creates confirmed-positive "
        "labels only."
    )

    print(
        "Unobserved concerns remain UNKNOWN, "
        "not negative."
    )

    # --------------------------------------------
    # Locate the already-extracted dataset
    # --------------------------------------------

    search_root = (
        prepare_search_root()
    )

    dataset_root = (
        find_dataset_root(
            search_root
        )
    )

    print(
        "\nDetected dataset root:"
    )

    print(
        dataset_root
    )

    # --------------------------------------------
    # Scan
    # --------------------------------------------

    (
        records,
        source_counts,
        invalid_files,
        dimension_counts,
    ) = scan_dataset(
        dataset_root
    )

    print(
        "\nRaw valid images:",
        len(
            records
        ),
    )

    print(
        "\nOriginal folder counts:"
    )

    for (
        class_name,
        count,
    ) in sorted(
        source_counts.items()
    ):

        print(
            f"  "
            f"{class_name:<40} "
            f"{count}"
        )

    # --------------------------------------------
    # Group source families + duplicates
    # --------------------------------------------

    groups = (
        build_source_groups(
            records
        )
    )

    print(
        "\nSource-family groups after "
        "deduplication:",
        len(
            groups
        ),
    )

    merged_family_counts = Counter()

    for group in groups:

        for target in (
            group[
                "targets"
            ]
        ):

            merged_family_counts[
                target
            ] += 1

    print(
        "\nIndependent family groups "
        "by Beautyverse concern:"
    )

    for target in (
        TARGET_LABELS
    ):

        print(
            f"  "
            f"{target:<20} "
            f"{merged_family_counts[target]}"
        )

    # --------------------------------------------
    # Split
    # --------------------------------------------

    split_map = (
        split_groups(
            groups
        )
    )

    # --------------------------------------------
    # Export
    # --------------------------------------------

    (
        manifest_rows,
        split_target_counts,
    ) = create_output(
        split_map
    )

    # --------------------------------------------
    # Report
    # --------------------------------------------

    report = build_report(
        records=records,

        groups=groups,

        source_counts=source_counts,

        invalid_files=invalid_files,

        dimension_counts=dimension_counts,

        manifest_rows=manifest_rows,

        split_target_counts=
            split_target_counts,
    )

    print(
        "\n========================================"
    )

    print(
        "DATA PREPARATION COMPLETE"
    )

    print(
        "========================================"
    )

    print(
        "\nRepresentative images exported:",
        len(
            manifest_rows
        ),
    )

    print(
        "\nSplit counts:"
    )

    for (
        split,
        count,
    ) in report[
        "split_counts"
    ].items():

        print(
            f"  "
            f"{split:<12} "
            f"{count}"
        )

    print(
        "\nExact duplicate groups:",
        report[
            "exact_duplicate_groups"
        ],
    )

    print(
        "Files involved in exact duplicate groups:",
        report[
            "files_in_exact_duplicate_groups"
        ],
    )

    print(
        "\nCross-source exact duplicate groups:",
        report[
            "cross_source_exact_duplicate_groups"
        ],
    )

    print(
        "\nProcessed dataset:"
    )

    print(
        PROCESSED_ROOT
    )

    print(
        "\nManifest:"
    )

    print(
        MANIFEST_PATH
    )

    print(
        "\nDataset report:"
    )

    print(
        REPORT_PATH
    )

    print(
        "\nDO NOT TRAIN YET."
    )

    print(
        "Review the report and split "
        "counts first."
    )


if __name__ == "__main__":
    main()
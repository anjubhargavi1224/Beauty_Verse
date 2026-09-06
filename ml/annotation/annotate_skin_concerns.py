from __future__ import annotations

import random
from pathlib import Path

import pandas as pd
import streamlit as st


# =========================================================
# CONFIGURATION
# =========================================================

SEED = 42

TARGET_PER_CONCERN = 100

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

PROJECT_ROOT = Path(__file__).resolve().parents[2]

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

QUEUE_PATH = (
    PROCESSED_ROOT
    / "annotation_queue.csv"
)

ANNOTATION_PATH = (
    PROCESSED_ROOT
    / "gold_annotations.csv"
)


# =========================================================
# PAGE
# =========================================================

st.set_page_config(
    page_title="Beautyverse Skin Concern Annotation",
    page_icon="✨",
    layout="wide",
)


# =========================================================
# HELPERS
# =========================================================

def get_known_positive_labels(row):
    known = []

    for label in TARGET_LABELS:
        mask_value = row.get(
            f"mask_{label}",
            0,
        )

        label_value = row.get(
            f"label_{label}",
            "",
        )

        try:
            mask_value = int(
                float(mask_value)
            )
        except (ValueError, TypeError):
            mask_value = 0

        try:
            label_value = int(
                float(label_value)
            )
        except (ValueError, TypeError):
            label_value = 0

        if (
            mask_value == 1
            and label_value == 1
        ):
            known.append(
                label
            )

    return known


def create_annotation_queue():
    if not MANIFEST_PATH.exists():
        raise FileNotFoundError(
            f"Manifest not found:\n{MANIFEST_PATH}"
        )

    manifest = pd.read_csv(
        MANIFEST_PATH
    )

    rng = random.Random(
        SEED
    )

    selected_indices = set()

    selected_rows = []

    # --------------------------------------------
    # Select approximately 100 examples
    # for every concern.
    # --------------------------------------------

    for label in TARGET_LABELS:
        mask_column = (
            f"mask_{label}"
        )

        label_column = (
            f"label_{label}"
        )

        candidates = manifest[
            (
                manifest[
                    mask_column
                ] == 1
            )
            &
            (
                manifest[
                    label_column
                ] == 1
            )
        ]

        candidate_indices = list(
            candidates.index
        )

        rng.shuffle(
            candidate_indices
        )

        count = 0

        for index in candidate_indices:
            if (
                index
                in selected_indices
            ):
                continue

            selected_indices.add(
                index
            )

            selected_rows.append(
                manifest.loc[
                    index
                ]
            )

            count += 1

            if (
                count
                >= TARGET_PER_CONCERN
            ):
                break

    queue = pd.DataFrame(
        selected_rows
    )

    # --------------------------------------------
    # Shuffle the complete queue so you
    # don't annotate 100 acne photos,
    # followed by 100 pigmentation photos.
    # --------------------------------------------

    queue = queue.sample(
        frac=1,
        random_state=SEED,
    ).reset_index(
        drop=True
    )

    queue.insert(
        0,
        "annotation_id",
        range(
            1,
            len(queue) + 1,
        ),
    )

    queue.to_csv(
        QUEUE_PATH,
        index=False,
    )

    return queue


def load_queue():
    if QUEUE_PATH.exists():
        return pd.read_csv(
            QUEUE_PATH
        )

    return create_annotation_queue()


def create_annotation_file(
    queue,
):
    rows = []

    for _, row in queue.iterrows():
        annotation_row = {
            "annotation_id":
                int(
                    row[
                        "annotation_id"
                    ]
                ),

            "image_path":
                row[
                    "image_path"
                ],

            "split":
                row[
                    "split"
                ],

            "group_id":
                row[
                    "group_id"
                ],

            "source_classes":
                row[
                    "source_classes"
                ],

            "completed":
                False,
        }

        known_labels = (
            get_known_positive_labels(
                row
            )
        )

        for label in TARGET_LABELS:

            # Known source label starts
            # as Yes.
            if label in known_labels:
                annotation_row[
                    f"annotation_{label}"
                ] = "Yes"

            else:
                annotation_row[
                    f"annotation_{label}"
                ] = "Unsure"

        rows.append(
            annotation_row
        )

    annotations = pd.DataFrame(
        rows
    )

    annotations.to_csv(
        ANNOTATION_PATH,
        index=False,
    )

    return annotations


def load_annotations(
    queue,
):
    if ANNOTATION_PATH.exists():

        annotations = pd.read_csv(
            ANNOTATION_PATH
        )

        annotations[
            "completed"
        ] = (
            annotations[
                "completed"
            ]
            .astype(str)
            .str.lower()
            .map(
                {
                    "true": True,
                    "false": False,
                }
            )
            .fillna(False)
        )

        return annotations

    return create_annotation_file(
        queue
    )


def save_annotations(
    annotations,
):
    annotations.to_csv(
        ANNOTATION_PATH,
        index=False,
    )


def resolve_image_path(
    image_path,
):
    path = Path(
        image_path
    )

    if path.is_absolute():
        return path

    return (
        PROJECT_ROOT
        / path
    )


def first_incomplete_index(
    annotations,
):
    incomplete = annotations[
        annotations[
            "completed"
        ] == False
    ]

    if incomplete.empty:
        return 0

    first_id = int(
        incomplete.iloc[0][
            "annotation_id"
        ]
    )

    return first_id - 1


# =========================================================
# LOAD DATA
# =========================================================

try:
    queue = load_queue()

    annotations = load_annotations(
        queue
    )

except Exception as exc:
    st.error(
        f"Could not load annotation data:\n\n{exc}"
    )

    st.stop()


# =========================================================
# SESSION STATE
# =========================================================

if "annotation_index" not in st.session_state:

    st.session_state[
        "annotation_index"
    ] = first_incomplete_index(
        annotations
    )


current_index = (
    st.session_state[
        "annotation_index"
    ]
)

current_index = max(
    0,
    min(
        current_index,
        len(
            annotations
        ) - 1,
    ),
)

st.session_state[
    "annotation_index"
] = current_index


# =========================================================
# HEADER
# =========================================================

st.title(
    "✨ Beautyverse Skin Concern Annotation"
)

st.caption(
    "Gold-label verification for visible cosmetic "
    "skin concerns."
)


completed_count = int(
    annotations[
        "completed"
    ].sum()
)

total_count = len(
    annotations
)

progress = (
    completed_count
    / total_count
    if total_count
    else 0
)


st.progress(
    progress
)

st.write(
    f"**Progress:** "
    f"{completed_count} / {total_count}"
)


if completed_count == total_count:

    st.success(
        "🎉 All annotation images are complete!"
    )

    st.write(
        "Saved to:"
    )

    st.code(
        str(
            ANNOTATION_PATH
        )
    )


st.divider()


# =========================================================
# CURRENT IMAGE
# =========================================================

current = annotations.iloc[
    current_index
]

queue_row = queue.iloc[
    current_index
]

image_path = resolve_image_path(
    current[
        "image_path"
    ]
)


left_column, right_column = (
    st.columns(
        [
            1.15,
            0.85,
        ]
    )
)


# =========================================================
# IMAGE COLUMN
# =========================================================

with left_column:

    st.subheader(
        f"Image "
        f"{current_index + 1} "
        f"of {total_count}"
    )

    if image_path.exists():

        st.image(
            str(
                image_path
            ),
            use_container_width=True,
        )

    else:

        st.error(
            "Image file not found:"
        )

        st.code(
            str(
                image_path
            )
        )


# =========================================================
# ANNOTATION COLUMN
# =========================================================

with right_column:

    st.subheader(
        "Visible concerns"
    )

    st.write(
        "**Dataset source:**"
    )

    st.code(
        str(
            current[
                "source_classes"
            ]
        )
    )

    known_positive = (
        get_known_positive_labels(
            queue_row
        )
    )

    if known_positive:

        readable_known = [
            DISPLAY_NAMES[
                label
            ]

            for label
            in known_positive
        ]

        st.info(
            "Original confirmed label: "
            + ", ".join(
                readable_known
            )
        )


    st.markdown(
        """
### Annotation rules

Choose **Yes** only when the concern is
clearly visible.

Choose **No** when you can reasonably see
that the concern is not present.

Choose **Unsure** when the image quality,
angle, crop, lighting or appearance makes
you uncertain.

When in doubt, use **Unsure**.
"""
    )


    selections = {}


    for label in TARGET_LABELS:

        current_value = str(
            current[
                f"annotation_{label}"
            ]
        )

        if current_value not in [
            "Yes",
            "No",
            "Unsure",
        ]:
            current_value = "Unsure"

        default_index = [
            "No",
            "Yes",
            "Unsure",
        ].index(
            current_value
        )

        selections[
            label
        ] = st.radio(
            DISPLAY_NAMES[
                label
            ],

            options=[
                "No",
                "Yes",
                "Unsure",
            ],

            index=default_index,

            horizontal=True,

            key=(
                f"{current['annotation_id']}"
                f"_{label}"
            ),
        )


# =========================================================
# SAVE
# =========================================================

def save_current(
    completed=True,
):

    row_index = (
        annotations[
            annotations[
                "annotation_id"
            ]
            ==
            current[
                "annotation_id"
            ]
        ]
        .index[0]
    )

    for label in TARGET_LABELS:

        annotations.loc[
            row_index,
            f"annotation_{label}",
        ] = selections[
            label
        ]

    annotations.loc[
        row_index,
        "completed",
    ] = completed

    save_annotations(
        annotations
    )


st.divider()


previous_column, save_column, next_column = (
    st.columns(
        3
    )
)


with previous_column:

    if st.button(
        "← Previous",
        use_container_width=True,
        disabled=(
            current_index == 0
        ),
    ):

        save_current(
            completed=bool(
                current[
                    "completed"
                ]
            )
        )

        st.session_state[
            "annotation_index"
        ] = (
            current_index - 1
        )

        st.rerun()


with save_column:

    if st.button(
        "💾 Save",
        use_container_width=True,
    ):

        save_current(
            completed=True
        )

        st.success(
            "Saved."
        )

        st.rerun()


with next_column:

    if st.button(
        "Save & Next →",
        type="primary",
        use_container_width=True,
    ):

        save_current(
            completed=True
        )

        if (
            current_index
            < total_count - 1
        ):

            st.session_state[
                "annotation_index"
            ] = (
                current_index + 1
            )

        st.rerun()


# =========================================================
# JUMP / NAVIGATION
# =========================================================

st.divider()

navigation_left, navigation_right = (
    st.columns(
        2
    )
)


with navigation_left:

    jump_to = st.number_input(
        "Jump to image",
        min_value=1,
        max_value=total_count,
        value=current_index + 1,
        step=1,
    )


with navigation_right:

    st.write("")
    st.write("")

    if st.button(
        "Go to image",
        use_container_width=True,
    ):

        save_current(
            completed=bool(
                current[
                    "completed"
                ]
            )
        )

        st.session_state[
            "annotation_index"
        ] = int(
            jump_to
        ) - 1

        st.rerun()


# =========================================================
# SUMMARY
# =========================================================

with st.expander(
    "Annotation summary"
):

    summary_rows = []

    for label in TARGET_LABELS:

        column = (
            f"annotation_{label}"
        )

        completed_annotations = annotations[
            annotations[
                "completed"
            ] == True
        ]

        counts = (
            completed_annotations[
                column
            ]
            .value_counts()
            .to_dict()
        )

        summary_rows.append(
            {
                "Concern":
                    DISPLAY_NAMES[
                        label
                    ],

                "Yes":
                    counts.get(
                        "Yes",
                        0
                    ),

                "No":
                    counts.get(
                        "No",
                        0
                    ),

                "Unsure":
                    counts.get(
                        "Unsure",
                        0
                    ),
            }
        )

    st.dataframe(
        pd.DataFrame(
            summary_rows
        ),

        use_container_width=True,

        hide_index=True,
    )


st.caption(
    "Beautyverse concern annotation is for "
    "cosmetic computer-vision research and "
    "does not constitute medical diagnosis."
)
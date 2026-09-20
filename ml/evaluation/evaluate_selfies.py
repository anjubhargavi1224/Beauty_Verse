"""Evaluate labeled selfies using production preprocessing, without external APIs.

Run from the repository root:
    python -m ml.evaluation.evaluate_selfies --manifest selfies.csv --output evaluation.json

CSV columns: image_path,skin_type,acne,pigmentation,redness,pores,wrinkles
Optional strata: lighting,makeup,skin_tone. Paths are relative to the CSV.
Concern labels: 1=present, 0=absent, blank=unknown (never counted as absent).
Use consented, independently labeled images not used for training/tuning.
"""
import argparse
import csv
import json
from pathlib import Path

LABELS = ("acne", "pigmentation", "redness", "pores", "wrinkles")
SKIN_TYPES = {"Combination", "Dry", "Normal", "Oily"}


def ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def summarize(records):
    accepted = [r for r in records if r["status"] == "analyzed"]
    labeled = [r for r in accepted if r["truth"].get("skin_type")]
    decided = [r for r in labeled if not r["skin_type"]["uncertainty_flag"]]
    concerns = {}
    for label in LABELS:
        known = [r for r in accepted if r["truth"].get(label) in ("0", "1")]
        tp = fp = tn = fn = uncertain = positives = negatives = 0
        for record in known:
            positive = record["truth"][label] == "1"
            positives += positive
            negatives += not positive
            status = record["concerns"][label]["status"]
            if status == "uncertain":
                uncertain += 1
            elif status == "detected":
                tp += positive
                fp += not positive
            else:
                fn += positive
                tn += not positive
        concerns[label] = {
            "known": len(known), "positives": positives, "negatives": negatives,
            "true_positive": tp, "false_positive": fp,
            "true_negative": tn, "false_negative": fn, "uncertain": uncertain,
            "precision": ratio(tp, tp + fp),
            # Includes abstained positives in the denominator: uncertainty must
            # not artificially improve the reported recall or coverage.
            "detection_recall": ratio(tp, positives),
            "false_positive_rate": ratio(fp, negatives),
            "decision_coverage": ratio(len(known) - uncertain, len(known)),
        }
    return {
        "images": len(records), "analyzed": len(accepted),
        "analysis_coverage": ratio(len(accepted), len(records)),
        "rejected_or_failed": len(records) - len(accepted),
        "skin_type": {
            "labeled_analyzed_images": len(labeled),
            "top1_accuracy": ratio(sum(r["skin_type"]["predicted_skin_type"] == r["truth"]["skin_type"] for r in labeled), len(labeled)),
            "decision_coverage": ratio(len(decided), len(labeled)),
            "accuracy_when_decided": ratio(sum(r["skin_type"]["predicted_skin_type"] == r["truth"]["skin_type"] for r in decided), len(decided)),
            "prediction_counts": {label: sum(r["skin_type"]["predicted_skin_type"] == label for r in labeled) for label in sorted(SKIN_TYPES)},
        },
        "concerns": concerns,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with args.manifest.open(newline="", encoding="utf-8-sig") as source:
        reader = csv.DictReader(source)
        if not reader.fieldnames or "image_path" not in reader.fieldnames:
            parser.error("CSV requires an image_path column.")
        rows = list(reader)
    if not rows:
        parser.error("CSV contains no images.")
    for i, row in enumerate(rows, 2):
        if not row.get("image_path"):
            parser.error(f"Row {i}: image_path is empty.")
        if row.get("skin_type", "") not in SKIN_TYPES | {""}:
            parser.error(f"Row {i}: invalid skin_type.")
        for label in LABELS:
            if row.get(label, "") not in {"", "0", "1"}:
                parser.error(f"Row {i}: {label} must be 0, 1, or blank.")

    # Lazy imports let --help and metric tests run without model dependencies.
    from backend.services.face_detection import face_detection_service as faces
    from backend.services.skin_regions import skin_region_service as regions
    from backend.services.skin_type_classifier import skin_type_classifier_service as types
    from backend.services.skin_concern_classifier import skin_concern_classifier_service as concerns

    records = []
    for row in rows:
        record = {"image_path": row["image_path"], "truth": row}
        try:
            image_path = args.manifest.parent / row["image_path"]
            image, result = faces.detect(image_path.read_bytes())
            if not result.face_landmarks:
                record["status"] = "no_face_detected"
            else:
                landmarks = result.face_landmarks[0]
                quality = regions.extract(image, landmarks)["capture_quality"]
                record["capture_quality"] = quality
                if not quality["usable"]:
                    record["status"] = "image_quality"
                else:
                    record["skin_type"] = types.predict(image, landmarks)
                    record["concerns"] = {c["id"]: c for c in concerns.predict(image, landmarks)["concerns"]}
                    record["status"] = "analyzed"
        except Exception as error:
            record.update(status="error", error=str(error))
        records.append(record)
        print(f"[{len(records)}/{len(rows)}] {record['status']}")

    strata = {}
    for field in ("lighting", "makeup", "skin_tone"):
        values = sorted({r["truth"].get(field, "") for r in records} - {""})
        strata[field] = {value: summarize([r for r in records if r["truth"].get(field) == value]) for value in values}
    report = {"summary": summarize(records), "strata": strata, "records": records,
              "note": "Fixed current model thresholds. This report does not calibrate probabilities or establish clinical accuracy. Inspect coverage and sample counts alongside accuracy."}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Saved {args.output}")


if __name__ == "__main__":
    main()

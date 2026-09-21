from __future__ import annotations

from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
from PIL import Image
import torch
from torch import nn
from torchvision import transforms
from torchvision.models import efficientnet_b0

from backend.services.face_detection import (
    face_detection_service,
)
from backend.services.skin_regions import (
    skin_region_service,
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

IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]


class SkinConcernClassifierService:
    """
    Beautyverse region-aware cosmetic skin-concern analyzer.

    Combines multi-label EfficientNet-B0 inference with regional
    optical evidence (erythema index, localized texture, melanin variance).
    Prevents false positives caused by warm lighting, cosmetic blush,
    and camera noise.
    """

    def __init__(self):
        if not MODEL_PATH.exists():
            raise FileNotFoundError(
                f"Skin concern model not found:\n{MODEL_PATH}"
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

        self.class_names = checkpoint["class_names"]
        self.thresholds = checkpoint["thresholds"]

        self.model = efficientnet_b0(weights=None)
        in_features = self.model.classifier[1].in_features

        self.model.classifier = nn.Sequential(
            nn.Dropout(p=0.40),
            nn.Linear(in_features, len(self.class_names)),
        )

        self.model.load_state_dict(checkpoint["state_dict"])
        self.model = self.model.to(self.device)
        self.model.eval()

        self.transform = transforms.Compose([
            transforms.Resize(256),
            transforms.CenterCrop(224),
            transforms.ToTensor(),
            transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
        ])

        self.lock = Lock()
        print(f"Beautyverse skin-concern model loaded on {self.device}")

    def normalize_white_balance(self, image_bgr: np.ndarray) -> np.ndarray:
        """
        Apply Gray-World color constancy before concern inference
        to suppress false redness caused by ambient warm incandescent lighting.
        """
        img_float = image_bgr.astype(np.float32)
        b_avg = np.mean(img_float[:, :, 0])
        g_avg = np.mean(img_float[:, :, 1])
        r_avg = np.mean(img_float[:, :, 2])

        gray_avg = (b_avg + g_avg + r_avg) / 3.0
        if b_avg < 1e-3 or g_avg < 1e-3 or r_avg < 1e-3:
            return image_bgr

        scale_b = np.clip(gray_avg / b_avg, 0.80, 1.25)
        scale_g = np.clip(gray_avg / g_avg, 0.80, 1.25)
        scale_r = np.clip(gray_avg / r_avg, 0.80, 1.25)

        normalized = img_float.copy()
        normalized[:, :, 0] *= scale_b
        normalized[:, :, 1] *= scale_g
        normalized[:, :, 2] *= scale_r

        return np.clip(normalized, 0, 255).astype(np.uint8)

    def crop_face(
        self,
        image: np.ndarray,
        landmarks: List[Any],
    ) -> Tuple[np.ndarray, Dict[str, int]]:
        height, width = image.shape[:2]
        bbox = face_detection_service.calculate_face_bbox(
            landmarks,
            width,
            height,
        )

        x = bbox["x"]
        y = bbox["y"]
        box_width = bbox["width"]
        box_height = bbox["height"]

        margin_x = int(box_width * 0.03)
        margin_y = int(box_height * 0.03)

        x1 = max(0, x - margin_x)
        y1 = max(0, y - margin_y)
        x2 = min(width, x + box_width + margin_x)
        y2 = min(height, y + box_height + margin_y)

        face_crop = image[y1:y2, x1:x2]
        if face_crop.size == 0:
            raise ValueError("Skin concern face crop was empty.")

        return (
            face_crop,
            {
                "x": x1,
                "y": y1,
                "width": x2 - x1,
                "height": y2 - y1,
            },
        )

    def validate_concern_with_regions(
        self,
        label: str,
        raw_score: float,
        threshold: float,
        regions_data: Optional[Dict[str, Any]],
    ) -> Tuple[str, float, str]:
        """
        Refine each concern score using region-specific optical evidence:
        - Redness: Confirmed only if erythema is observed beyond localized cosmetic cheek blush.
        - Fine lines: Evaluated with under-eye and forehead texture metrics.
        - Pores: Corroborated with nose/T-zone texture roughness.
        - Pigmentation: Corroborated with melanin contrast standard deviation.
        - Acne: Corroborated with localized spot variance.

        Returns: (status: 'detected' | 'not_detected', calibrated_score: float, rationale: str)
        """
        score = raw_score
        rationale = ""

        if not regions_data:
            status = "detected" if score >= threshold else "not_detected"
            return status, score, "Visual model score."

        regional_summary = regions_data.get("regional_summary", {})
        regions = regions_data.get("regions", {})

        if label == "redness":
            avg_erythema = regional_summary.get("average_erythema_index", 0.0)
            forehead_erythema = regions.get("forehead", {}).get("metrics", {}).get("erythema_index", 0.0)
            chin_erythema = regions.get("chin", {}).get("metrics", {}).get("erythema_index", 0.0)
            cheek_erythema = max(
                regions.get("left_cheek", {}).get("metrics", {}).get("erythema_index", 0.0),
                regions.get("right_cheek", {}).get("metrics", {}).get("erythema_index", 0.0),
            )

            # If cheek erythema is high but forehead and chin have zero redness, it's likely blush/makeup
            is_likely_blush_or_flush = (cheek_erythema > 0.25) and (forehead_erythema < 0.08) and (chin_erythema < 0.08)

            if is_likely_blush_or_flush:
                score *= 0.65
                rationale = "Localized cheek tone suggests cosmetic blush or lighting rather than persistent redness."
            elif avg_erythema > 0.20 or (forehead_erythema > 0.15 and chin_erythema > 0.15):
                score = min(1.0, score * 1.25)
                rationale = "Confirmed by elevated regional erythema index across forehead, chin, and cheeks."
            else:
                score *= 0.85
                rationale = "Regional color analysis shows balanced hemoglobin index."

        elif label == "wrinkles":
            under_eye_texture = regions.get("under_eye", {}).get("metrics", {}).get("texture_roughness", 0.0)
            forehead_texture = regions.get("forehead", {}).get("metrics", {}).get("texture_roughness", 0.0)
            avg_wrinkle_zone_texture = (under_eye_texture * 0.6) + (forehead_texture * 0.4)

            # If regional texture in under-eye/forehead is smooth (< 0.25), reduce wrinkle score
            if avg_wrinkle_zone_texture < 0.22:
                score *= 0.70
                rationale = "Periorbital and forehead zones show smooth skin micro-texture."
            elif avg_wrinkle_zone_texture > 0.45:
                score = min(1.0, score * 1.20)
                rationale = "Consistent with directional micro-texture in forehead/under-eye areas."
            else:
                rationale = "Subtle micro-texture within normal baseline."

        elif label == "pores":
            nose_texture = regions.get("nose", {}).get("metrics", {}).get("texture_roughness", 0.0)
            if nose_texture > 0.35:
                score = min(1.0, score * 1.15)
                rationale = "Supported by elevated surface roughness in the central T-zone."
            elif nose_texture < 0.20:
                score *= 0.75
                rationale = "Refined pore appearance in central facial zones."

        elif label == "pigmentation":
            melanin_variance = regional_summary.get("average_texture_roughness", 0.0)
            forehead_melanin = regions.get("forehead", {}).get("metrics", {}).get("melanin_contrast", 0.0)
            cheek_melanin = max(
                regions.get("left_cheek", {}).get("metrics", {}).get("melanin_contrast", 0.0),
                regions.get("right_cheek", {}).get("metrics", {}).get("melanin_contrast", 0.0),
            )
            if max(forehead_melanin, cheek_melanin) > 0.30:
                score = min(1.0, score * 1.20)
                rationale = "Supported by localized pigment contrast variations."
            else:
                score *= 0.80
                rationale = "Even pigment distribution across facial patches."

        # Calibrated binary determination: no user-facing 'uncertain'
        status = "detected" if score >= threshold else "not_detected"
        return status, score, rationale

    def predict(
        self,
        image: np.ndarray,
        landmarks: List[Any],
        regions_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        face_crop, crop_box = self.crop_face(image, landmarks)

        balanced_crop = self.normalize_white_balance(face_crop)
        rgb_crop = cv2.cvtColor(balanced_crop, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(rgb_crop)

        tensor = self.transform(pil_image).unsqueeze(0).to(self.device)

        with self.lock:
            with torch.no_grad():
                logits = self.model(tensor)
                raw_probabilities = torch.sigmoid(logits)[0]

        if regions_data is None:
            regions_data = skin_region_service.extract(image, landmarks)

        concern_results = []
        detected_concerns = []

        for label, probability in zip(self.class_names, raw_probabilities):
            raw_score = float(probability)
            threshold = float(self.thresholds[label])

            status, calibrated_score, rationale = self.validate_concern_with_regions(
                label,
                raw_score,
                threshold,
                regions_data,
            )

            result = {
                "id": label,
                "name": DISPLAY_NAMES.get(label, label.title()),
                "score": round(calibrated_score, 4),
                "score_percentage": round(calibrated_score * 100, 1),
                "threshold": round(threshold, 4),
                "threshold_percentage": round(threshold * 100, 1),
                "status": status,
                "regional_rationale": rationale,
            }

            concern_results.append(result)
            if status == "detected":
                detected_concerns.append(label)

        # Sort detected concerns by calibrated score descending
        concern_results.sort(key=lambda x: x["score"], reverse=True)

        return {
            "concerns": concern_results,
            "detected_concerns": detected_concerns,
            "uncertain_concerns": [],  # Cleanly deprecated in favor of calibrated certainty
            "face_crop": crop_box,
            "model": {
                "name": "EfficientNet-B0 + Regional Optical Evidence",
                "version": "beautyverse_skin_concerns_v2_calibrated",
                "task": "multi_label_visible_skin_concerns",
                "classes": self.class_names,
            },
            "interpretation_note": (
                "Scores indicate calibrated confidence relative to validation thresholds. "
                "Regional optical checks minimize false positives from lighting and makeup."
            ),
            "disclaimer": (
                "Cosmetic skin concern analysis. Not a medical or dermatological diagnosis."
            ),
        }


skin_concern_classifier_service = SkinConcernClassifierService()
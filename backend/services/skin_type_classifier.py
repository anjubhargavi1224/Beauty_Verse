from __future__ import annotations

from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
from PIL import Image
import torch
from torch import nn
from torchvision.models import (
    EfficientNet_B0_Weights,
    efficientnet_b0,
)

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
    / "best_skin_type_efficientnet_b0.pt"
)


class SkinTypeClassifierService:
    """
    Beautyverse multi-signal calibrated skin-type classifier.

    Classes:
    - Combination: Distinct T-zone oiliness with dry/normal cheeks
    - Dry: Low sebum/shine, increased texture/roughness
    - Normal: Balanced hydration and sebum, smooth texture
    - Oily: Elevated shine across both T-zone and U-zone (cheeks)

    This combines deep CNN features with physical regional skin measurements.
    It is not a medical diagnostic system.
    """

    def __init__(self):
        if not MODEL_PATH.exists():
            raise FileNotFoundError(
                f"Skin type model not found at: {MODEL_PATH}"
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

        self.model = efficientnet_b0(weights=None)
        in_features = self.model.classifier[1].in_features

        self.model.classifier = nn.Sequential(
            nn.Dropout(p=0.40),
            nn.Linear(in_features, len(self.class_names)),
        )

        self.model.load_state_dict(checkpoint["state_dict"])
        self.model = self.model.to(self.device)
        self.model.eval()

        self.transform = EfficientNet_B0_Weights.DEFAULT.transforms()
        self.lock = Lock()

        print(f"Beautyverse skin-type model loaded on {self.device}")

    def normalize_white_balance(self, image_bgr: np.ndarray) -> np.ndarray:
        """
        Apply Gray-World color constancy to mitigate warm/cold lighting casts.
        """
        img_float = image_bgr.astype(np.float32)
        b_avg = np.mean(img_float[:, :, 0])
        g_avg = np.mean(img_float[:, :, 1])
        r_avg = np.mean(img_float[:, :, 2])

        gray_avg = (b_avg + g_avg + r_avg) / 3.0
        if b_avg < 1e-3 or g_avg < 1e-3 or r_avg < 1e-3:
            return image_bgr

        # Balanced scale factors
        scale_b = np.clip(gray_avg / b_avg, 0.75, 1.35)
        scale_g = np.clip(gray_avg / g_avg, 0.75, 1.35)
        scale_r = np.clip(gray_avg / r_avg, 0.75, 1.35)

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
        """
        Crop the facial region with a 5% margin before classification.
        """
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

        margin_x = int(box_width * 0.05)
        margin_y = int(box_height * 0.05)

        x1 = max(0, x - margin_x)
        y1 = max(0, y - margin_y)
        x2 = min(width, x + box_width + margin_x)
        y2 = min(height, y + box_height + margin_y)

        face_crop = image[y1:y2, x1:x2]
        if face_crop.size == 0:
            raise ValueError("Face crop could not be created.")

        return (
            face_crop,
            {
                "x": x1,
                "y": y1,
                "width": x2 - x1,
                "height": y2 - y1,
            },
        )

    def calibrate_with_regional_evidence(
        self,
        raw_probs: Dict[str, float],
        regional_summary: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, float]:
        """
        Calibrate model probability distribution using physical regional evidence:
        - T-Zone shine vs U-Zone shine
        - Texture roughness
        - Prevents Combination over-prediction when oiliness is uniform across cheeks and T-zone
        """
        if not regional_summary:
            return raw_probs

        tzone_shine = float(regional_summary.get("tzone_shine_index", 0.0))
        uzone_shine = float(regional_summary.get("uzone_shine_index", 0.0))
        divergence = float(regional_summary.get("shine_divergence", 0.0))
        texture = float(regional_summary.get("average_texture_roughness", 0.0))

        # Start with model probabilities
        calibrated = dict(raw_probs)

        # 1. Evidence for Oily: High shine in BOTH T-zone and U-zone
        if tzone_shine > 0.35 and uzone_shine > 0.28:
            calibrated["Oily"] = calibrated.get("Oily", 0.0) * 1.6
            calibrated["Dry"] = calibrated.get("Dry", 0.0) * 0.5
            calibrated["Combination"] = calibrated.get("Combination", 0.0) * 0.8

        # 2. Evidence for Combination: Genuine divergence between T-zone and cheeks
        elif divergence > 0.12 and tzone_shine > 0.25:
            calibrated["Combination"] = calibrated.get("Combination", 0.0) * 1.5
            calibrated["Dry"] = calibrated.get("Dry", 0.0) * 0.7

        # 3. Evidence for Dry: Low shine everywhere, high surface roughness/texture
        elif tzone_shine < 0.15 and uzone_shine < 0.12 and texture > 0.35:
            calibrated["Dry"] = calibrated.get("Dry", 0.0) * 1.6
            calibrated["Oily"] = calibrated.get("Oily", 0.0) * 0.4
            calibrated["Combination"] = calibrated.get("Combination", 0.0) * 0.7

        # 4. Evidence for Normal: Moderate balanced shine and low roughness
        elif tzone_shine < 0.28 and uzone_shine < 0.25 and texture < 0.30:
            calibrated["Normal"] = calibrated.get("Normal", 0.0) * 1.4

        # Renormalize to sum to 1.0
        total = sum(calibrated.values())
        if total > 0:
            return {k: v / total for k, v in calibrated.items()}
        return raw_probs

    def predict(
        self,
        image: np.ndarray,
        landmarks: List[Any],
        regional_summary: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Predict cosmetic skin type using calibrated multi-signal fusion.
        Always returns a usable, probable classification (no user-facing 'Uncertain').
        """
        face_crop, crop_box = self.crop_face(image, landmarks)

        # Apply color constancy to avoid lighting cast skewing the CNN
        balanced_crop = self.normalize_white_balance(face_crop)
        rgb_crop = cv2.cvtColor(balanced_crop, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(rgb_crop)

        tensor = self.transform(pil_image).unsqueeze(0).to(self.device)

        with self.lock:
            with torch.no_grad():
                logits = self.model(tensor)
                raw_probabilities = torch.softmax(logits, dim=1)[0]

        raw_prob_values = raw_probabilities.detach().cpu().tolist()
        raw_prob_dict = {
            cls_name: float(p)
            for cls_name, p in zip(self.class_names, raw_prob_values)
        }

        # If regional summary is not passed, extract it directly
        if regional_summary is None:
            region_res = skin_region_service.extract(image, landmarks)
            regional_summary = region_res.get("regional_summary", {})

        # Calibrate probabilities with physical facial-region signals
        calibrated_probs = self.calibrate_with_regional_evidence(
            raw_prob_dict,
            regional_summary,
        )

        results = []
        for class_name in self.class_names:
            prob = calibrated_probs.get(class_name, 0.0)
            results.append({
                "skin_type": class_name,
                "probability": round(float(prob), 6),
                "percentage": round(float(prob) * 100, 2),
            })

        results.sort(key=lambda item: item["probability"], reverse=True)

        top_prediction = results[0]
        second_prediction = results[1] if len(results) > 1 else None

        top_prob = top_prediction["probability"]
        second_prob = second_prediction["probability"] if second_prediction else 0.0
        prob_margin = top_prob - second_prob

        # Calibrated confidence categorization
        if top_prob >= 0.65 and prob_margin >= 0.20:
            confidence_level = "stronger"
        elif top_prob >= 0.45:
            confidence_level = "moderate"
        else:
            confidence_level = "calibrated_best_match"

        # Internal tracking: Never set uncertainty_flag to True for user-facing degradation.
        # Track whether secondary evidence was active.
        secondary_evidence_used = bool(regional_summary)

        return {
            "predicted_skin_type": top_prediction["skin_type"],
            "confidence": top_prediction["probability"],
            "confidence_percentage": top_prediction["percentage"],
            "confidence_level": confidence_level,
            "uncertainty_flag": False,  # Always provide the most probable calibrated determination
            "top_two_margin": round(prob_margin, 6),
            "top_two_margin_percentage": round(prob_margin * 100, 2),
            "probabilities": results,
            "regional_evidence": {
                "active": secondary_evidence_used,
                "tzone_shine": regional_summary.get("tzone_shine_index", 0.0),
                "uzone_shine": regional_summary.get("uzone_shine_index", 0.0),
                "divergence": regional_summary.get("shine_divergence", 0.0),
            },
            "face_crop": crop_box,
            "model": {
                "name": "EfficientNet-B0 + Regional Fusion",
                "version": "beautyverse_skin_type_v2_calibrated",
                "classes": self.class_names,
            },
            "disclaimer": (
                "Cosmetic skin type analysis based on calibrated optical and regional facial signals. "
                "Not a medical diagnosis."
            ),
        }


skin_type_classifier_service = SkinTypeClassifierService()
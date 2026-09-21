from __future__ import annotations

from typing import Any, Dict, List, Tuple
import cv2
import numpy as np


class SkinRegionService:
    """
    Extract cosmetic skin-analysis regions and deep regional metrics
    using MediaPipe facial landmarks.

    Extracts:
    - Forehead (T-Zone)
    - Nose (T-Zone)
    - Left Cheek (U-Zone)
    - Right Cheek (U-Zone)
    - Chin (U-Zone)
    - Under Eye (Periorbital zone for fine lines / dark circles)

    This service performs cosmetic image preprocessing only.
    It does NOT perform medical diagnosis.
    """

    REGION_CONFIG = {
        "forehead": {
            "anchor": 10,
            "width": 0.24,
            "height": 0.14,
            "x_offset": 0.0,
            "y_offset": 0.07,
            "zone": "tzone",
        },
        "nose": {
            "anchor": 1,
            "width": 0.14,
            "height": 0.14,
            "x_offset": 0.0,
            "y_offset": -0.015,
            "zone": "tzone",
        },
        "left_cheek": {
            "anchor": 205,
            "width": 0.20,
            "height": 0.17,
            "x_offset": 0.0,
            "y_offset": 0.0,
            "zone": "uzone",
        },
        "right_cheek": {
            "anchor": 425,
            "width": 0.20,
            "height": 0.17,
            "x_offset": 0.0,
            "y_offset": 0.0,
            "zone": "uzone",
        },
        "chin": {
            "anchor": 152,
            "width": 0.20,
            "height": 0.12,
            "x_offset": 0.0,
            "y_offset": -0.075,
            "zone": "uzone",
        },
        "under_eye": {
            "anchor": 230,
            "width": 0.22,
            "height": 0.09,
            "x_offset": 0.0,
            "y_offset": 0.02,
            "zone": "periorbital",
        },
    }

    def _calculate_face_bounds(
        self,
        landmarks: List[Any],
        width: int,
        height: int,
    ) -> Tuple[int, int, int, int]:
        xs = [landmark.x for landmark in landmarks]
        ys = [landmark.y for landmark in landmarks]

        x1 = int(max(0.0, min(xs)) * width)
        y1 = int(max(0.0, min(ys)) * height)
        x2 = int(min(1.0, max(xs)) * width)
        y2 = int(min(1.0, max(ys)) * height)

        return x1, y1, x2, y2

    def _calculate_capture_quality(
        self,
        face_crop: np.ndarray,
    ) -> Dict[str, Any]:
        """
        Evaluate photograph capture quality across the facial crop.
        """
        if face_crop.size == 0:
            return {
                "brightness": 0.0,
                "contrast": 0.0,
                "sharpness": 0.0,
                "overexposed_percentage": 0.0,
                "underexposed_percentage": 0.0,
                "lighting_status": "invalid",
                "focus_status": "invalid",
                "usable": False,
            }

        gray = cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY)
        target_width = 500

        if gray.shape[1] > target_width:
            scale = target_width / gray.shape[1]
            gray = cv2.resize(
                gray,
                None,
                fx=scale,
                fy=scale,
                interpolation=cv2.INTER_AREA,
            )

        brightness = float(np.mean(gray))
        contrast = float(np.std(gray))
        laplacian_variance = float(cv2.Laplacian(gray, cv2.CV_64F).var())

        overexposed = float(np.mean(gray >= 245) * 100)
        underexposed = float(np.mean(gray <= 20) * 100)

        if brightness < 50:
            lighting_status = "too_dark"
        elif brightness > 225:
            lighting_status = "too_bright"
        elif overexposed > 18:
            lighting_status = "overexposed"
        elif underexposed > 18:
            lighting_status = "underexposed"
        else:
            lighting_status = "acceptable"

        if laplacian_variance < 25:
            focus_status = "possibly_blurry"
        else:
            focus_status = "acceptable"

        usable = (
            lighting_status == "acceptable"
            and focus_status == "acceptable"
        )

        return {
            "brightness": round(brightness, 2),
            "contrast": round(contrast, 2),
            "sharpness": round(laplacian_variance, 2),
            "overexposed_percentage": round(overexposed, 2),
            "underexposed_percentage": round(underexposed, 2),
            "lighting_status": lighting_status,
            "focus_status": focus_status,
            "usable": usable,
        }

    def _analyze_patch_metrics(
        self,
        patch_bgr: np.ndarray,
        reference_skin_erythema: float = 0.12,
    ) -> Dict[str, Any]:
        """
        Compute deep cosmetic signals from a region patch:
        - shine_index: High-luminance specular highlights indicative of sebum/oiliness
        - erythema_index: Normalized hemoglobin/redness signal: (R - G) / (R + G + 1e-5)
        - texture_roughness: High-frequency texture and surface roughness
        - melanin_contrast: Localized standard deviation in luminance
        """
        if patch_bgr.size == 0:
            return {
                "brightness": 0.0,
                "lighting_status": "invalid",
                "shine_index": 0.0,
                "erythema_index": 0.0,
                "texture_roughness": 0.0,
                "melanin_contrast": 0.0,
            }

        gray = cv2.cvtColor(patch_bgr, cv2.COLOR_BGR2GRAY)
        brightness = float(np.mean(gray))

        if brightness < 50:
            status = "too_dark"
        elif brightness > 225:
            status = "too_bright"
        else:
            status = "acceptable"

        # 1. Specular Shine / Sebum Index
        # Calculate percentage of pixels approaching high-luminance specular threshold (> 210)
        # and ratio of 95th percentile luminance to median luminance
        p95 = float(np.percentile(gray, 95))
        p50 = max(float(np.median(gray)), 1.0)
        specular_ratio = (p95 - p50) / 255.0
        high_spec_pct = float(np.mean(gray >= 210))
        shine_index = float(np.clip((specular_ratio * 0.7) + (high_spec_pct * 3.0), 0.0, 1.0))

        # 2. Erythema / Redness Index
        # BGR channels
        b = patch_bgr[:, :, 0].astype(np.float64)
        g = patch_bgr[:, :, 1].astype(np.float64)
        r = patch_bgr[:, :, 2].astype(np.float64)

        # Normalized difference index (R - G) / (R + G + 1e-5)
        rg_diff = (r - g) / (r + g + 1e-5)
        raw_erythema = float(np.mean(rg_diff))
        # Differential erythema relative to normal facial baseline
        erythema_index = float(np.clip((raw_erythema - 0.08) * 3.5, 0.0, 1.0))

        # 3. Texture / Roughness Index
        # High-frequency variance using Laplacian
        lap_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        # Normalized texture scale
        texture_roughness = float(np.clip(lap_var / 120.0, 0.0, 1.0))

        # 4. Melanin / Contrast Variance (Spots & unevenness)
        melanin_contrast = float(np.clip(np.std(gray) / 45.0, 0.0, 1.0))

        return {
            "brightness": round(brightness, 2),
            "lighting_status": status,
            "shine_index": round(shine_index, 3),
            "erythema_index": round(erythema_index, 3),
            "texture_roughness": round(texture_roughness, 3),
            "melanin_contrast": round(melanin_contrast, 3),
        }

    def extract(
        self,
        image: np.ndarray,
        landmarks: List[Any],
    ) -> Dict[str, Any]:
        image_height, image_width = image.shape[:2]

        (
            face_x1,
            face_y1,
            face_x2,
            face_y2,
        ) = self._calculate_face_bounds(
            landmarks,
            image_width,
            image_height,
        )

        face_width = max(1, face_x2 - face_x1)
        face_height = max(1, face_y2 - face_y1)

        face_crop = image[face_y1:face_y2, face_x1:face_x2]
        capture_quality = self._calculate_capture_quality(face_crop)

        regions = {}
        tzone_shines = []
        uzone_shines = []
        all_erythema = []
        all_textures = []

        for region_name, config in self.REGION_CONFIG.items():
            anchor_index = config["anchor"]
            if anchor_index >= len(landmarks):
                continue

            anchor = landmarks[anchor_index]
            center_x = int(anchor.x * image_width)
            center_y = int(anchor.y * image_height)

            center_x += int(config["x_offset"] * face_width)
            center_y += int(config["y_offset"] * face_height)

            region_width = int(config["width"] * face_width)
            region_height = int(config["height"] * face_height)

            x1 = max(0, int(center_x - region_width / 2))
            y1 = max(0, int(center_y - region_height / 2))
            x2 = min(image_width, int(center_x + region_width / 2))
            y2 = min(image_height, int(center_y + region_height / 2))

            patch = image[y1:y2, x1:x2]
            metrics = self._analyze_patch_metrics(patch)

            zone = config.get("zone", "other")
            if zone == "tzone":
                tzone_shines.append(metrics["shine_index"])
            elif zone == "uzone":
                uzone_shines.append(metrics["shine_index"])

            all_erythema.append((region_name, metrics["erythema_index"]))
            all_textures.append(metrics["texture_roughness"])

            regions[region_name] = {
                "anchor_landmark": anchor_index,
                "zone": zone,
                "bounding_box": {
                    "x": x1,
                    "y": y1,
                    "width": x2 - x1,
                    "height": y2 - y1,
                },
                "quality": {
                    "brightness": metrics["brightness"],
                    "lighting_status": metrics["lighting_status"],
                },
                "metrics": metrics,
            }

        # Compute regional summary for skin-type and concern calibration
        avg_tzone_shine = float(np.mean(tzone_shines)) if tzone_shines else 0.0
        avg_uzone_shine = float(np.mean(uzone_shines)) if uzone_shines else 0.0
        shine_divergence = max(0.0, avg_tzone_shine - avg_uzone_shine)

        all_erythema.sort(key=lambda x: x[1], reverse=True)
        max_erythema_region = all_erythema[0][0] if all_erythema else "none"
        avg_erythema = float(np.mean([x[1] for x in all_erythema])) if all_erythema else 0.0
        avg_texture = float(np.mean(all_textures)) if all_textures else 0.0

        regional_summary = {
            "tzone_shine_index": round(avg_tzone_shine, 3),
            "uzone_shine_index": round(avg_uzone_shine, 3),
            "shine_divergence": round(shine_divergence, 3),
            "average_erythema_index": round(avg_erythema, 3),
            "max_erythema_region": max_erythema_region,
            "average_texture_roughness": round(avg_texture, 3),
        }

        return {
            "face_bounding_box": {
                "x": face_x1,
                "y": face_y1,
                "width": face_x2 - face_x1,
                "height": face_y2 - face_y1,
            },
            "capture_quality": capture_quality,
            "regions": regions,
            "regional_summary": regional_summary,
        }

    def annotate(
        self,
        image: np.ndarray,
        regions_result: Dict[str, Any],
    ) -> np.ndarray:
        annotated = image.copy()

        for region_name, region in regions_result["regions"].items():
            box = region["bounding_box"]
            x1 = box["x"]
            y1 = box["y"]
            x2 = x1 + box["width"]
            y2 = y1 + box["height"]

            cv2.rectangle(
                annotated,
                (x1, y1),
                (x2, y2),
                (255, 255, 255),
                2,
            )

            cv2.putText(
                annotated,
                region_name,
                (x1, max(20, y1 - 8)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (255, 255, 255),
                2,
                cv2.LINE_AA,
            )

        return annotated


skin_region_service = SkinRegionService()
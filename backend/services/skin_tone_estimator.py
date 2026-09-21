from __future__ import annotations

import math
from typing import Any, Dict, List, Tuple
import cv2
import numpy as np


class SkinToneEstimatorService:
    """
    Estimates skin tone, complexion category, Fitzpatrick scale,
    and undertone from calibrated facial skin patches.

    Uses Individual Typology Angle (ITA) in CIELAB color space:
    ITA = arctan((L* - 50) / b*) * (180 / pi)
    """

    # Fitzpatrick Skin Type thresholds based on ITA°
    # Type I:   > 55° (Very Light / Pale)
    # Type II:  41° to 55° (Light / Fair)
    # Type III: 28° to 41° (Medium-Light / Olive)
    # Type IV:  10° to 28° (Medium / Moderate Brown)
    # Type V:   -30° to 10° (Tan / Dark Brown)
    # Type VI:  < -30° (Deep / Very Dark)
    FITZPATRICK_MAP = [
        (55.0, "Type I", "Very Fair", "High sensitivity to UV, burns easily, rarely tans"),
        (41.0, "Type II", "Fair", "Sensitive to UV, usually burns, tans with difficulty"),
        (28.0, "Type III", "Medium Light", "Moderately sensitive to UV, sometimes mild burn, tans gradually"),
        (10.0, "Type IV", "Medium", "Minimally sensitive to UV, rarely burns, tans easily"),
        (-30.0, "Type V", "Tan / Deep Medium", "Very rarely burns, tans easily to dark brown"),
        (float("-inf"), "Type VI", "Deep / Rich", "Deeply pigmented, virtually never burns, high melanin protection"),
    ]

    # MediaPipe landmarks for safe skin sampling (avoiding eyes, brows, lips, nostrils, hair)
    # Forehead center, left cheek upper/middle, right cheek upper/middle, chin center
    SAFE_SKIN_LANDMARK_INDICES = [
        10,   # Forehead center
        67,   # Forehead left
        297,  # Forehead right
        117,  # Left cheek inner
        123,  # Left cheek middle
        346,  # Right cheek inner
        352,  # Right cheek middle
        152,  # Chin
        200,  # Chin upper
    ]

    def sample_skin_patches(
        self,
        image_bgr: np.ndarray,
        landmarks: List[Any],
        patch_radius_px: int = 12,
    ) -> List[np.ndarray]:
        """
        Extract clean skin pixel samples around safe anatomical landmarks.
        """
        if not landmarks or image_bgr is None or image_bgr.size == 0:
            return []

        h, w = image_bgr.shape[:2]
        patches = []

        for idx in self.SAFE_SKIN_LANDMARK_INDICES:
            if idx >= len(landmarks):
                continue
            lm = landmarks[idx]
            if hasattr(lm, "x") and hasattr(lm, "y"):
                lx, ly = lm.x, lm.y
            elif isinstance(lm, dict) and "x" in lm and "y" in lm:
                lx, ly = lm["x"], lm["y"]
            else:
                continue

            cx = int(lx * w)
            cy = int(ly * h)

            x1 = max(0, cx - patch_radius_px)
            y1 = max(0, cy - patch_radius_px)
            x2 = min(w, cx + patch_radius_px)
            y2 = min(h, cy + patch_radius_px)

            patch = image_bgr[y1:y2, x1:x2]
            if patch.size > 0:
                # Filter out extreme specular reflections (> 245 in any channel) or deep shadows (< 20)
                gray = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY)
                valid_mask = (gray > 25) & (gray < 240)
                if np.sum(valid_mask) >= (patch.shape[0] * patch.shape[1] * 0.4):
                    patches.append(patch[valid_mask])

        return patches

    def estimate(
        self,
        image_bgr: np.ndarray,
        landmarks: Optional[List[Any]] = None,
    ) -> Dict[str, Any]:
        """
        Estimate skin tone, complexion name, ITA°, Fitzpatrick type, and undertone.
        """
        patches = self.sample_skin_patches(image_bgr, landmarks or [])

        if not patches:
            # Fallback to center face crop if landmark patches are empty
            h, w = image_bgr.shape[:2]
            center_crop = image_bgr[int(h * 0.25):int(h * 0.75), int(w * 0.25):int(w * 0.75)]
            if center_crop.size > 0:
                pixels = center_crop.reshape(-1, 3)
            else:
                pixels = np.array([[128, 128, 128]], dtype=np.uint8)
        else:
            pixels = np.vstack(patches)

        # Convert sampled skin pixels to RGB and CIELAB
        # cv2.cvtColor requires 2D or 3D array
        pixels_2d = pixels.reshape(-1, 1, 3).astype(np.uint8)
        lab_pixels = cv2.cvtColor(pixels_2d, cv2.COLOR_BGR2LAB).reshape(-1, 3).astype(np.float64)
        rgb_pixels = cv2.cvtColor(pixels_2d, cv2.COLOR_BGR2RGB).reshape(-1, 3).astype(np.float64)

        # OpenCV scales L from [0, 100] to [0, 255], a and b from [-128, 127] to [0, 255] (with offset 128)
        l_star = np.median(lab_pixels[:, 0]) * (100.0 / 255.0)
        a_star = np.median(lab_pixels[:, 1]) - 128.0
        b_star = np.median(lab_pixels[:, 2]) - 128.0

        median_r = int(np.clip(np.median(rgb_pixels[:, 0]), 0, 255))
        median_g = int(np.clip(np.median(rgb_pixels[:, 1]), 0, 255))
        median_b = int(np.clip(np.median(rgb_pixels[:, 2]), 0, 255))

        # Individual Typology Angle (ITA) in degrees
        # Protect against division by zero or negative b*
        b_denom = max(b_star, 0.01)
        ita_rad = math.atan2(l_star - 50.0, b_denom)
        ita_deg = math.degrees(ita_rad)

        # Map to Fitzpatrick Scale and Complexion Group
        fitzpatrick_type = "Type III"
        complexion_name = "Medium"
        uv_profile = "Moderately sensitive to UV"

        for threshold, f_type, c_name, uv_desc in self.FITZPATRICK_MAP:
            if ita_deg >= threshold:
                fitzpatrick_type = f_type
                complexion_name = c_name
                uv_profile = uv_desc
                break

        # Undertone estimation
        # Cool: a* relative to b* is higher (pink/rosy/blue undertones)
        # Warm: b* relative to a* is significantly higher (golden/yellow/peachy undertones)
        # Neutral: balanced ratio between a* and b*
        ab_ratio = a_star / (b_star + 1e-5)
        if a_star > 14.0 or ab_ratio > 0.85:
            undertone = "Cool"
            undertone_desc = "Rosy, pink, or soft bluish baseline undertone"
        elif b_star > 18.0 or ab_ratio < 0.55:
            undertone = "Warm"
            undertone_desc = "Golden, yellow, peachy, or warm honey baseline undertone"
        else:
            undertone = "Neutral"
            undertone_desc = "Balanced mix of warm golden and cool rosy undertones"

        hex_color = f"#{median_r:02x}{median_g:02x}{median_b:02x}"

        return {
            "complexion": complexion_name,
            "fitzpatrick_scale": fitzpatrick_type,
            "undertone": undertone,
            "undertone_description": undertone_desc,
            "ita_degrees": round(ita_deg, 2),
            "uv_sensitivity": uv_profile,
            "color_metrics": {
                "l_star": round(float(l_star), 2),
                "a_star": round(float(a_star), 2),
                "b_star": round(float(b_star), 2),
                "representative_hex": hex_color,
                "rgb": [median_r, median_g, median_b],
            },
            "display_label": f"{complexion_name} ({undertone} Undertone)",
        }


skin_tone_estimator = SkinToneEstimatorService()

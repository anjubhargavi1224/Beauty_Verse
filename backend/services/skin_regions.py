import cv2
import numpy as np


class SkinRegionService:
    """
    Extract cosmetic skin-analysis regions using
    MediaPipe facial landmarks.

    This service performs image preprocessing only.
    It does NOT perform medical diagnosis.
    """

    REGION_CONFIG = {
        "forehead": {
            "anchor": 10,
            "width": 0.22,
            "height": 0.13,
            "x_offset": 0.0,
            "y_offset": 0.07,
        },

        "left_cheek": {
            "anchor": 205,
            "width": 0.20,
            "height": 0.17,
            "x_offset": 0.0,
            "y_offset": 0.0,
        },

        "right_cheek": {
            "anchor": 425,
            "width": 0.20,
            "height": 0.17,
            "x_offset": 0.0,
            "y_offset": 0.0,
        },

        "nose": {
            "anchor": 1,
            "width": 0.12,
            "height": 0.13,
            "x_offset": 0.0,
            "y_offset": -0.015,
        },

        "chin": {
            "anchor": 152,
            "width": 0.20,
            "height": 0.12,
            "x_offset": 0.0,
            "y_offset": -0.075,
        },
    }

    def _calculate_face_bounds(
        self,
        landmarks,
        width,
        height,
    ):
        xs = [landmark.x for landmark in landmarks]
        ys = [landmark.y for landmark in landmarks]

        x1 = int(max(0.0, min(xs)) * width)
        y1 = int(max(0.0, min(ys)) * height)

        x2 = int(min(1.0, max(xs)) * width)
        y2 = int(min(1.0, max(ys)) * height)

        return x1, y1, x2, y2

    def _calculate_capture_quality(
        self,
        face_crop,
    ):
        """
        Evaluate the overall photograph rather than
        using smooth skin patches to determine blur.
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

        gray = cv2.cvtColor(
            face_crop,
            cv2.COLOR_BGR2GRAY,
        )

        # Normalize image dimensions so focus measurements
        # are more consistent across different camera sizes.
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

        brightness = float(
            np.mean(gray)
        )

        contrast = float(
            np.std(gray)
        )

        laplacian_variance = float(
            cv2.Laplacian(
                gray,
                cv2.CV_64F,
            ).var()
        )

        overexposed = float(
            np.mean(gray >= 245) * 100
        )

        underexposed = float(
            np.mean(gray <= 20) * 100
        )

        if brightness < 55:
            lighting_status = "too_dark"

        elif brightness > 220:
            lighting_status = "too_bright"

        elif overexposed > 15:
            lighting_status = "overexposed"

        elif underexposed > 15:
            lighting_status = "underexposed"

        else:
            lighting_status = "acceptable"

        # This is intentionally evaluated on the full face.
        if laplacian_variance < 30:
            focus_status = "possibly_blurry"
        else:
            focus_status = "acceptable"

        usable = (
            lighting_status == "acceptable"
            and focus_status == "acceptable"
        )

        return {
            "brightness": round(
                brightness,
                2,
            ),

            "contrast": round(
                contrast,
                2,
            ),

            "sharpness": round(
                laplacian_variance,
                2,
            ),

            "overexposed_percentage": round(
                overexposed,
                2,
            ),

            "underexposed_percentage": round(
                underexposed,
                2,
            ),

            "lighting_status": lighting_status,

            "focus_status": focus_status,

            "usable": usable,
        }

    def _get_region_lighting(
        self,
        patch,
    ):
        """
        Region-level lighting analysis.

        We deliberately do NOT calculate blur here
        because smooth skin produces artificially low
        Laplacian scores.
        """

        if patch.size == 0:
            return {
                "brightness": 0.0,
                "lighting_status": "invalid",
            }

        gray = cv2.cvtColor(
            patch,
            cv2.COLOR_BGR2GRAY,
        )

        brightness = float(
            np.mean(gray)
        )

        if brightness < 55:
            status = "too_dark"

        elif brightness > 220:
            status = "too_bright"

        else:
            status = "acceptable"

        return {
            "brightness": round(
                brightness,
                2,
            ),

            "lighting_status": status,
        }

    def extract(
        self,
        image,
        landmarks,
    ):
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

        face_width = max(
            1,
            face_x2 - face_x1,
        )

        face_height = max(
            1,
            face_y2 - face_y1,
        )

        face_crop = image[
            face_y1:face_y2,
            face_x1:face_x2,
        ]

        capture_quality = (
            self._calculate_capture_quality(
                face_crop
            )
        )

        regions = {}

        for region_name, config in self.REGION_CONFIG.items():

            anchor_index = config["anchor"]

            anchor = landmarks[
                anchor_index
            ]

            center_x = int(
                anchor.x * image_width
            )

            center_y = int(
                anchor.y * image_height
            )

            center_x += int(
                config["x_offset"]
                * face_width
            )

            center_y += int(
                config["y_offset"]
                * face_height
            )

            region_width = int(
                config["width"]
                * face_width
            )

            region_height = int(
                config["height"]
                * face_height
            )

            x1 = int(
                center_x
                - region_width / 2
            )

            y1 = int(
                center_y
                - region_height / 2
            )

            x2 = int(
                center_x
                + region_width / 2
            )

            y2 = int(
                center_y
                + region_height / 2
            )

            x1 = max(
                0,
                min(image_width - 1, x1),
            )

            y1 = max(
                0,
                min(image_height - 1, y1),
            )

            x2 = max(
                x1 + 1,
                min(image_width, x2),
            )

            y2 = max(
                y1 + 1,
                min(image_height, y2),
            )

            patch = image[
                y1:y2,
                x1:x2,
            ]

            region_lighting = (
                self._get_region_lighting(
                    patch
                )
            )

            regions[
                region_name
            ] = {
                "anchor_landmark": anchor_index,

                "bounding_box": {
                    "x": x1,
                    "y": y1,
                    "width": x2 - x1,
                    "height": y2 - y1,
                },

                "quality": region_lighting,
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
        }

    def annotate(
        self,
        image,
        regions_result,
    ):
        annotated = image.copy()

        for region_name, region in (
            regions_result[
                "regions"
            ].items()
        ):
            box = region[
                "bounding_box"
            ]

            x1 = box["x"]
            y1 = box["y"]

            x2 = (
                x1
                + box["width"]
            )

            y2 = (
                y1
                + box["height"]
            )

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
                (
                    x1,
                    max(20, y1 - 8),
                ),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                2,
                cv2.LINE_AA,
            )

        return annotated


skin_region_service = SkinRegionService()
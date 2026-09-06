from pathlib import Path
from threading import Lock

import cv2
import mediapipe as mp
import numpy as np


MODEL_PATH = (
    Path(__file__).resolve().parents[1]
    / "models"
    / "face_landmarker.task"
)


class FaceDetectionService:
    def __init__(self):
        if not MODEL_PATH.exists():
            raise FileNotFoundError(
                f"MediaPipe model not found: {MODEL_PATH}"
            )

        base_options = mp.tasks.BaseOptions(
            model_asset_path=str(MODEL_PATH)
        )

        options = mp.tasks.vision.FaceLandmarkerOptions(
            base_options=base_options,
            running_mode=mp.tasks.vision.RunningMode.IMAGE,
            num_faces=1,
            min_face_detection_confidence=0.5,
            min_face_presence_confidence=0.5,
            min_tracking_confidence=0.5,
            output_face_blendshapes=False,
            output_facial_transformation_matrixes=False,
        )

        self.landmarker = (
            mp.tasks.vision.FaceLandmarker.create_from_options(
                options
            )
        )

        self.lock = Lock()

    def decode_image(self, image_bytes: bytes):
        np_array = np.frombuffer(
            image_bytes,
            dtype=np.uint8,
        )

        image = cv2.imdecode(
            np_array,
            cv2.IMREAD_COLOR,
        )

        if image is None:
            raise ValueError(
                "The uploaded file could not be decoded as an image."
            )

        return image

    def detect(self, image_bytes: bytes):
        """
        Returns:
            OpenCV BGR image
            MediaPipe FaceLandmarkerResult
        """

        image = self.decode_image(image_bytes)

        rgb_image = cv2.cvtColor(
            image,
            cv2.COLOR_BGR2RGB,
        )

        rgb_image = np.ascontiguousarray(
            rgb_image
        )

        mp_image = mp.Image(
            image_format=mp.ImageFormat.SRGB,
            data=rgb_image,
        )

        with self.lock:
            result = self.landmarker.detect(
                mp_image
            )

        return image, result

    def calculate_face_bbox(
        self,
        landmarks,
        image_width,
        image_height,
    ):
        x_values = [
            landmark.x
            for landmark in landmarks
        ]

        y_values = [
            landmark.y
            for landmark in landmarks
        ]

        min_x = max(
            0.0,
            min(x_values),
        )

        max_x = min(
            1.0,
            max(x_values),
        )

        min_y = max(
            0.0,
            min(y_values),
        )

        max_y = min(
            1.0,
            max(y_values),
        )

        x1 = int(
            min_x * image_width
        )

        y1 = int(
            min_y * image_height
        )

        x2 = int(
            max_x * image_width
        )

        y2 = int(
            max_y * image_height
        )

        return {
            "x": x1,
            "y": y1,
            "width": max(0, x2 - x1),
            "height": max(0, y2 - y1),
        }

    def summarize(
        self,
        image,
        result,
    ):
        height, width = image.shape[:2]

        faces = []

        for face_index, landmarks in enumerate(
            result.face_landmarks
        ):
            bbox = self.calculate_face_bbox(
                landmarks,
                width,
                height,
            )

            sample = []

            for index, landmark in enumerate(
                landmarks[:10]
            ):
                sample.append(
                    {
                        "index": index,
                        "x": round(
                            float(landmark.x),
                            6,
                        ),
                        "y": round(
                            float(landmark.y),
                            6,
                        ),
                        "z": round(
                            float(landmark.z),
                            6,
                        ),
                    }
                )

            faces.append(
                {
                    "face_index": face_index,
                    "landmark_count": len(
                        landmarks
                    ),
                    "bounding_box": bbox,
                    "landmark_sample": sample,
                }
            )

        return {
            "face_detected": len(faces) > 0,
            "face_count": len(faces),
            "image": {
                "width": width,
                "height": height,
            },
            "faces": faces,
        }

    def analyze(
        self,
        image_bytes: bytes,
    ):
        image, result = self.detect(
            image_bytes
        )

        return self.summarize(
            image,
            result,
        )

    def close(self):
        if self.landmarker:
            self.landmarker.close()


face_detection_service = FaceDetectionService()
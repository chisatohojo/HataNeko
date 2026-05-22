from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL.Image import Image

from hateneko.core.scan_result import Issue
from hateneko.detectors.base import BaseDetector

try:
    import cv2
    import numpy as np
except ImportError:  # pragma: no cover - optional runtime dependency
    cv2 = None
    np = None


class FaceDetector(BaseDetector):
    """OpenCV Haar cascade based face-count check."""

    name = "face"
    _cascade = None

    def detect(
        self,
        image: Image | None,
        file_path: str | Path,
        context: dict[str, Any],
    ) -> list[Issue]:
        if image is None or not context.get("scan_face_count", True):
            return []

        if cv2 is None or np is None:
            return [
                Issue(
                    type="face_detector_unavailable",
                    severity="warning",
                    message="OpenCV が利用できないため顔数チェックを実行できません。",
                )
            ]

        faces = self._detect_faces(image, context)
        expected = int(context.get("expected_person_count", 1))
        flag_zero_faces = bool(context.get("scan_zero_faces", False))
        issues: list[Issue] = []

        if expected > 0 and len(faces) > expected:
            issues.append(
                Issue(
                    type="too_many_faces",
                    severity="warning",
                    message=(
                        f"{expected}人想定ですが、顔候補が {len(faces)} 件検出されました。"
                    ),
                )
            )
            for bbox in faces:
                issues.append(
                    Issue(
                        type="face_candidate_region",
                        severity="warning",
                        message="顔候補領域です。",
                        bbox=bbox,
                    )
                )
        elif len(faces) == 0 and flag_zero_faces:
            issues.append(
                Issue(
                    type="no_face_detected",
                    severity="warning",
                    message="顔候補が検出されませんでした。必要に応じて確認してください。",
                )
            )

        return issues

    def _detect_faces(
        self,
        image: Image,
        context: dict[str, Any],
    ) -> list[tuple[int, int, int, int]]:
        cascade = self._load_cascade()
        if cascade is None:
            return []

        rgb = image.convert("RGB")
        array = np.array(rgb)
        gray = cv2.cvtColor(array, cv2.COLOR_RGB2GRAY)

        min_size = int(context.get("face_min_size", 32))
        faces = cascade.detectMultiScale(
            gray,
            scaleFactor=float(context.get("face_scale_factor", 1.1)),
            minNeighbors=int(context.get("face_min_neighbors", 5)),
            minSize=(min_size, min_size),
        )
        return [
            (int(x), int(y), int(width), int(height))
            for x, y, width, height in faces
        ]

    @classmethod
    def _load_cascade(cls):
        if cls._cascade is not None:
            return cls._cascade
        cascade_path = Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"
        cascade = cv2.CascadeClassifier(str(cascade_path))
        if cascade.empty():
            return None
        cls._cascade = cascade
        return cls._cascade

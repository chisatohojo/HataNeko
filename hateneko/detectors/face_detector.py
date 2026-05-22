from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL.Image import Image

from hateneko.core.scan_result import Issue
from hateneko.detectors.base import BaseDetector


class FaceDetector(BaseDetector):
    """Placeholder for a future OpenCV or model-backed face detector."""

    name = "face"

    def detect(
        self,
        image: Image | None,
        file_path: str | Path,
        context: dict[str, Any],
    ) -> list[Issue]:
        return []


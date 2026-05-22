from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL.Image import Image

from hateneko.core.scan_result import Issue
from hateneko.detectors.base import BaseDetector


class PoseDetector(BaseDetector):
    """Placeholder for future MediaPipe Pose based checks."""

    name = "pose"

    def detect(
        self,
        image: Image | None,
        file_path: str | Path,
        context: dict[str, Any],
    ) -> list[Issue]:
        return []


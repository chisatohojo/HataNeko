from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL.Image import Image

from hateneko.core.scan_result import Issue
from hateneko.detectors.base import BaseDetector


class ResolutionDetector(BaseDetector):
    name = "resolution"

    def detect(
        self,
        image: Image | None,
        file_path: str | Path,
        context: dict[str, Any],
    ) -> list[Issue]:
        if image is None:
            return []

        width, height = image.size
        target_width = int(context.get("target_width", 1024))
        target_height = int(context.get("target_height", 1536))
        tolerance = float(context.get("allow_aspect_ratio_tolerance", 0.05))

        issues: list[Issue] = []
        if (width, height) != (target_width, target_height):
            issues.append(
                Issue(
                    type="resolution_mismatch",
                    severity="warning",
                    message=f"基準解像度 {target_width}x{target_height} と異なります: {width}x{height}",
                )
            )

        if height > 0 and target_height > 0:
            actual_ratio = width / height
            target_ratio = target_width / target_height
            if abs(actual_ratio - target_ratio) / target_ratio > tolerance:
                issues.append(
                    Issue(
                        type="aspect_ratio_mismatch",
                        severity="warning",
                        message=(
                            "基準の縦横比と大きく異なります: "
                            f"{actual_ratio:.3f} / 基準 {target_ratio:.3f}"
                        ),
                    )
                )
        return issues


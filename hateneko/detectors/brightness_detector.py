from __future__ import annotations

from pathlib import Path
from statistics import fmean, pstdev
from typing import Any

from PIL.Image import Image

from hateneko.core.scan_result import Issue
from hateneko.detectors.base import BaseDetector


class BrightnessDetector(BaseDetector):
    name = "brightness"

    def detect(
        self,
        image: Image | None,
        file_path: str | Path,
        context: dict[str, Any],
    ) -> list[Issue]:
        if image is None:
            return []

        sample = image.convert("L")
        sample.thumbnail((128, 128))
        data_reader = getattr(sample, "get_flattened_data", sample.getdata)
        values = list(data_reader())
        if not values:
            return []

        mean = fmean(values)
        deviation = pstdev(values)
        issues: list[Issue] = []
        if mean <= 5 and deviation <= 5:
            issues.append(
                Issue(
                    type="almost_black",
                    severity="warning",
                    message="ほぼ真っ黒な画像です。生成失敗の可能性があります。",
                    score=float(mean),
                )
            )
        elif mean >= 250 and deviation <= 5:
            issues.append(
                Issue(
                    type="almost_white",
                    severity="warning",
                    message="ほぼ真っ白な画像です。生成失敗の可能性があります。",
                    score=float(mean),
                )
            )
        elif deviation <= 2.5:
            issues.append(
                Issue(
                    type="almost_solid_color",
                    severity="warning",
                    message="単色に近い画像です。生成失敗の可能性があります。",
                    score=float(deviation),
                )
            )
        return issues

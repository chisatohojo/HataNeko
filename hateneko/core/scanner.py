from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from PIL import Image, UnidentifiedImageError

from hateneko.core.scan_result import Issue, ScanResult
from hateneko.detectors.base import BaseDetector
from hateneko.detectors.brightness_detector import BrightnessDetector
from hateneko.detectors.duplicate_detector import DuplicateDetector
from hateneko.detectors.file_detector import FileDetector
from hateneko.detectors.resolution_detector import ResolutionDetector


class Scanner:
    def __init__(self, detectors: list[BaseDetector]) -> None:
        self.detectors = detectors

    def scan_image(
        self,
        file_path: str | Path,
        context: dict[str, Any] | None = None,
    ) -> ScanResult:
        path = Path(file_path)
        if context is None:
            context = {}
        image = None
        issues: list[Issue] = []

        try:
            with Image.open(path) as opened:
                image = opened.copy()
        except (OSError, UnidentifiedImageError) as exc:
            context["open_error"] = str(exc)

        for detector in self.detectors:
            try:
                issues.extend(detector.detect(image, path, context))
            except Exception as exc:  # Detector failures should never crash the app.
                issues.append(
                    Issue(
                        type=f"{detector.name}_detector_error",
                        severity="warning",
                        message=f"{detector.name} 検出器でエラーが発生しました: {exc}",
                    )
                )

        return ScanResult.from_issues(path, issues)

    def scan_folder(self, image_paths: Iterable[str | Path]) -> dict[str, ScanResult]:
        context: dict[str, Any] = {}
        results: dict[str, ScanResult] = {}
        for path in image_paths:
            result = self.scan_image(path, context)
            results[str(Path(path))] = result
        return results


def build_default_scanner(settings: dict[str, Any] | None = None) -> Scanner:
    settings = settings or {}
    context_defaults = {
        "target_width": int(settings.get("target_width", 1024)),
        "target_height": int(settings.get("target_height", 1536)),
        "allow_aspect_ratio_tolerance": float(
            settings.get("allow_aspect_ratio_tolerance", 0.05)
        ),
        "scan_duplicate": bool(settings.get("scan_duplicate", True)),
    }

    detectors: list[BaseDetector] = [
        FileDetector(),
        _ContextResolutionDetector(context_defaults),
        BrightnessDetector(),
        _ContextDuplicateDetector(context_defaults),
    ]
    return Scanner(detectors)


class _ContextResolutionDetector(ResolutionDetector):
    def __init__(self, defaults: dict[str, Any]) -> None:
        self.defaults = defaults

    def detect(self, image, file_path, context):
        merged = {**self.defaults, **context}
        return super().detect(image, file_path, merged)


class _ContextDuplicateDetector(DuplicateDetector):
    def __init__(self, defaults: dict[str, Any]) -> None:
        self.defaults = defaults

    def detect(self, image, file_path, context):
        merged = {**self.defaults, **context}
        if "seen_hashes" in context:
            merged["seen_hashes"] = context["seen_hashes"]
        issues = super().detect(image, file_path, merged)
        if "seen_hashes" in merged:
            context["seen_hashes"] = merged["seen_hashes"]
        return issues

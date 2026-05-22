from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from PIL import Image, UnidentifiedImageError

from hateneko.core.scan_result import Issue, ScanResult
from hateneko.detectors.base import BaseDetector
from hateneko.detectors.brightness_detector import BrightnessDetector
from hateneko.detectors.duplicate_detector import DuplicateDetector
from hateneko.detectors.face_detector import FaceDetector
from hateneko.detectors.file_detector import FileDetector
from hateneko.detectors.hand_detector import HandDetector
from hateneko.detectors.pose_detector import PoseDetector
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
        "scan_near_duplicate": bool(settings.get("scan_near_duplicate", True)),
        "perceptual_hash_threshold": int(settings.get("perceptual_hash_threshold", 6)),
        "expected_person_count": int(settings.get("expected_person_count", 1)),
        "scan_face_count": bool(settings.get("scan_face_count", True)),
        "scan_zero_faces": bool(settings.get("scan_zero_faces", False)),
        "scan_pose_checks": bool(settings.get("scan_pose_checks", False)),
        "scan_missing_pose": bool(settings.get("scan_missing_pose", False)),
        "pose_max_poses": int(settings.get("pose_max_poses", 2)),
        "scan_hand_checks": bool(settings.get("scan_hand_checks", False)),
        "expected_hand_count": int(settings.get("expected_hand_count", 2)),
        "max_hands_to_detect": int(settings.get("max_hands_to_detect", 4)),
        "mediapipe_delegate": str(settings.get("mediapipe_delegate", "CPU")),
    }

    detectors: list[BaseDetector] = [
        FileDetector(),
        _ContextResolutionDetector(context_defaults),
        BrightnessDetector(),
        _ContextDuplicateDetector(context_defaults),
        _ContextFaceDetector(context_defaults),
        _ContextPoseDetector(context_defaults),
        _ContextHandDetector(context_defaults),
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
        if "seen_phashes" in context:
            merged["seen_phashes"] = context["seen_phashes"]
        issues = super().detect(image, file_path, merged)
        if "seen_hashes" in merged:
            context["seen_hashes"] = merged["seen_hashes"]
        if "seen_phashes" in merged:
            context["seen_phashes"] = merged["seen_phashes"]
        return issues


class _ContextFaceDetector(FaceDetector):
    def __init__(self, defaults: dict[str, Any]) -> None:
        self.defaults = defaults

    def detect(self, image, file_path, context):
        merged = {**self.defaults, **context}
        return super().detect(image, file_path, merged)


class _ContextPoseDetector(PoseDetector):
    def __init__(self, defaults: dict[str, Any]) -> None:
        super().__init__()
        self.defaults = defaults

    def detect(self, image, file_path, context):
        merged = {**self.defaults, **context}
        issues = super().detect(image, file_path, merged)
        context["pose_landmarks"] = merged.get("pose_landmarks", [])
        context["pose_bboxes"] = merged.get("pose_bboxes", [])
        context["pose_image_size"] = merged.get("pose_image_size")
        return issues


class _ContextHandDetector(HandDetector):
    def __init__(self, defaults: dict[str, Any]) -> None:
        super().__init__()
        self.defaults = defaults

    def detect(self, image, file_path, context):
        merged = {**self.defaults, **context}
        issues = super().detect(image, file_path, merged)
        context["hand_landmarks"] = merged.get("hand_landmarks", [])
        return issues

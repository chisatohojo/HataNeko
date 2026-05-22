from __future__ import annotations

from pathlib import Path
from math import acos, degrees, hypot
from typing import Any

from PIL.Image import Image

from hateneko.core.model_assets import (
    ModelDownloadError,
    POSE_LANDMARKER_LITE,
    ensure_model,
)
from hateneko.core.scan_result import Issue
from hateneko.detectors.base import BaseDetector

try:
    import mediapipe as mp
    import numpy as np
    from mediapipe.tasks import python
    from mediapipe.tasks.python import vision
except ImportError:  # pragma: no cover - optional runtime dependency
    mp = None
    np = None
    python = None
    vision = None


class PoseDetector(BaseDetector):
    """MediaPipe Pose based checks for arm and pose anomalies."""

    name = "pose"

    def __init__(self) -> None:
        self._landmarker = None

    def detect(
        self,
        image: Image | None,
        file_path: str | Path,
        context: dict[str, Any],
    ) -> list[Issue]:
        context["pose_landmarks"] = []
        context["pose_bboxes"] = []
        if image is None or not context.get("scan_pose_checks", True):
            return []
        if mp is None or np is None or python is None or vision is None:
            return [
                Issue(
                    type="pose_detector_unavailable",
                    severity="warning",
                    message="MediaPipe が利用できないため姿勢チェックを実行できません。",
                )
            ]

        try:
            landmarker = self._get_landmarker(context)
        except ModelDownloadError as exc:
            return [
                Issue(
                    type="pose_model_unavailable",
                    severity="warning",
                    message=str(exc),
                )
            ]

        rgb = image.convert("RGB")
        array = np.asarray(rgb, dtype=np.uint8)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=array)
        result = landmarker.detect(mp_image)
        poses = list(result.pose_landmarks or [])
        context["pose_landmarks"] = poses
        context["pose_image_size"] = image.size
        context["pose_bboxes"] = [
            _landmark_bbox(pose, image.size, min_visibility=0.2) for pose in poses
        ]

        expected = int(context.get("expected_person_count", 1))
        issues: list[Issue] = []
        if len(poses) == 0 and context.get("scan_missing_pose", False):
            issues.append(
                Issue(
                    type="no_pose_detected",
                    severity="warning",
                    message="姿勢ランドマークが検出されませんでした。必要に応じて確認してください。",
                )
            )
        elif expected > 0 and len(poses) > expected:
            issues.append(
                Issue(
                    type="too_many_poses",
                    severity="warning",
                    message=f"{expected}人想定ですが、姿勢候補が {len(poses)} 件検出されました。",
                )
            )
            for bbox in context["pose_bboxes"]:
                if bbox is not None:
                    issues.append(
                        Issue(
                            type="pose_candidate_region",
                            severity="warning",
                            message="姿勢候補領域です。",
                            bbox=bbox,
                        )
                    )

        for pose_index, pose in enumerate(poses):
            issues.extend(self._check_arms(pose, image.size, pose_index, context))
        return issues

    def _get_landmarker(self, context: dict[str, Any]):
        if self._landmarker is not None:
            return self._landmarker

        model_path = ensure_model(POSE_LANDMARKER_LITE)
        base_options = python.BaseOptions(model_asset_path=str(model_path))
        options = vision.PoseLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.IMAGE,
            num_poses=max(1, int(context.get("pose_max_poses", 2))),
            min_pose_detection_confidence=float(
                context.get("pose_min_detection_confidence", 0.5)
            ),
            min_pose_presence_confidence=float(
                context.get("pose_min_presence_confidence", 0.5)
            ),
        )
        self._landmarker = vision.PoseLandmarker.create_from_options(options)
        return self._landmarker

    def _check_arms(
        self,
        pose,
        image_size: tuple[int, int],
        pose_index: int,
        context: dict[str, Any],
    ) -> list[Issue]:
        issues: list[Issue] = []
        min_visibility = float(context.get("min_pose_landmark_visibility", 0.35))
        sides = [
            ("left", 11, 13, 15),
            ("right", 12, 14, 16),
        ]

        for side, shoulder_index, elbow_index, wrist_index in sides:
            shoulder = pose[shoulder_index]
            elbow = pose[elbow_index]
            wrist = pose[wrist_index]
            if not _visible(shoulder, min_visibility) or not _visible(elbow, min_visibility):
                continue
            if not _visible(wrist, min_visibility):
                continue

            angle = _angle_degrees(shoulder, elbow, wrist)
            bbox = _points_bbox([shoulder, elbow, wrist], image_size)
            label = "左" if side == "left" else "右"
            if angle is not None and angle < float(context.get("min_elbow_angle", 18.0)):
                issues.append(
                    Issue(
                        type="arm_angle_too_sharp",
                        severity="warning",
                        message=f"{label}腕の肘角度が極端に小さい候補です: {angle:.1f}度",
                        bbox=bbox,
                        score=angle,
                    )
                )

            upper = _distance(shoulder, elbow)
            lower = _distance(elbow, wrist)
            if upper > 0 and lower > 0:
                ratio = max(upper, lower) / min(upper, lower)
                if ratio > float(context.get("arm_segment_ratio_limit", 2.6)):
                    issues.append(
                        Issue(
                            type="arm_segment_ratio_suspicious",
                            severity="warning",
                            message=f"{label}腕の上腕/前腕比が大きく異なる候補です: {ratio:.2f}",
                            bbox=bbox,
                            score=ratio,
                        )
                    )

            body_scale = _body_scale(pose)
            shoulder_to_wrist = _distance(shoulder, wrist)
            if body_scale > 0 and shoulder_to_wrist / body_scale > float(
                context.get("arm_length_body_ratio_limit", 2.4)
            ):
                issues.append(
                    Issue(
                        type="arm_too_long_candidate",
                        severity="warning",
                        message=f"{label}腕が体の基準長に対して長すぎる候補です。",
                        bbox=bbox,
                        score=shoulder_to_wrist / body_scale,
                    )
                )
        return issues


def _visible(landmark, min_visibility: float) -> bool:
    visibility = getattr(landmark, "visibility", None)
    if visibility is None:
        return True
    return visibility >= min_visibility


def _distance(a, b) -> float:
    return hypot(a.x - b.x, a.y - b.y)


def _angle_degrees(a, b, c) -> float | None:
    ba = (a.x - b.x, a.y - b.y)
    bc = (c.x - b.x, c.y - b.y)
    ba_len = hypot(*ba)
    bc_len = hypot(*bc)
    if ba_len == 0 or bc_len == 0:
        return None
    cosine = (ba[0] * bc[0] + ba[1] * bc[1]) / (ba_len * bc_len)
    cosine = max(-1.0, min(1.0, cosine))
    return degrees(acos(cosine))


def _body_scale(pose) -> float:
    distances = []
    pairs = [(11, 12), (23, 24), (11, 23), (12, 24)]
    for first, second in pairs:
        distances.append(_distance(pose[first], pose[second]))
    return max(distances, default=0.0)


def _points_bbox(points, image_size: tuple[int, int]) -> tuple[int, int, int, int]:
    width, height = image_size
    xs = [max(0.0, min(1.0, point.x)) for point in points]
    ys = [max(0.0, min(1.0, point.y)) for point in points]
    left = int(min(xs) * width)
    top = int(min(ys) * height)
    right = int(max(xs) * width)
    bottom = int(max(ys) * height)
    pad = max(8, int(min(width, height) * 0.02))
    left = max(0, left - pad)
    top = max(0, top - pad)
    right = min(width, right + pad)
    bottom = min(height, bottom + pad)
    return (left, top, max(8, right - left), max(8, bottom - top))


def _landmark_bbox(
    landmarks,
    image_size: tuple[int, int],
    min_visibility: float,
) -> tuple[int, int, int, int] | None:
    visible = [landmark for landmark in landmarks if _visible(landmark, min_visibility)]
    if not visible:
        return None
    return _points_bbox(visible, image_size)

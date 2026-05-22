from __future__ import annotations

from pathlib import Path
from itertools import combinations
from math import hypot
from typing import Any

from PIL.Image import Image

from hateneko.core.model_assets import (
    HAND_LANDMARKER,
    ModelDownloadError,
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


class HandDetector(BaseDetector):
    """MediaPipe Hands based checks for hand and finger candidates."""

    name = "hand"
    fingertip_indexes = (4, 8, 12, 16, 20)

    def __init__(self) -> None:
        self._landmarker = None

    def detect(
        self,
        image: Image | None,
        file_path: str | Path,
        context: dict[str, Any],
    ) -> list[Issue]:
        context["hand_landmarks"] = []
        if image is None or not context.get("scan_hand_checks", True):
            return []
        if mp is None or np is None or python is None or vision is None:
            return [
                Issue(
                    type="hand_detector_unavailable",
                    severity="warning",
                    message="MediaPipe が利用できないため手・指チェックを実行できません。",
                )
            ]

        try:
            landmarker = self._get_landmarker(context)
        except ModelDownloadError as exc:
            return [
                Issue(
                    type="hand_model_unavailable",
                    severity="warning",
                    message=str(exc),
                )
            ]

        rgb = image.convert("RGB")
        array = np.asarray(rgb, dtype=np.uint8)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=array)
        result = landmarker.detect(mp_image)
        hands = list(result.hand_landmarks or [])
        context["hand_landmarks"] = hands

        issues: list[Issue] = []
        expected_person_count = int(context.get("expected_person_count", 1))
        expected_hands = int(context.get("expected_hand_count", expected_person_count * 2))
        if expected_hands > 0 and len(hands) > expected_hands:
            issues.append(
                Issue(
                    type="too_many_hands",
                    severity="warning",
                    message=f"{expected_hands}手想定ですが、手候補が {len(hands)} 件検出されました。",
                )
            )
            for hand in hands:
                issues.append(
                    Issue(
                        type="hand_candidate_region",
                        severity="warning",
                        message="手候補領域です。",
                        bbox=_hand_bbox(hand, image.size),
                    )
                )

        for hand_index, hand in enumerate(hands):
            bbox = _hand_bbox(hand, image.size)
            issues.extend(self._check_fingers(hand, bbox, hand_index, context))
            detached = self._detached_from_pose(hand, context)
            if detached is not None:
                issues.append(
                    Issue(
                        type="detached_hand_candidate",
                        severity="warning",
                        message=f"姿勢の手首位置から離れた手候補です: 距離 {detached:.3f}",
                        bbox=bbox,
                        score=detached,
                    )
                )
        return issues

    def _get_landmarker(self, context: dict[str, Any]):
        if self._landmarker is not None:
            return self._landmarker

        model_path = ensure_model(HAND_LANDMARKER)
        base_options = python.BaseOptions(model_asset_path=str(model_path))
        options = vision.HandLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.IMAGE,
            num_hands=max(1, int(context.get("max_hands_to_detect", 4))),
            min_hand_detection_confidence=float(
                context.get("hand_min_detection_confidence", 0.5)
            ),
            min_hand_presence_confidence=float(
                context.get("hand_min_presence_confidence", 0.5)
            ),
        )
        self._landmarker = vision.HandLandmarker.create_from_options(options)
        return self._landmarker

    def _check_fingers(
        self,
        hand,
        bbox: tuple[int, int, int, int],
        hand_index: int,
        context: dict[str, Any],
    ) -> list[Issue]:
        issues: list[Issue] = []
        fingertips = [hand[index] for index in self.fingertip_indexes]
        hand_size = _hand_size(hand)
        if hand_size <= 0:
            return issues

        min_tip_distance = min(
            (_distance(first, second) for first, second in combinations(fingertips, 2)),
            default=1.0,
        )
        if min_tip_distance / hand_size < float(context.get("finger_cluster_ratio", 0.08)):
            issues.append(
                Issue(
                    type="fingertips_clustered",
                    severity="warning",
                    message="指先候補が極端に密集しています。",
                    bbox=bbox,
                    score=min_tip_distance / hand_size,
                )
            )

        lengths = [_distance(hand[0], fingertip) for fingertip in fingertips]
        shortest = min((length for length in lengths if length > 0), default=0.0)
        longest = max(lengths, default=0.0)
        if shortest > 0:
            ratio = longest / shortest
            if ratio > float(context.get("finger_length_ratio_limit", 3.5)):
                issues.append(
                    Issue(
                        type="finger_length_outlier",
                        severity="warning",
                        message=f"指先候補の長さ差が大きい手です: {ratio:.2f}",
                        bbox=bbox,
                        score=ratio,
                    )
                )

        palm_width = _distance(hand[5], hand[17])
        wrist_to_middle = _distance(hand[0], hand[12])
        if palm_width > 0 and wrist_to_middle / palm_width > float(
            context.get("finger_palm_ratio_limit", 3.8)
        ):
            issues.append(
                Issue(
                    type="finger_too_long_candidate",
                    severity="warning",
                    message="手のひらに対して指が長すぎる候補です。",
                    bbox=bbox,
                    score=wrist_to_middle / palm_width,
                )
            )
        return issues

    def _detached_from_pose(self, hand, context: dict[str, Any]) -> float | None:
        poses = context.get("pose_landmarks") or []
        if not poses:
            return None
        hand_wrist = hand[0]
        pose_wrists = []
        for pose in poses:
            pose_wrists.extend([pose[15], pose[16]])
        if not pose_wrists:
            return None
        distance = min(_distance(hand_wrist, wrist) for wrist in pose_wrists)
        threshold = float(context.get("hand_pose_wrist_distance_limit", 0.18))
        if distance > threshold:
            return distance
        return None


def _distance(a, b) -> float:
    return hypot(a.x - b.x, a.y - b.y)


def _hand_size(hand) -> float:
    bbox = _normalized_bbox(hand)
    return hypot(bbox[2], bbox[3])


def _normalized_bbox(hand) -> tuple[float, float, float, float]:
    xs = [max(0.0, min(1.0, landmark.x)) for landmark in hand]
    ys = [max(0.0, min(1.0, landmark.y)) for landmark in hand]
    left = min(xs)
    top = min(ys)
    right = max(xs)
    bottom = max(ys)
    return (left, top, max(0.0, right - left), max(0.0, bottom - top))


def _hand_bbox(hand, image_size: tuple[int, int]) -> tuple[int, int, int, int]:
    image_width, image_height = image_size
    left, top, width, height = _normalized_bbox(hand)
    pad = max(8, int(min(image_width, image_height) * 0.02))
    pixel_left = max(0, int(left * image_width) - pad)
    pixel_top = max(0, int(top * image_height) - pad)
    pixel_right = min(image_width, int((left + width) * image_width) + pad)
    pixel_bottom = min(image_height, int((top + height) * image_height) + pad)
    return (
        pixel_left,
        pixel_top,
        max(8, pixel_right - pixel_left),
        max(8, pixel_bottom - pixel_top),
    )

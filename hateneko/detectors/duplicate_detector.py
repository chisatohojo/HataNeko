from __future__ import annotations

from pathlib import Path
from typing import Any

import imagehash
from PIL.Image import Image

from hateneko.core.hash_checker import sha256_file
from hateneko.core.scan_result import Issue
from hateneko.detectors.base import BaseDetector


class DuplicateDetector(BaseDetector):
    name = "duplicate"

    def detect(
        self,
        image: Image | None,
        file_path: str | Path,
        context: dict[str, Any],
    ) -> list[Issue]:
        if not context.get("scan_duplicate", True):
            return []

        path = Path(file_path)
        if not path.exists() or not path.is_file():
            return []

        seen_hashes: dict[str, str] = context.setdefault("seen_hashes", {})
        try:
            digest = sha256_file(path)
        except OSError as exc:
            return [
                Issue(
                    type="hash_error",
                    severity="warning",
                    message=f"重複チェック用ハッシュを計算できません: {exc}",
                )
            ]

        original = seen_hashes.get(digest)
        if original and Path(original) != path:
            return [
                Issue(
                    type="duplicate_exact",
                    severity="warning",
                    message=f"完全一致の重複画像候補です: {Path(original).name}",
                )
            ]

        seen_hashes[digest] = str(path)

        if image is None or not context.get("scan_near_duplicate", True):
            return []

        try:
            perceptual_hash = imagehash.phash(image)
        except Exception as exc:
            return [
                Issue(
                    type="perceptual_hash_error",
                    severity="warning",
                    message=f"近似重複チェック用ハッシュを計算できません: {exc}",
                )
            ]

        threshold = int(context.get("perceptual_hash_threshold", 6))
        seen_phashes: list[tuple[str, Any]] = context.setdefault("seen_phashes", [])
        for original_path, original_hash in seen_phashes:
            distance = perceptual_hash - original_hash
            if distance <= threshold:
                return [
                    Issue(
                        type="duplicate_near",
                        severity="warning",
                        message=(
                            "近似重複画像候補です: "
                            f"{Path(original_path).name} / 距離 {distance}"
                        ),
                        score=float(distance),
                    )
                ]

        seen_phashes.append((str(path), perceptual_hash))
        return []

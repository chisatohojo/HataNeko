from __future__ import annotations

from pathlib import Path
from typing import Any

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
        return []


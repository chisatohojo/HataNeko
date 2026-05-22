from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL.Image import Image

from hateneko.core.scan_result import Issue
from hateneko.detectors.base import BaseDetector


class FileDetector(BaseDetector):
    name = "file"

    def detect(
        self,
        image: Image | None,
        file_path: str | Path,
        context: dict[str, Any],
    ) -> list[Issue]:
        path = Path(file_path)
        issues: list[Issue] = []
        if not path.exists():
            return [
                Issue(
                    type="file_missing",
                    severity="danger",
                    message="ファイルが見つかりません。",
                )
            ]

        try:
            size = path.stat().st_size
        except OSError as exc:
            return [
                Issue(
                    type="file_stat_error",
                    severity="danger",
                    message=f"ファイル情報を取得できません: {exc}",
                )
            ]

        if size <= int(context.get("min_file_size_bytes", 8)):
            issues.append(
                Issue(
                    type="file_too_small",
                    severity="danger",
                    message="ファイルサイズが極端に小さいため、画像異常の可能性があります。",
                )
            )
        if image is None:
            issues.append(
                Issue(
                    type="image_open_error",
                    severity="danger",
                    message="画像として読み込めませんでした。",
                )
            )
        return issues


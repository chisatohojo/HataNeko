from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import imagehash
from PIL import Image

from hateneko.core.hash_checker import sha256_file
from hateneko.core.scan_result import Issue, ScanResult
from hateneko.core.scanner import build_default_scanner


ProgressCallback = Callable[[str, ScanResult, int, int], None]

_thread_state = threading.local()


@dataclass(slots=True)
class FastScanItem:
    path: Path
    result: ScanResult
    exact_hash: str | None = None
    perceptual_hash: Any | None = None


def scan_images_parallel(
    image_paths: list[Path],
    settings: dict[str, Any],
    progress: ProgressCallback | None = None,
) -> dict[str, ScanResult]:
    if not image_paths:
        return {}

    worker_count = _worker_count(settings)
    total = len(image_paths)
    completed = 0
    items: list[FastScanItem] = []

    with ThreadPoolExecutor(max_workers=worker_count, thread_name_prefix="hateneko-scan") as executor:
        futures = [
            executor.submit(_scan_one_image, path, dict(settings))
            for path in image_paths
        ]
        for future in as_completed(futures):
            item = future.result()
            items.append(item)
            completed += 1
            if progress is not None:
                progress(str(item.path), item.result, completed, total)

    ordered_items = sorted(items, key=lambda item: image_paths.index(item.path))
    if settings.get("scan_duplicate", True):
        _append_duplicate_issues(ordered_items, settings)

    results = {str(item.path): item.result for item in ordered_items}
    if progress is not None:
        for item in ordered_items:
            progress(str(item.path), item.result, total, total)
    return results


def _scan_one_image(path: Path, settings: dict[str, Any]) -> FastScanItem:
    scanner = _scanner_for_thread(settings)
    scan_settings = dict(settings)
    scan_settings["scan_duplicate"] = False
    result = scanner.scan_image(path, {})

    exact_hash = None
    perceptual_hash = None
    if settings.get("scan_duplicate", True):
        try:
            exact_hash = sha256_file(path)
        except OSError as exc:
            result.issues.append(
                Issue(
                    type="hash_error",
                    severity="warning",
                    message=f"重複チェック用ハッシュを計算できません: {exc}",
                )
            )

    if (
        settings.get("scan_duplicate", True)
        and settings.get("scan_near_duplicate", True)
        and path.exists()
    ):
        try:
            with Image.open(path) as image:
                perceptual_hash = imagehash.phash(image)
        except Exception as exc:
            result.issues.append(
                Issue(
                    type="perceptual_hash_error",
                    severity="warning",
                    message=f"近似重複チェック用ハッシュを計算できません: {exc}",
                )
            )

    return FastScanItem(
        path=path,
        result=_refresh_result(result),
        exact_hash=exact_hash,
        perceptual_hash=perceptual_hash,
    )


def _scanner_for_thread(settings: dict[str, Any]):
    signature = (
        int(settings.get("target_width", 1024)),
        int(settings.get("target_height", 1536)),
        float(settings.get("allow_aspect_ratio_tolerance", 0.05)),
        bool(settings.get("scan_face_count", True)),
        bool(settings.get("scan_pose_checks", False)),
        bool(settings.get("scan_hand_checks", False)),
        str(settings.get("mediapipe_delegate", "CPU")),
    )
    if getattr(_thread_state, "signature", None) != signature:
        scan_settings = dict(settings)
        scan_settings["scan_duplicate"] = False
        _thread_state.scanner = build_default_scanner(scan_settings)
        _thread_state.signature = signature
    return _thread_state.scanner


def _append_duplicate_issues(
    items: list[FastScanItem],
    settings: dict[str, Any],
) -> None:
    seen_exact: dict[str, Path] = {}
    exact_duplicate_paths: set[Path] = set()
    for item in items:
        if item.exact_hash is None:
            continue
        original = seen_exact.get(item.exact_hash)
        if original is not None and original != item.path:
            exact_duplicate_paths.add(item.path)
            item.result.issues.append(
                Issue(
                    type="duplicate_exact",
                    severity="warning",
                    message=f"完全一致の重複画像候補です: {original.name}",
                )
            )
        else:
            seen_exact[item.exact_hash] = item.path

    if settings.get("scan_near_duplicate", True):
        threshold = int(settings.get("perceptual_hash_threshold", 6))
        seen_phashes: list[tuple[Path, Any]] = []
        for item in items:
            if item.perceptual_hash is None or item.path in exact_duplicate_paths:
                continue
            for original_path, original_hash in seen_phashes:
                distance = item.perceptual_hash - original_hash
                if distance <= threshold:
                    item.result.issues.append(
                        Issue(
                            type="duplicate_near",
                            severity="warning",
                            message=(
                                "近似重複画像候補です: "
                                f"{original_path.name} / 距離 {distance}"
                            ),
                            score=float(distance),
                        )
                    )
                    break
            else:
                seen_phashes.append((item.path, item.perceptual_hash))

    for item in items:
        item.result = _refresh_result(item.result)


def _refresh_result(result: ScanResult) -> ScanResult:
    return ScanResult.from_issues(result.file_path, result.issues)


def _worker_count(settings: dict[str, Any]) -> int:
    requested = int(settings.get("scan_worker_count", 0))
    if requested > 0:
        return requested
    cpu_count = os.cpu_count() or 4
    return max(2, cpu_count)

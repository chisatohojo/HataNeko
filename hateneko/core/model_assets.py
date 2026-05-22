from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlretrieve

from hateneko.core.paths import model_dir


@dataclass(frozen=True, slots=True)
class ModelAsset:
    filename: str
    url: str

    @property
    def path(self) -> Path:
        return model_dir() / self.filename


HAND_LANDMARKER = ModelAsset(
    filename="hand_landmarker.task",
    url=(
        "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
        "hand_landmarker/float16/latest/hand_landmarker.task"
    ),
)

POSE_LANDMARKER_LITE = ModelAsset(
    filename="pose_landmarker_lite.task",
    url=(
        "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
        "pose_landmarker_lite/float16/latest/pose_landmarker_lite.task"
    ),
)


class ModelDownloadError(RuntimeError):
    pass


def ensure_model(asset: ModelAsset) -> Path:
    path = asset.path
    if path.exists() and path.stat().st_size > 0:
        return path

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".download")
    try:
        urlretrieve(asset.url, tmp_path)
        tmp_path.replace(path)
    except (OSError, URLError) as exc:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        raise ModelDownloadError(f"モデルを取得できませんでした: {asset.url} / {exc}") from exc
    return path

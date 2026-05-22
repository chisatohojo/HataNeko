from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image, UnidentifiedImageError


SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


@dataclass(frozen=True, slots=True)
class ImageInfo:
    path: Path
    width: int | None
    height: int | None
    size_bytes: int
    error: str | None = None


class ImageLoader:
    def __init__(self, extensions: set[str] | None = None) -> None:
        self.extensions = {ext.lower() for ext in (extensions or SUPPORTED_EXTENSIONS)}

    def list_images(self, folder: str | Path) -> list[Path]:
        base = Path(folder)
        if not base.exists() or not base.is_dir():
            return []

        paths = [
            path
            for path in base.iterdir()
            if path.is_file() and path.suffix.lower() in self.extensions
        ]
        return sorted(paths, key=lambda path: path.name.casefold())

    def get_info(self, file_path: str | Path) -> ImageInfo:
        path = Path(file_path)
        size = path.stat().st_size if path.exists() else 0
        try:
            with Image.open(path) as image:
                width, height = image.size
            return ImageInfo(path=path, width=width, height=height, size_bytes=size)
        except (OSError, UnidentifiedImageError) as exc:
            return ImageInfo(
                path=path,
                width=None,
                height=None,
                size_bytes=size,
                error=str(exc),
            )


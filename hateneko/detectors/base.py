from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from PIL.Image import Image

from hateneko.core.scan_result import Issue


class BaseDetector(ABC):
    name = "base"

    @abstractmethod
    def detect(
        self,
        image: Image | None,
        file_path: str | Path,
        context: dict[str, Any],
    ) -> list[Issue]:
        raise NotImplementedError


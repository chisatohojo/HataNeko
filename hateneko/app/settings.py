from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEFAULT_SETTINGS: dict[str, Any] = {
    "expected_person_count": 1,
    "target_width": 1024,
    "target_height": 1536,
    "allow_aspect_ratio_tolerance": 0.05,
    "delete_mode": "move_to_deleted_folder",
    "thumbnail_size": 160,
    "auto_advance_after_action": True,
    "show_overlay": True,
    "scan_face_count": True,
    "scan_zero_faces": False,
    "scan_duplicate": True,
    "scan_near_duplicate": True,
    "perceptual_hash_threshold": 6,
}


class SettingsManager:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path else self.default_path()
        self.data = dict(DEFAULT_SETTINGS)
        self.load()

    @staticmethod
    def default_path() -> Path:
        return Path(__file__).resolve().parents[2] / "settings.json"

    def load(self) -> dict[str, Any]:
        should_save = not self.path.exists()
        if self.path.exists():
            try:
                loaded = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    self.data.update(loaded)
                    should_save = any(key not in loaded for key in DEFAULT_SETTINGS)
            except (OSError, json.JSONDecodeError):
                should_save = True
        if should_save:
            self.save()
        return self.data

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.data[key] = value
        self.save()

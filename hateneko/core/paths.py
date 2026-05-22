from __future__ import annotations

import sys
from pathlib import Path


APP_DIR_NAME = "HataNekoData"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def bundled_root() -> Path:
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS")).resolve()
    return project_root()


def resource_path(relative_path: str | Path) -> Path:
    return bundled_root() / relative_path


def executable_dir() -> Path:
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return project_root()


def user_data_dir() -> Path:
    if is_frozen():
        return executable_dir() / APP_DIR_NAME
    return project_root()


def settings_path() -> Path:
    return user_data_dir() / "settings.json"


def model_dir() -> Path:
    return user_data_dir() / "models"

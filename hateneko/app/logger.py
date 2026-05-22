from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from hateneko.core.file_manager import LOG_FOLDER


class ActionLogger:
    def __init__(self) -> None:
        self.log_path: Path | None = None

    def set_base_folder(self, base_folder: str | Path) -> None:
        log_dir = Path(base_folder) / LOG_FOLDER
        log_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = log_dir / "action_log.jsonl"

    def log(self, action: str, **payload: Any) -> None:
        if self.log_path is None:
            return
        row = {
            "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
            "action": action,
            **payload,
        }
        with self.log_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")


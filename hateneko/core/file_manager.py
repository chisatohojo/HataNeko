from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

try:
    from send2trash import send2trash
except ImportError:  # pragma: no cover - optional runtime dependency
    send2trash = None


CATEGORY_FOLDERS = {
    "ok": "_hateneko_ok",
    "fix": "_hateneko_fix",
    "ng": "_hateneko_ng",
    "deleted": "_hateneko_deleted",
}
LOG_FOLDER = "_hateneko_logs"


@dataclass(slots=True)
class MoveRecord:
    action: str
    source: Path
    destination: Path | None
    undoable: bool = True


class FileManager:
    def ensure_output_dirs(self, base_folder: str | Path) -> dict[str, Path]:
        base = Path(base_folder)
        folders = {
            category: base / folder_name
            for category, folder_name in CATEGORY_FOLDERS.items()
        }
        folders["logs"] = base / LOG_FOLDER
        for folder in folders.values():
            folder.mkdir(parents=True, exist_ok=True)
        return folders

    def move_to_category(
        self,
        source: str | Path,
        base_folder: str | Path,
        category: str,
        delete_mode: str = "move_to_deleted_folder",
    ) -> MoveRecord:
        source_path = Path(source)
        if category not in CATEGORY_FOLDERS:
            raise ValueError(f"Unknown category: {category}")
        if not source_path.exists():
            raise FileNotFoundError(source_path)

        action = f"move_to_{category}"
        if category == "deleted" and delete_mode == "send_to_recycle_bin":
            if send2trash is None:
                raise RuntimeError("send2trash is not installed.")
            send2trash(str(source_path))
            return MoveRecord(
                action="send_to_recycle_bin",
                source=source_path,
                destination=None,
                undoable=False,
            )

        folders = self.ensure_output_dirs(base_folder)
        destination = self.unique_destination(folders[category] / source_path.name)
        shutil.move(str(source_path), str(destination))
        return MoveRecord(action=action, source=source_path, destination=destination)

    def undo_move(self, record: MoveRecord) -> Path:
        if not record.undoable or record.destination is None:
            raise RuntimeError("This action cannot be undone.")
        if not record.destination.exists():
            raise FileNotFoundError(record.destination)

        destination = self.unique_destination(record.source)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(record.destination), str(destination))
        return destination

    def unique_destination(self, desired_path: str | Path) -> Path:
        desired = Path(desired_path)
        if not desired.exists():
            return desired

        stem = desired.stem
        suffix = desired.suffix
        parent = desired.parent
        counter = 1
        while True:
            candidate = parent / f"{stem}_{counter:03d}{suffix}"
            if not candidate.exists():
                return candidate
            counter += 1


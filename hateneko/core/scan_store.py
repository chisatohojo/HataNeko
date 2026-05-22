from __future__ import annotations

import json
from pathlib import Path

from hateneko.core.file_manager import LOG_FOLDER
from hateneko.core.scan_result import ScanResult


SCAN_RESULTS_FILE = "scan_results.json"


class ScanResultStore:
    def path_for(self, base_folder: str | Path) -> Path:
        return Path(base_folder) / LOG_FOLDER / SCAN_RESULTS_FILE

    def load(
        self,
        base_folder: str | Path,
        image_paths: list[Path],
    ) -> dict[str, ScanResult]:
        store_path = self.path_for(base_folder)
        if not store_path.exists():
            return {}

        allowed_paths = {str(path) for path in image_paths}
        try:
            payload = json.loads(store_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

        raw_results = payload.get("results", []) if isinstance(payload, dict) else []
        results: dict[str, ScanResult] = {}
        for raw in raw_results:
            if not isinstance(raw, dict):
                continue
            result = ScanResult.from_dict(raw)
            path = str(Path(result.file_path))
            if path in allowed_paths and Path(path).exists():
                results[path] = result
        return results

    def save(
        self,
        base_folder: str | Path,
        scan_results: dict[str, ScanResult],
    ) -> Path:
        store_path = self.path_for(base_folder)
        store_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "results": [
                result.to_dict()
                for path, result in sorted(scan_results.items())
                if Path(path).exists()
            ],
        }
        store_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return store_path

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image

from hateneko.core.scan_result import Issue, ScanResult
from hateneko.core.scan_store import ScanResultStore


class ScanResultStoreTest(unittest.TestCase):
    def test_save_and_load_scan_results(self) -> None:
        with TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            image_path = base / "sample.png"
            Image.new("RGB", (64, 64), (10, 20, 30)).save(image_path)

            result = ScanResult.from_issues(
                image_path,
                [
                    Issue(
                        type="too_many_faces",
                        severity="warning",
                        message="顔候補が多すぎます。",
                        bbox=(1, 2, 3, 4),
                    )
                ],
            )

            store = ScanResultStore()
            store.save(base, {str(image_path): result})
            loaded = store.load(base, [image_path])

            self.assertIn(str(image_path), loaded)
            self.assertEqual(loaded[str(image_path)].issue_types, ["too_many_faces"])
            self.assertEqual(loaded[str(image_path)].issues[0].bbox, (1, 2, 3, 4))


if __name__ == "__main__":
    unittest.main()

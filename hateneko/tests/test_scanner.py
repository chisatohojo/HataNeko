from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image

from hateneko.core.scanner import build_default_scanner


class ScannerTest(unittest.TestCase):
    def test_resolution_and_solid_color_are_reported(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "solid.png"
            Image.new("RGB", (512, 512), (0, 0, 0)).save(path)

            scanner = build_default_scanner(
                {
                    "target_width": 1024,
                    "target_height": 1536,
                    "allow_aspect_ratio_tolerance": 0.05,
                }
            )
            result = scanner.scan_image(path, {})

            self.assertTrue(result.suspicious)
            self.assertIn("resolution_mismatch", result.issue_types)
            self.assertIn("aspect_ratio_mismatch", result.issue_types)
            self.assertIn("almost_black", result.issue_types)

    def test_exact_duplicate_is_reported_for_later_file(self) -> None:
        with TemporaryDirectory() as temp_dir:
            first = Path(temp_dir) / "a.png"
            second = Path(temp_dir) / "b.png"
            Image.new("RGB", (1024, 1536), (10, 20, 30)).save(first)
            second.write_bytes(first.read_bytes())

            scanner = build_default_scanner({"target_width": 1024, "target_height": 1536})
            context: dict[str, object] = {}
            first_result = scanner.scan_image(first, context)
            second_result = scanner.scan_image(second, context)

            self.assertNotIn("duplicate_exact", first_result.issue_types)
            self.assertIn("duplicate_exact", second_result.issue_types)


if __name__ == "__main__":
    unittest.main()


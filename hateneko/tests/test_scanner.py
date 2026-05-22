from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image, ImageDraw

from hateneko.core.fast_scanner import scan_images_parallel
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

    def test_near_duplicate_is_reported_for_perceptual_match(self) -> None:
        with TemporaryDirectory() as temp_dir:
            first = Path(temp_dir) / "a.png"
            second = Path(temp_dir) / "b.jpg"

            image = Image.new("RGB", (256, 256), (245, 245, 245))
            draw = ImageDraw.Draw(image)
            draw.rectangle((40, 50, 210, 190), fill=(30, 120, 210))
            draw.ellipse((90, 80, 170, 160), fill=(240, 180, 40))
            image.save(first)
            image.save(second, quality=92)

            scanner = build_default_scanner(
                {
                    "target_width": 256,
                    "target_height": 256,
                    "scan_duplicate": True,
                    "scan_near_duplicate": True,
                    "perceptual_hash_threshold": 6,
                    "scan_face_count": False,
                }
            )
            context: dict[str, object] = {}
            first_result = scanner.scan_image(first, context)
            second_result = scanner.scan_image(second, context)

            self.assertNotIn("duplicate_near", first_result.issue_types)
            self.assertIn("duplicate_near", second_result.issue_types)

    def test_zero_face_warning_is_optional(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "blank.png"
            Image.new("RGB", (128, 128), (90, 120, 160)).save(path)

            scanner = build_default_scanner(
                {
                    "target_width": 128,
                    "target_height": 128,
                    "scan_face_count": True,
                    "scan_zero_faces": True,
                    "scan_duplicate": False,
                }
            )
            result = scanner.scan_image(path, {})

            self.assertIn("no_face_detected", result.issue_types)

    def test_parallel_scanner_reports_duplicates(self) -> None:
        with TemporaryDirectory() as temp_dir:
            first = Path(temp_dir) / "a.png"
            second = Path(temp_dir) / "b.png"
            Image.new("RGB", (128, 128), (10, 20, 30)).save(first)
            second.write_bytes(first.read_bytes())

            results = scan_images_parallel(
                [first, second],
                {
                    "target_width": 128,
                    "target_height": 128,
                    "scan_duplicate": True,
                    "scan_near_duplicate": True,
                    "scan_face_count": False,
                    "scan_worker_count": 2,
                    "high_performance_scan": True,
                },
            )

            self.assertNotIn("duplicate_exact", results[str(first)].issue_types)
            self.assertIn("duplicate_exact", results[str(second)].issue_types)


if __name__ == "__main__":
    unittest.main()

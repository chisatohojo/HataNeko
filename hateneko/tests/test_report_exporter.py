from __future__ import annotations

import csv
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from hateneko.core.report_exporter import (
    build_scan_summary,
    write_csv_report,
    write_json_report,
)
from hateneko.core.scan_result import Issue, ScanResult


class ReportExporterTest(unittest.TestCase):
    def test_summary_counts_statuses_and_issues(self) -> None:
        paths = [Path("a.png"), Path("b.png")]
        result = ScanResult.from_issues(
            paths[0],
            [
                Issue(
                    type="resolution_mismatch",
                    severity="warning",
                    message="基準解像度と異なります。",
                )
            ],
        )

        summary = build_scan_summary(
            paths,
            {str(paths[0]): "suspicious", str(paths[1]): "unconfirmed"},
            {str(paths[0]): result},
        )

        self.assertEqual(summary["total"], 2)
        self.assertEqual(summary["scanned"], 1)
        self.assertEqual(summary["unscanned"], 1)
        self.assertEqual(summary["suspicious"], 1)
        self.assertEqual(summary["issue_counts"]["resolution_mismatch"], 1)

    def test_writes_csv_and_json_reports(self) -> None:
        with TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            image_path = base / "sample.png"
            image_path.write_bytes(b"not-used-by-exporter")
            result = ScanResult.from_issues(
                image_path,
                [
                    Issue(
                        type="duplicate_near",
                        severity="warning",
                        message="近似重複候補です。",
                        bbox=(1, 2, 3, 4),
                    )
                ],
            )

            csv_path = write_csv_report(
                base,
                [image_path],
                {str(image_path): "suspicious"},
                {str(image_path): result},
            )
            json_path = write_json_report(
                base,
                [image_path],
                {str(image_path): "suspicious"},
                {str(image_path): result},
            )

            with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
                rows = list(csv.DictReader(file))
            payload = json.loads(json_path.read_text(encoding="utf-8"))

            self.assertEqual(rows[0]["file_name"], "sample.png")
            self.assertEqual(rows[0]["issue_types"], "duplicate_near")
            self.assertEqual(payload["summary"]["issue_counts"]["duplicate_near"], 1)
            self.assertEqual(payload["results"][0]["status"], "suspicious")


if __name__ == "__main__":
    unittest.main()

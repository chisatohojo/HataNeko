from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

from hateneko.core.file_manager import LOG_FOLDER
from hateneko.core.scan_result import ScanResult


CSV_REPORT_FILE = "scan_report.csv"
JSON_REPORT_FILE = "scan_report.json"


def build_scan_summary(
    image_paths: list[Path],
    statuses: dict[str, str],
    scan_results: dict[str, ScanResult],
) -> dict[str, Any]:
    status_counts = Counter(statuses.get(str(path), "unconfirmed") for path in image_paths)
    issue_counts: Counter[str] = Counter()
    severity_counts: Counter[str] = Counter()
    scanned = 0

    for path in image_paths:
        result = scan_results.get(str(path))
        if result is None:
            continue
        scanned += 1
        for issue in result.issues:
            issue_counts[issue.type] += 1
            severity_counts[issue.severity] += 1

    return {
        "total": len(image_paths),
        "scanned": scanned,
        "unscanned": max(0, len(image_paths) - scanned),
        "suspicious": status_counts.get("suspicious", 0),
        "status_counts": dict(sorted(status_counts.items())),
        "issue_counts": dict(issue_counts.most_common()),
        "severity_counts": dict(sorted(severity_counts.items())),
    }


def write_csv_report(
    base_folder: str | Path,
    image_paths: list[Path],
    statuses: dict[str, str],
    scan_results: dict[str, ScanResult],
    filename: str = CSV_REPORT_FILE,
) -> Path:
    report_path = Path(base_folder) / LOG_FOLDER / filename
    report_path.parent.mkdir(parents=True, exist_ok=True)

    with report_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "file_path",
                "file_name",
                "status",
                "scan_status",
                "score",
                "issue_count",
                "issue_types",
                "severities",
                "messages",
                "bboxes",
            ],
        )
        writer.writeheader()
        for path in image_paths:
            result = scan_results.get(str(path))
            issues = result.issues if result else []
            writer.writerow(
                {
                    "file_path": str(path),
                    "file_name": path.name,
                    "status": statuses.get(str(path), "unconfirmed"),
                    "scan_status": result.status if result else "",
                    "score": result.score if result else "",
                    "issue_count": len(issues),
                    "issue_types": ";".join(issue.type for issue in issues),
                    "severities": ";".join(issue.severity for issue in issues),
                    "messages": " | ".join(issue.message for issue in issues),
                    "bboxes": ";".join(str(issue.bbox) for issue in issues if issue.bbox),
                }
            )
    return report_path


def write_json_report(
    base_folder: str | Path,
    image_paths: list[Path],
    statuses: dict[str, str],
    scan_results: dict[str, ScanResult],
    filename: str = JSON_REPORT_FILE,
) -> Path:
    report_path = Path(base_folder) / LOG_FOLDER / filename
    report_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "summary": build_scan_summary(image_paths, statuses, scan_results),
        "results": [
            {
                "file_path": str(path),
                "file_name": path.name,
                "status": statuses.get(str(path), "unconfirmed"),
                "scan_result": (
                    scan_results[str(path)].to_dict()
                    if str(path) in scan_results
                    else None
                ),
            }
            for path in image_paths
        ],
    }
    report_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report_path

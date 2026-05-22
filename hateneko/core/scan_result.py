from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


STATUS_UNCONFIRMED = "unconfirmed"
STATUS_SUSPICIOUS = "suspicious"
STATUS_OK = "ok"
STATUS_FIX = "fix"
STATUS_NG = "ng"
STATUS_DELETED = "deleted"


@dataclass(slots=True)
class Issue:
    type: str
    severity: str
    message: str
    bbox: tuple[int, int, int, int] | None = None
    score: float | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if self.bbox is not None:
            data["bbox"] = list(self.bbox)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Issue":
        bbox = data.get("bbox")
        return cls(
            type=str(data.get("type", "unknown")),
            severity=str(data.get("severity", "warning")),
            message=str(data.get("message", "")),
            bbox=tuple(bbox) if bbox is not None else None,
            score=data.get("score"),
        )


@dataclass(slots=True)
class ScanResult:
    file_path: str
    status: str = STATUS_UNCONFIRMED
    score: int = 100
    issues: list[Issue] = field(default_factory=list)

    @property
    def suspicious(self) -> bool:
        return bool(self.issues)

    @property
    def issue_types(self) -> list[str]:
        return [issue.type for issue in self.issues]

    @classmethod
    def from_issues(cls, file_path: str | Path, issues: list[Issue]) -> "ScanResult":
        status = STATUS_SUSPICIOUS if issues else STATUS_UNCONFIRMED
        score = max(0, 100 - sum(_severity_penalty(issue.severity) for issue in issues))
        return cls(file_path=str(file_path), status=status, score=score, issues=issues)

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_path": self.file_path,
            "status": self.status,
            "score": self.score,
            "issues": [issue.to_dict() for issue in self.issues],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ScanResult":
        issues = [
            Issue.from_dict(issue)
            for issue in data.get("issues", [])
            if isinstance(issue, dict)
        ]
        return cls(
            file_path=str(data.get("file_path", "")),
            status=str(data.get("status", STATUS_UNCONFIRMED)),
            score=int(data.get("score", 100)),
            issues=issues,
        )


def _severity_penalty(severity: str) -> int:
    if severity == "danger":
        return 35
    if severity == "warning":
        return 18
    return 8

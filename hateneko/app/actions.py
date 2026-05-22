from __future__ import annotations


STATUS_LABELS = {
    "all": "All",
    "unconfirmed": "未確認",
    "suspicious": "Suspicious",
    "ok": "OK",
    "fix": "Fix",
    "ng": "NG",
    "deleted": "Deleted",
}

STATUS_COLORS = {
    "unconfirmed": "#f3f4f6",
    "suspicious": "#fee2e2",
    "ok": "#dcfce7",
    "fix": "#fef3c7",
    "ng": "#e5e7eb",
    "deleted": "#e0e7ff",
}

CATEGORY_TO_STATUS = {
    "ok": "ok",
    "fix": "fix",
    "ng": "ng",
    "deleted": "deleted",
}


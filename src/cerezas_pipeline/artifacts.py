from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .dates import RunWindow


@dataclass(frozen=True)
class RunPaths:
    root: Path
    raw: Path
    locations: Path
    weather: Path
    fixed: Path
    csv: Path
    reports: Path
    pdf: Path
    manifest: Path

    @classmethod
    def create(cls, data_root: Path, window: RunWindow) -> "RunPaths":
        root = data_root / "runs" / window.kind.value / window.report_date.isoformat()
        values = {
            "root": root,
            "raw": root / "01_raw",
            "locations": root / "02_locations",
            "weather": root / "03_weather",
            "fixed": root / "04_fixed",
            "csv": root / "05_csv",
            "reports": root / "06_reports",
            "pdf": root / "07_pdf",
            "manifest": root / "manifest.json",
        }
        for key, path in values.items():
            if key not in {"manifest"}:
                path.mkdir(parents=True, exist_ok=True)
        return cls(**values)

    def write_manifest(self, payload: dict[str, Any]) -> None:
        body = dict(payload)
        body["updated_at"] = datetime.now(timezone.utc).isoformat()
        temporary = self.manifest.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, self.manifest)


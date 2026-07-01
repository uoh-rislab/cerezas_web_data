from __future__ import annotations

import traceback
from datetime import date
from typing import Any, Callable

from .artifacts import RunPaths
from .climate import process_all
from .convert import convert_all
from .dates import RunKind, window_for
from .extract import extract_all
from .pdf_report import generate_all_pdfs
from .repair import repair_all
from .settings import Settings
from .weather import fetch_weather


Stage = tuple[str, Callable[..., list[dict[str, Any]]]]


def run_pipeline(
    settings: Settings,
    kind: RunKind,
    scheduled_date: date,
    generate_pdf: bool = True,
) -> dict[str, Any]:
    window = window_for(
        kind,
        scheduled_date,
        season_start_month=settings.season_start_month,
        season_start_day=settings.season_start_day,
    )
    paths = RunPaths.create(settings.data_root, window)
    manifest: dict[str, Any] = {
        "run_id": window.run_id,
        "kind": kind.value,
        "scheduled_date": scheduled_date.isoformat(),
        "report_date": window.report_date.isoformat(),
        "window": {"start_utc": window.start_utc.isoformat(), "end_utc": window.end_utc.isoformat()},
        "status": "running",
        "generate_pdf": generate_pdf,
        "stages": {},
    }
    paths.write_manifest(manifest)
    stages: list[Stage] = [
        ("extract", lambda: extract_all(settings, window, paths)),
        ("weather", lambda: fetch_weather(settings, window, paths)),
        ("repair", lambda: repair_all(settings, window, paths)),
        ("csv", lambda: convert_all(settings, paths)),
        ("climate", lambda: process_all(settings, window, paths)),
    ]
    if generate_pdf:
        stages.append(("pdf", lambda: generate_all_pdfs(settings, window, paths)))
    try:
        for name, execute in stages:
            manifest["stages"][name] = {"status": "running"}
            paths.write_manifest(manifest)
            result = execute()
            manifest["stages"][name] = {"status": "complete", "result": result}
            paths.write_manifest(manifest)
        manifest["status"] = "complete"
        paths.write_manifest(manifest)
        return manifest
    except Exception as error:
        manifest["status"] = "failed"
        manifest["error"] = {"type": type(error).__name__, "message": str(error), "traceback": traceback.format_exc()}
        paths.write_manifest(manifest)
        raise

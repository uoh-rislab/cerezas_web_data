from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterable, Optional
from zoneinfo import ZoneInfo

from .dates import RunKind, RunWindow, window_for

if TYPE_CHECKING:
    from .settings import Settings, Site


@dataclass(frozen=True)
class ReportMetadataPeriod:
    start: date
    end: date


def metadata_period(kind: RunKind, report_date: date) -> ReportMetadataPeriod:
    if kind == RunKind.DAILY:
        return ReportMetadataPeriod(report_date, report_date)
    if kind == RunKind.WEEKLY:
        return ReportMetadataPeriod(report_date - timedelta(days=6), report_date)
    start = report_date.replace(day=1)
    return ReportMetadataPeriod(start, report_date)


def date_to_unix_timestamp(value: date, timezone_name: str) -> str:
    local = datetime.combine(value, time.min, ZoneInfo(timezone_name))
    return str(int(local.timestamp()))


def _max_report_name(collection: Any) -> int:
    max_name = 0
    for document in collection.find({}, {"name": 1, "_id": 0}):
        try:
            max_name = max(max_name, int(document.get("name", 0)))
        except (TypeError, ValueError):
            continue
    return max_name


def _matching_existing(collection: Any, payload: dict[str, str]) -> Optional[dict[str, Any]]:
    query = {
        "data-field": payload["data-field"],
        "zone": payload["zone"],
        "in-date": payload["in-date"],
        "out-date": payload["out-date"],
        "kind": payload["kind"],
    }
    return collection.find_one(query)


def build_report_metadata_payload(
    settings: "Settings",
    site: "Site",
    window: RunWindow,
    name: str,
) -> dict[str, str]:
    period = metadata_period(window.kind, window.report_date)
    timezone_name = settings.report_metadata.timezone
    return {
        "data-field": site.site_id,
        "zone": settings.report_metadata.zone,
        "in-date": date_to_unix_timestamp(period.start, timezone_name),
        "out-date": date_to_unix_timestamp(period.end, timezone_name),
        "name": name,
        "kind": window.kind.value,
    }


def insert_report_metadata(
    settings: "Settings",
    site: "Site",
    window: RunWindow,
    dry_run: bool = False,
) -> dict[str, Any]:
    if not settings.report_metadata.enabled and not dry_run:
        return {"site": site.site_id, "status": "disabled"}

    from pymongo import MongoClient

    client = MongoClient(settings.mongo.uri, serverSelectionTimeoutMS=15_000)
    try:
        collection = client[settings.report_metadata.database][site.site_id]
        payload = build_report_metadata_payload(settings, site, window, name="0")
        existing = _matching_existing(collection, payload)
        if existing:
            return {
                "site": site.site_id,
                "status": "exists",
                "kind": window.kind.value,
                "name": str(existing.get("name", "")),
            }

        next_name = str(_max_report_name(collection) + 1)
        payload["name"] = next_name
        if dry_run:
            return {"site": site.site_id, "status": "dry_run", "payload": payload}

        result = collection.insert_one(payload)
        return {
            "site": site.site_id,
            "status": "inserted",
            "kind": window.kind.value,
            "name": next_name,
            "inserted_id": str(result.inserted_id),
        }
    finally:
        client.close()


def _find_site_pdf(root: Path, site: "Site") -> Optional[Path]:
    directory = root / "07_pdf" / site.group
    for label in (site.filename, site.name):
        matches = sorted(directory.glob(f"*{label}.pdf"))
        if matches:
            return matches[-1]
    return None


def _iter_existing_pdf_windows(
    settings: "Settings",
    year: int,
    kinds: Iterable[RunKind],
) -> Iterable[tuple[RunWindow, "Site", Path]]:
    for kind in kinds:
        kind_root = settings.data_root / "runs" / kind.value
        if not kind_root.exists():
            continue
        for run_root in sorted(kind_root.iterdir()):
            if not run_root.is_dir():
                continue
            try:
                report_date = date.fromisoformat(run_root.name)
            except ValueError:
                continue
            if report_date.year != year:
                continue
            window = window_for(
                kind,
                report_date + timedelta(days=1),
                season_start_month=settings.season_start_month,
                season_start_day=settings.season_start_day,
            )
            for site in settings.sites.values():
                pdf_path = _find_site_pdf(run_root, site)
                if pdf_path:
                    yield window, site, pdf_path


def backfill_report_metadata(
    settings: "Settings",
    year: int,
    kinds: Optional[Iterable[RunKind]] = None,
    dry_run: bool = False,
) -> list[dict[str, Any]]:
    selected_kinds = tuple(kinds or (RunKind.DAILY, RunKind.WEEKLY, RunKind.MONTHLY))
    results: list[dict[str, Any]] = []
    for window, site, pdf_path in _iter_existing_pdf_windows(settings, year, selected_kinds):
        result = insert_report_metadata(settings, site, window, dry_run=dry_run)
        result["pdf"] = str(pdf_path)
        result["report_date"] = window.report_date.isoformat()
        results.append(result)
    return results

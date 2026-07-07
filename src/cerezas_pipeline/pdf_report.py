from __future__ import annotations

import os
import shutil
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path
from typing import Any, Iterator

import pandas as pd
import yaml

from .artifacts import RunPaths
from .dates import RunKind, RunWindow
from .report_metadata import insert_report_metadata
from .settings import Settings, Site


SPANISH_MONTHS = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio",
    7: "Julio", 8: "Agosto", 9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}


@contextmanager
def _working_directory(path: Path) -> Iterator[None]:
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


def _dataset_key(site: Site) -> str:
    return site.site_id.split("-", 1)[1]


def _write_metadata(settings: Settings, assets: Path) -> None:
    metadata_path = assets / "site_metadata.yaml"
    if metadata_path.exists():
        return
    metadata: dict[str, dict[str, str]] = {}
    for site in settings.sites.values():
        metadata[_dataset_key(site)] = {
            "nombre": site.name,
            "filename": site.filename,
            "ubicacion": site.location,
        }
    metadata_path.write_text(yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False), encoding="utf-8")


def _prepare_compatibility_tree(settings: Settings, window: RunWindow, paths: RunPaths) -> Path:
    if not settings.assets_dir.exists():
        raise RuntimeError(
            f"No existe el directorio de assets {settings.assets_dir}. "
            "Copie los assets originales de ClimateProcessing antes de generar PDF."
        )
    if not (settings.assets_dir / "logo_fic.png").exists():
        raise RuntimeError(f"Falta {settings.assets_dir / 'logo_fic.png'}")
    if not os.getenv("MAPBOX_ACCESS_TOKEN"):
        raise RuntimeError("Configure MAPBOX_ACCESS_TOKEN para generar el mapa satelital original")

    root = paths.root / ".faithful_pdf"
    (root / "generate_pdf").mkdir(parents=True, exist_ok=True)
    shutil.copytree(settings.assets_dir, root / "assets", dirs_exist_ok=True)
    _write_metadata(settings, root / "assets")
    for kind in ("daily", "weekly"):
        (root / "locations" / kind / window.report_date.isoformat()).mkdir(parents=True, exist_ok=True)
    (root / "locations").mkdir(parents=True, exist_ok=True)
    return root


def _write_locations(site: Site, window: RunWindow, paths: RunPaths, root: Path) -> None:
    source = paths.locations / f"{site.site_id}.tsv"
    frame = pd.read_csv(source, sep="\t") if source.exists() and source.stat().st_size else pd.DataFrame()
    locations: dict[str, dict[str, Any]] = {}
    for row in frame.to_dict("records"):
        if "T°-H" not in str(row.get("sensor", "")) and "Temp" not in str(row.get("sensor", "")):
            continue
        try:
            device_id = str(row["end_device_id"]).replace("eui-", "").upper()
            locations[device_id] = {
                "latitud": float(row["latitud"]),
                "longitud": float(row["longitud"]),
                "sensor_type": "LSN50v2-S31B",
            }
        except (KeyError, TypeError, ValueError):
            continue
    body = "sensor_locations = " + repr(locations) + "\n"
    report_date = window.report_date.isoformat()
    for kind in ("daily", "weekly"):
        target = root / "locations" / kind / report_date / f"sensor_locations_{site.site_id}.txt"
        target.write_text(body, encoding="utf-8")
    (root / "locations" / f"sensor_locations_{site.site_id}.txt").write_text(body, encoding="utf-8")


def _move_generated(source_dir: Path, destination: Path, site: Site) -> Path:
    matches = sorted(source_dir.glob(f"*{site.filename}.pdf"))
    if not matches:
        matches = sorted(source_dir.glob(f"*{site.name}.pdf"))
    if not matches:
        raise RuntimeError(f"El generador original no produjo PDF para {site.site_id}")
    destination.mkdir(parents=True, exist_ok=True)
    for label in {site.filename, site.name}:
        for previous in destination.glob(f"*{label}.pdf"):
            previous.unlink()
    output = destination / matches[-1].name
    shutil.move(str(matches[-1]), output)
    return output


def _daily_or_weekly(site: Site, window: RunWindow, paths: RunPaths, root: Path) -> Path:
    from .faithful_pdf import daily, weekly

    report_date = window.report_date
    end_date = f"{report_date.isoformat()} 23:59:59"
    month_root = report_date.strftime("%Y-%m")
    month_words = f"{SPANISH_MONTHS[report_date.month]} {report_date.year}"
    base_reports = f"{paths.reports}/"
    workdir = root / "generate_pdf"

    with _working_directory(workdir):
        if window.kind == RunKind.DAILY:
            scheduled = window.scheduled_date
            last_monday = scheduled - timedelta(days=scheduled.weekday())
            daily.main(
                base_reports, site.site_id, _dataset_key(site), month_root, month_words,
                f"{report_date.year}-05-01", end_date, last_monday.isoformat(),
            )
            generated_dir = root / "output" / "pdf_d" / report_date.isoformat()
        else:
            last_seven = window.scheduled_date - timedelta(days=7)
            weekly.main(
                base_reports, site.site_id, _dataset_key(site), month_root, month_words,
                f"{report_date.year}-05-01", end_date, last_seven.isoformat(),
            )
            generated_dir = root / "output" / "pdf_w" / report_date.isoformat()
    return _move_generated(generated_dir, paths.pdf / site.group, site)


def _monthly_comparison(site: Site, window: RunWindow, paths: RunPaths, root: Path) -> Path:
    from .faithful_pdf import monthly

    report_date = window.report_date
    previous_date = report_date.replace(year=report_date.year - 1)
    previous_report = (
        settings_data_root(paths) / "runs" / "monthly" / previous_date.isoformat()
        / "06_reports" / f"{site.site_id}.csv"
    )
    if not previous_report.exists():
        raise RuntimeError(
            f"Falta el reporte comparativo del año anterior: {previous_report}. "
            "Prepare primero el histórico con: cerezas-pipeline run --kind monthly "
            f"--scheduled-date {(previous_date + timedelta(days=1)).isoformat()} --skip-pdf."
        )
    start = report_date.replace(day=1)
    previous_start = previous_date.replace(day=1)
    with _working_directory(root / "generate_pdf"):
        monthly.main(
            f"{paths.reports}/", f"{previous_report.parent}/", site.site_id, site.site_id,
            _dataset_key(site), report_date.strftime("%Y-%m"),
            f"{SPANISH_MONTHS[report_date.month]} {report_date.year}", start.isoformat(),
            f"{report_date.isoformat()} 23:59:59", (report_date - timedelta(days=6)).isoformat(),
            previous_start.isoformat(), f"{previous_date.isoformat()} 23:59:59",
        )
    return _move_generated(root / "generate_pdf" / "pdf", paths.pdf / site.group, site)


def settings_data_root(paths: RunPaths) -> Path:
    # root = <data-root>/runs/<kind>/<date>
    return paths.root.parents[2]


def generate_site_pdf(settings: Settings, site: Site, window: RunWindow, paths: RunPaths, root: Path) -> dict[str, Any]:
    report = pd.read_csv(paths.reports / f"{site.site_id}.csv")
    sensor_columns = [column for column in report.columns if column.startswith("A8") and " " not in column]
    if report.empty or not sensor_columns:
        return {"site": site.site_id, "generated": False, "reason": "sin datos"}
    _write_locations(site, window, paths, root)
    if window.kind in (RunKind.DAILY, RunKind.WEEKLY):
        output = _daily_or_weekly(site, window, paths, root)
    else:
        output = _monthly_comparison(site, window, paths, root)
    metadata = insert_report_metadata(settings, site, window)
    return {"site": site.site_id, "generated": True, "path": str(output), "metadata": metadata}


def generate_all_pdfs(settings: Settings, window: RunWindow, paths: RunPaths) -> list[dict[str, Any]]:
    root = _prepare_compatibility_tree(settings, window, paths)
    return [generate_site_pdf(settings, site, window, paths, root) for site in settings.sites.values()]

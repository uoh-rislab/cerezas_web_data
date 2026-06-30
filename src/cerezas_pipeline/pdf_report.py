from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .artifacts import RunPaths
from .dates import RunKind, RunWindow
from .settings import Settings, Site


TITLES = {
    RunKind.DAILY: "Boletín Diario",
    RunKind.WEEKLY: "Boletín Semanal",
    RunKind.MONTHLY: "Boletín Mensual",
}


def _sensor_columns(frame: pd.DataFrame) -> list[str]:
    return [column for column in frame.columns if column not in {"Año", "Mes", "Dia", "Hora"} and " " not in column]


def _chart(frame: pd.DataFrame, sensors: list[str], output: Path, window: RunWindow) -> None:
    timestamp = pd.to_datetime(dict(year=frame["Año"], month=frame["Mes"], day=frame["Dia"], hour=frame["Hora"]))
    if window.kind == RunKind.DAILY:
        cutoff = timestamp.max() - pd.Timedelta(days=7)
        selection = timestamp >= cutoff
    else:
        selection = pd.Series(True, index=frame.index)
    figure, axis = plt.subplots(figsize=(10, 4.8))
    for sensor in sensors:
        axis.plot(timestamp[selection], frame.loc[selection, sensor], linewidth=1, label=sensor)
    axis.set_ylabel("Temperatura (°C)")
    axis.set_xlabel("Fecha")
    axis.grid(alpha=0.25)
    axis.legend(fontsize=7, ncol=2)
    figure.autofmt_xdate()
    figure.tight_layout()
    figure.savefig(output, dpi=160)
    plt.close(figure)


def generate_site_pdf(site: Site, window: RunWindow, paths: RunPaths) -> dict[str, Any]:
    source = paths.reports / f"{site.site_id}.csv"
    frame = pd.read_csv(source)
    sensors = _sensor_columns(frame)
    if frame.empty or not sensors:
        return {"site": site.site_id, "generated": False, "reason": "sin datos"}

    group_dir = paths.pdf / site.group
    group_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{window.report_date.isoformat()} UOH Cerezas {TITLES[window.kind]} - {site.filename}.pdf"
    output = group_dir / filename
    temporary = output.with_suffix(".pdf.tmp")
    styles = getSampleStyleSheet()
    centered = ParagraphStyle("Centered", parent=styles["Normal"], alignment=TA_CENTER, leading=15)

    with tempfile.TemporaryDirectory(dir=paths.root) as directory:
        chart = Path(directory) / "temperature.png"
        _chart(frame, sensors, chart, window)
        document = SimpleDocTemplate(
            str(temporary), pagesize=A4, rightMargin=1.6 * cm, leftMargin=1.6 * cm,
            topMargin=1.5 * cm, bottomMargin=1.5 * cm,
            title=f"{TITLES[window.kind]} - {site.name}",
        )
        story = [
            Paragraph("<b>Universidad de O'Higgins - Proyecto Cerezas</b>", centered),
            Spacer(1, 0.25 * cm),
            Paragraph(f"<b>{TITLES[window.kind]}</b>", styles["Title"]),
            Paragraph(site.name, centered),
            Paragraph(f"{site.location}, Región de O'Higgins", centered),
            Spacer(1, 0.3 * cm),
            Paragraph(
                f"Período analizado: {window.start_utc.date().isoformat()} al {window.report_date.isoformat()} (UTC-4 fijo)",
                centered,
            ),
            Spacer(1, 0.5 * cm),
            Image(str(chart), width=17.5 * cm, height=8.4 * cm),
            Spacer(1, 0.4 * cm),
            Paragraph("<b>Resumen acumulado por sensor</b>", styles["Heading2"]),
        ]
        latest = frame.iloc[-1]
        rows = [["Sensor", "T °C", "HF", "PF", "UF", "HC"]]
        for sensor in sensors:
            rows.append(
                [
                    sensor,
                    f"{latest[sensor]:.1f}",
                    f"{latest.get(sensor + ' HF', 0):.1f}",
                    f"{latest.get(sensor + ' PF', 0):.1f}",
                    f"{latest.get(sensor + ' UF', 0):.1f}",
                    f"{latest.get(sensor + ' HC', 0):.1f}",
                ]
            )
        table = Table(rows, repeatRows=1, colWidths=[6.2 * cm, 1.7 * cm, 1.7 * cm, 1.7 * cm, 1.7 * cm, 1.7 * cm])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#7a1f3d")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )
        story.append(table)
        document.build(story)
    os.replace(temporary, output)
    return {"site": site.site_id, "generated": True, "path": str(output)}


def generate_all_pdfs(settings: Settings, window: RunWindow, paths: RunPaths) -> list[dict[str, Any]]:
    return [generate_site_pdf(site, window, paths) for site in settings.sites.values()]


from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from .artifacts import RunPaths
from .dates import FIXED_CHILE_TZ
from .settings import Settings, Site


CSV_COLUMNS = [
    "name", "time", "device_id", "sensor_type", "valor", "latitud", "longitud",
    "year", "month", "day", "hour", "time_day",
]


def _row(entry: dict[str, Any]) -> Optional[dict[str, Any]]:
    payload = entry.get("payload_decoded") or {}
    static = entry.get("sensor_static_data") or {}
    temperature = payload.get("TempC_SHT")
    timestamp = entry.get("time_sensor_tx")
    device = entry.get("sensor_device_id")
    latitude = static.get("sensor_lat")
    longitude = static.get("sensor_lon")
    if temperature is None or not timestamp or not device or latitude is None or longitude is None:
        return None
    if "LSN50v2-S31" not in str(static.get("sensor_model", "")):
        return None
    utc = pd.Timestamp(timestamp)
    if utc.tzinfo is None:
        utc = utc.tz_localize("UTC")
    local = utc.tz_convert(FIXED_CHILE_TZ)
    return {
        "name": "temp_environment",
        "time": int(utc.timestamp() * 1_000_000_000),
        "device_id": str(device).replace("eui-", "").upper(),
        "sensor_type": "LSN50v2-S31B",
        "valor": float(temperature),
        "latitud": round(float(latitude), 6),
        "longitud": round(float(longitude), 6),
        "year": local.year,
        "month": local.month,
        "day": local.day,
        "hour": local.hour,
        "time_day": local.hour + local.day / 60.0,
    }


def convert_site(site: Site, paths: RunPaths) -> dict[str, Any]:
    rows = []
    source = paths.fixed / f"{site.site_id}.jsonl"
    if source.exists():
        with source.open(encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    row = _row(json.loads(line))
                    if row:
                        rows.append(row)
    frame = pd.DataFrame(rows, columns=CSV_COLUMNS).sort_values("time") if rows else pd.DataFrame(columns=CSV_COLUMNS)
    output = paths.csv / f"{site.site_id}.csv"
    temporary = output.with_suffix(".csv.tmp")
    frame.to_csv(temporary, index=False)
    os.replace(temporary, output)
    return {"site": site.site_id, "rows": len(frame), "sensors": int(frame["device_id"].nunique()) if len(frame) else 0}


def convert_all(settings: Settings, paths: RunPaths) -> list[dict[str, Any]]:
    return [convert_site(site, paths) for site in settings.sites.values()]

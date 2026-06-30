from __future__ import annotations

import json
import os
from datetime import timezone
from pathlib import Path
from typing import Any

import pandas as pd

from .artifacts import RunPaths
from .dates import RunWindow
from .settings import Settings, Site
from .weather import load_weather


def _parse_timestamp(value: str) -> pd.Timestamp:
    return pd.Timestamp(value).tz_convert("UTC") if pd.Timestamp(value).tzinfo else pd.Timestamp(value, tz="UTC")


def _load_locations(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    return pd.read_csv(path, sep="\t").fillna("")


def repair_site(settings: Settings, site: Site, window: RunWindow, paths: RunPaths) -> dict[str, Any]:
    raw_path = paths.raw / f"{site.site_id}.jsonl"
    locations = _load_locations(paths.locations / f"{site.site_id}.tsv")
    weather = load_weather(paths.weather / f"{site.city}.csv")
    original: list[dict[str, Any]] = []
    present: dict[str, set[pd.Timestamp]] = {}

    if raw_path.exists():
        with raw_path.open(encoding="utf-8") as source:
            for line in source:
                if not line.strip():
                    continue
                entry = json.loads(line)
                model = str((entry.get("sensor_static_data") or {}).get("sensor_model", ""))
                if "LSN50v2-S31" not in model:
                    continue
                device = str(entry.get("sensor_device_id", "")).lower()
                timestamp = entry.get("time_sensor_tx")
                if not device or not timestamp:
                    continue
                hour = _parse_timestamp(str(timestamp)).floor("h")
                present.setdefault(device, set()).add(hour)
                original.append(entry)

    expected = pd.date_range(window.start_utc, window.end_utc.replace(minute=0, second=0, microsecond=0), freq="h")
    synthetic: list[dict[str, Any]] = []
    for row in locations.to_dict("records"):
        if "T°-H" not in str(row.get("sensor", "")) and "Temp" not in str(row.get("sensor", "")):
            continue
        try:
            latitude = float(row["latitud"])
            longitude = float(row["longitud"])
        except (KeyError, TypeError, ValueError):
            continue
        device = str(row["end_device_id"]).lower()
        missing = expected.difference(pd.DatetimeIndex(present.get(device, set())))
        for hour in missing:
            weather_hour = hour.tz_convert(None)
            if weather_hour not in weather.index:
                continue
            values = weather.loc[weather_hour]
            if isinstance(values, pd.DataFrame):
                values = values.iloc[0]
            synthetic.append(
                {
                    "sensor_device_id": device,
                    "field_id": row.get("field_id") or site.site_id,
                    "payload_decoded": {
                        "Hum_SHT": float(values["humidity"]),
                        "TempC_SHT": float(values["temperature"]),
                    },
                    "time_sensor_tx": hour.to_pydatetime().astimezone(timezone.utc).isoformat(),
                    "sensor_static_data": {
                        "sensor_model": row.get("model", ""),
                        "sensor_lat": latitude,
                        "sensor_lon": longitude,
                        "city": site.city,
                        "source": "meteostat",
                    },
                }
            )

    combined = original + synthetic
    combined.sort(key=lambda item: str(item["time_sensor_tx"]))
    output = paths.fixed / f"{site.site_id}.jsonl"
    temporary = output.with_suffix(".jsonl.tmp")
    with temporary.open("w", encoding="utf-8") as target:
        for entry in combined:
            target.write(json.dumps(entry, ensure_ascii=False) + "\n")
    os.replace(temporary, output)
    return {"site": site.site_id, "original": len(original), "synthetic": len(synthetic)}


def repair_all(settings: Settings, window: RunWindow, paths: RunPaths) -> list[dict[str, Any]]:
    return [repair_site(settings, site, window, paths) for site in settings.sites.values()]

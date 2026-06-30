from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
from meteostat import Hourly, Stations

from .artifacts import RunPaths
from .dates import RunWindow
from .settings import Settings


WEATHER_COLUMNS = ["time", "temperature", "humidity"]


def _fetch_station(latitude: float, longitude: float, window: RunWindow) -> pd.DataFrame:
    station = Stations().nearby(latitude, longitude).fetch(1)
    if station.empty:
        raise RuntimeError(f"No se encontró estación Meteostat para {latitude}, {longitude}")
    station_id = station.index[0]
    start = window.start_utc.replace(tzinfo=None)
    end = window.end_utc.replace(tzinfo=None)
    frame = Hourly(station_id, start, end).fetch()
    if frame.empty:
        raise RuntimeError(f"Meteostat no devolvió datos para la estación {station_id}")
    frame = frame.rename(columns={"temp": "temperature", "rhum": "humidity"})
    frame = frame[["temperature", "humidity"]].copy()
    frame.index.name = "time"
    full_index = pd.date_range(start=start, end=pd.Timestamp(end).floor("h"), freq="h")
    frame = frame.reindex(full_index).interpolate(limit_direction="both")
    frame.index.name = "time"
    return frame.reset_index()


def fetch_weather(settings: Settings, window: RunWindow, paths: RunPaths) -> list[dict[str, object]]:
    results = []
    required_cities = sorted({site.city for site in settings.sites.values()})
    for city in required_cities:
        station = settings.stations[city]
        frame = _fetch_station(float(station["latitude"]), float(station["longitude"]), window)
        output = paths.weather / f"{city}.csv"
        temporary = output.with_suffix(".csv.tmp")
        frame.to_csv(temporary, index=False)
        os.replace(temporary, output)
        results.append({"city": city, "hours": len(frame), "path": str(output)})
    return results


def load_weather(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, parse_dates=["time"])
    frame["hour"] = frame["time"].dt.floor("h")
    return frame.set_index("hour")

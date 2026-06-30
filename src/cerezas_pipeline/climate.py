from __future__ import annotations

import os
from typing import Any

import numpy as np
import pandas as pd

from .artifacts import RunPaths
from .dates import FIXED_CHILE_TZ, RunWindow
from .settings import Settings, Site


def _utah_unit(temperature: float) -> float:
    if temperature < 1.3:
        return 0.0
    if temperature < 2.5:
        return 0.5
    if temperature < 9.2:
        return 1.0
    if temperature < 12.5:
        return 0.5
    if temperature < 16:
        return 0.0
    if temperature < 18.1:
        return -0.5
    return -1.0


def _dynamic_portions(temperatures: np.ndarray) -> np.ndarray:
    if len(temperatures) == 0:
        return np.array([], dtype=float)
    temp_k = temperatures.astype(float) + 273.0
    slope, melting = 1.6, 277.0
    a0, a1 = 139500.0, 2.567e18
    e0, e1 = 4153.5, 12888.8
    xi = np.exp(slope * melting * (temp_k - melting) / temp_k)
    xi = xi / (1.0 + xi)
    xs = (a0 / a1) * np.exp((e1 - e0) / temp_k)
    ak1 = a1 * np.exp(-e1 / temp_k)
    result = np.zeros(len(temp_k), dtype=float)
    intermediate = xs[0] - xs[0] * np.exp(-ak1[0])
    for index in range(len(temp_k)):
        previous = result[index - 1] if index else 0.0
        stored = intermediate if intermediate < 1 else intermediate * (1 - xi[index - 1 if index else 0])
        intermediate = xs[index] - (xs[index] - stored) * np.exp(-ak1[index])
        result[index] = intermediate * xi[index] + previous if intermediate >= 1 else previous
    return result


def _add_metrics(frame: pd.DataFrame, sensor: str) -> None:
    values = frame[sensor].to_numpy(dtype=float)
    chill_mask = frame["Mes"].between(5, 7).to_numpy()
    chill_values = np.where(chill_mask, values, 20.0)
    frame[f"{sensor} HF"] = np.cumsum(np.where(chill_mask & (values < 7.2), 1.0, 0.0))
    frame[f"{sensor} UF"] = np.cumsum([_utah_unit(value) if active else 0.0 for value, active in zip(values, chill_mask)])
    portions = np.zeros(len(frame), dtype=float)
    active_indices = np.flatnonzero(chill_mask)
    if len(active_indices):
        calculated = _dynamic_portions(chill_values[active_indices])
        portions[active_indices] = calculated
        if active_indices[-1] + 1 < len(frame):
            portions[active_indices[-1] + 1 :] = calculated[-1]
    frame[f"{sensor} PF"] = portions

    frame[f"{sensor} HC"] = 0.0
    accumulator = 0.0
    for (_, month, day), indices in frame.groupby(["Año", "Mes", "Dia"]).groups.items():
        if 7 <= month <= 12:
            daily = frame.loc[indices, sensor]
            accumulator = max(0.0, accumulator + ((daily.max() + daily.min()) / 2.0 - 4.5))
        frame.loc[indices, f"{sensor} HC"] = accumulator


def process_site(site: Site, window: RunWindow, paths: RunPaths) -> dict[str, Any]:
    source = paths.csv / f"{site.site_id}.csv"
    data = pd.read_csv(source)
    output = paths.reports / f"{site.site_id}.csv"
    temporary = output.with_suffix(".csv.tmp")
    if data.empty:
        pd.DataFrame(columns=["Año", "Mes", "Dia", "Hora"]).to_csv(temporary, index=False)
        os.replace(temporary, output)
        return {"site": site.site_id, "rows": 0, "sensors": 0}

    data["timestamp"] = pd.to_datetime(data["time"], unit="ns", utc=True).dt.tz_convert(FIXED_CHILE_TZ).dt.floor("h")
    pivot = data.pivot_table(index="timestamp", columns="device_id", values="valor", aggfunc="mean")
    local_start = pd.Timestamp(window.start_utc).tz_convert(FIXED_CHILE_TZ).floor("h")
    local_end = pd.Timestamp(window.end_utc).tz_convert(FIXED_CHILE_TZ).floor("h")
    pivot = pivot.reindex(pd.date_range(local_start, local_end, freq="h"))
    pivot = pivot.interpolate(limit_direction="both").ffill().bfill()
    pivot = pivot.dropna(axis=1, how="all")

    report = pd.DataFrame(
        {
            "Año": pivot.index.year,
            "Mes": pivot.index.month,
            "Dia": pivot.index.day,
            "Hora": pivot.index.hour,
        }
    )
    for sensor in pivot.columns:
        report[str(sensor)] = pivot[sensor].to_numpy()
    for sensor in map(str, pivot.columns):
        _add_metrics(report, sensor)
    report.to_csv(temporary, index=False)
    os.replace(temporary, output)
    return {"site": site.site_id, "rows": len(report), "sensors": len(pivot.columns)}


def process_all(settings: Settings, window: RunWindow, paths: RunPaths) -> list[dict[str, Any]]:
    return [process_site(site, window, paths) for site in settings.sites.values()]


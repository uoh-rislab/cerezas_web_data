from __future__ import annotations

import json
import os
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Optional

from pymongo import ASCENDING, MongoClient

from .artifacts import RunPaths
from .dates import RunWindow
from .settings import Settings, Site


LOCATION_COLUMNS = (
    "app_id",
    "field_id",
    "end_device_id",
    "latitud",
    "longitud",
    "model",
    "sensor",
)


def _query(window: RunWindow, field_id: Optional[str] = None) -> dict[str, Any]:
    query: dict[str, Any] = {
        "time_sensor_tx": {
            "$gte": window.start_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "$lte": window.end_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
    }
    if field_id:
        query["field_id"] = field_id
    return query


def _location(doc: dict[str, Any], collection: str, site: Site, settings: Settings) -> Optional[dict[str, Any]]:
    device_id = str(doc.get("sensor_device_id", "")).strip()
    if not device_id or settings.sensor_is_excluded(device_id):
        return None
    static = doc.get("sensor_static_data") or {}
    model = str(static.get("sensor_model", ""))
    return {
        "app_id": collection,
        "field_id": str(doc.get("field_id") or site.site_id),
        "end_device_id": device_id,
        "latitud": static.get("sensor_lat"),
        "longitud": static.get("sensor_lon"),
        "model": model,
        "sensor": settings.sensor_models.get(model, "N/A"),
    }


def _write_site(
    site: Site,
    sources: Iterable[tuple[str, Any]],
    query: dict[str, Any],
    paths: RunPaths,
    settings: Settings,
) -> dict[str, Any]:
    raw_path = paths.raw / f"{site.site_id}.jsonl"
    temporary = raw_path.with_suffix(".jsonl.tmp")
    locations: dict[str, dict[str, Any]] = {}
    count = 0
    with temporary.open("w", encoding="utf-8") as output:
        for collection_name, collection in sources:
            cursor = collection.find(query, no_cursor_timeout=True).sort("time_sensor_tx", ASCENDING)
            try:
                for doc in cursor:
                    device_id = str(doc.get("sensor_device_id", ""))
                    if settings.sensor_is_excluded(device_id):
                        continue
                    output.write(json.dumps(doc, default=str, ensure_ascii=False) + "\n")
                    count += 1
                    location = _location(doc, collection_name, site, settings)
                    if location:
                        locations.setdefault(location["end_device_id"].lower(), location)
            finally:
                cursor.close()
    os.replace(temporary, raw_path)

    location_path = paths.locations / f"{site.site_id}.tsv"
    location_tmp = location_path.with_suffix(".tsv.tmp")
    with location_tmp.open("w", encoding="utf-8") as output:
        output.write("\t".join(LOCATION_COLUMNS) + "\n")
        for item in locations.values():
            output.write("\t".join(str(item.get(column, "")) for column in LOCATION_COLUMNS) + "\n")
    os.replace(location_tmp, location_path)
    return {"site": site.site_id, "documents": count, "sensors": len(locations)}


def extract_all(settings: Settings, window: RunWindow, paths: RunPaths) -> list[dict[str, Any]]:
    client = MongoClient(settings.mongo.uri, serverSelectionTimeoutMS=15_000)
    try:
        client.admin.command("ping")
        database = client[settings.mongo.database]
        available = set(database.list_collection_names())
        results: list[dict[str, Any]] = []
        for site in settings.sites.values():
            if site.group == "fic1":
                collections = [
                    (name, database[name])
                    for name in settings.mongo.fic1_collections
                    if name in available
                ]
                query = _query(window, field_id=site.site_id)
            else:
                if (
                    not site.site_id.startswith(settings.mongo.fic2_collection_prefix)
                    or site.site_id not in available
                ):
                    continue
                collections = [(site.site_id, database[site.site_id])]
                query = _query(window)
            results.append(_write_site(site, collections, query, paths, settings))
        return results
    finally:
        client.close()

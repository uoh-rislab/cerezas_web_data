from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Union

import yaml


@dataclass(frozen=True)
class Site:
    site_id: str
    group: str
    city: str
    name: str
    filename: str
    location: str


@dataclass(frozen=True)
class MongoSettings:
    uri: str
    database: str
    fic1_collections: tuple[str, ...]
    fic2_collection_prefix: str


@dataclass(frozen=True)
class ReportMetadataSettings:
    enabled: bool
    database: str
    zone: str
    timezone: str


@dataclass
class Settings:
    config_dir: Path
    data_root: Path
    assets_dir: Path
    mongo: MongoSettings
    report_metadata: ReportMetadataSettings
    sites: dict[str, Site]
    stations: dict[str, dict[str, Any]]
    sensor_models: dict[str, str]
    excluded_device_ids: set[str]
    excluded_device_patterns: tuple[re.Pattern[str], ...]
    schedule_timezone: str
    schedule_hour: int
    schedule_minute: int
    schedule_start_month: int
    schedule_start_day: int
    schedule_end_month: int
    schedule_end_day: int
    season_start_month: int
    season_start_day: int
    catchup_days: int
    retry_minutes: int

    def sensor_is_excluded(self, device_id: str) -> bool:
        normalized = device_id.lower()
        return normalized in self.excluded_device_ids or any(
            pattern.search(normalized) for pattern in self.excluded_device_patterns
        )


def _read_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def load_settings(config_dir: Optional[Union[str, Path]] = None) -> Settings:
    directory = Path(config_dir or os.getenv("CEREZAS_CONFIG_DIR", "/app/config")).resolve()
    pipeline = _read_yaml(directory / "pipeline.yaml")
    sites_raw = _read_yaml(directory / "sites.yaml")["sites"]
    stations = _read_yaml(directory / "stations.yaml")["stations"]

    mongo_raw = pipeline["mongo"]
    uri = os.getenv("MONGO_URI")
    if not uri:
        user = os.getenv("MONGO_USER")
        password = os.getenv("MONGO_PASSWORD")
        if not user or not password:
            raise RuntimeError("Configure MONGO_URI o MONGO_USER y MONGO_PASSWORD")
        from urllib.parse import quote_plus

        uri = (
            f"mongodb://{quote_plus(user)}:{quote_plus(password)}@"
            f"{mongo_raw['host']}:{mongo_raw['port']}/?authSource={mongo_raw['auth_database']}"
        )

    sites = {
        site_id: Site(site_id=site_id, **values)
        for site_id, values in sites_raw.items()
    }
    filters = pipeline.get("sensor_filters", {})
    report_metadata = pipeline.get("report_metadata", {})
    return Settings(
        config_dir=directory,
        data_root=Path(os.getenv("CEREZAS_DATA_ROOT", pipeline["paths"]["data_root"])),
        assets_dir=Path(os.getenv("CEREZAS_ASSETS_DIR", str(directory / "assets"))),
        mongo=MongoSettings(
            uri=uri,
            database=mongo_raw["database"],
            fic1_collections=tuple(mongo_raw["fic1_collections"]),
            fic2_collection_prefix=mongo_raw["fic2_collection_prefix"],
        ),
        report_metadata=ReportMetadataSettings(
            enabled=bool(report_metadata.get("enabled", False)),
            database=str(report_metadata.get("database", "FIC_CEREZAS_HORAS_FRIO")),
            zone=str(report_metadata.get("zone", "")),
            timezone=str(report_metadata.get("timezone", "America/Santiago")),
        ),
        sites=sites,
        stations=stations,
        sensor_models=pipeline["sensor_models"],
        excluded_device_ids={value.lower() for value in filters.get("excluded_device_ids", [])},
        excluded_device_patterns=tuple(
            re.compile(value, re.IGNORECASE) for value in filters.get("excluded_device_patterns", [])
        ),
        schedule_timezone=str(pipeline.get("schedule_timezone", "America/Santiago")),
        schedule_hour=int(pipeline["schedule_hour"]),
        schedule_minute=int(pipeline["schedule_minute"]),
        schedule_start_month=int(pipeline["schedule_start_month"]),
        schedule_start_day=int(pipeline["schedule_start_day"]),
        schedule_end_month=int(pipeline["schedule_end_month"]),
        schedule_end_day=int(pipeline["schedule_end_day"]),
        season_start_month=int(pipeline["season_start_month"]),
        season_start_day=int(pipeline["season_start_day"]),
        catchup_days=int(pipeline.get("catchup_days", 7)),
        retry_minutes=int(pipeline.get("retry_minutes", 15)),
    )

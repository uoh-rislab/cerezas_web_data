from __future__ import annotations

import logging
import sqlite3
import time
from datetime import date, datetime, time as datetime_time, timedelta
from pathlib import Path
from typing import Optional

from .dates import (
    FIXED_CHILE_TZ,
    RunKind,
    fixed_now,
    is_in_schedule_window,
    kinds_for_scheduled_date,
)
from .pipeline import run_pipeline
from .settings import Settings


LOGGER = logging.getLogger(__name__)


class SchedulerState:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path)
        self.connection.execute(
            """CREATE TABLE IF NOT EXISTS runs (
                scheduled_date TEXT NOT NULL,
                kind TEXT NOT NULL,
                status TEXT NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0,
                last_attempt TEXT,
                error TEXT,
                PRIMARY KEY (scheduled_date, kind)
            )"""
        )
        self.connection.execute(
            "CREATE TABLE IF NOT EXISTS service_state (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        self.connection.commit()

    def get(self, key: str) -> Optional[str]:
        row = self.connection.execute("SELECT value FROM service_state WHERE key = ?", (key,)).fetchone()
        return row[0] if row else None

    def set(self, key: str, value: str) -> None:
        self.connection.execute(
            "INSERT INTO service_state(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        self.connection.commit()

    def should_run(self, scheduled_date: date, kind: RunKind, retry_minutes: int, now: datetime) -> bool:
        row = self.connection.execute(
            "SELECT status, last_attempt FROM runs WHERE scheduled_date = ? AND kind = ?",
            (scheduled_date.isoformat(), kind.value),
        ).fetchone()
        if not row:
            return True
        status, last_attempt = row
        if status == "complete":
            return False
        attempted = datetime.fromisoformat(last_attempt) if last_attempt else now - timedelta(days=1)
        return now - attempted >= timedelta(minutes=retry_minutes)

    def mark(self, scheduled_date: date, kind: RunKind, status: str, now: datetime, error: Optional[str] = None) -> None:
        self.connection.execute(
            """INSERT INTO runs(scheduled_date, kind, status, attempts, last_attempt, error)
               VALUES(?, ?, ?, 1, ?, ?)
               ON CONFLICT(scheduled_date, kind) DO UPDATE SET
                 status=excluded.status,
                 attempts=runs.attempts + CASE WHEN excluded.status='running' THEN 1 ELSE 0 END,
                 last_attempt=excluded.last_attempt,
                 error=excluded.error""",
            (scheduled_date.isoformat(), kind.value, status, now.isoformat(), error),
        )
        self.connection.commit()


def due_dates(settings: Settings, state: SchedulerState, now: datetime) -> list[date]:
    if not is_in_schedule_window(
        now.date(),
        settings.schedule_start_month,
        settings.schedule_start_day,
        settings.schedule_end_month,
        settings.schedule_end_day,
    ):
        return []
    last_seen = state.get("last_seen")
    if last_seen:
        first = max(date.fromisoformat(last_seen), now.date() - timedelta(days=settings.catchup_days))
    else:
        first = now.date()
    days = []
    current = first
    while current <= now.date():
        scheduled_at = datetime.combine(
            current,
            datetime_time(settings.schedule_hour, settings.schedule_minute),
            FIXED_CHILE_TZ,
        )
        if scheduled_at <= now:
            days.append(current)
        current += timedelta(days=1)
    return days


def run_scheduler(settings: Settings, poll_seconds: int = 30) -> None:
    state = SchedulerState(settings.data_root / "state" / "scheduler.db")
    LOGGER.info("Scheduler activo: %02d:%02d UTC-4 fijo", settings.schedule_hour, settings.schedule_minute)
    while True:
        now = fixed_now()
        for scheduled_date in due_dates(settings, state, now):
            for kind in kinds_for_scheduled_date(
                scheduled_date,
                settings.schedule_start_month,
                settings.schedule_start_day,
                settings.schedule_end_month,
                settings.schedule_end_day,
            ):
                if not state.should_run(scheduled_date, kind, settings.retry_minutes, now):
                    continue
                LOGGER.info("Iniciando %s para fecha programada %s", kind.value, scheduled_date)
                state.mark(scheduled_date, kind, "running", now)
                try:
                    run_pipeline(settings, kind, scheduled_date)
                    state.mark(scheduled_date, kind, "complete", fixed_now())
                    LOGGER.info("Completado %s para %s", kind.value, scheduled_date)
                except Exception as error:
                    state.mark(scheduled_date, kind, "failed", fixed_now(), str(error))
                    LOGGER.exception("Falló %s para %s", kind.value, scheduled_date)
        state.set("last_seen", now.date().isoformat())
        state.set("heartbeat", now.isoformat())
        time.sleep(poll_seconds)

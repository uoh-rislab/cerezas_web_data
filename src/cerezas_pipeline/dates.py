from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from enum import Enum


class RunKind(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


FIXED_CHILE_TZ = timezone(timedelta(hours=-4), name="UTC-04:00")


@dataclass(frozen=True)
class RunWindow:
    kind: RunKind
    scheduled_date: date
    report_date: date
    start_utc: datetime
    end_utc: datetime

    @property
    def run_id(self) -> str:
        return f"{self.kind.value}-{self.report_date.isoformat()}"


def is_in_schedule_window(
    day: date,
    start_month: int = 5,
    start_day: int = 2,
    end_month: int = 11,
    end_day: int = 1,
) -> bool:
    start = date(day.year, start_month, start_day)
    end = date(day.year, end_month, end_day)
    return start <= day <= end


def kinds_for_scheduled_date(
    day: date,
    start_month: int = 5,
    start_day: int = 2,
    end_month: int = 11,
    end_day: int = 1,
) -> list[RunKind]:
    """Return no jobs outside the schedule window; otherwise apply daily/weekly/monthly rules."""
    if not is_in_schedule_window(day, start_month, start_day, end_month, end_day):
        return []
    kinds = [RunKind.WEEKLY if day.weekday() == 0 else RunKind.DAILY]
    if day.day == 1:
        kinds.append(RunKind.MONTHLY)
    return kinds


def window_for(
    kind: RunKind,
    scheduled_date: date,
    season_start_month: int = 5,
    season_start_day: int = 1,
) -> RunWindow:
    report_date = scheduled_date - timedelta(days=1)
    start_local_date = date(report_date.year, season_start_month, season_start_day)
    if report_date < start_local_date:
        # Permite ejecuciones manuales anteriores a mayo usando la temporada previa.
        start_local_date = date(report_date.year - 1, season_start_month, season_start_day)

    start_local = datetime.combine(start_local_date, time.min, FIXED_CHILE_TZ)
    end_local = datetime.combine(report_date, time.max, FIXED_CHILE_TZ)
    return RunWindow(
        kind=kind,
        scheduled_date=scheduled_date,
        report_date=report_date,
        start_utc=start_local.astimezone(timezone.utc),
        end_utc=end_local.astimezone(timezone.utc),
    )


def fixed_now() -> datetime:
    return datetime.now(timezone.utc).astimezone(FIXED_CHILE_TZ)

import unittest
from datetime import date, datetime, timedelta, timezone

from cerezas_pipeline.dates import RunKind, kinds_for_scheduled_date, scheduled_datetime, window_for


class ScheduleTests(unittest.TestCase):
    def test_monday_runs_weekly(self):
        self.assertEqual(kinds_for_scheduled_date(date(2026, 6, 29)), [RunKind.WEEKLY])

    def test_saturday_and_sunday_run_daily(self):
        self.assertEqual(kinds_for_scheduled_date(date(2026, 7, 4)), [RunKind.DAILY])
        self.assertEqual(kinds_for_scheduled_date(date(2026, 7, 5)), [RunKind.DAILY])

    def test_first_day_adds_monthly_without_replacing_daily(self):
        self.assertEqual(
            kinds_for_scheduled_date(date(2026, 7, 1)),
            [RunKind.DAILY, RunKind.MONTHLY],
        )

    def test_first_day_monday_adds_monthly_without_replacing_weekly(self):
        self.assertEqual(
            kinds_for_scheduled_date(date(2026, 6, 1)),
            [RunKind.WEEKLY, RunKind.MONTHLY],
        )

    def test_schedule_starts_on_may_second(self):
        self.assertEqual(kinds_for_scheduled_date(date(2026, 5, 1)), [])
        self.assertEqual(kinds_for_scheduled_date(date(2026, 5, 2)), [RunKind.DAILY])

    def test_schedule_ends_on_november_first(self):
        self.assertEqual(kinds_for_scheduled_date(date(2026, 10, 31)), [RunKind.DAILY])
        self.assertEqual(
            kinds_for_scheduled_date(date(2026, 11, 1)),
            [RunKind.DAILY, RunKind.MONTHLY],
        )
        self.assertEqual(kinds_for_scheduled_date(date(2026, 11, 2)), [])


class WindowTests(unittest.TestCase):
    def test_daily_is_season_to_date_from_may_first(self):
        window = window_for(RunKind.DAILY, date(2026, 7, 1))
        self.assertEqual(window.report_date, date(2026, 6, 30))
        self.assertEqual(window.start_utc, datetime(2026, 5, 1, 4, tzinfo=timezone.utc))
        self.assertEqual(window.end_utc, datetime(2026, 7, 1, 3, 59, 59, 999999, tzinfo=timezone.utc))

    def test_monthly_is_previous_calendar_month(self):
        window = window_for(RunKind.MONTHLY, date(2026, 7, 1))
        self.assertEqual(window.report_date, date(2026, 6, 30))
        self.assertEqual(window.start_utc, datetime(2026, 5, 1, 4, tzinfo=timezone.utc))
        self.assertEqual(window.end_utc, datetime(2026, 7, 1, 3, 59, 59, 999999, tzinfo=timezone.utc))


class ChileScheduleTimezoneTests(unittest.TestCase):
    def test_schedule_uses_summer_and_winter_offsets(self):
        summer = scheduled_datetime(date(2026, 1, 15), 0, 30)
        winter = scheduled_datetime(date(2026, 7, 15), 0, 30)

        self.assertEqual(summer.utcoffset(), timedelta(hours=-3))
        self.assertEqual(winter.utcoffset(), timedelta(hours=-4))
        self.assertEqual(summer.astimezone(timezone.utc).hour, 3)
        self.assertEqual(winter.astimezone(timezone.utc).hour, 4)

    def test_nonexistent_midnight_runs_at_first_valid_minute(self):
        transition_day = scheduled_datetime(date(2026, 9, 6), 0, 30)

        self.assertEqual((transition_day.hour, transition_day.minute), (1, 0))
        self.assertEqual(transition_day.utcoffset(), timedelta(hours=-3))

if __name__ == "__main__":
    unittest.main()

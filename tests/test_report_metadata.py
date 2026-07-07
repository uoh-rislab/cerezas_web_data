import unittest
from datetime import date
from types import SimpleNamespace

from cerezas_pipeline.dates import RunKind, window_for
from cerezas_pipeline.report_metadata import (
    build_report_metadata_payload,
    date_to_unix_timestamp,
    metadata_period,
)


class ReportMetadataTests(unittest.TestCase):
    def test_metadata_periods(self):
        self.assertEqual(
            metadata_period(RunKind.DAILY, date(2026, 6, 29)).start,
            date(2026, 6, 29),
        )
        self.assertEqual(
            metadata_period(RunKind.WEEKLY, date(2026, 6, 28)).start,
            date(2026, 6, 22),
        )
        monthly = metadata_period(RunKind.MONTHLY, date(2026, 6, 30))
        self.assertEqual(monthly.start, date(2026, 6, 1))
        self.assertEqual(monthly.end, date(2026, 6, 30))

    def test_date_to_unix_timestamp_uses_chile_timezone(self):
        self.assertEqual(
            date_to_unix_timestamp(date(2025, 12, 11), "America/Santiago"),
            "1765422000",
        )

    def test_payload_includes_report_kind(self):
        settings = SimpleNamespace(
            report_metadata=SimpleNamespace(zone="", timezone="America/Santiago")
        )
        site = SimpleNamespace(
            site_id="fic2-graneros-agrofurore",
            group="fic2",
            city="graneros",
            name="Agrofurore",
            filename="Agrofurore",
            location="Graneros",
        )
        window = window_for(RunKind.MONTHLY, date(2026, 7, 1))
        payload = build_report_metadata_payload(settings, site, window, name="7")

        self.assertEqual(payload["data-field"], "fic2-graneros-agrofurore")
        self.assertEqual(payload["zone"], "")
        self.assertEqual(payload["kind"], "monthly")
        self.assertEqual(payload["name"], "7")


if __name__ == "__main__":
    unittest.main()

import tempfile
import unittest
from datetime import date
from pathlib import Path

from cerezas_pipeline.dates import RunKind
from cerezas_pipeline.email_delivery.templates import build_email_template

try:
    import yaml  # noqa: F401
except ImportError:
    yaml = None


class EmailTemplateTests(unittest.TestCase):
    def test_daily_template(self):
        template = build_email_template(RunKind.DAILY, date(2026, 6, 29))
        self.assertEqual(
            template.subject,
            "UOH Cerezas - Boletín diario de monitoreo agroclimático: 29 Junio del 2026",
        )
        self.assertIn("correspondiente a la presente semana", template.plain)
        self.assertIn("<strong>Universidad de O'Higgins - Proyecto FIC Cerezas</strong>", template.html)
        self.assertIn('src="cid:fic-logo"', template.html)
        self.assertIn("Transferencia tecnologías 4.0", template.plain)

    def test_weekly_template(self):
        template = build_email_template(RunKind.WEEKLY, date(2026, 6, 28))
        period = "22 Junio - 28 Junio del 2026"
        self.assertEqual(
            template.subject,
            f"UOH Cerezas - Boletín semanal de monitoreo agroclimático: {period}",
        )
        self.assertIn(f"correspondiente al período {period}", template.plain)

    def test_monthly_template(self):
        template = build_email_template(RunKind.MONTHLY, date(2025, 6, 30))
        self.assertEqual(
            template.subject,
            "UOH Cerezas - Boletín mensual monitoreo agroclimático Junio 2025",
        )
        self.assertIn("correspondiente a Junio 2025", template.plain)


class EmailConfigTests(unittest.TestCase):
    @unittest.skipIf(yaml is None, "PyYAML is not installed in the host Python")
    def test_global_cc_is_appended_and_deduplicated(self):
        from cerezas_pipeline.email_delivery.config import load_email_settings

        content = """\
enabled: false
global_cc:
  - {name: Global, email: global@example.com}
sites:
  test-site:
    to:
      - {name: Primary, email: primary@example.com}
    cc:
      - {name: Duplicate, email: GLOBAL@example.com}
      - {name: Local, email: local@example.com}
"""
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "email.yaml").write_text(content, encoding="utf-8")
            settings = load_email_settings(Path(directory))

        recipients = settings.recipients_for("test-site")
        self.assertEqual([value.email for value in recipients.to], ["primary@example.com"])
        self.assertEqual(
            [value.email for value in recipients.cc],
            ["global@example.com", "local@example.com"],
        )


if __name__ == "__main__":
    unittest.main()

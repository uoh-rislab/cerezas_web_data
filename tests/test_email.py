import tempfile
import unittest
from datetime import date
from pathlib import Path

from cerezas_pipeline.dates import RunKind
from cerezas_pipeline.email_delivery.audit import decode_text
from cerezas_pipeline.email_delivery.templates import PROJECT_LINE, build_email_template

try:
    import yaml  # noqa: F401
except ImportError:
    yaml = None


class EmailTemplateTests(unittest.TestCase):
    def test_daily_template(self):
        template = build_email_template(RunKind.DAILY, date(2026, 6, 29))
        self.assertEqual(
            template.subject,
            "Boletín diario de monitoreo agroclimático: 29 Junio del 2026",
        )
        self.assertIn("correspondiente a la presente semana", template.plain)
        self.assertIn("<strong>Universidad de O'Higgins - Proyecto FIC Cerezas</strong>", template.html)
        self.assertIn(f"<em>{PROJECT_LINE}</em>", template.html)
        self.assertIn('src="cid:fic-logo"', template.html)
        self.assertIn("Transferencia tecnologías 4.0", template.plain)

    def test_weekly_template(self):
        template = build_email_template(RunKind.WEEKLY, date(2026, 6, 28))
        period = "22 Junio - 28 Junio del 2026"
        self.assertEqual(
            template.subject,
            f"Boletín semanal de monitoreo agroclimático: {period}",
        )
        self.assertIn(f"correspondiente al período {period}", template.plain)
        self.assertIn(PROJECT_LINE, template.plain)
        self.assertIn(f"<em>{PROJECT_LINE}</em>", template.html)

    def test_monthly_template(self):
        template = build_email_template(RunKind.MONTHLY, date(2025, 6, 30))
        self.assertEqual(
            template.subject,
            "Boletín mensual monitoreo agroclimático Junio 2025",
        )
        self.assertIn("correspondiente a Junio 2025", template.plain)
        self.assertIn(PROJECT_LINE, template.plain)
        self.assertIn(f"<em>{PROJECT_LINE}</em>", template.html)


class EmailAuditTests(unittest.TestCase):
    def test_decode_text_handles_encoded_headers(self):
        self.assertEqual(
            decode_text("=?utf-8?q?Bolet=C3=ADn_diario?="),
            "Boletín diario",
        )


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

    @unittest.skipIf(yaml is None, "PyYAML is not installed in the host Python")
    def test_smtp_config_is_loaded(self):
        from cerezas_pipeline.email_delivery.config import load_email_settings

        content = """\
enabled: true
delivery_method: smtp
sender:
  display_name: Sender Name
  email: sender@example.com
smtp:
  username: sender@example.com
  password_env: SMTP_PASSWORD
"""
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "email.yaml").write_text(content, encoding="utf-8")
            settings = load_email_settings(Path(directory))

        self.assertEqual(settings.delivery_method, "smtp")
        self.assertEqual(settings.sender_email, "sender@example.com")
        self.assertEqual(settings.smtp_host, "smtp.gmail.com")
        self.assertEqual(settings.smtp_port, 587)
        self.assertEqual(settings.smtp_username, "sender@example.com")
        self.assertEqual(settings.smtp_password_env, "SMTP_PASSWORD")


if __name__ == "__main__":
    unittest.main()

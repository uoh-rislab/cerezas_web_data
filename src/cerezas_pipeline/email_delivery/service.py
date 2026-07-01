from __future__ import annotations

import base64
import json
import logging
import mimetypes
import sqlite3
from datetime import date, datetime, timedelta
from email.message import EmailMessage
from email.utils import formataddr
from pathlib import Path
from typing import Any, Optional
from zoneinfo import ZoneInfo

from ..artifacts import RunPaths
from ..dates import RunKind, window_for
from ..settings import Settings, Site
from .config import EmailAddress, EmailSettings
from .templates import build_email_template


LOGGER = logging.getLogger(__name__)
GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"


def _formatted(address: EmailAddress) -> str:
    return formataddr((address.name, address.email)) if address.name else address.email


def _find_pdf(paths: RunPaths, site: Site) -> Optional[Path]:
    directory = paths.pdf / site.group
    for label in (site.filename, site.name):
        matches = sorted(directory.glob(f"*{label}.pdf"))
        if matches:
            return matches[-1]
    return None


def build_message(
    email_settings: EmailSettings,
    kind: RunKind,
    report_date: date,
    site: Site,
    pdf_path: Path,
    logo_path: Path,
) -> EmailMessage:
    recipients = email_settings.recipients_for(site.site_id)
    template = build_email_template(kind, report_date)
    message = EmailMessage()
    message["Subject"] = template.subject
    message["From"] = formataddr((email_settings.sender_display_name, email_settings.delegated_user))
    message["To"] = ", ".join(_formatted(value) for value in recipients.to)
    if recipients.cc:
        message["Cc"] = ", ".join(_formatted(value) for value in recipients.cc)
    message.set_content(template.plain)
    message.add_alternative(template.html, subtype="html")

    logo_type, _ = mimetypes.guess_type(logo_path.name)
    maintype, subtype = (logo_type or "image/png").split("/", 1)
    html_part = message.get_payload()[-1]
    html_part.add_related(
        logo_path.read_bytes(), maintype=maintype, subtype=subtype,
        cid="<fic-logo>", filename=logo_path.name,
    )
    message.add_attachment(
        pdf_path.read_bytes(), maintype="application", subtype="pdf", filename=pdf_path.name,
    )
    return message


def _gmail_service(email_settings: EmailSettings) -> Any:
    if not email_settings.delegated_user:
        raise RuntimeError("Configure sender.delegated_user en email.yaml")
    if not email_settings.service_account_file.exists():
        raise RuntimeError(f"No existe {email_settings.service_account_file}")
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    credentials = service_account.Credentials.from_service_account_file(
        str(email_settings.service_account_file), scopes=[GMAIL_SEND_SCOPE]
    ).with_subject(email_settings.delegated_user)
    return build("gmail", "v1", credentials=credentials, cache_discovery=False)


def send_message(service: Any, message: EmailMessage) -> str:
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")
    result = service.users().messages().send(userId="me", body={"raw": raw}).execute()
    return str(result["id"])


class EmailDeliveryStore:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path)
        self.connection.execute(
            """CREATE TABLE IF NOT EXISTS email_deliveries (
                scheduled_date TEXT NOT NULL,
                kind TEXT NOT NULL,
                site_id TEXT NOT NULL,
                status TEXT NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0,
                last_attempt TEXT,
                gmail_message_id TEXT,
                error TEXT,
                PRIMARY KEY (scheduled_date, kind, site_id)
            )"""
        )
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def should_send(
        self, scheduled_date: date, kind: RunKind, site_id: str,
        retry_minutes: int, now: datetime,
    ) -> bool:
        row = self.connection.execute(
            "SELECT status, last_attempt FROM email_deliveries WHERE scheduled_date=? AND kind=? AND site_id=?",
            (scheduled_date.isoformat(), kind.value, site_id),
        ).fetchone()
        if not row:
            return True
        status, last_attempt = row
        if status == "complete":
            return False
        attempted = datetime.fromisoformat(last_attempt) if last_attempt else now - timedelta(days=1)
        return now - attempted >= timedelta(minutes=retry_minutes)

    def mark(
        self, scheduled_date: date, kind: RunKind, site_id: str, status: str,
        now: datetime, message_id: Optional[str] = None, error: Optional[str] = None,
    ) -> None:
        self.connection.execute(
            """INSERT INTO email_deliveries
               (scheduled_date, kind, site_id, status, attempts, last_attempt, gmail_message_id, error)
               VALUES (?, ?, ?, ?, 1, ?, ?, ?)
               ON CONFLICT(scheduled_date, kind, site_id) DO UPDATE SET
                 status=excluded.status,
                 attempts=email_deliveries.attempts + 1,
                 last_attempt=excluded.last_attempt,
                 gmail_message_id=excluded.gmail_message_id,
                 error=excluded.error""",
            (scheduled_date.isoformat(), kind.value, site_id, status, now.isoformat(), message_id, error),
        )
        self.connection.commit()


def is_email_time(email_settings: EmailSettings, now: datetime) -> bool:
    local = now.astimezone(ZoneInfo(email_settings.timezone))
    return (local.hour, local.minute) >= (email_settings.send_hour, email_settings.send_minute)


def _pipeline_complete(paths: RunPaths) -> bool:
    if not paths.manifest.exists():
        return False
    try:
        return json.loads(paths.manifest.read_text(encoding="utf-8")).get("status") == "complete"
    except (OSError, json.JSONDecodeError):
        return False


def deliver_kind(
    settings: Settings,
    email_settings: EmailSettings,
    scheduled_date: date,
    kind: RunKind,
    send: bool = True,
    site_filter: Optional[str] = None,
) -> list[dict[str, Any]]:
    window = window_for(
        kind, scheduled_date,
        season_start_month=settings.season_start_month,
        season_start_day=settings.season_start_day,
    )
    paths = RunPaths.create(settings.data_root, window)
    if send and not _pipeline_complete(paths):
        return [{"kind": kind.value, "status": "waiting", "reason": "pipeline incomplete"}]

    logo = settings.assets_dir / "logo_fic.png"
    if not logo.exists():
        raise RuntimeError(f"Falta el logo para correo: {logo}")
    now = datetime.now(ZoneInfo(email_settings.timezone))
    service = None
    results: list[dict[str, Any]] = []
    store = EmailDeliveryStore(settings.data_root / "state" / "scheduler.db")
    try:
        for site in settings.sites.values():
            if site_filter and site.site_id != site_filter:
                continue
            recipients = email_settings.recipients_for(site.site_id)
            if send and not recipients.to:
                results.append({"site": site.site_id, "status": "skipped", "reason": "no primary recipients"})
                continue
            if send and not store.should_send(
                scheduled_date, kind, site.site_id, email_settings.retry_minutes, now
            ):
                results.append({"site": site.site_id, "status": "already sent"})
                continue
            pdf = _find_pdf(paths, site)
            if not pdf:
                results.append({"site": site.site_id, "status": "waiting", "reason": "PDF not found"})
                continue
            message = build_message(email_settings, kind, window.report_date, site, pdf, logo)
            if not send:
                results.append(
                    {"site": site.site_id, "status": "preview", "subject": message["Subject"],
                     "to": message["To"], "cc": message.get("Cc", ""), "pdf": str(pdf)}
                )
                continue
            try:
                service = service or _gmail_service(email_settings)
                message_id = send_message(service, message)
                store.mark(scheduled_date, kind, site.site_id, "complete", now, message_id=message_id)
                results.append({"site": site.site_id, "status": "sent", "gmail_message_id": message_id})
            except Exception as error:
                store.mark(scheduled_date, kind, site.site_id, "failed", now, error=str(error))
                LOGGER.exception("Falló el correo %s %s", kind.value, site.site_id)
                results.append({"site": site.site_id, "status": "failed", "error": str(error)})
    finally:
        store.close()
    return results

from __future__ import annotations

import email
import imaplib
import os
from email.header import decode_header
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .config import EmailSettings


DEFAULT_SENT_MAILBOX = '"[Gmail]/Sent Mail"'


def decode_text(value: str | None) -> str:
    if not value:
        return ""
    decoded = ""
    for text, charset in decode_header(value):
        if isinstance(text, bytes):
            decoded += text.decode(charset or "utf-8", errors="replace")
        else:
            decoded += text
    return decoded


def _sender_username(email_settings: EmailSettings) -> str:
    username = email_settings.smtp_username or email_settings.sender_email or email_settings.delegated_user
    if not username:
        raise RuntimeError("Configure smtp.username o sender.email en email.yaml")
    return username


def _imap_password(email_settings: "EmailSettings") -> str:
    if email_settings.smtp_password_file and email_settings.smtp_password_file.is_file():
        return email_settings.smtp_password_file.read_text(encoding="utf-8").strip()
    if email_settings.smtp_password_env:
        password = os.environ.get(email_settings.smtp_password_env, "")
        if password:
            return password
    raise RuntimeError(
        "Configure smtp.password_env o smtp.password_file con el App Password de Gmail"
    )


def get_last_sent_recipients(
    email_settings: "EmailSettings",
    limit: int = 10,
    mailbox: str = DEFAULT_SENT_MAILBOX,
) -> list[dict[str, Any]]:
    username = _sender_username(email_settings)
    password = _imap_password(email_settings)
    results: list[dict[str, Any]] = []

    with imaplib.IMAP4_SSL("imap.gmail.com") as mail:
        mail.login(username, password)
        status, _ = mail.select(mailbox, readonly=True)
        if status != "OK":
            raise RuntimeError(
                f"No se pudo abrir el buzón IMAP {mailbox}. Verifique que IMAP esté habilitado."
            )

        status, data = mail.search(None, "ALL")
        if status != "OK":
            raise RuntimeError("No se pudieron buscar correos enviados por IMAP")

        ids = data[0].split()
        for message_id in reversed(ids[-limit:]):
            status, message_data = mail.fetch(message_id, "(RFC822)")
            if status != "OK" or not message_data:
                continue
            message = email.message_from_bytes(message_data[0][1])
            results.append(
                {
                    "date": decode_text(message["Date"]),
                    "to": decode_text(message["To"]),
                    "cc": decode_text(message["Cc"]),
                    "bcc": decode_text(message["Bcc"]),
                    "subject": decode_text(message["Subject"]),
                }
            )
    return results

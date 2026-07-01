from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import yaml


@dataclass(frozen=True)
class EmailAddress:
    name: str
    email: str


@dataclass(frozen=True)
class SiteRecipients:
    to: tuple[EmailAddress, ...]
    cc: tuple[EmailAddress, ...]


@dataclass(frozen=True)
class EmailSettings:
    enabled: bool
    timezone: str
    send_hour: int
    send_minute: int
    retry_minutes: int
    sender_display_name: str
    delegated_user: str
    service_account_file: Path
    global_cc: tuple[EmailAddress, ...]
    sites: dict[str, SiteRecipients]

    def recipients_for(self, site_id: str) -> SiteRecipients:
        configured = self.sites.get(site_id, SiteRecipients((), ()))
        return SiteRecipients(configured.to, _deduplicate(self.global_cc + configured.cc))


def _addresses(values: Optional[list[dict[str, Any]]]) -> tuple[EmailAddress, ...]:
    return tuple(
        EmailAddress(name=str(value.get("name", "")).strip(), email=str(value["email"]).strip())
        for value in (values or [])
        if str(value.get("email", "")).strip()
    )


def _deduplicate(values: tuple[EmailAddress, ...]) -> tuple[EmailAddress, ...]:
    result: list[EmailAddress] = []
    seen: set[str] = set()
    for value in values:
        key = value.email.lower()
        if key not in seen:
            seen.add(key)
            result.append(value)
    return tuple(result)


def disabled_email_settings() -> EmailSettings:
    return EmailSettings(False, "America/Santiago", 4, 0, 30, "", "", Path(""), (), {})


def load_email_settings(config_dir: Path) -> EmailSettings:
    path = config_dir / "email.yaml"
    if not path.exists():
        return disabled_email_settings()
    with path.open(encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}
    sender = raw.get("sender") or {}
    sites = {
        site_id: SiteRecipients(
            _addresses((values or {}).get("to")),
            _addresses((values or {}).get("cc")),
        )
        for site_id, values in (raw.get("sites") or {}).items()
    }
    return EmailSettings(
        enabled=bool(raw.get("enabled", False)),
        timezone=str(raw.get("timezone", "America/Santiago")),
        send_hour=int(raw.get("send_hour", 4)),
        send_minute=int(raw.get("send_minute", 0)),
        retry_minutes=int(raw.get("retry_minutes", 30)),
        sender_display_name=str(sender.get("display_name", "")),
        delegated_user=str(sender.get("delegated_user", "")).strip(),
        service_account_file=Path(str(sender.get("service_account_file", "/run/secrets/gmail-service-account.json"))),
        global_cc=_addresses(raw.get("global_cc")),
        sites=sites,
    )

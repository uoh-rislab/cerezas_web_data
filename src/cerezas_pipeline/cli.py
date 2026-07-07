from __future__ import annotations

import argparse
import json
import logging
import sqlite3
from datetime import date
from pathlib import Path

from .artifacts import RunPaths
from .dates import RunKind, chile_now, kinds_for_scheduled_date, window_for
from .email_delivery.audit import DEFAULT_SENT_MAILBOX, get_last_sent_recipients
from .email_delivery.config import load_email_settings
from .email_delivery.service import deliver_kind
from .pdf_report import generate_all_pdfs
from .pipeline import run_pipeline
from .scheduler import run_scheduler
from .settings import load_settings


def _date(value: str) -> date:
    return date.fromisoformat(value)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Pipeline de reportería UOH Cerezas")
    parser.add_argument("--config-dir", help="Directorio con archivos YAML")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run = subparsers.add_parser("run", help="Ejecutar un pipeline manualmente")
    run.add_argument("--kind", choices=[kind.value for kind in RunKind], required=True)
    run.add_argument("--scheduled-date", type=_date, default=None)
    run.add_argument(
        "--skip-pdf",
        action="store_true",
        help="Procesar hasta CSV/reportes sin generar boletines PDF",
    )

    dispatch = subparsers.add_parser("dispatch", help="Ejecutar lo programado para una fecha")
    dispatch.add_argument("--scheduled-date", type=_date, default=None)

    pdf = subparsers.add_parser("pdf", help="Regenerar solamente los PDF de una ejecución existente")
    pdf.add_argument("--kind", choices=[kind.value for kind in RunKind], required=True)
    pdf.add_argument("--scheduled-date", type=_date, required=True)

    email = subparsers.add_parser("email", help="Previsualizar o enviar correos de una ejecución existente")
    email.add_argument("--kind", choices=[kind.value for kind in RunKind], required=True)
    email.add_argument("--scheduled-date", type=_date, required=True)
    email.add_argument("--site", help="Limitar a un site ID")
    email.add_argument("--send", action="store_true", help="Enviar realmente mediante el método configurado")

    email_sent = subparsers.add_parser(
        "email-sent",
        help="Listar destinatarios de los últimos correos enviados por la cuenta SMTP",
    )
    email_sent.add_argument("--limit", type=int, default=10)
    email_sent.add_argument("--mailbox", default=DEFAULT_SENT_MAILBOX)

    plan = subparsers.add_parser("plan", help="Mostrar ejecuciones y ventanas sin conectarse")
    plan.add_argument("--scheduled-date", type=_date, default=None)

    subparsers.add_parser("schedule", help="Iniciar el scheduler permanente")
    subparsers.add_parser("health", help="Verificar estado operativo básico")
    return parser


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    arguments = _parser().parse_args()
    scheduled_date = getattr(arguments, "scheduled_date", None) or chile_now().date()

    if arguments.command == "plan":
        payload = []
        for kind in kinds_for_scheduled_date(scheduled_date):
            window = window_for(kind, scheduled_date)
            payload.append(
                {
                    "kind": kind.value,
                    "scheduled_date": scheduled_date.isoformat(),
                    "report_date": window.report_date.isoformat(),
                    "start_utc": window.start_utc.isoformat(),
                    "end_utc": window.end_utc.isoformat(),
                }
            )
        print(json.dumps(payload, indent=2))
        return

    settings = load_settings(arguments.config_dir)
    if arguments.command == "run":
        result = run_pipeline(
            settings,
            RunKind(arguments.kind),
            scheduled_date,
            generate_pdf=not arguments.skip_pdf,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif arguments.command == "dispatch":
        for kind in kinds_for_scheduled_date(scheduled_date):
            run_pipeline(settings, kind, scheduled_date)
    elif arguments.command == "pdf":
        kind = RunKind(arguments.kind)
        window = window_for(
            kind,
            scheduled_date,
            season_start_month=settings.season_start_month,
            season_start_day=settings.season_start_day,
        )
        paths = RunPaths.create(settings.data_root, window)
        results = generate_all_pdfs(settings, window, paths)
        print(json.dumps(results, ensure_ascii=False, indent=2))
    elif arguments.command == "email":
        email_settings = load_email_settings(settings.config_dir)
        if arguments.send and not email_settings.enabled:
            raise SystemExit("El envío está deshabilitado en config/email.yaml")
        results = deliver_kind(
            settings, email_settings, scheduled_date, RunKind(arguments.kind),
            send=arguments.send, site_filter=arguments.site,
        )
        print(json.dumps(results, ensure_ascii=False, indent=2))
    elif arguments.command == "email-sent":
        email_settings = load_email_settings(settings.config_dir)
        results = get_last_sent_recipients(
            email_settings,
            limit=arguments.limit,
            mailbox=arguments.mailbox,
        )
        print(json.dumps(results, ensure_ascii=False, indent=2))
    elif arguments.command == "schedule":
        run_scheduler(settings)
    elif arguments.command == "health":
        state = settings.data_root / "state" / "scheduler.db"
        if not state.exists():
            raise SystemExit("scheduler.db aún no existe")
        connection = sqlite3.connect(state)
        connection.execute("SELECT 1").fetchone()
        print("ok")


if __name__ == "__main__":
    main()

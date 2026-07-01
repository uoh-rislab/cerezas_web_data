from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from html import escape

from ..dates import RunKind


MONTHS = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio",
    7: "Julio", 8: "Agosto", 9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}


@dataclass(frozen=True)
class EmailTemplate:
    subject: str
    plain: str
    html: str


def _daily_date(value: date) -> str:
    return f"{value.day} {MONTHS[value.month]} del {value.year}"


def _weekly_range(end: date) -> str:
    start = end - timedelta(days=6)
    return f"{start.day} {MONTHS[start.month]} - {end.day} {MONTHS[end.month]} del {end.year}"


def _month(value: date) -> str:
    return f"{MONTHS[value.month]} {value.year}"


def build_email_template(kind: RunKind, report_date: date) -> EmailTemplate:
    if kind == RunKind.DAILY:
        period = _daily_date(report_date)
        subject = f"UOH Cerezas - Boletín diario de monitoreo agroclimático: {period}"
        description = (
            "nos complace informar que a través de este medio hacemos envío del Boletín Diario "
            "de Monitoreo Agroclimático correspondiente a la presente semana."
        )
        project = '<br>"Transferencia tecnologías 4.0 para la gestión del riesgo en la cadena de valor de la cereza"'
        project_plain = '\n"Transferencia tecnologías 4.0 para la gestión del riesgo en la cadena de valor de la cereza"'
    elif kind == RunKind.WEEKLY:
        period = _weekly_range(report_date)
        subject = f"UOH Cerezas - Boletín semanal de monitoreo agroclimático: {period}"
        description = (
            "nos complace informar que a través de este medio hacemos envío del Boletín Semanal "
            f"de Monitoreo Agroclimático correspondiente al período {period}."
        )
        project = ""
        project_plain = ""
    else:
        period = _month(report_date)
        subject = f"UOH Cerezas - Boletín mensual monitoreo agroclimático {period}"
        description = (
            "nos complace informar que a través de este medio hacemos envío del Boletín Mensual "
            f"de Monitoreo Agroclimático correspondiente a {period}."
        )
        project = ""
        project_plain = ""

    plain = (
        "Estimada/os,\n\n"
        f"Muy buenos días. Junto con saludar, {description}\n\n"
        "Estaremos atentos a su retroalimentación\n\n"
        "Un cordial saludo,\n--\n"
        "Universidad de O'Higgins - Proyecto FIC Cerezas"
        f"{project_plain}\n"
    )
    html = f"""\
<html><body style="font-family:Arial,Helvetica,sans-serif;font-size:14px;color:#222">
<p>Estimada/os,</p>
<p>Muy buenos días. Junto con saludar, {escape(description)}</p>
<p>Estaremos atentos a su retroalimentación</p>
<p>Un cordial saludo,</p>
<p>--<br><strong>Universidad de O'Higgins - Proyecto FIC Cerezas</strong>{project}</p>
<p><img src="cid:fic-logo" alt="Universidad de O'Higgins - Proyecto FIC Cerezas" style="max-width:620px;height:auto"></p>
</body></html>
"""
    return EmailTemplate(subject, plain, html)

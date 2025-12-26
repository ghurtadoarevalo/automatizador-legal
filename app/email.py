from datetime import date, datetime
from html import escape
from typing import Any, Mapping
from zoneinfo import ZoneInfo

DEFAULT_TZ = ZoneInfo("America/Santiago")

_REPORT_CSS = """
    :root{
      --bg:#0b1220;
      --card:#0f1b2d;
      --muted:#8aa0bd;
      --text:#eaf2ff;
      --border:rgba(255,255,255,.08);
      --ok:#2dd4bf;
      --bad:#fb7185;
      --badge-bg:rgba(255,255,255,.08);
      --shadow: 0 12px 28px rgba(0,0,0,.35);
    }
    *{box-sizing:border-box}
    body{
      margin:0;
      font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial, "Noto Sans", "Helvetica Neue", sans-serif;
      background: radial-gradient(1200px 700px at 20% 0%, rgba(45,212,191,.18), transparent 60%),
                  radial-gradient(900px 600px at 90% 10%, rgba(251,113,133,.14), transparent 55%),
                  var(--bg);
      color:var(--text);
      line-height:1.45;
    }
    header{
      padding:28px 18px 10px;
      max-width:1100px;
      margin:0 auto;
    }
    .title{
      display:flex; gap:12px; align-items:baseline; flex-wrap:wrap;
    }
    .title h1{margin:0; font-size:22px; letter-spacing:.2px}
    .meta{color:var(--muted); font-size:13px}
    main{max-width:1100px; margin:0 auto; padding:10px 18px 40px}
    .grid{display:grid; gap:14px}
    .card{
      background: linear-gradient(180deg, rgba(255,255,255,.04), transparent 28%),
                  var(--card);
      border:1px solid var(--border);
      border-radius:14px;
      box-shadow: var(--shadow);
      overflow:hidden;
    }
    .card-head{
      padding:14px 16px 12px;
      border-bottom:1px solid var(--border);
      display:flex;
      justify-content:space-between;
      gap:12px;
      align-items:flex-start;
      flex-wrap:wrap;
    }
    .card-head h2{margin:0; font-size:15px}
    .sub{color:var(--muted); font-size:12px; margin-top:2px}
    .badges{display:flex; gap:8px; flex-wrap:wrap}
    .badge{
      font-size:12px;
      padding:6px 10px;
      border:1px solid var(--border);
      background:var(--badge-bg);
      border-radius:999px;
      color:var(--text);
      display:inline-flex;
      gap:6px;
      align-items:center;
      white-space:nowrap;
    }
    .badge.bad{border-color:rgba(251,113,133,.45); background:rgba(251,113,133,.10)}
    .badge.ok{border-color:rgba(45,212,191,.45); background:rgba(45,212,191,.10)}
    .table-wrap{width:100%; overflow:auto}
    table{width:100%; border-collapse:separate; border-spacing:0}
    th, td{padding:10px 12px; border-bottom:1px solid var(--border); vertical-align:top}
    th{
      text-align:left;
      font-size:12px;
      color:var(--muted);
      font-weight:600;
      letter-spacing:.2px;
      background:rgba(255,255,255,.02);
      position:sticky;
      top:0;
      z-index:1;
    }
    tr:hover td{background:rgba(255,255,255,.03)}
    .date{
      font-variant-numeric: tabular-nums;
      white-space:nowrap;
    }
    .future td{border-bottom-color:rgba(251,113,133,.22)}
    .future .date{
      color:var(--bad);
      font-weight:700;
    }
    .pill{
      display:inline-flex;
      align-items:center;
      gap:6px;
      padding:2px 10px;
      border-radius:999px;
      border:1px solid rgba(251,113,133,.45);
      background:rgba(251,113,133,.10);
      font-size:11px;
      margin-left:8px;
      color:var(--text);
    }
    .empty{
      padding:16px;
      color:var(--muted);
      font-size:13px;
    }
    .footer{
      margin-top:14px;
      color:var(--muted);
      font-size:12px;
      text-align:center;
    }
"""


def _extract_case_fields(case_wrapper: Mapping[str, Any] | None) -> Mapping[str, Any]:
    """
    Cases often arrive wrapped like: {"json": {...fields...}, "pairedItem": {...}}
    We only need the actual case fields stored in "json".
    """
    if not case_wrapper:
        return {}
    case_fields = case_wrapper.get("json")
    if isinstance(case_fields, Mapping):
        return case_fields
    # Fallback: if payload isn't wrapped, assume it's already the case dict.
    return case_wrapper


def _parse_ddmmyyyy(value: str, tz: ZoneInfo = DEFAULT_TZ) -> date | None:
    try:
        # Expected format from PJUD table: "dd/mm/yyyy"
        # Date from string is timezone-agnostic; tz exists to keep call-sites consistent.
        _ = tz
        return datetime.strptime(value.strip(), "%d/%m/%Y").date()
    except ValueError:
        return None


def _case_meta_line(case_wrapper: Mapping[str, Any] | None) -> str:
    case_fields = _extract_case_fields(case_wrapper)
    if not case_fields:
        return "Sin metadata de caso"
    labels = {
        "competency": "Competencia",
        "court": "Corte",
        "book": "Libro",
        "rol": "Rol",
        "year": "Año",
    }
    keys = ("competency", "court", "book", "rol", "year")
    chunks = [
        f"{labels.get(k, k)}: {case_fields.get(k)}" for k in keys if case_fields.get(k)
    ]
    return " · ".join(chunks) if chunks else "Sin metadata de caso"


def _is_no_data_message(schedule: list[list[str]] | None) -> str | None:
    """
    PJUD sometimes returns a single-cell row: ["Ningún dato disponible en esta tabla"]
    If so, return that message to show it nicely; otherwise None.
    """
    if not schedule:
        return None
    if len(schedule) == 1 and len(schedule[0]) == 1:
        msg = schedule[0][0] or ""
        if "Ningún dato disponible" in msg:
            return msg
    return None


def render_schedule_results_email_html(
    schedules: list[list[list[str]] | str],
    *,
    cases: list[dict] | None = None,
) -> str:
    """
    Gmail/email-client friendly HTML:
    - Uses table-based layout (nested tables)
    - Uses inline styles only (no <style> tag)
    - Avoids modern CSS features that are inconsistently supported in email clients
    """
    now = datetime.now(DEFAULT_TZ)
    today = now.date()
    generated_at = now.strftime("%d/%m/%Y %H:%M:%S")

    # Common inline styles
    page_bg = "background-color:#0b1220;"
    text = "color:#eaf2ff;"
    muted = "color:#8aa0bd;"
    card_bg = "background-color:#0f1b2d;"
    border = "border:1px solid rgba(255,255,255,0.10);"
    radius = "border-radius:12px;"
    font = "font-family:Arial, Helvetica, sans-serif;"

    def badge(label: str, *, variant: str = "neutral") -> str:
        if variant == "ok":
            b = "border:1px solid rgba(45,212,191,0.55); background-color:rgba(45,212,191,0.12);"
        elif variant == "bad":
            b = "border:1px solid rgba(251,113,133,0.55); background-color:rgba(251,113,133,0.12);"
        else:
            b = "border:1px solid rgba(255,255,255,0.12); background-color:rgba(255,255,255,0.06);"
        return (
            f'<span style="display:inline-block; padding:6px 10px; border-radius:999px; '
            f'font-size:12px; {text} {b}">{escape(label)}</span>'
        )

    parts: list[str] = []
    parts.append("<!doctype html><html><body>")
    parts.append(
        f'<table role="presentation" cellpadding="0" cellspacing="0" width="100%" style="{page_bg} {font} {text} padding:0; margin:0;">'
        '<tr><td align="center" style="padding:24px 12px;">'
        f'<table role="presentation" cellpadding="0" cellspacing="0" width="100%" style="max-width:900px;">'
        "<tr><td>"
        f'<div style="font-size:18px; font-weight:700; {text}">Resultados — Programación de Sala</div>'
        f'<div style="margin-top:6px; font-size:12px; {muted}">Generado: {escape(generated_at)}</div>'
        f'<div style="margin-top:8px; font-size:12px; {muted}">Se marca como <b style="{text}">FUTURA</b> cualquier fecha mayor a la fecha actual.</div>'
        "</td></tr>"
    )

    for idx, schedule in enumerate(schedules, start=1):
        case_wrapper = cases[idx - 1] if cases and idx - 1 < len(cases) else None
        meta_line = _case_meta_line(
            case_wrapper if isinstance(case_wrapper, Mapping) else None
        )

        is_error = isinstance(schedule, str)
        rows = []
        future_rows = 0
        
        if not is_error:
            rows = [r for r in (schedule or []) if r]
            future_rows = sum(
                1
                for r in rows
                if (parsed := _parse_ddmmyyyy(r[-1] if r else "")) is not None
                and parsed > today
            )

        parts.append('<tr><td style="padding-top:14px;">')
        parts.append(
            f'<table role="presentation" cellpadding="0" cellspacing="0" width="100%" '
            f'style="{card_bg} {border} {radius} overflow:hidden;">'
        )
        # Card head
        parts.append('<tr><td style="padding:14px 14px 10px;">')
        parts.append(
            f'<div style="font-size:14px; font-weight:700; {text}">Caso #{idx}</div>'
            f'<div style="margin-top:4px; font-size:12px; {muted}">{escape(meta_line)}</div>'
        )
        parts.append('<div style="margin-top:10px;">')
        if is_error:
            parts.append(badge("Error de validación", variant="bad"))
        else:
            parts.append(badge(f"Filas: {len(rows)}", variant="ok"))
            parts.append("&nbsp;")
            parts.append(
                badge(
                    f"Fechas futuras: {future_rows}",
                    variant=("bad" if future_rows else "neutral"),
                )
            )
        parts.append("</div>")
        parts.append("</td></tr>")

        if is_error:
            parts.append(
                f'<tr><td style="padding:12px 14px 14px; font-size:13px; color:#fb7185;">'
                f'<strong>Fallo la validación:</strong> {escape(schedule)}'
                f'</td></tr>'
            )
            parts.append("</table></td></tr>")
            continue

        if not rows:
            parts.append(
                f'<tr><td style="padding:12px 14px 14px; font-size:12px; {muted}">Sin resultados.</td></tr>'
            )
            parts.append("</table></td></tr>")
            continue

        if msg := _is_no_data_message(schedule):
            parts.append(
                f'<tr><td style="padding:12px 14px 14px; font-size:12px; {muted}">{escape(msg)}</td></tr>'
            )
            parts.append("</table></td></tr>")
            continue

        # Table of rows (simple, no sticky headers)
        max_cols = max((len(r) for r in rows), default=0)
        headers = ["Sala", "Número", "Causa", "Ingreso", "Fecha"]
        # Keep safe if upstream changes column count:
        if max_cols and max_cols != len(headers):
            headers = [f"Columna {i}" for i in range(1, max_cols + 1)]
            headers[-1] = "Fecha"

        parts.append('<tr><td style="padding:0 14px 14px;">')
        parts.append(
            f'<table role="presentation" cellpadding="0" cellspacing="0" width="100%" '
            f'style="border-collapse:collapse; {border} border-radius:10px;">'
        )
        # header row
        parts.append("<tr>")
        for h in headers:
            parts.append(
                f'<td style="padding:10px 10px; font-size:12px; font-weight:700; {muted} '
                f'background-color:rgba(255,255,255,0.04); border-bottom:1px solid rgba(255,255,255,0.10);">'
                f"{escape(h)}</td>"
            )
        parts.append("</tr>")

        for r in rows:
            padded = (r + [""] * max(0, len(headers) - len(r)))[: len(headers)]
            parsed = _parse_ddmmyyyy(padded[-1]) if padded else None
            is_future = bool(parsed and parsed > today)
            row_bg = "background-color:rgba(251,113,133,0.06);" if is_future else ""
            parts.append(f'<tr style="{row_bg}">')
            for col_idx, cell in enumerate(padded):
                if col_idx == len(headers) - 1:
                    date_style = (
                        "color:#fb7185; font-weight:700;" if is_future else text
                    )
                    fut = ""
                    if is_future:
                        fut = (
                            ' <span style="display:inline-block; margin-left:6px; padding:2px 8px; '
                            "border-radius:999px; font-size:11px; "
                            "border:1px solid rgba(251,113,133,0.55); background-color:rgba(251,113,133,0.12); "
                            f'{text}">FUTURA</span>'
                        )
                    parts.append(
                        f'<td style="padding:10px 10px; font-size:12px; {date_style} '
                        f'border-bottom:1px solid rgba(255,255,255,0.10); white-space:nowrap;">'
                        f"{escape(cell)}{fut}</td>"
                    )
                else:
                    parts.append(
                        f'<td style="padding:10px 10px; font-size:12px; {text} '
                        f'border-bottom:1px solid rgba(255,255,255,0.10);">'
                        f"{escape(cell)}</td>"
                    )
            parts.append("</tr>")

        parts.append("</table></td></tr>")
        parts.append("</table></td></tr>")

    parts.append(
        '<tr><td style="padding-top:16px;">'
        f'<div style="text-align:center; font-size:12px; {muted}">Automatizador legal · Reporte</div>'
        "</td></tr></table></td></tr></table>"
    )
    parts.append("</body></html>")
    return "".join(parts)


def process_schedule_results(
    schedule_results: list[list[list[str]] | str],
    *,
    cases: list[dict] | None = None,
) -> str:
    """Backwards-compatible name used by the endpoint."""
    return render_schedule_results_email_html(schedule_results, cases=cases)

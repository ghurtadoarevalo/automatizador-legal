import os
import asyncio
import uuid
from typing import Any

import httpx
from fastapi import FastAPI
from pydantic import BaseModel

from app.automatization import playwright_start_process
from app.email import process_schedule_results
from app.process_excel import validate_row_data

app = FastAPI()

N8N_WEBHOOK_URL = os.getenv(
    "N8N_WEBHOOK_URL",
    "https://n8n.ghurtadodev.cl/webhook/7e84ffba-5315-43f3-bc46-a645f96bb786",
)


class Cases(BaseModel):
    cases: list[dict]


async def _post_to_n8n_webhook(payload: dict[str, Any]) -> None:
    timeout = httpx.Timeout(connect=10.0, read=60.0, write=30.0, pool=10.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(N8N_WEBHOOK_URL, json=payload)
        resp.raise_for_status()


async def _process_cases_and_notify(*, job_id: str, parsed_cases: list[dict], format: str) -> None:
    all_results: list[Any] = []
    valid_cases: list[dict] = []
    case_indices: list[int] = []

    for i, case_wrapper in enumerate(parsed_cases):
        # Handle potential wrapping as seen in app/email.py _extract_case_fields
        case_fields = (
            case_wrapper.get("json", case_wrapper) if isinstance(case_wrapper, dict) else case_wrapper
        )

        try:
            validate_row_data(
                competency=case_fields.get("competency"),
                rol=case_fields.get("rol"),
                year=case_fields.get("year"),
                court=case_fields.get("court"),
                book=case_fields.get("book"),
            )
            all_results.append(None)  # Placeholder
            valid_cases.append(case_wrapper)
            case_indices.append(i)
        except ValueError as e:
            all_results.append(str(e))

    try:
        if valid_cases:
            print(f"[{job_id}] Iniciando proceso para {len(valid_cases)} casos válidos")
            cdp_url = os.getenv("PLAYWRIGHT_CDP_URL")
            schedule_results = await playwright_start_process(
                valid_cases,
                headless=False,  # ignored when using CDP
                cdp_url=cdp_url,
            )

            for idx, result in zip(case_indices, schedule_results or []):
                all_results[idx] = result

        html = process_schedule_results(all_results, cases=parsed_cases)

        await _post_to_n8n_webhook(
            {
                "job_id": job_id,
                "status": "completed",
                "format": format,
                "cases": parsed_cases,
                "results": all_results,
                "html": html,
            }
        )
        print(f"[{job_id}] Webhook n8n enviado OK")
    except Exception as e:
        # Best-effort error notification
        try:
            await _post_to_n8n_webhook(
                {
                    "job_id": job_id,
                    "status": "failed",
                    "format": format,
                    "cases": parsed_cases,
                    "error": str(e),
                    "results": all_results,
                }
            )
            print(f"[{job_id}] Webhook n8n enviado con ERROR")
        except Exception as notify_err:
            print(f"[{job_id}] Falló notificación a n8n: {notify_err}")
        print(f"[{job_id}] Error en proceso: {e}")


def _swallow_task_exception(task: asyncio.Task) -> None:
    try:
        task.exception()
    except asyncio.CancelledError:
        return


@app.post("/", status_code=202)
async def root(cases: Cases, format: str = "json"):
    parsed_cases = cases.cases
    if not parsed_cases:
        return {"error": "No cases found"}

    job_id = str(uuid.uuid4())

    task = asyncio.create_task(
        _process_cases_and_notify(job_id=job_id, parsed_cases=parsed_cases, format=format)
    )
    # Avoid "Task exception was never retrieved" warnings
    task.add_done_callback(_swallow_task_exception)

    return {
        "message": "Se está procesando la información",
        "job_id": job_id,
    }

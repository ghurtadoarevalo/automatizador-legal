import os
from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.responses import HTMLResponse

from app.automatization import playwright_start_process
from app.email import process_schedule_results
from app.process_excel import validate_row_data

app = FastAPI()


class Cases(BaseModel):
    cases: list[dict]


@app.post("/")
async def root(cases: Cases, format: str = "json"):
    parsed_cases = cases.cases
    if not parsed_cases:
        return {"error": "No cases found"}

    all_results = []
    valid_cases = []
    case_indices = []

    for i, case_wrapper in enumerate(parsed_cases):
        # Handle potential wrapping as seen in app/email.py _extract_case_fields
        case_fields = case_wrapper.get("json", case_wrapper) if isinstance(case_wrapper, dict) else case_wrapper
        
        try:
            validate_row_data(
                competency=case_fields.get("competency"),
                rol=case_fields.get("rol"),
                year=case_fields.get("year"),
                court=case_fields.get("court"),
                book=case_fields.get("book")
            )
            all_results.append(None)  # Placeholder
            valid_cases.append(case_wrapper)
            case_indices.append(i)
        except ValueError as e:
            all_results.append(str(e))

    try:
        if valid_cases:
            print(f"Iniciando proceso para {len(valid_cases)} casos válidos")
            # If set, the container will use the Mac's Chrome UI via CDP
            # Example: http://host.docker.internal:9222
            cdp_url = os.getenv("PLAYWRIGHT_CDP_URL")
            schedule_results = await playwright_start_process(
                valid_cases,
                headless=False,  # ignored when using CDP; Chrome is on your Mac anyway
                cdp_url=cdp_url,
            )
            
            # Map valid results back to all_results
            for idx, result in zip(case_indices, schedule_results or []):
                all_results[idx] = result
    except Exception as e:
        print(e)
        return {"error": str(e)}

    html = process_schedule_results(all_results, cases=parsed_cases)
    return HTMLResponse(content=html, status_code=200)

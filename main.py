import os
from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.responses import HTMLResponse

from app.automatization import playwright_start_process
from app.email import process_schedule_results


app = FastAPI()


class Cases(BaseModel):
    cases: list[dict]


@app.post("/")
async def root(cases: Cases, format: str = "json"):
    parsed_cases = cases.cases
    if not parsed_cases:
        return {"error": "No cases found"}
    try:
        print(f"Iniciando proceso para {parsed_cases}")

        # If set, the container will use the Mac's Chrome UI via CDP
        # Example: http://host.docker.internal:9222
        cdp_url = os.getenv("PLAYWRIGHT_CDP_URL")
        schedule_results = await playwright_start_process(
            parsed_cases,
            headless=False,  # ignored when using CDP; Chrome is on your Mac anyway
            cdp_url=cdp_url,
        )
    except Exception as e:
        print(e)
        return {"error": str(e)}
    html = process_schedule_results(schedule_results or [], cases=parsed_cases)
    return HTMLResponse(content=html, status_code=200)

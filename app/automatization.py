import os
import random
import datetime as _dt
from pathlib import Path

from playwright.async_api import async_playwright, Playwright, Page
from playwright_stealth import Stealth
from pydantic import BaseModel


def _ts() -> str:
    return _dt.datetime.now().strftime("%Y%m%d-%H%M%S")


async def _dump_debug(page: Page, label: str) -> None:
    """
    Save enough information to debug headless-only issues.
    Safe to call even if the page is already half-broken.
    """
    try:
        _ARTIFACTS_DIR = Path("artifacts")
        _ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
        base = _ARTIFACTS_DIR / f"{_ts()}_{label}"
        await page.screenshot(path=str(base.with_suffix(".png")), full_page=True)
        base.with_suffix(".html").write_text(await page.content(), encoding="utf-8")
        base.with_suffix(".url.txt").write_text(page.url, encoding="utf-8")
    except Exception:
        # Debug dump should never crash the main flow.
        return


async def _init_browser_and_page(
    p: Playwright,
    *,
    headless: bool,
    cdp_url: str | None,
) -> tuple[object, Page, bool]:
    """
    If cdp_url is provided, connect to a Chrome/Chromium instance running on the HOST (Mac)
    via CDP (e.g. http://host.docker.internal:9222) so the browser UI appears on the host.

    Returns: (browser, page, is_cdp)
    - is_cdp=True means we must NOT close the browser (it belongs to the host).
    """
    if cdp_url:
        # Normalize common user inputs (avoid accidental trailing "/." or "/")
        cdp_url = cdp_url.strip()
        while cdp_url.endswith("/.") or cdp_url.endswith("/"):
            cdp_url = cdp_url[:-2] if cdp_url.endswith("/.") else cdp_url[:-1]

        browser = await p.chromium.connect_over_cdp(cdp_url, slow_mo=1000)
        # Reuse a persistent context if available (better for captcha/session).
        if getattr(browser, "contexts", None) and browser.contexts:
            context = browser.contexts[0]
        else:
            context = await browser.new_context(
                timezone_id="America/Santiago",
                locale="es-CL",
            )
        page = await context.new_page()
        return browser, page, True

    browser = await p.chromium.launch(headless=headless, slow_mo=1000)
    context = await browser.new_context(
        timezone_id="America/Santiago",
        locale="es-CL",
    )
    page = await context.new_page()
    return browser, page, False


async def playwright_goto_courtroom_schedule_page(page: Page):
    await page.goto("https://oficinajudicialvirtual.pjud.cl/home/index.php")
    await page.wait_for_load_state("domcontentloaded")
    await page.mouse.move(random.random() * 800, random.random() * 800)

    await page.wait_for_selector('//*[@id="focus"]/button')
    await page.click('//*[@id="focus"]/button')
    await page.mouse.move(random.random() * 800, random.random() * 800)
    await page.wait_for_selector('//*[@id="sidebar"]/ul/li[16]/a')
    await page.click('//*[@id="sidebar"]/ul/li[16]/a')
    await page.mouse.move(random.random() * 800, random.random() * 800)


async def playwright_find_courtroom_schedule(page: Page, case: dict):
    await page.wait_for_selector('//*[@id="progComp"]')
    await page.select_option('//*[@id="progComp"]', case["competency"])
    await page.mouse.move(random.random() * 800, random.random() * 800)
    if case["competency"] == "Corte Apelaciones":
        await page.wait_for_selector('//*[@id="progCorte"]')
        await page.select_option('//*[@id="progCorte"]', case["court"])
        await page.mouse.move(random.random() * 800, random.random() * 800)
    await page.wait_for_selector('//*[@id="progRolCausa"]')
    await page.fill('//*[@id="progRolCausa"]', case["rol"])
    await page.mouse.move(random.random() * 800, random.random() * 800)
    await page.wait_for_selector('//*[@id="progEraCausa"]')
    await page.fill('//*[@id="progEraCausa"]', case["year"])
    await page.mouse.move(random.random() * 800, random.random() * 800)
    if case["competency"] == "Corte Apelaciones":
        await page.wait_for_selector('//*[@id="progTipoCausa"]')
        await page.click('//*[@id="progTipoCausa"]')
        await page.select_option('//*[@id="progTipoCausa"]', case["book"])
        await page.mouse.move(random.random() * 800, random.random() * 800)
    await page.wait_for_selector('//*[@id="btnProgConsulta"]')
    await page.click('//*[@id="btnProgConsulta"]')
    await page.mouse.move(random.random() * 800, random.random() * 800)


async def playwright_get_courtroom_schedule(page: Page):
    await page.wait_for_selector('//*[@id="dtaTableDetalleProgSala"]')
    table_locator = page.locator('//*[@id="dtaTableDetalleProgSala"]')
    row_locators = await table_locator.locator("tr").all()
    rows = []
    for index, row_locator in enumerate(row_locators):
        cells = await row_locator.locator("td").all()
        row = [await cell.inner_text() for cell in cells]
        rows.append(row)
    return rows


class Case(BaseModel):
    competency: str
    rol: str
    year: str
    court: str | None
    book: str | None


class Cases(BaseModel):
    cases: list[Case]


async def playwright_start_process(cases: Cases, headless: bool = True, cdp_url: str | None = None):
    schedule_results: list[list[list[str]]] = []

    # Allow env var configuration (useful inside docker-compose)
    if not cdp_url:
        cdp_url = os.getenv("PLAYWRIGHT_CDP_URL")

    # NOTE: playwright-stealth wraps Playwright internals and can interfere with CDP connections.
    # We only enable stealth for the local-launch path.
    cm = async_playwright() if cdp_url else Stealth().use_async(async_playwright())

    async with cm as p:
        browser, page, is_cdp = await _init_browser_and_page(p, headless=headless, cdp_url=cdp_url)
        try:
            await playwright_goto_courtroom_schedule_page(page)
            print("Pagina cargada")
            for case in cases:
                # Incoming cases are dicts from the API body; keep a tolerant fallback.
                case_dict = case.get("json") if isinstance(case, dict) else None
                if not case_dict:
                    case_dict = case

                print("\n" + "-" * 20)
                print(f"Iniciando proceso para {case_dict}")

                await playwright_find_courtroom_schedule(page, case_dict)
                schedule = await playwright_get_courtroom_schedule(page)
                schedule_results.append(schedule[2:])
                print(f"Proceso para {case_dict} finalizado")
        except Exception:
            await _dump_debug(page, "flow_timeout")
            raise Exception("Error al obtener el horario de la sala")
        finally:
            await page.close()
            # If connected to host Chrome via CDP, do not close the host browser.
            if not is_cdp:
                try:
                    await browser.close()
                except Exception:
                    pass
    return schedule_results

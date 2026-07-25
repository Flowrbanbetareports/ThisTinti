from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path

from playwright.sync_api import Route, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app" / "static"


def browser_executable() -> str | None:
    configured = os.getenv("PLAYWRIGHT_CHROMIUM_EXECUTABLE")
    if configured and Path(configured).is_file():
        return configured
    for candidate in ("google-chrome", "chromium", "chromium-browser"):
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    return None


def build_document() -> str:
    index = (STATIC / "index.html").read_text(encoding="utf-8")
    body = index.split("<body>", 1)[1].split("</body>", 1)[0]
    body = re.sub(r'<script src="/app\.js(?:\?v=[^"]+)?" defer></script>', "", body)
    css = "\n".join(
        (STATIC / name).read_text(encoding="utf-8")
        for name in ("styles-original.css", "styles.css", "onboarding.css", "sidebar-scroll.css", "local-first-run.css")
    ).replace('@import url("/styles-original.css");', "")
    core = (STATIC / "app-core.js").read_text(encoding="utf-8")
    core = "\n".join("const getCookie = () => '';" if line.startswith("const getCookie =") else line for line in core.splitlines())
    return f"<!doctype html><html><head><meta charset='utf-8'><base href='http://127.0.0.1:8765/'><style>{css}</style></head><body>{body}<script>{core}</script></body></html>"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> None:
    requests: list[dict] = []
    job = {
        "id": "job-failed-1",
        "job_type": "reprocess_document",
        "status": "failed",
        "priority": 100,
        "attempts": 3,
        "max_attempts": 3,
        "progress": 45,
        "error_message": "Riga 2: quantity non è numerico",
        "created_at": "2026-07-25T12:00:00Z",
        "started_at": "2026-07-25T12:01:00Z",
        "completed_at": "2026-07-25T12:02:00Z",
        "result": {},
        "context": {"filename": "ordine-errato.json", "document_id": "doc-1", "retry_of": None},
        "can_cancel": False,
        "can_retry": True,
    }
    document = {
        "id": "doc-1",
        "document_type": "order",
        "number": "PO-ERR-1",
        "document_date": "2026-07-25",
        "source_filename": "ordine-errato.json",
        "parse_status": "failed",
        "parse_message": "Riga 2: quantity non è numerico",
        "confidence": 0.4,
        "supplier": "Fornitore prova",
        "lines": [],
    }

    def route_api(route: Route) -> None:
        request = route.request
        url = request.url
        method = request.method
        if url.endswith("/api/health"):
            route.fulfill(json={"edition": "local"})
        elif url.endswith("/api/auth/me"):
            route.fulfill(status=401, json={"detail": "not authenticated"})
        elif url.endswith("/api/dashboard"):
            route.fulfill(json={"documents": 1, "cases_open": 0, "chains": 0, "amount_potential": 0, "parsing_failures": 1})
        elif url.endswith("/api/documents"):
            route.fulfill(json=[])
        elif url.endswith("/api/chains"):
            route.fulfill(json=[])
        elif url.endswith("/api/cases"):
            route.fulfill(json=[])
        elif "/api/jobs?" in url:
            route.fulfill(json={"items": [job], "total": 1, "limit": 25, "offset": 0, "status_counts": {"queued": 0, "running": 0, "completed": 0, "failed": 1, "cancelled": 0}})
        elif url.endswith("/api/jobs/job-failed-1/retry") and method == "POST":
            requests.append({"kind": "retry"})
            route.fulfill(status=202, json={"created": True, "job": {**job, "id": "job-retry-1", "status": "queued", "can_retry": False, "can_cancel": True, "context": {**job["context"], "retry_of": job["id"]}}})
        elif url.endswith("/api/jobs/job-failed-1"):
            route.fulfill(json=job)
        elif url.endswith("/api/documents/doc-1"):
            route.fulfill(json=document)
        elif url.endswith("/api/documents/doc-1/file"):
            route.fulfill(status=200, body=b"{}", headers={"content-type": "application/json"})
        elif url.endswith("/api/jobs/documents/doc-1/reprocess") and method == "POST":
            requests.append({"kind": "reprocess", "payload": json.loads(request.post_data or "{}")})
            route.fulfill(status=202, json={"created": True, "job": {**job, "id": "job-reprocess-1", "status": "queued", "can_retry": False, "can_cancel": True}})
        else:
            route.fulfill(status=404, json={"detail": f"not mocked: {method} {url}"})

    executable = browser_executable()
    with sync_playwright() as playwright:
        launch_args = {"headless": True}
        if executable:
            launch_args["executable_path"] = executable
        browser = playwright.chromium.launch(**launch_args)
        page = browser.new_page(viewport={"width": 1366, "height": 768})
        page.route("**/api/**", route_api)
        page.set_content(build_document(), wait_until="load")
        page.wait_for_timeout(100)
        page.evaluate("""async () => {
          state.user = {role: 'admin', email: 'admin@example.com'};
          document.querySelector('#authView').classList.add('hidden');
          document.querySelector('#appView').classList.remove('hidden');
          await openView('jobs');
        }""")
        page.wait_for_selector("#jobsTable .job-retry-button")
        require(page.get_by_text("Riga 2: quantity non è numerico", exact=True).is_visible(), "Persistent job error is not visible")
        require(page.locator("#jobsFailed").inner_text() == "1", "Failed-job metric is incorrect")
        require(page.locator("#jobsTable .job-retry-button").is_visible(), "Retry action is not visible")

        page.locator("#jobsTable .job-document-button").click()
        page.wait_for_selector("#documentDialog[open]")
        require(page.locator("#documentDialog .persistent-error").is_visible(), "Document parser error is not persistent")
        page.locator("#documentReprocessButton").click()
        page.wait_for_selector("#reprocessDialog[open]")
        require(page.locator("#reprocessNumber").input_value() == "PO-ERR-1", "Reprocess form did not preserve document number")
        require(page.locator("#reprocessSupplier").input_value() == "Fornitore prova", "Reprocess form did not preserve supplier")
        page.locator("#reprocessNumber").fill("PO-CORRETTO-1")
        page.locator("#reprocessForm").evaluate("form => form.requestSubmit()")
        page.wait_for_timeout(500)
        require(any(item["kind"] == "reprocess" for item in requests), "Reprocess request was not sent")
        reprocess = next(item for item in requests if item["kind"] == "reprocess")
        require(reprocess["payload"]["number"] == "PO-CORRETTO-1", "Corrected document number was not submitted")
        browser.close()

    print(json.dumps({"failed_metric": 1, "persistent_error": True, "reprocess_request": reprocess["payload"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

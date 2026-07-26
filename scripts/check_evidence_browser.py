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
    return f"<!doctype html><html><head><meta charset='utf-8'><base href='http://127.0.0.1:8765/'><style>{css}</style></head><body>{body}<script>{core}</script></body></html>"


def route_api(route: Route) -> None:
    url = route.request.url
    if url.endswith("/api/health"):
        route.fulfill(json={"edition": "local"})
    elif url.endswith("/api/auth/me"):
        route.fulfill(status=401, json={"detail": "not authenticated"})
    elif "/api/cases?" in url or url.endswith("/api/cases"):
        route.fulfill(
            json=[
                {
                    "id": "case-critical",
                    "case_type": "line_total_mismatch",
                    "severity": "critical",
                    "amount_estimate": 25,
                    "confidence": 0.99,
                    "status": "open",
                    "title": "Pagamento critico da verificare",
                    "explanation": "Una prova deve portare alla riga originale.",
                }
            ]
        )
    elif url.endswith("/api/cases/case-critical"):
        route.fulfill(
            json={
                "id": "case-critical",
                "chain_id": "chain-1",
                "case_type": "line_total_mismatch",
                "severity": "critical",
                "amount_estimate": 25,
                "confidence": 0.99,
                "status": "open",
                "title": "Pagamento critico da verificare",
                "explanation": "Una prova deve portare alla riga originale.",
                "recommended_action": "Confrontare documento e riga estratta.",
                "created_at": "2026-07-25T12:00:00Z",
                "evidence": [
                    {
                        "id": "evidence-1",
                        "document_id": "doc-1",
                        "document_line_id": "line-2",
                        "field_name": "line_total",
                        "observed_value": "25.00",
                        "expected_value": "20.00",
                        "note": "Verificare sul file originale.",
                    }
                ],
            }
        )
    elif url.endswith("/api/documents/doc-1"):
        route.fulfill(
            json={
                "id": "doc-1",
                "document_type": "invoice",
                "number": "INV-1",
                "source_filename": "invoice.json",
                "parse_status": "parsed",
                "parse_message": None,
                "confidence": 0.98,
                "supplier": "Fornitore prova",
                "archived": True,
                "file_available": False,
                "lines": [
                    {
                        "id": "line-1",
                        "line_no": 1,
                        "sku": "A",
                        "description": "Prima",
                        "color": None,
                        "size": None,
                        "lot": None,
                        "quantity": 1,
                        "unit_price": 10,
                        "discount_rate": 0,
                    },
                    {
                        "id": "line-2",
                        "line_no": 2,
                        "sku": "B",
                        "description": "Riga sorgente",
                        "color": None,
                        "size": None,
                        "lot": None,
                        "quantity": 2,
                        "unit_price": 10,
                        "discount_rate": 0,
                    },
                ],
            }
        )
    elif url.endswith("/api/documents/doc-1/file"):
        route.fulfill(status=410, json={"detail": "Stored file unavailable"})
    else:
        route.fulfill(status=404, json={"detail": "not mocked"})


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> None:
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
          state.user = {role: 'reviewer', email: 'reviewer@example.test'};
          state.criticalCasesOpen = 1;
          document.querySelector('#authView').classList.add('hidden');
          document.querySelector('#appView').classList.remove('hidden');
          await window.openView('cases');
        }""")
        page.wait_for_selector('#casesTable tr[data-case-id="case-critical"]')
        critical_row = page.locator('#casesTable tr[data-case-id="case-critical"]')
        critical_row.focus()
        page.keyboard.press("Enter")
        page.wait_for_selector("#caseDialog[open]")
        require(
            page.locator("#criticalCaseCount").inner_text() == "1 critica aperta",
            "Dedicated critical count is not visible",
        )
        require(page.locator("#caseDialogBody .badge.critical").is_visible(), "Critical severity badge is not visible")
        require(
            page.get_by_role("button", name="Apri riga estratta").is_visible(),
            "Extracted-line action is not visible",
        )
        require(page.get_by_role("button", name="Apri originale").is_visible(), "Original-file action is not visible")

        page.get_by_role("button", name="Apri riga estratta").click()
        page.wait_for_selector("#documentDialog[open]")
        highlighted = page.locator('tr[data-line-id="line-2"]')
        require(highlighted.is_visible(), "Source row line-2 is not visible")
        require(
            "document-row-highlight" in (highlighted.get_attribute("class") or ""),
            "Source row line-2 is not highlighted",
        )
        require(page.get_by_text("Riga sorgente", exact=True).is_visible(), "Source-row label is not visible")
        require(
            page.get_by_text("Documento archiviato.", exact=False).is_visible(),
            "Archived-document state is not persistent",
        )
        require(
            page.get_by_text("File originale non disponibile.", exact=False).is_visible(),
            "Missing-file state is not persistent",
        )
        page.locator('[data-close-dialog="documentDialog"]').click()
        page.locator("#caseDialogBody .evidence-original-button").click()
        page.wait_for_selector("#caseDialogBody .evidence-origin-status.evidence-error")
        require(
            "archivio locale" in page.locator("#caseDialogBody .evidence-origin-status").inner_text(),
            "Original-file error did not remain visible in the evidence",
        )

        result = {
            "critical_label": True,
            "critical_count": 1,
            "case_keyboard_open": True,
            "evidence_actions": page.locator(".evidence-actions button").count(),
            "highlighted_line": highlighted.get_attribute("data-line-id"),
            "archived_state": True,
            "missing_file_state": True,
            "persistent_original_error": True,
        }
        browser.close()
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

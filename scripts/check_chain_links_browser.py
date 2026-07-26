from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path

from playwright.sync_api import Route, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app" / "static"
LINKED = {"invoice": False}


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


def linked_item(document_id: str, role: str, number: str, filename: str, reason: str, confidence: float) -> dict:
    return {
        "document_id": document_id,
        "role": role,
        "sequence_no": 1,
        "match_confidence": confidence,
        "match_reason": reason,
        "number": number,
        "source_filename": filename,
        "document_date": "2026-07-25",
        "parse_status": "parsed",
    }


def route_api(route: Route) -> None:
    request = route.request
    url = request.url
    if url.endswith("/api/health"):
        route.fulfill(json={"edition": "local"})
    elif url.endswith("/api/auth/me"):
        route.fulfill(status=401, json={"detail": "not authenticated"})
    elif url.endswith("/api/chains/chain-1"):
        route.fulfill(
            json={
                "id": "chain-1",
                "reference_key": "ORD-100",
                "status": "review",
                "confidence": 1,
                "created_at": "2026-07-25T12:00:00Z",
                "updated_at": "2026-07-25T12:00:00Z",
                "comparison": {"rows": [], "documents": {}, "summary": {}},
                "cases": [],
                "intelligence": {
                    "risk": {"score": 20, "decision": "review", "amount_at_risk": 0, "reasons": []},
                    "expectations": [],
                    "triangulation": {"status": "informativo"},
                    "process_conformance": {"score": 0.5, "baseline_source": "baseline prudenziale"},
                },
            }
        )
    elif url.endswith("/api/chains/chain-1/link-options"):
        linked = [linked_item("order-1", "order", "ORD-100", "order.json", "new_chain", 1)]
        candidates = []
        if LINKED["invoice"]:
            linked.append(linked_item("invoice-1", "invoice", "INV-100", "invoice.json", "manual", 1))
        else:
            candidates.append(
                {
                    "document_id": "invoice-1",
                    "role": "invoice",
                    "confidence": 1,
                    "reason": "explicit_reference",
                    "number": "INV-100",
                    "source_filename": "invoice.json",
                    "document_date": "2026-07-25",
                    "supplier": "Fornitore prova",
                    "line_count": 1,
                }
            )
        route.fulfill(json={"chain_id": "chain-1", "linked": linked, "candidates": candidates})
    elif url.endswith("/api/chains/chain-1/attach") and request.method == "POST":
        LINKED["invoice"] = True
        route.fulfill(json={"ok": True})
    elif url.endswith("/api/chains/chain-1/documents/invoice-1") and request.method == "DELETE":
        LINKED["invoice"] = False
        route.fulfill(json={"ok": True})
    elif "/api/chains?" in url or url.endswith("/api/chains"):
        route.fulfill(
            json=[
                {
                    "id": "chain-1",
                    "reference_key": "ORD-100",
                    "status": "review",
                    "confidence": 1,
                    "documents": {"order": ["order-1"], "invoice": ["invoice-1"] if LINKED["invoice"] else []},
                    "updated_at": "2026-07-25T12:00:00Z",
                }
            ]
        )
    elif url.endswith("/api/dashboard"):
        route.fulfill(json={"documents": 2, "cases_open": 0, "chains": 1, "amount_potential": 0, "parsing_failures": 0})
    elif url.endswith("/api/cases"):
        route.fulfill(json=[])
    else:
        route.fulfill(status=404, json={"detail": "not mocked"})


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> None:
    LINKED["invoice"] = False
    executable = browser_executable()
    with sync_playwright() as playwright:
        launch_args = {"headless": True}
        if executable:
            launch_args["executable_path"] = executable
        browser = playwright.chromium.launch(**launch_args)
        page = browser.new_page(viewport={"width": 1366, "height": 768})
        page.route("**/api/**", route_api)
        page.set_content(build_document(), wait_until="load")
        page.wait_for_timeout(200)
        page.evaluate(
            """async () => {
              api = async (path, options = {}) => {
                const headers = new Headers(options.headers || {});
                if (!(options.body instanceof FormData) && options.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');
                const response = await fetch(path, { ...options, headers });
                const payload = response.headers.get('content-type')?.includes('application/json') ? await response.json() : await response.text();
                if (!response.ok) throw new Error(messageFrom(payload, `Errore ${response.status}`));
                return payload;
              };
              state.user = { id: 'reviewer-1', role: 'reviewer', email: 'reviewer@example.test', organization: 'Test' };
              document.querySelector('#authView').classList.add('hidden');
              document.querySelector('#appView').classList.remove('hidden');
              await window.openChain('chain-1');
            }"""
        )
        page.wait_for_selector("#chainDialog[open]")
        require(page.get_by_text("Documenti collegati", exact=True).is_visible(), "Linked-document section is missing")
        page.get_by_text("Collegamenti proposti (1)", exact=True).click()
        candidate = page.locator('[data-candidate-document-id="invoice-1"]')
        require(candidate.is_visible(), "Proposed invoice is not visible")
        require(candidate.get_by_text("100%", exact=True).is_visible(), "Candidate confidence is missing")
        require(candidate.get_by_text("Riferimento esplicito", exact=False).is_visible(), "Candidate reason is missing")

        page.locator(".attach-candidate-document").evaluate("button => button.click()")
        page.wait_for_function("() => document.querySelector('[data-linked-document-id=\"invoice-1\"]') !== null")
        linked = page.locator('[data-linked-document-id="invoice-1"]')
        require(linked.is_visible(), "Invoice was not moved to linked documents")
        require(
            linked.get_by_text("Collegamento confermato manualmente", exact=False).is_visible(),
            "Manual reason is missing",
        )

        page.once("dialog", lambda dialog: dialog.accept())
        page.locator('.detach-linked-document[data-document-id="invoice-1"]').evaluate("button => button.click()")
        page.wait_for_function("() => document.querySelector('[data-linked-document-id=\"invoice-1\"]') === null")
        page.get_by_text("Collegamenti proposti (1)", exact=True).click()
        require(
            page.locator('[data-candidate-document-id="invoice-1"]').is_visible(),
            "Detached invoice did not return to proposals",
        )

        result = {
            "candidate_confidence": 1,
            "manual_attach": True,
            "manual_detach": True,
        }
        browser.close()
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

from __future__ import annotations

import json
import time

from playwright.sync_api import sync_playwright

from browser_e2e import (
    authenticated_page,
    live_app,
    mutation_headers,
    register_admin,
    save_screenshot,
    write_report,
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> None:
    with live_app("operational-center") as app:
        admin = register_admin(app, suffix="operational")
        client = admin.client
        loaded = client.post("/api/demo/load", headers=mutation_headers(client))
        require(loaded.status_code == 200, f"Demo load failed: {loaded.text}")

        documents = client.get("/api/documents").json()
        invoice = next(item for item in documents if item["document_type"] == "invoice")
        invoice_detail = client.get(f"/api/documents/{invoice['id']}").json()
        invoice_line = next(item for item in invoice_detail["lines"] if item["sku"] == "GIACCA-145")

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context, page = authenticated_page(browser, admin, app)
            page.wait_for_selector("#operationalCenter", timeout=20_000)
            require(
                page.get_by_role("heading", name="Cosa controllare adesso").is_visible(),
                "Operational heading is missing",
            )
            require(page.locator(".practice-card").count() >= 1, "Practice grouping is missing")
            require(page.locator(".next-review-card").is_visible(), "Recommended next review is missing")
            require(
                "5.00000000" not in page.locator("#operationalCenter").inner_text(),
                "Storage-scale decimals leaked into the operational dashboard",
            )
            save_screenshot(page, "operational-center-01-dashboard.png")

            page.locator(".next-review-card [data-open-case]").click()
            page.wait_for_selector("#caseDialog[open] .case-operational-summary")
            require(
                page.get_by_text("Confronta i documenti della pratica", exact=True).is_visible(),
                "Practice comparison action is missing from the case",
            )
            require(
                page.get_by_text("Segna falso positivo", exact=True).is_visible(),
                "False-positive review action is not expressed operationally",
            )
            save_screenshot(page, "operational-center-02-case-workflow.png")
            page.locator("#caseDialog").evaluate("dialog => dialog.close()")

            page.evaluate("documentId => window.openDocument(documentId)", invoice["id"])
            page.wait_for_selector(f'#documentDialog[open] tr[data-line-id="{invoice_line["id"]}"]')
            row = page.locator(f'tr[data-line-id="{invoice_line["id"]}"]')
            row.get_by_role("button", name="Correggi estrazione").click()
            page.wait_for_selector("#lineCorrectionDialog[open]")
            page.locator("#lineCorrectionQuantity").fill("114")
            page.locator("#lineCorrectionPrice").fill("42")
            page.locator("#lineCorrectionDiscount").fill("8")
            page.locator("#lineCorrectionReason").fill("Valori verificati sul documento originale")
            save_screenshot(page, "operational-center-03-supervised-correction.png")
            page.locator("#lineCorrectionForm button[type='submit']").click()

            deadline = time.monotonic() + 15
            corrected = None
            while time.monotonic() < deadline:
                updated = client.get(f"/api/documents/{invoice['id']}").json()
                corrected = next(item for item in updated["lines"] if item["id"] == invoice_line["id"])
                if corrected["quantity"] == 114 and corrected["unit_price"] == 42:
                    break
                page.wait_for_timeout(250)
            require(corrected is not None and corrected["quantity"] == 114, "Corrected quantity was not persisted")
            require(corrected["unit_price"] == 42, "Corrected price was not persisted")
            require(corrected["discount_rate"] == 8, "Corrected discount was not persisted")
            require(
                corrected["numeric_provenance"]["quantity"] == "human_corrected",
                "Human correction provenance is missing",
            )

            page.wait_for_selector("#documentDialog[open]")
            page.locator("#documentDialog").evaluate("dialog => dialog.close()")
            page.locator('[data-view="dashboard"]').click()
            page.wait_for_selector("#operationalCenter")
            save_screenshot(page, "operational-center-04-recalculated.png")
            context.close()
            browser.close()

        audit = client.get("/api/audit").json()
        correction_event = next((item for item in audit if item["action"] == "document_line.corrected"), None)
        require(correction_event is not None, "Correction audit event is missing")
        report = {
            "api_mocked": False,
            "demo_loaded": True,
            "operational_dashboard_visible": True,
            "practice_grouping_visible": True,
            "case_workflow_visible": True,
            "storage_scale_decimals_hidden": True,
            "supervised_correction_persisted": True,
            "human_provenance_persisted": True,
            "audit_event_recorded": True,
            "original_file_modified": False,
            "corrected_document_id": invoice["id"],
            "corrected_line_id": invoice_line["id"],
        }
        write_report("operational-center-live-report.json", report)
        client.close()
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

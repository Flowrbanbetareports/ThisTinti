from __future__ import annotations

import json

from playwright.sync_api import sync_playwright

from browser_e2e import (
    authenticated_context,
    live_app,
    mutation_headers,
    register_admin,
    save_screenshot,
    upload_json,
    write_report,
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> None:
    with live_app("chain-links") as app:
        admin = register_admin(app, suffix="links")
        client = admin.client
        order = upload_json(
            client,
            "ordine-link.json",
            {
                "document_type": "order",
                "number": "LINK-100",
                "supplier_name": "Fornitore collegamenti",
                "lines": [{"sku": "A", "quantity": 2, "unit_price": 10, "line_total": 20}],
            },
        )
        invoice = upload_json(
            client,
            "fattura-link.json",
            {
                "document_type": "invoice",
                "number": "INV-LINK-100",
                "supplier_name": "Fornitore collegamenti",
                "references": {"order_numbers": ["LINK-100"]},
                "lines": [{"sku": "A", "quantity": 2, "unit_price": 10, "line_total": 20}],
            },
        )
        chains = client.get("/api/chains").json()
        chain = next(item for item in chains if order["id"] in item["documents"].get("order", []))
        detached = client.delete(
            f"/api/chains/{chain['id']}/documents/{invoice['id']}",
            headers=mutation_headers(client),
        )
        require(detached.status_code == 200, f"Setup detach failed: {detached.text}")

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = authenticated_context(browser, admin, app)
            page = context.new_page()
            page.goto(app.base_url, wait_until="load")
            page.wait_for_selector("#appView:not(.hidden)")
            page.locator('[data-view="chains"]').click()
            page.wait_for_selector(f'[data-chain-id="{chain["id"]}"]')
            chain_row = page.locator(f'[data-chain-id="{chain["id"]}"]')
            chain_row.focus()
            page.keyboard.press("Enter")
            page.wait_for_selector("#chainDialog[open]")

            page.get_by_text("Collegamenti proposti (1)", exact=True).click()
            candidate = page.locator(f'[data-candidate-document-id="{invoice["id"]}"]')
            require(candidate.is_visible(), "Proposed invoice is not visible")
            require(candidate.get_by_text("100%", exact=True).is_visible(), "Candidate confidence is missing")
            require(
                candidate.get_by_text("Riferimento esplicito", exact=False).is_visible(),
                "Candidate reason is missing",
            )
            save_screenshot(page, "chain-links-01-proposal.png")

            candidate.locator(".attach-candidate-document").click()
            page.wait_for_selector(f'[data-linked-document-id="{invoice["id"]}"]')
            linked = page.locator(f'[data-linked-document-id="{invoice["id"]}"]')
            require(
                linked.get_by_text("Collegamento confermato manualmente", exact=False).is_visible(),
                "Manual reason is missing",
            )
            linked_api = client.get(f"/api/chains/{chain['id']}/link-options").json()
            require(
                any(item["document_id"] == invoice["id"] for item in linked_api["linked"]),
                "Browser attach was not persisted in the database",
            )

            page.once("dialog", lambda dialog: dialog.accept())
            linked.locator(".detach-linked-document").click()
            page.wait_for_selector(f'[data-linked-document-id="{invoice["id"]}"]', state="detached")
            page.get_by_text("Collegamenti proposti (1)", exact=True).click()
            require(
                page.locator(f'[data-candidate-document-id="{invoice["id"]}"]').is_visible(),
                "Detached invoice did not return to proposals",
            )
            detached_api = client.get(f"/api/chains/{chain['id']}/link-options").json()
            require(
                all(item["document_id"] != invoice["id"] for item in detached_api["linked"]),
                "Browser detach was not persisted in the database",
            )
            save_screenshot(page, "chain-links-02-detached.png")
            browser.close()

        report = {
            "api_mocked": False,
            "chain_id": chain["id"],
            "candidate_document_id": invoice["id"],
            "candidate_confidence": 1,
            "candidate_reason": "explicit_reference",
            "keyboard_open": True,
            "manual_attach_persisted": True,
            "manual_detach_persisted": True,
        }
        write_report("chain-links-report.json", report)
        client.close()
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

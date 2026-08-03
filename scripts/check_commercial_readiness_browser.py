from __future__ import annotations

import json

from playwright.sync_api import sync_playwright

from browser_e2e import authenticated_page, live_app, register_admin, save_screenshot, write_report


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> None:
    with live_app("commercial-readiness") as app:
        admin = register_admin(app, suffix="commercial")
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context, page = authenticated_page(browser, admin, app)
            project_link = page.get_by_role("link", name="Progetto e piani")
            require(project_link.is_visible(), "Admin project link is missing")
            page.goto(f"{app.base_url}/commercial.html")
            page.wait_for_selector("#commercialContent:not(.hidden)", timeout=20_000)
            require(page.get_by_role("heading", name="Progetto e piani").is_visible(), "Project page heading is missing")
            require(page.get_by_text("Checkout disattivato", exact=True).is_visible(), "Disabled checkout boundary is missing")
            require(page.get_by_text("Nessun annuncio", exact=True).is_visible(), "Disabled sponsor boundary is missing")
            require(page.get_by_role("button", name="Acquista — non disponibile").is_disabled(), "Checkout became active")
            require(
                page.get_by_role("link", name="Apri dashboard progetto").get_attribute("href")
                == "https://flowrbanbetareports.github.io/ThisTinti/project.html",
                "Public project dashboard link is missing",
            )
            save_screenshot(page, "commercial-readiness-01-project-page.png")
            with page.expect_download() as download_info:
                page.get_by_role("link", name="Scarica anteprima ZIP").click()
            download = download_info.value
            require("Integration-Pack" in download.suggested_filename, "Integration Pack download name is invalid")
            context.close()
            browser.close()

        audit = admin.client.get("/api/audit").json()
        require(
            any(item["action"] == "commercial.integration_pack_exported" for item in audit),
            "Integration Pack audit event is missing",
        )
        report = {
            "api_mocked": False,
            "admin_page_visible": True,
            "checkout_disabled": True,
            "sponsor_disabled": True,
            "telemetry_added": False,
            "integration_pack_downloaded": True,
            "integration_pack_audited": True,
            "public_metrics_separate_from_runtime": True,
        }
        write_report("commercial-readiness-live-report.json", report)
        admin.client.close()
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

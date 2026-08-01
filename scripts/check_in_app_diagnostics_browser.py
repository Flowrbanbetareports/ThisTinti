from __future__ import annotations

import json
import time

from playwright.sync_api import sync_playwright

from browser_e2e import (
    authenticated_page,
    live_app,
    register_admin,
    run_worker_once,
    save_screenshot,
    write_report,
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def wait_for_diagnostic_job(client, timeout_seconds: float = 10) -> dict:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        response = client.get("/api/jobs?job_type=ingest_document&limit=25&offset=0")
        require(response.status_code == 200, f"Job list returned HTTP {response.status_code}")
        for job in response.json()["items"]:
            if str(job.get("context", {}).get("filename", "")).startswith("DIAG-"):
                return job
        time.sleep(0.1)
    raise RuntimeError("The in-app diagnostic did not create its traceable job")


def main() -> None:
    with live_app("in-app-diagnostics") as app:
        admin = register_admin(app, suffix="diagnostics")
        client = admin.client

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context, page = authenticated_page(browser, admin, app)

            page.wait_for_selector("[data-diagnostics-link]")
            diagnostics_link = page.locator("[data-diagnostics-link]")
            require(diagnostics_link.is_visible(), "Diagnostics is not available from the authenticated app")
            diagnostics_link.focus()
            page.keyboard.press("Enter")
            page.wait_for_url("**/diagnostics.html")
            page.wait_for_selector("#runReadOnly")

            page.locator("#runReadOnly").click()
            page.locator("#overallStatus").filter(has_text="PARZIALE").wait_for()
            require(
                page.get_by_text("NON ESEGUITO", exact=True).is_visible(),
                "Read-only diagnostics promoted the active numeric check",
            )

            page.locator("#runReadOnly").focus()
            page.keyboard.press("Tab")
            require(
                page.evaluate("document.activeElement?.id") == "runActive",
                "Keyboard focus does not advance to the active diagnostic",
            )

            page.locator("#runActive").click()
            queued_job = wait_for_diagnostic_job(client)
            require(queued_job["status"] == "queued", "Diagnostic job was not durably queued")
            run_worker_once(app, "browser-in-app-diagnostics-worker")
            page.locator("#overallStatus").filter(has_text="PASS").wait_for()

            completed_job = client.get(f"/api/jobs/{queued_job['id']}").json()
            require(completed_job["status"] == "completed", "Diagnostic job did not complete")
            require(
                completed_job.get("result", {}).get("outcome") == "parse_failed",
                "Invalid numeric input was not rejected as parse_failed",
            )

            with page.expect_download() as download_exchange:
                page.locator("#downloadReport").click()
            downloaded = download_exchange.value
            report_json = json.loads(downloaded.path().read_text(encoding="utf-8"))
            numeric_check = next(
                item for item in report_json["checks"] if item["name"] == "Rifiuto di un valore numerico non valido"
            )
            require(report_json["overall"] == "PASS", "Downloaded report does not preserve the visible PASS")
            require(numeric_check["status"] == "PASS", "Downloaded report does not prove numeric rejection")
            require(report_json["observed"]["session"]["role"] == "admin", "Session role is missing from report")
            require(
                report_json["observed"]["service"]["health_version"]
                == report_json["observed"]["service"]["openapi_version"],
                "Runtime and OpenAPI versions differ in the report",
            )

            page.set_viewport_size({"width": 683, "height": 384})
            dimensions = page.evaluate(
                """() => ({
                  viewportWidth: document.documentElement.clientWidth,
                  pageScrollWidth: document.documentElement.scrollWidth,
                  tableScrollable: document.querySelector('.table-wrap').scrollWidth
                    >= document.querySelector('.table-wrap').clientWidth,
                })"""
            )
            require(
                dimensions["pageScrollWidth"] <= dimensions["viewportWidth"] + 1,
                "Diagnostics overflows globally at the 200%-equivalent viewport",
            )
            require(dimensions["tableScrollable"], "The result table is not contained in its scroll region")

            page.emulate_media(reduced_motion="reduce")
            require(
                page.evaluate("matchMedia('(prefers-reduced-motion: reduce)').matches"),
                "Reduced-motion preference was not observed",
            )
            require(
                page.locator("#runReadOnly").evaluate("element => getComputedStyle(element).transitionDuration")
                == "0s",
                "Reduced-motion CSS leaves a button transition active",
            )
            save_screenshot(page, "in-app-diagnostics-01-pass-reflow.png")
            browser.close()

        evidence = {
            "api_mocked": False,
            "opened_from_authenticated_app": True,
            "read_only_outcome": "PARZIALE",
            "non_executed_visible": True,
            "keyboard_navigation": True,
            "active_outcome": report_json["overall"],
            "numeric_rejection": numeric_check["status"],
            "diagnostic_job_id": queued_job["id"],
            "diagnostic_job_outcome": completed_job["result"]["outcome"],
            "downloaded_report_schema": report_json["schema"],
            "reflow_200_percent_equivalent": dimensions,
            "reduced_motion": True,
        }
        write_report("in-app-diagnostics-report.json", evidence)
        client.close()
    print(json.dumps(evidence, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

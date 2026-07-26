from __future__ import annotations

import json

from playwright.sync_api import sync_playwright

from browser_e2e import (
    authenticated_context,
    live_app,
    register_admin,
    run_worker_once,
    save_screenshot,
    upload_json,
    write_report,
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> None:
    with live_app("job-recovery") as app:
        client = register_admin(app, suffix="recovery")
        document = upload_json(
            client,
            "ordine-recuperabile.json",
            {
                "document_type": "order",
                "number": "RECOVERY-ORIGINAL",
                "supplier_name": "Fornitore recupero",
                "lines": [{"sku": "REC-1", "quantity": 1, "unit_price": 12}],
            },
        )
        me = client.get("/api/auth/me").json()

        from app.db import SessionLocal
        from app.models import Document, ProcessingJob

        with SessionLocal() as db:
            stored_document = db.get(Document, document["id"])
            stored_document.parse_status = "failed"
            stored_document.parse_message = "Riga 2: quantity non è numerico"
            failed = ProcessingJob(
                tenant_id=me["tenant_id"],
                created_by=me["id"],
                job_type="reprocess_document",
                status="failed",
                attempts=3,
                max_attempts=3,
                progress=45,
                input_json=json.dumps(
                    {
                        "document_id": document["id"],
                        "overrides": {
                            "document_type": "order",
                            "number": "RECOVERY-RETRIED",
                            "supplier_name": "Fornitore recupero",
                            "document_date": None,
                        },
                    }
                ),
                error_message="Riga 2: quantity non è numerico",
            )
            db.add(failed)
            db.commit()
            failed_id = failed.id

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = authenticated_context(browser, client, app)
            page = context.new_page()
            page.goto(app.base_url, wait_until="load")
            page.wait_for_selector("#appView:not(.hidden)")
            page.locator('[data-view="jobs"]').click()
            page.wait_for_selector(f'[data-job-row="{failed_id}"]')

            failed_row = page.locator(f'[data-job-row="{failed_id}"]')
            require(
                failed_row.get_by_text("Riga 2: quantity non è numerico", exact=True).is_visible(),
                "Persistent job error is not visible",
            )
            require(page.locator("#jobsFailed").inner_text() == "1", "Failed-job metric is incorrect")

            failed_row.locator(".job-document-button").click()
            page.wait_for_selector("#documentDialog[open]")
            require(
                page.locator("#documentDialog .persistent-error").is_visible(),
                "Document parser error is not persistent",
            )
            save_screenshot(page, "job-recovery-01-persistent-error.png")
            page.locator('[data-close-dialog="documentDialog"]').click()

            failed_row.locator(".job-retry-button").click()
            page.wait_for_function(
                """failedId => [...document.querySelectorAll('[data-job-row]')]
                  .some(row => row.dataset.jobRow !== failedId && row.textContent.includes('In attesa'))""",
                failed_id,
            )
            jobs_after_retry = client.get("/api/jobs?limit=25&offset=0").json()["items"]
            retried = next(item for item in jobs_after_retry if item["context"].get("retry_of") == failed_id)
            run_worker_once(app, "browser-retry-worker")
            retried_status = client.get(f"/api/jobs/{retried['id']}").json()
            require(retried_status["status"] == "completed", "Retried job did not complete against the real worker")

            page.locator("#refreshJobsButton").click()
            page.wait_for_function(
                """jobId => {
                  const row = document.querySelector(`[data-job-row="${jobId}"]`);
                  return row && row.textContent.includes('Completata');
                }""",
                retried["id"],
            )
            page.locator(f'[data-job-row="{failed_id}"] .job-document-button').click()
            page.wait_for_selector("#documentDialog[open]")
            page.locator("#documentReprocessButton").click()
            page.wait_for_selector("#reprocessDialog[open]")
            page.locator("#reprocessNumber").fill("RECOVERY-FINAL")
            page.locator("#reprocessSubmitButton").click()
            page.wait_for_selector("#reprocessDialog", state="hidden")

            jobs_after_reprocess = client.get("/api/jobs?limit=25&offset=0").json()["items"]
            reprocess_job = next(
                item
                for item in jobs_after_reprocess
                if item["id"] != retried["id"]
                and item["job_type"] == "reprocess_document"
                and item["status"] == "queued"
            )
            run_worker_once(app, "browser-reprocess-worker")
            final_job = client.get(f"/api/jobs/{reprocess_job['id']}").json()
            final_document = client.get(f"/api/documents/{document['id']}").json()
            require(final_job["status"] == "completed", "UI reprocess job did not complete")
            require(final_document["number"] == "RECOVERY-FINAL", "Corrected metadata was not persisted")
            require(final_document["parse_status"] == "parsed", "Successful reprocess did not clear the parser failure")

            page.locator("#refreshJobsButton").click()
            page.wait_for_function(
                """jobId => {
                  const row = document.querySelector(`[data-job-row="${jobId}"]`);
                  return row && row.textContent.includes('Completata');
                }""",
                reprocess_job["id"],
            )
            save_screenshot(page, "job-recovery-02-completed.png")
            browser.close()

        report = {
            "api_mocked": False,
            "database_persistent": True,
            "failed_job_id": failed_id,
            "persistent_error": True,
            "retry_job_id": retried["id"],
            "retry_status": retried_status["status"],
            "reprocess_job_id": reprocess_job["id"],
            "reprocess_status": final_job["status"],
            "final_document_number": final_document["number"],
            "final_parse_status": final_document["parse_status"],
            "worker_processes": 2,
        }
        write_report("job-recovery-report.json", report)
        client.close()
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

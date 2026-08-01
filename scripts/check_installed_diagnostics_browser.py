from __future__ import annotations

import argparse
import json
import socket
import subprocess  # nosec B404
import time
from contextlib import contextmanager
from pathlib import Path

import httpx
from playwright.sync_api import sync_playwright

from browser_e2e import LiveApp, authenticated_page, register_admin


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def stop(process: subprocess.Popen[bytes] | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def log_tail(path: Path, limit: int = 16000) -> str:
    if not path.exists():
        return "<log assente>"
    return path.read_bytes()[-limit:].decode("utf-8", errors="replace")


def wait_ready(base_url: str, processes: list[tuple[str, subprocess.Popen[bytes], Path]]) -> None:
    deadline = time.monotonic() + 60
    last = "servizio non raggiungibile"
    while time.monotonic() < deadline:
        for label, process, path in processes:
            if process.poll() is not None:
                raise RuntimeError(f"{label} terminato con codice {process.returncode}:\n{log_tail(path)}")
        try:
            response = httpx.get(f"{base_url}/api/readiness", timeout=2, trust_env=False)
            last = response.text
            if response.status_code == 200 and response.json().get("ready") is True:
                return
        except (httpx.HTTPError, ValueError) as exc:
            last = str(exc)
        time.sleep(0.25)
    diagnostics = "\n".join(f"--- {label} ---\n{log_tail(path)}" for label, _, path in processes)
    raise RuntimeError(f"Timeout avvio installato: {last}\n{diagnostics}")


def wait_health(base_url: str, server: subprocess.Popen[bytes], log_path: Path) -> None:
    deadline = time.monotonic() + 60
    last = "servizio non raggiungibile"
    while time.monotonic() < deadline:
        if server.poll() is not None:
            raise RuntimeError(f"server terminato con codice {server.returncode}:\n{log_tail(log_path)}")
        try:
            response = httpx.get(f"{base_url}/api/health", timeout=2, trust_env=False)
            last = response.text
            if response.status_code == 200:
                return
        except httpx.HTTPError as exc:
            last = str(exc)
        time.sleep(0.25)
    raise RuntimeError(f"Timeout health installato: {last}\n{log_tail(log_path)}")


@contextmanager
def installed_app(executable: Path, data_dir: Path, port: int, evidence_dir: Path):
    evidence_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    server_path = evidence_dir / "installed-diagnostics-server.log"
    worker_path = evidence_dir / "installed-diagnostics-worker.log"
    server_handle = server_path.open("ab", buffering=0)
    worker_handle = worker_path.open("ab", buffering=0)
    base_url = f"http://127.0.0.1:{port}"
    server = worker = None
    try:
        server = subprocess.Popen(  # nosec B603
            [str(executable), "--server", "--data-dir", str(data_dir), "--port", str(port)],
            stdout=server_handle,
            stderr=subprocess.STDOUT,
        )
        wait_health(base_url, server, server_path)
        worker = subprocess.Popen(  # nosec B603
            [str(executable), "--worker", "--data-dir", str(data_dir), "--port", str(port)],
            stdout=worker_handle,
            stderr=subprocess.STDOUT,
        )
        wait_ready(base_url, [("server", server, server_path), ("worker", worker, worker_path)])
        yield LiveApp(base_url=base_url, environment={}, root=data_dir)
    finally:
        stop(worker)
        stop(server)
        worker_handle.close()
        server_handle.close()


def wait_for_diagnostic_job(client: httpx.Client, timeout_seconds: float = 30) -> dict:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        response = client.get("/api/jobs?job_type=ingest_document&limit=25&offset=0")
        require(response.status_code == 200, f"Elenco attività HTTP {response.status_code}")
        for job in response.json()["items"]:
            if str(job.get("context", {}).get("filename", "")).startswith("DIAG-"):
                return job
        time.sleep(0.1)
    raise RuntimeError("La Diagnostica installata non ha creato il job persistente")


def wait_for_job_completion(client: httpx.Client, job_id: str, timeout_seconds: float = 120) -> dict:
    deadline = time.monotonic() + timeout_seconds
    last: dict = {}
    while time.monotonic() < deadline:
        response = client.get(f"/api/jobs/{job_id}")
        require(response.status_code == 200, f"Dettaglio attività HTTP {response.status_code}")
        last = response.json()
        if last.get("status") in {"completed", "failed", "cancelled"}:
            return last
        time.sleep(0.25)
    raise RuntimeError(f"Timeout attività diagnostica: {last}")


def check_reflow(page, evidence_dir: Path) -> dict[str, dict]:
    widths = {"125": 1093, "150": 911, "200": 683}
    results: dict[str, dict] = {}
    for zoom, width in widths.items():
        page.set_viewport_size({"width": width, "height": 768})
        dimensions = page.evaluate(
            """() => ({
              viewport_width: document.documentElement.clientWidth,
              page_scroll_width: document.documentElement.scrollWidth,
              table_scrollable: document.querySelector('.table-wrap').scrollWidth
                >= document.querySelector('.table-wrap').clientWidth,
            })"""
        )
        require(
            dimensions["page_scroll_width"] <= dimensions["viewport_width"] + 1,
            f"Overflow globale al reflow equivalente {zoom}%",
        )
        results[zoom] = dimensions
        page.screenshot(path=evidence_dir / f"installed-diagnostics-{zoom}-percent.png", full_page=True)
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Collaudo Chromium della Diagnostica nel vero EXE installato")
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--verbal", type=Path, required=True)
    parser.add_argument("--expected-version", required=True)
    args = parser.parse_args()

    executable = args.executable.resolve()
    data_dir = args.data_dir.resolve()
    evidence_dir = args.evidence_dir.resolve()
    report_path = args.report.resolve()
    verbal_path = args.verbal.resolve()
    require(executable.is_file(), f"EXE installato non trovato: {executable}")
    evidence_dir.mkdir(parents=True, exist_ok=True)
    port = free_port()
    base_url = f"http://127.0.0.1:{port}"
    summary: dict[str, object] = {
        "schema": "thistinti.windows-installed-diagnostics.v1",
        "expected_version": args.expected_version,
        "executable": executable.name,
        "api_mocked": False,
        "passed": False,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    admin = None
    with installed_app(executable, data_dir, port, evidence_dir) as app:
        admin = register_admin(app, suffix="windows-installed")
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context, page = authenticated_page(browser, admin, app)
            page.wait_for_selector("[data-diagnostics-link]")
            page.locator("[data-diagnostics-link]").focus()
            page.keyboard.press("Enter")
            page.wait_for_url("**/diagnostics.html")
            page.wait_for_selector("#runReadOnly")

            page.locator("#runReadOnly").click()
            page.locator("#overallStatus").filter(has_text="PARZIALE").wait_for()
            require(
                page.get_by_text("NON ESEGUITO", exact=True).is_visible(), "Test attivo promosso dal controllo sicuro"
            )
            require(page.get_by_text("FAIL", exact=True).count() == 0, "Controllo sicuro con FAIL")

            page.locator(".topbar a.secondary").focus()
            focus_order = []
            for _ in range(4):
                page.keyboard.press("Tab")
                focus_order.append(
                    page.evaluate("document.activeElement?.id || document.activeElement?.textContent.trim()")
                )
            require(
                focus_order == ["runReadOnly", "runActive", "downloadReport", "copySummary"],
                f"Ordine tastiera inatteso: {focus_order}",
            )

            page.locator("#runActive").click()
            queued_job = wait_for_diagnostic_job(admin.client)
            page.locator("#overallStatus").filter(has_text="PASS").wait_for(timeout=130000)
            completed_job = wait_for_job_completion(admin.client, queued_job["id"])
            require(completed_job.get("status") == "completed", f"Job diagnostico non completato: {completed_job}")
            require(
                completed_job.get("result", {}).get("outcome") == "parse_failed",
                "Il valore numerico non valido non è stato rifiutato come parse_failed",
            )

            with page.expect_download() as exchange:
                page.locator("#downloadReport").click()
            diagnostic_report = json.loads(exchange.value.path().read_text(encoding="utf-8"))
            require(diagnostic_report.get("schema") == "thistinti.local-diagnostics.v1", "Schema verbale inatteso")
            require(diagnostic_report.get("overall") == "PASS", "Verbale scaricato non PASS")
            require(diagnostic_report.get("version") == args.expected_version, "Versione installata inattesa")
            numeric = next(
                item
                for item in diagnostic_report["checks"]
                if item["name"] == "Rifiuto di un valore numerico non valido"
            )
            require(numeric["status"] == "PASS", "Il verbale non prova il rifiuto numerico")
            verbal_path.parent.mkdir(parents=True, exist_ok=True)
            verbal_path.write_text(json.dumps(diagnostic_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

            context.grant_permissions(["clipboard-read", "clipboard-write"], origin=base_url)
            page.locator("#copySummary").click()
            page.get_by_text("Riepilogo copiato negli appunti.", exact=True).wait_for()
            clipboard = page.evaluate("navigator.clipboard.readText()")
            require(f"Versione: {args.expected_version}" in clipboard, "Riepilogo copiato privo di versione")

            reflow = check_reflow(page, evidence_dir)
            page.emulate_media(reduced_motion="reduce")
            require(
                page.evaluate("matchMedia('(prefers-reduced-motion: reduce)').matches"), "Riduzione animazioni ignorata"
            )
            require(
                page.locator("#runReadOnly").evaluate("element => getComputedStyle(element).transitionDuration")
                == "0s",
                "Transizione ancora attiva con riduzione animazioni",
            )
            page.screenshot(path=evidence_dir / "installed-diagnostics-pass.png", full_page=True)
            context.close()
            browser.close()

        summary.update(
            {
                "read_only_outcome": "PARZIALE",
                "read_only_failures": 0,
                "active_outcome": diagnostic_report["overall"],
                "numeric_rejection": numeric["status"],
                "diagnostic_job_id": queued_job["id"],
                "diagnostic_job_status": completed_job["status"],
                "diagnostic_job_outcome": completed_job["result"]["outcome"],
                "downloaded_report_schema": diagnostic_report["schema"],
                "keyboard_focus_order": focus_order,
                "copy_summary": True,
                "reflow_equivalent": reflow,
                "reduced_motion": True,
            }
        )
        admin.client.close()

    require(admin is not None, "Amministratore diagnostico non creato")
    with installed_app(executable, data_dir, port, evidence_dir) as restarted:
        login = httpx.Client(base_url=restarted.base_url, timeout=10, trust_env=False)
        response = login.post(
            "/api/auth/login",
            headers={"X-Session-Mode": "token"},
            json={"email": admin.email, "password": admin.password},
        )
        require(response.status_code == 200, f"Login dopo riavvio HTTP {response.status_code}")
        token = response.json()["token"]
        persisted = login.get(f"/api/jobs/{summary['diagnostic_job_id']}", headers={"Authorization": f"Bearer {token}"})
        require(persisted.status_code == 200, f"Job non leggibile dopo riavvio HTTP {persisted.status_code}")
        require(persisted.json().get("result", {}).get("outcome") == "parse_failed", "Esito perso dopo riavvio")
        health = login.get("/api/health")
        require(
            health.status_code == 200 and health.json().get("version") == args.expected_version,
            "Versione errata dopo riavvio",
        )
        login.close()

    summary["restart_persistence"] = True
    summary["passed"] = True
    report_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

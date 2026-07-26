from __future__ import annotations

import json
import os
import secrets
import socket

# The harness starts only fixed local test commands without a shell.
import subprocess  # nosec B404
import sys
import tempfile
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import httpx

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_DIR = ROOT / "browser-evidence"
LEGAL_NOTICE_VERSION = "2026-07-20-v2"

# When these checks are launched as ``python scripts/check_*.py``, Python places
# ``scripts/`` (not the repository root) on sys.path. Keep the real application
# importable without depending on a developer-specific PYTHONPATH.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@dataclass(frozen=True)
class LiveApp:
    base_url: str
    environment: dict[str, str]
    root: Path


@dataclass(frozen=True)
class RegisteredAdmin:
    client: httpx.Client
    email: str
    password: str


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _wait_until_ready(base_url: str, process: subprocess.Popen[bytes]) -> None:
    deadline = time.monotonic() + 20
    last_error = "server did not answer"
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"ThisTinti server exited with code {process.returncode}")
        try:
            response = httpx.get(f"{base_url}/api/health", timeout=1, trust_env=False)
            if response.status_code == 200:
                return
            last_error = f"health returned HTTP {response.status_code}"
        except httpx.HTTPError as exc:
            last_error = str(exc)
        time.sleep(0.1)
    raise RuntimeError(f"ThisTinti server was not ready: {last_error}")


@contextmanager
def live_app(name: str) -> Iterator[LiveApp]:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f"thistinti-{name}-") as temporary:
        root = Path(temporary)
        port = _free_port()
        base_url = f"http://127.0.0.1:{port}"
        environment = os.environ.copy()
        environment.update(
            {
                "THISTINTI_ENV": "test",
                "THISTINTI_LOCAL_EDITION": "true",
                "THISTINTI_DATABASE_URL": f"sqlite:///{root / 'thistinti.db'}",
                "THISTINTI_STORAGE_DIR": str(root / "uploads"),
                "THISTINTI_QUARANTINE_DIR": str(root / "quarantine"),
                "THISTINTI_REJECTED_DIR": str(root / "rejected"),
                "THISTINTI_SECRET_KEY": secrets.token_urlsafe(48),
                "THISTINTI_ALLOW_REGISTRATION": "true",
                "THISTINTI_AUTO_CREATE_SCHEMA": "true",
                "THISTINTI_ALLOW_SYNCHRONOUS_INGESTION": "true",
                "THISTINTI_ASYNC_INGESTION_ENABLED": "true",
                "THISTINTI_REQUIRE_MALWARE_SCANNER": "false",
            }
        )
        previous = {key: os.environ.get(key) for key in environment if key.startswith("THISTINTI_")}
        for key, value in environment.items():
            if key.startswith("THISTINTI_"):
                os.environ[key] = value
        log_path = EVIDENCE_DIR / f"{name}-server.log"
        with log_path.open("wb") as log:
            # Fixed interpreter, module and loopback host; no shell or user input.
            process = subprocess.Popen(  # nosec B603
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "app.main:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port),
                    "--log-level",
                    "warning",
                ],
                cwd=ROOT,
                env=environment,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
            try:
                _wait_until_ready(base_url, process)
                yield LiveApp(base_url=base_url, environment=environment, root=root)
            finally:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
                for key, old_value in previous.items():
                    if old_value is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = old_value


def register_admin(app: LiveApp, *, suffix: str) -> RegisteredAdmin:
    client = httpx.Client(base_url=app.base_url, follow_redirects=True, timeout=10, trust_env=False)
    email = f"admin-{suffix}@example.com"
    password = f"BrowserE2E-{secrets.token_urlsafe(24)}"
    response = client.post(
        "/api/auth/register",
        json={
            "organization_name": f"Browser E2E {suffix}",
            "email": email,
            "password": password,
            "legal_notice_version": LEGAL_NOTICE_VERSION,
            "accepted_terms": True,
            "accepted_specific_clauses": True,
        },
    )
    if response.status_code != 201:
        raise RuntimeError(f"Registration failed: HTTP {response.status_code}: {response.text}")
    return RegisteredAdmin(client=client, email=email, password=password)


def mutation_headers(client: httpx.Client) -> dict[str, str]:
    csrf = client.cookies.get("thistinti_csrf")
    if not csrf:
        raise RuntimeError("Registration did not create a CSRF cookie")
    return {"X-CSRF-Token": csrf}


def upload_json(client: httpx.Client, filename: str, payload: dict) -> dict:
    response = client.post(
        "/api/documents/upload",
        headers=mutation_headers(client),
        files={"file": (filename, json.dumps(payload).encode("utf-8"), "application/json")},
    )
    if response.status_code != 201:
        raise RuntimeError(f"Upload failed: HTTP {response.status_code}: {response.text}")
    return response.json()["document"]


def authenticated_page(browser, admin: RegisteredAdmin, app: LiveApp):
    context = browser.new_context(viewport={"width": 1366, "height": 768})
    context.add_init_script(
        """
        localStorage.setItem('thistinti_experience_welcome_v1', '1');
        localStorage.setItem('thistinti_experience_advanced_v1', '1');
        localStorage.setItem('thistinti_local_setup_complete', 'true');
        """
    )
    page = context.new_page()
    with page.expect_response(lambda response: response.url.endswith("/api/auth/me")):
        page.goto(app.base_url, wait_until="load")
    page.locator("#loginEmail").fill(admin.email)
    page.locator("#loginPassword").fill(admin.password)
    with page.expect_response(
        lambda response: response.url.endswith("/api/auth/login") and response.request.method == "POST"
    ) as login_exchange:
        page.locator('#loginForm button[type="submit"]').click()
    login_response = login_exchange.value
    if login_response.status != 200:
        raise RuntimeError(f"Browser login failed: HTTP {login_response.status}: {login_response.text()}")
    page.wait_for_selector("#appView:not(.hidden)")
    cookie_names = {cookie["name"] for cookie in context.cookies(app.base_url)}
    required = {"thistinti_session", "thistinti_csrf"}
    if not required.issubset(cookie_names):
        raise RuntimeError(f"Browser login did not create required cookies: {sorted(cookie_names)}")
    return context, page


def run_worker_once(app: LiveApp, worker_id: str) -> None:
    # Fixed repository worker command; no shell or user input.
    result = subprocess.run(  # nosec B603
        [sys.executable, "scripts/run_worker.py", "--once", "--worker-id", worker_id],
        cwd=ROOT,
        env=app.environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode:
        raise RuntimeError(f"Worker failed: {result.stdout}\n{result.stderr}")


def save_screenshot(page, name: str) -> Path:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    path = EVIDENCE_DIR / name
    page.screenshot(path=path, full_page=True)
    return path


def write_report(name: str, payload: dict) -> Path:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    path = EVIDENCE_DIR / name
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path

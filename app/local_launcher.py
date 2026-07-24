from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import sqlite3
import subprocess  # nosec B404
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

from .legal import LEGAL_NOTICE_VERSION, has_current_acceptance, record_acceptance
from .local_runtime import (
    LOCAL_PORT,
    configure_local_environment,
    copy_source_snapshot,
    create_full_local_backup,
    default_data_root,
    resource_root,
    run_local_migrations,
)

APP_TITLE = "ThisTinti Local"


def _health_url(port: int) -> str:
    return f"http://127.0.0.1:{port}/api/health"


def _local_setup_mode(data_root: Path) -> str:
    """Return the correct first screen without exposing account details."""
    database = data_root / "database" / "thistinti.db"
    if not database.exists() or database.stat().st_size == 0:
        return "create"
    try:
        with sqlite3.connect(database) as connection:
            table = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'users'"
            ).fetchone()
            if not table:
                return "create"
            users = connection.execute("SELECT COUNT(*) FROM users").fetchone()
            return "login" if users and int(users[0]) > 0 else "create"
    except (OSError, sqlite3.Error, TypeError, ValueError):
        return "choose"


def _app_url(port: int, data_root: Path) -> str:
    return f"http://127.0.0.1:{port}/?local_setup={_local_setup_mode(data_root)}"


def _is_healthy(port: int, timeout: float = 0.5) -> bool:
    try:
        with urllib.request.urlopen(_health_url(port), timeout=timeout) as response:  # nosec B310
            payload = json.loads(response.read().decode("utf-8"))
            return response.status == 200 and payload.get("name") == "ThisTinti"
    except (OSError, ValueError, urllib.error.URLError):
        return False


def _port_available(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def _wait_ready(port: int, process: subprocess.Popen[bytes], timeout: float = 45.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Il motore ThisTinti si è arrestato con codice {process.returncode}.")
        if _is_healthy(port, timeout=1.0):
            return
        time.sleep(0.25)
    raise TimeoutError("ThisTinti non ha completato l'avvio entro 45 secondi.")


def _child_command(mode: str, data_root: Path, port: int) -> list[str]:
    flag = "--server" if mode == "server" else "--worker"
    if getattr(sys, "frozen", False):
        return [sys.executable, flag, "--data-dir", str(data_root), "--port", str(port)]
    return [sys.executable, "-m", "app.local_launcher", flag, "--data-dir", str(data_root), "--port", str(port)]


def _child_working_directory(data_root: Path) -> Path:
    if getattr(sys, "frozen", False):
        return data_root
    return resource_root()


def _creation_flags() -> int:
    return int(getattr(subprocess, "CREATE_NO_WINDOW", 0))


def start_server(data_root: Path, port: int) -> subprocess.Popen[bytes]:
    log_dir = data_root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "local-server.log"
    log_handle = log_path.open("ab", buffering=0)
    process = subprocess.Popen(  # nosec B603
        _child_command("server", data_root, port),
        cwd=str(_child_working_directory(data_root)),
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        creationflags=_creation_flags(),
    )
    process._thistinti_log_handle = log_handle  # type: ignore[attr-defined]
    try:
        _wait_ready(port, process)
    except Exception:
        stop_server(process)
        raise
    return process


def start_worker(data_root: Path, port: int) -> subprocess.Popen[bytes]:
    log_dir = data_root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "local-worker.log"
    log_handle = log_path.open("ab", buffering=0)
    process = subprocess.Popen(  # nosec B603
        _child_command("worker", data_root, port),
        cwd=str(_child_working_directory(data_root)),
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        creationflags=_creation_flags(),
    )
    process._thistinti_log_handle = log_handle  # type: ignore[attr-defined]
    return process


def _wait_readiness(
    port: int, server: subprocess.Popen[bytes], worker: subprocess.Popen[bytes], timeout: float = 45.0
) -> None:
    url = f"http://127.0.0.1:{port}/api/readiness"
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if server.poll() is not None:
            raise RuntimeError(f"Il motore ThisTinti si è arrestato con codice {server.returncode}.")
        if worker.poll() is not None:
            raise RuntimeError(f"Il worker ThisTinti si è arrestato con codice {worker.returncode}.")
        try:
            with urllib.request.urlopen(url, timeout=1.0) as response:  # nosec B310
                payload = json.loads(response.read().decode("utf-8"))
                if response.status == 200 and payload.get("ready") is True:
                    return
        except (OSError, ValueError, urllib.error.URLError):
            pass
        time.sleep(0.25)
    raise TimeoutError("ThisTinti non ha completato la readiness locale entro 45 secondi.")


def stop_server(process: subprocess.Popen[bytes] | None) -> None:
    if process is None:
        return
    if process.poll() is None:
        if sys.platform == "win32":
            process.terminate()
        else:
            process.send_signal(signal.SIGTERM)
        try:
            process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
    handle = getattr(process, "_thistinti_log_handle", None)
    if handle:
        handle.close()


def run_worker(data_root: Path, port: int) -> int:
    configure_local_environment(data_root, port)
    os.environ["THISTINTI_PROCESS_ROLE"] = "worker"
    import socket as _socket
    import time as _time

    from .db import SessionLocal
    from .models import ProcessingJob
    from .services.jobs import claim_next_job, execute_job, run_maintenance, touch_worker

    worker_id = f"{_socket.gethostname()}-local-worker"[:120]
    last_maintenance = 0.0
    while True:
        processed = False
        with SessionLocal() as db:
            touch_worker(db, worker_id)
            job = claim_next_job(db, worker_id)
            if job:
                job_id = job.id
                db.commit()
            else:
                job_id = None
                db.commit()
        if job_id:
            with SessionLocal() as db:
                claimed = db.get(ProcessingJob, job_id)
                if claimed and claimed.status == "running" and claimed.locked_by == worker_id:
                    execute_job(db, claimed)
                    db.commit()
                    processed = True
        now = _time.monotonic()
        if now - last_maintenance >= 60:
            with SessionLocal() as db:
                touch_worker(db, worker_id)
                run_maintenance(db)
                db.commit()
            last_maintenance = now
        if not processed:
            _time.sleep(0.25)


def run_server(data_root: Path, port: int) -> int:
    configure_local_environment(data_root, port)
    run_local_migrations(data_root)
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=port,
        log_level="info",
        access_log=False,
        reload=False,
    )
    return 0


def _open_path(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32":
        os.startfile(path)  # type: ignore[attr-defined]  # nosec B606
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])  # nosec B603 B607
    else:
        subprocess.Popen(["xdg-open", str(path)])  # nosec B603 B607


def run_headless(data_root: Path, port: int) -> int:
    if _is_healthy(port):
        raise RuntimeError(f"ThisTinti è già attivo su http://127.0.0.1:{port}")
    server = start_server(data_root, port)
    worker = start_worker(data_root, port)
    try:
        _wait_readiness(port, server, worker)
        print(f"ThisTinti Local è operativo su http://127.0.0.1:{port}")
        while server.poll() is None and worker.poll() is None:
            time.sleep(1)
        raise RuntimeError("Un processo locale si è arrestato inaspettatamente")
    except KeyboardInterrupt:
        return 0
    finally:
        stop_server(worker)
        stop_server(server)


def _show_legal_acceptance(data_root: Path) -> bool:
    import tkinter as tk
    from tkinter import messagebox, scrolledtext, ttk

    resources = resource_root()
    if has_current_acceptance(data_root, resources):
        return True
    terms_path = resources / "TERMS_OF_USE.md"
    license_path = resources / "LICENSE"
    if not terms_path.exists() or not license_path.exists():
        messagebox.showerror(APP_TITLE, "Documenti legali mancanti. Reinstallare la distribuzione ufficiale.")
        return False

    window = tk.Tk()
    window.title("ThisTinti — licenza e avviso sui rischi")
    window.geometry("760x680")
    window.minsize(620, 560)
    accepted = {"value": False}

    frame = ttk.Frame(window, padding=20)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="Prima di usare ThisTinti", font=("Segoe UI", 19, "bold")).pack(anchor="w")
    ttk.Label(
        frame,
        text=(
            "ThisTinti è gratuito e locale, ma può commettere errori. "
            "Non deve autorizzare pagamenti o sostituire controlli contabili, fiscali o legali."
        ),
        wraplength=700,
    ).pack(anchor="w", pady=(6, 12))
    text = scrolledtext.ScrolledText(frame, wrap="word", height=24, font=("Segoe UI", 9))
    text.pack(fill="both", expand=True)
    text.insert("1.0", terms_path.read_text(encoding="utf-8"))
    text.configure(state="disabled")

    terms_var = tk.BooleanVar(value=False)
    clauses_var = tk.BooleanVar(value=False)
    first = ttk.Checkbutton(
        frame,
        text="Ho letto e accetto la Apache License 2.0 e l’avviso sui rischi.",
        variable=terms_var,
    )
    first.pack(anchor="w", pady=(12, 4))
    second = ttk.Checkbutton(
        frame,
        text=(
            "Approvo specificamente le clausole 3, 4, 5, 7, 8, 9, 10, 11 e 12: "
            "limiti d’uso, verifica umana, responsabilità dell’utilizzatore, assenza di garanzie, "
            "limitazione di responsabilità, modifiche di terzi e assenza di supporto."
        ),
        variable=clauses_var,
    )
    second.pack(anchor="w")

    buttons = ttk.Frame(frame)
    buttons.pack(fill="x", pady=(14, 0))
    accept_button = ttk.Button(buttons, text="Accetta e continua", state="disabled")
    accept_button.pack(side="right")
    ttk.Button(buttons, text="Esci", command=window.destroy).pack(side="right", padx=(0, 8))

    def update_state(*_args) -> None:
        accept_button.configure(state="normal" if terms_var.get() and clauses_var.get() else "disabled")

    def confirm() -> None:
        record_acceptance(data_root, resources)
        accepted["value"] = True
        window.destroy()

    terms_var.trace_add("write", update_state)
    clauses_var.trace_add("write", update_state)
    accept_button.configure(command=confirm)
    window.protocol("WM_DELETE_WINDOW", window.destroy)
    window.mainloop()
    return bool(accepted["value"])


def _open_legal_documents() -> None:
    path = resource_root() / "TERMS_OF_USE.md"
    if path.exists():
        webbrowser.open(path.resolve().as_uri(), new=2)


def run_gui(data_root: Path, port: int) -> int:
    if not _show_legal_acceptance(data_root):
        return 2
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    class Launcher:
        def __init__(self) -> None:
            self.root = tk.Tk()
            self.root.title(APP_TITLE)
            self.root.geometry("560x410")
            self.root.minsize(520, 390)
            self.process: subprocess.Popen[bytes] | None = None
            self.worker_process: subprocess.Popen[bytes] | None = None
            self.start_error: Exception | None = None
            self.status = tk.StringVar(value="Preparazione dell'ambiente locale…")
            self.detail = tk.StringVar(value="I dati restano su questo computer.")
            self._build()
            self.root.protocol("WM_DELETE_WINDOW", self.close)
            threading.Thread(target=self._start_background, daemon=True).start()

        def _build(self) -> None:
            frame = ttk.Frame(self.root, padding=24)
            frame.pack(fill="both", expand=True)
            ttk.Label(frame, text="ThisTinti Local", font=("Segoe UI", 21, "bold")).pack(anchor="w")
            ttk.Label(
                frame,
                text="Controllo documentale locale, gratuito e senza cloud obbligatorio.",
                wraplength=455,
            ).pack(anchor="w", pady=(4, 20))
            ttk.Separator(frame).pack(fill="x", pady=(0, 18))
            ttk.Label(frame, textvariable=self.status, font=("Segoe UI", 11, "bold")).pack(anchor="w")
            ttk.Label(frame, textvariable=self.detail, wraplength=455).pack(anchor="w", pady=(4, 18))
            self.progress = ttk.Progressbar(frame, mode="indeterminate")
            self.progress.pack(fill="x", pady=(0, 18))
            self.progress.start(12)
            buttons = ttk.Frame(frame)
            buttons.pack(fill="x")
            self.open_button = ttk.Button(buttons, text="Apri ThisTinti", command=self.open_browser, state="disabled")
            self.open_button.grid(row=0, column=0, sticky="w")
            ttk.Button(buttons, text="Cartella dati", command=lambda: _open_path(data_root)).grid(
                row=0, column=1, padx=8, sticky="w"
            )
            ttk.Button(buttons, text="Crea backup", command=self.create_backup).grid(row=0, column=2, sticky="w")
            ttk.Button(buttons, text="Esporta sorgente", command=self.export_source).grid(
                row=1, column=0, pady=(10, 0), sticky="w"
            )
            ttk.Button(buttons, text="Note legali", command=_open_legal_documents).grid(
                row=1, column=1, pady=(10, 0), sticky="w"
            )
            ttk.Button(buttons, text="Chiudi", command=self.close).grid(row=1, column=2, pady=(10, 0), sticky="e")
            buttons.columnconfigure(1, weight=1)
            ttk.Label(
                frame,
                text=f"Nessuna telemetria. Nessun documento viene inviato a ThisTinti. Avviso {LEGAL_NOTICE_VERSION}.",
                foreground="#555555",
            ).pack(anchor="w", pady=(22, 0))

        def _start_background(self) -> None:
            try:
                if _is_healthy(port):
                    self.root.after(0, lambda: self._ready(None, "È già attiva un'istanza locale."))
                    return
                if not _port_available(port):
                    raise RuntimeError(f"La porta locale {port} è occupata da un altro programma.")
                self.process = start_server(data_root, port)
                self.worker_process = start_worker(data_root, port)
                _wait_readiness(port, self.process, self.worker_process)
                self.root.after(0, lambda: self._ready(self.process, "Motore e worker locali sono operativi."))
            except Exception as exc:  # noqa: BLE001
                stop_server(self.worker_process)
                stop_server(self.process)
                self.start_error = exc
                self.root.after(0, self._failed)

        def _ready(self, process: subprocess.Popen[bytes] | None, detail: str) -> None:
            self.process = process
            self.progress.stop()
            self.progress.configure(mode="determinate", value=100)
            self.status.set("ThisTinti è pronto")
            self.detail.set(detail)
            self.open_button.configure(state="normal")
            self.open_browser()

        def _failed(self) -> None:
            self.progress.stop()
            self.status.set("Avvio non riuscito")
            self.detail.set(str(self.start_error or "Errore sconosciuto"))
            messagebox.showerror(APP_TITLE, self.detail.get())

        def open_browser(self) -> None:
            webbrowser.open(_app_url(port, data_root), new=2)

        def create_backup(self) -> None:
            default_name = time.strftime("ThisTinti-backup-%Y%m%d-%H%M%S.zip")
            target = filedialog.asksaveasfilename(
                title="Salva backup completo",
                defaultextension=".zip",
                initialfile=default_name,
                filetypes=[("Archivio ZIP", "*.zip")],
            )
            if not target:
                return
            try:
                result = create_full_local_backup(data_root, Path(target))
                messagebox.showinfo(APP_TITLE, f"Backup creato:\n{result}")
            except Exception as exc:  # noqa: BLE001
                messagebox.showerror(APP_TITLE, str(exc))

        def export_source(self) -> None:
            target = filedialog.askdirectory(title="Scegli la cartella di destinazione")
            if not target:
                return
            try:
                copy_source_snapshot(Path(target))
                messagebox.showinfo(APP_TITLE, "Il sorgente è stato esportato correttamente.")
            except Exception as exc:  # noqa: BLE001
                messagebox.showerror(APP_TITLE, str(exc))

        def close(self) -> None:
            if self.process is not None and self.process.poll() is None:
                if not messagebox.askyesno(APP_TITLE, "Chiudere anche il motore locale ThisTinti?"):
                    return
                self.status.set("Arresto in corso…")
                self.root.update_idletasks()
                stop_server(self.worker_process)
                stop_server(self.process)
            self.root.destroy()

        def run(self) -> int:
            self.root.mainloop()
            return 0

    return Launcher().run()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ThisTinti Local Edition")
    parser.add_argument("--server", action="store_true", help="Avvia soltanto il server locale")
    parser.add_argument("--worker", action="store_true", help="Avvia soltanto il worker locale")
    parser.add_argument("--data-dir", type=Path, default=default_data_root())
    parser.add_argument("--port", type=int, default=LOCAL_PORT)
    parser.add_argument("--no-browser", action="store_true", help="Avvia il server senza interfaccia grafica")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    data_root = args.data_dir.expanduser().resolve()
    if not (1024 <= args.port <= 65535):
        raise SystemExit("La porta deve essere compresa tra 1024 e 65535.")
    if args.worker:
        return run_worker(data_root, args.port)
    if args.server:
        return run_server(data_root, args.port)
    if args.no_browser:
        return run_headless(data_root, args.port)
    return run_gui(data_root, args.port)


if __name__ == "__main__":
    raise SystemExit(main())

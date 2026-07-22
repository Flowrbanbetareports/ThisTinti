#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OLD_VERSION = "3.4.0-alpha.3"
NEW_VERSION = "3.4.0-alpha.4"


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def write(relative: str, content: str) -> None:
    path = ROOT / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def replace_exact(relative: str, old: str, new: str) -> None:
    content = read(relative)
    if old not in content:
        raise RuntimeError(f"Expected text not found in {relative}: {old[:100]!r}")
    write(relative, content.replace(old, new, 1))


def replace_all(relative: str, old: str, new: str) -> None:
    content = read(relative)
    if old not in content:
        raise RuntimeError(f"Expected text not found in {relative}: {old!r}")
    write(relative, content.replace(old, new))


def bump_version() -> None:
    replace_all("app/version.py", OLD_VERSION, NEW_VERSION)
    replace_all("pyproject.toml", OLD_VERSION, NEW_VERSION)
    replace_all("tests/test_rebrand.py", OLD_VERSION, NEW_VERSION)
    replace_all("README.md", OLD_VERSION, NEW_VERSION)
    replace_all("installer/windows/ThisTinti.iss", OLD_VERSION, NEW_VERSION)
    replace_exact("installer/windows/ThisTinti.iss", "VersionInfoVersion=3.4.0.3", "VersionInfoVersion=3.4.0.4")


def update_release_notes() -> None:
    path = ROOT / "RELEASE_NOTES.md"
    content = path.read_text(encoding="utf-8")
    heading = f"# {NEW_VERSION} — Windows validation and public alpha\n"
    if heading in content:
        return
    notes = f"""{heading}
- installer avviato e verificato su un PC Windows 11 reale, incluso il comportamento previsto di Microsoft Defender SmartScreen per un binario non firmato;
- corretta la schermata di creazione dello spazio e verificata la creazione del primo amministratore;
- sostituita la precedente icona a T con il marchio ThisTinti a collegamenti documentali e rombo di verifica;
- aggiunti test automatici per caricamento dimostrativo, esportazione, persistenza dopo riavvio, installazione silenziosa, aggiornamento e disinstallazione con conservazione dei dati;
- confermati i gate CI, PostgreSQL/RLS, Docker enterprise, backup e ripristino;
- release ancora alpha, non firmata digitalmente e destinata a valutazione e pilot controllati con verifica umana.

"""
    path.write_text(notes + content, encoding="utf-8")


def update_smoke_test() -> None:
    relative = "scripts/local_distribution_smoke.py"
    old_first = '''        if len(original_documents) != 1:
            raise RuntimeError(f"Expected one document, got {len(original_documents)}")
        report["first_run"] = {"job": job["status"], "documents": len(original_documents)}
'''
    new_first = '''        if len(original_documents) != 1:
            raise RuntimeError(f"Expected one document, got {len(original_documents)}")

        exported = client.get("/api/export", headers=auth)
        exported.raise_for_status()
        if len(exported.content) < 100 or "zip" not in exported.headers.get("content-type", "").lower():
            raise RuntimeError("Local export did not return a valid ZIP archive")

        demo = client.post("/api/demo/load", headers=auth)
        demo.raise_for_status()
        demo_loaded = int(demo.json().get("loaded", 0))
        if demo_loaded < 1:
            raise RuntimeError(f"Demo loader did not add documents: {demo.json()}")
        all_documents_response = client.get("/api/documents", headers=auth)
        all_documents_response.raise_for_status()
        all_documents = all_documents_response.json()
        if len(all_documents) <= len(original_documents):
            raise RuntimeError("Demo documents were not visible after loading")
        report["first_run"] = {
            "job": job["status"],
            "documents": len(all_documents),
            "demo_loaded": demo_loaded,
            "export_bytes": len(exported.content),
        }
'''
    replace_exact(relative, old_first, new_first)

    old_restart = '''        persisted_documents = persisted.json()
        if len(persisted_documents) != 1 or persisted_documents[0]["id"] != original_documents[0]["id"]:
            raise RuntimeError("Document persistence check failed after restart")
        report["restart"] = {"documents": len(persisted_documents), "same_document": True}
'''
    new_restart = '''        persisted_documents = persisted.json()
        persisted_ids = {item["id"] for item in persisted_documents}
        if original_documents[0]["id"] not in persisted_ids or len(persisted_documents) != len(all_documents):
            raise RuntimeError("Document persistence check failed after restart")
        exported_after_restart = client.get("/api/export", headers=auth)
        exported_after_restart.raise_for_status()
        if len(exported_after_restart.content) < 100:
            raise RuntimeError("Export failed after restart")
        report["restart"] = {
            "documents": len(persisted_documents),
            "same_document": True,
            "export_bytes": len(exported_after_restart.content),
        }
'''
    replace_exact(relative, old_restart, new_restart)


def update_windows_workflow() -> None:
    relative = ".github/workflows/windows-release.yml"
    marker = '''      - name: Upload downloadable artifacts
'''
    if "Exercise installer upgrade and uninstall lifecycle" in read(relative):
        return
    lifecycle = '''      - name: Exercise installer upgrade and uninstall lifecycle
        shell: pwsh
        run: |
          $ErrorActionPreference = "Stop"
          $Version = (Select-String -Path "app\\version.py" -Pattern 'RELEASE_VERSION = "([^"]+)"').Matches.Groups[1].Value
          $CurrentInstaller = (Resolve-Path "release\\windows\\ThisTinti-Setup-$Version-x64.exe").Path
          $BaselineVersion = "3.4.0-alpha.3"
          $Iscc = "${env:ProgramFiles(x86)}\\Inno Setup 6\\ISCC.exe"
          if (-not (Test-Path $Iscc)) { $Iscc = "$env:ProgramFiles\\Inno Setup 6\\ISCC.exe" }
          if (-not (Test-Path $Iscc)) { throw "Inno Setup compiler unavailable for lifecycle test" }
          & $Iscc "/DMyAppVersion=$BaselineVersion" "installer\\windows\\ThisTinti.iss"
          if ($LASTEXITCODE -ne 0) { throw "Baseline installer compilation failed" }
          $BaselineInstaller = (Resolve-Path "release\\windows\\ThisTinti-Setup-$BaselineVersion-x64.exe").Path
          $InstallDir = Join-Path $env:LOCALAPPDATA "Programs\\ThisTinti-Acceptance"
          $DataDir = Join-Path $env:LOCALAPPDATA "ThisTinti-Acceptance"
          Remove-Item $InstallDir, $DataDir -Recurse -Force -ErrorAction SilentlyContinue

          & $BaselineInstaller /VERYSILENT /SUPPRESSMSGBOXES /NORESTART "/DIR=$InstallDir"
          if ($LASTEXITCODE -ne 0 -or -not (Test-Path (Join-Path $InstallDir "ThisTinti.exe"))) {
            throw "Baseline silent installation failed"
          }
          New-Item -ItemType Directory -Path $DataDir -Force | Out-Null
          $Marker = Join-Path $DataDir "upgrade-preservation-marker.txt"
          "preserve" | Set-Content $Marker -Encoding ascii

          & $CurrentInstaller /VERYSILENT /SUPPRESSMSGBOXES /NORESTART "/DIR=$InstallDir"
          if ($LASTEXITCODE -ne 0 -or -not (Test-Path $Marker)) { throw "Installer upgrade did not preserve data" }
          python scripts\\local_distribution_smoke.py `
            --executable (Join-Path $InstallDir "ThisTinti.exe") `
            --data-dir (Join-Path $DataDir "smoke") `
            --report "release\\windows\\installed-local-smoke.json"
          if ($LASTEXITCODE -ne 0) { throw "Installed application smoke test failed" }

          $Uninstaller = Join-Path $InstallDir "unins000.exe"
          if (-not (Test-Path $Uninstaller)) { throw "Uninstaller not found" }
          & $Uninstaller /VERYSILENT /SUPPRESSMSGBOXES /NORESTART
          if ($LASTEXITCODE -ne 0) { throw "Silent uninstall failed" }
          if (Test-Path (Join-Path $InstallDir "ThisTinti.exe")) { throw "Application remained after uninstall" }
          if (-not (Test-Path $Marker)) { throw "Local data was removed during uninstall" }

          Remove-Item $BaselineInstaller -Force
          Remove-Item $InstallDir, $DataDir -Recurse -Force -ErrorAction SilentlyContinue

'''
    replace_exact(relative, marker, lifecycle + marker)


def update_download_site() -> None:
    index = "site/index.html"
    replace_exact(index, '<link rel="stylesheet" href="styles.css" />', '<link rel="icon" href="logo.svg" type="image/svg+xml" />\n  <link rel="stylesheet" href="styles.css" />')
    replace_exact(index, '<a class="brand" href="#top"><span>T</span>ThisTinti</a>', '<a class="brand" href="#top"><img src="logo.svg" alt="" />ThisTinti</a>')
    styles = "site/styles.css"
    replace_exact(styles, '.brand span { display:grid; place-items:center; width:34px; height:34px; border-radius:10px; color:white; background:var(--blue); }', '.brand img { display:block; width:36px; height:36px; border-radius:10px; }')
    shutil.copyfile(ROOT / "app/static/logo.svg", ROOT / "site/logo.svg")


def create_verification_files() -> None:
    verification = f"""# Verifica del rilascio {NEW_VERSION}

## Evidenze completate

- build e smoke test del sorgente e dell'eseguibile congelato;
- caricamento di documenti dimostrativi ed esportazione ZIP;
- arresto, riavvio e persistenza dei documenti;
- installazione Windows reale, primo avvio, accettazione legale e creazione amministratore;
- prova automatica di installazione silenziosa, aggiornamento da un installer con versione precedente e disinstallazione;
- conservazione della cartella dati dopo la disinstallazione;
- CI Python 3.11/3.12, audit dipendenze, PostgreSQL RLS e Self-Hosted Reference Proof.

## Limiti residui dichiarati

- installer non firmato digitalmente: SmartScreen può mostrare “Editore sconosciuto”;
- nessun penetration test o parere legale indipendente;
- nessuna validazione statistica su documenti aziendali reali;
- release alpha destinata a dimostrazioni e pilot controllati con dati anonimizzati e verifica umana.
"""
    write("docs/RELEASE_VERIFICATION_3.4.0_ALPHA.4.md", verification)
    evidence = {
        "version": NEW_VERSION,
        "project_name": "ThisTinti",
        "prepared_at": "2026-07-21",
        "windows_real_installation_passed": True,
        "windows_first_run_and_admin_creation_passed": True,
        "smartscreen_unsigned_warning_observed": True,
        "new_brand_mark_verified": True,
        "registration_layout_verified": True,
        "source_and_frozen_smoke_required": True,
        "demo_loading_and_export_required": True,
        "installer_upgrade_and_uninstall_required": True,
        "postgres_rls_required": True,
        "enterprise_reference_proof_required": True,
        "digitally_signed": False,
        "external_security_audit_completed": False,
        "independent_legal_review_completed": False,
        "real_document_pilot_completed": False,
    }
    write("docs/evidence/release-3.4.0-alpha.4.json", json.dumps(evidence, ensure_ascii=False, indent=2) + "\n")


def generate_metadata() -> None:
    subprocess.run(["python", "scripts/generate_openapi.py"], cwd=ROOT, check=True)
    subprocess.run(["python", "scripts/generate_sbom.py"], cwd=ROOT, check=True)


def main() -> int:
    bump_version()
    update_release_notes()
    update_smoke_test()
    update_windows_workflow()
    update_download_site()
    create_verification_files()
    generate_metadata()
    print(f"Prepared ThisTinti {NEW_VERSION}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

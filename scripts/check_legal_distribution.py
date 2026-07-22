#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_VERSION = "2026-07-20-v2"
REQUIRED = [
    ROOT / "LICENSE",
    ROOT / "TERMS_OF_USE.md",
    ROOT / "DISCLAIMER.md",
    ROOT / "PRIVACY.md",
    ROOT / "TRADEMARKS.md",
    ROOT / "legal" / "INSTALLER_TERMS.txt",
    ROOT / "app" / "static" / "legal.html",
    ROOT / "site" / "legal.html",
    ROOT / "docs" / "ENTERPRISE_SELF_HOSTED.md",
    ROOT / "docs" / "RESPONSIBILITY_MATRIX.md",
    ROOT / "docs" / "ENTERPRISE_ACCEPTANCE_CHECKLIST.md",
    ROOT / "deploy" / "enterprise" / "docker-compose.enterprise.yml",
    ROOT / "deploy" / "enterprise" / "README.md",
]


def require(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def main() -> int:
    failures: list[str] = []
    for path in REQUIRED:
        require(
            path.is_file() and path.stat().st_size > 100,
            f"Missing or empty legal file: {path.relative_to(ROOT)}",
            failures,
        )

    legal_py = (ROOT / "app" / "legal.py").read_text(encoding="utf-8")
    runtime = (ROOT / "app" / "local_runtime.py").read_text(encoding="utf-8")
    frontend = (ROOT / "app" / "static" / "index.html").read_text(encoding="utf-8")
    app_js = (ROOT / "app" / "static" / "app.js").read_text(encoding="utf-8")
    site = (ROOT / "site" / "index.html").read_text(encoding="utf-8")
    site_js = (ROOT / "site" / "site.js").read_text(encoding="utf-8")
    installer = (ROOT / "installer" / "windows" / "ThisTinti.iss").read_text(encoding="utf-8")
    spec = (ROOT / "installer" / "windows" / "ThisTinti.spec").read_text(encoding="utf-8")
    workflow = (ROOT / ".github" / "workflows" / "windows-release.yml").read_text(encoding="utf-8")
    enterprise_compose = (ROOT / "deploy" / "enterprise" / "docker-compose.enterprise.yml").read_text(
        encoding="utf-8"
    )
    enterprise_init = (ROOT / "scripts" / "enterprise_init.py").read_text(encoding="utf-8")
    enterprise_preflight = (ROOT / "scripts" / "enterprise_preflight.py").read_text(encoding="utf-8")

    for name, text in {
        "app/legal.py": legal_py,
        "app/local_runtime.py": runtime,
        "app/static/app.js": app_js,
    }.items():
        require(EXPECTED_VERSION in text, f"Legal version mismatch in {name}", failures)

    require("acceptSpecificClauses" in frontend, "Frontend specific-clause acceptance missing", failures)
    require("Output automatici da verificare" in frontend, "Persistent in-app warning missing", failures)
    require("downloadRiskAcceptance" in site, "Download risk gate missing", failures)
    require("applyDownloadState" in site_js, "Download gate logic missing", failures)
    require(
        "SpecificApprovalCheck" in installer and "1341 e 1342" in installer,
        "Installer specific approval missing",
        failures,
    )
    require(
        "if WizardSilent and SilentTermsAccepted() then" in installer
        and "SpecificApprovalCheck.Checked := True" in installer,
        "Silent installer acceptance does not satisfy the explicit clause gate",
        failures,
    )
    for name in ("TERMS_OF_USE.md", "DISCLAIMER.md", "TRADEMARKS.md", "SUPPORT.md"):
        require(name in spec, f"Frozen build does not include {name}", failures)
        require(name in workflow, f"GitHub Release does not include {name}", failures)
    require("RESPONSIBILITY_MATRIX.md" in workflow, "Self-hosted responsibility matrix missing from release", failures)
    require("ENTERPRISE_ACCEPTANCE_CHECKLIST.md" in workflow, "Self-hosted checklist missing from release", failures)

    for marker in (
        'THISTINTI_SELF_HOSTED_REFERENCE: "true"',
        'THISTINTI_ALLOW_REGISTRATION: "false"',
        'THISTINTI_REQUIRE_MALWARE_SCANNER: "true"',
        "THISTINTI_OPERATOR_ACCEPTANCE_FILE: /run/secrets/operator_acceptance",
        "internal: true",
    ):
        require(marker in enterprise_compose, f"Enterprise safety marker missing: {marker}", failures)
    require("accept-operator-responsibility" in enterprise_init, "Enterprise operator acceptance missing", failures)
    require("legal_document_hashes" in enterprise_preflight, "Enterprise legal hash check missing", failures)
    require(
        "servizio gestito" in (ROOT / "TERMS_OF_USE.md").read_text(encoding="utf-8").lower(),
        "Managed-service boundary missing",
        failures,
    )

    marketing = "\n".join(
        (ROOT / path).read_text(encoding="utf-8").lower()
        for path in ("site/index.html", "README.md", "RELEASE_NOTES.md")
    )
    forbidden = [
        r"responsabilit[aà] zero",
        r"impedisce le frodi",
        r"non sbaglia",
        r"garantisce la conformit[aà]",
        r"autorizza pagamenti sicuri",
        r"nessuna responsabilit[aà]",
        r"immunit[aà] legale",
        r"enterprise certificato",
    ]
    for pattern in forbidden:
        require(re.search(pattern, marketing) is None, f"Unsafe marketing claim detected: {pattern}", failures)

    if failures:
        print("Legal distribution check failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    print(f"Legal distribution layers consistent ({EXPECTED_VERSION})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

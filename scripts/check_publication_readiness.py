#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = (
    "docs/PUBLIC_LAUNCH_CHECKLIST.md",
    "docs/NAME_AND_DOMAIN_CLEARANCE.md",
    "docs/REBRAND_3.4.0_ALPHA.3.md",
    "docs/RELEASE_VERIFICATION_3.4.0_ALPHA.3.md",
    "docs/RELEASE_VERIFICATION_3.4.0_ALPHA.5.md",
    "docs/evidence/rebrand-3.4.0-alpha.3.json",
    "docs/LICENSE_REVIEW.md",
    "docs/USER_GUIDE_SIMPLE.md",
    "docs/PILOT_KIT.md",
    "docs/PILOT_DATASET_SPEC.md",
    "docs/PROFESSIONALIZATION_PROGRAM.md",
    "docs/BETA_READINESS_STATUS.md",
    "docs/BETA_EXTERNAL_REVIEW_PACKET.md",
    "docs/ACCESSIBILITY_CONFORMANCE_PLAN.md",
    "docs/PERFORMANCE_AND_SLO.md",
    "docs/CODE_SIGNING_RUNBOOK.md",
    "docs/evidence/beta/external-gates.json",
    "docs/SECURE_DEVELOPMENT_BASELINE.md",
    "docs/LEGAL_REVIEW_BRIEF.md",
    "docs/SECURITY_REVIEW_BRIEF.md",
    "docs/DOMAIN_AND_PAGES_SETUP.md",
    "docs/THIRD_PARTY_NOTICES.md",
    "docs/BRAND_STATUS.md",
    "docs/DATA_LIFECYCLE.md",
    "docs/RELEASE_AUTHENTICITY.md",
    "docs/sbom.cdx.json",
    "docs/licenses-inventory.csv",
    "GOVERNANCE.md",
    "ROADMAP.md",
    "SECURITY.md",
    "SUPPORT.md",
    "TERMS_OF_USE.md",
    "DISCLAIMER.md",
    "site/index.html",
    "site/guide.html",
    "site/legal.html",
    "site/404.html",
    "site/logo.svg",
    "site/social-card.svg",
    "site/robots.txt",
    "site/sitemap.xml",
    "site/site.js",
    "app/static/logo.svg",
    "scripts/generate_brand_icon.py",
    ".github/workflows/windows-release.yml",
    ".github/workflows/enterprise-self-hosted.yml",
    ".github/workflows/pages.yml",
    ".github/workflows/publish-public-preview.yml",
)

FORBIDDEN_MARKETING = (
    r"responsabilit[aà] zero",
    r"nessuna responsabilit[aà]",
    r"non sbaglia",
    r"infallibile",
    r"garantisce la conformit[aà]",
    r"impedisce le frodi",
    r"pronto per qualsiasi azienda",
    r"autorizza automaticamente i pagamenti",
)


def tracked_files() -> list[Path]:
    excluded = {".git", ".pytest_cache", ".ruff_cache", "__pycache__", ".coverage-data"}
    return [
        path.relative_to(ROOT)
        for path in ROOT.rglob("*")
        if path.is_file() and not any(part in excluded for part in path.relative_to(ROOT).parts)
    ]


def main() -> int:
    failures: list[str] = []

    for relative in REQUIRED_FILES:
        path = ROOT / relative
        if not path.is_file() or path.stat().st_size < 80:
            failures.append(f"Missing or empty publication file: {relative}")

    version = (ROOT / "app/version.py").read_text(encoding="utf-8")
    match = re.search(r'RELEASE_VERSION\s*=\s*"([^"]+)"', version)
    if not match:
        failures.append("Cannot read RELEASE_VERSION")
        release_version = ""
    else:
        release_version = match.group(1)

    for relative in ("pyproject.toml", "installer/windows/ThisTinti.iss", "README.md"):
        text = (ROOT / relative).read_text(encoding="utf-8")
        if release_version and release_version not in text:
            failures.append(f"Version {release_version} missing from {relative}")

    site = (ROOT / "site/index.html").read_text(encoding="utf-8")
    site_js = (ROOT / "site/site.js").read_text(encoding="utf-8")
    for marker in (
        "downloadRiskAcceptance",
        "Public Preview",
        "Metti ordine nei documenti",
        "guide.html",
        "copyShareButton",
        "enterpriseSourceLink",
        "securityLink",
        "Local Edition",
    ):
        if marker not in site and marker not in site_js:
            failures.append(f"Public site marker missing: {marker}")

    public_text = "\n".join(
        (ROOT / relative).read_text(encoding="utf-8", errors="replace").lower()
        for relative in ("README.md", "RELEASE_NOTES.md", "site/index.html", "site/legal.html")
    )
    for pattern in FORBIDDEN_MARKETING:
        if re.search(pattern, public_text):
            failures.append(f"Unsafe marketing claim detected: {pattern}")

    tracked = tracked_files()

    legacy_tokens = (
        "This" + "Tinto",
        "THIS" + "TINTO",
        "this" + "tinto",
    )
    for relative in tracked:
        if any(token in str(relative) for token in legacy_tokens):
            failures.append(f"Legacy project name remains in path: {relative}")
        path = ROOT / relative
        if not path.is_file() or path.stat().st_size > 2_000_000:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if any(token in text for token in legacy_tokens):
            failures.append(f"Legacy project name remains in file: {relative}")

    forbidden_paths = {
        Path(".env"),
        Path("deploy/enterprise/.env"),
        Path("deploy/enterprise/operator-acceptance.json"),
    }
    for relative in tracked:
        if relative in forbidden_paths:
            failures.append(f"Sensitive generated file is tracked: {relative}")
        if any(part in {"backups", "logs", "secrets"} for part in relative.parts):
            if relative.name != ".gitkeep" and "example" not in relative.name.lower():
                failures.append(f"Operational material is tracked: {relative}")

    private_key_marker = "-----BEGIN " + "PRIVATE KEY-----"
    for relative in tracked:
        path = ROOT / relative
        if not path.is_file() or path.stat().st_size > 2_000_000:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if private_key_marker in text:
            failures.append(f"Private key material detected: {relative}")

    if failures:
        print("Publication readiness check failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print(f"Publication preparation consistent for {release_version}")
    print("Manual launch blockers remain documented in docs/PUBLIC_LAUNCH_CHECKLIST.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

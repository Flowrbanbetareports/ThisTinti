from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, content: str) -> None:
    (ROOT / path).write_text(content, encoding="utf-8")


def replace_once(text: str, old: str, new: str, *, label: str) -> str:
    if new in text:
        return text
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)


def replace_first(text: str, old: str, new: str, *, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"{label}: match not found")
    return text.replace(old, new, 1)


def replace_regex(text: str, pattern: str, replacement: str, *, label: str) -> str:
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.S)
    if count != 1:
        raise RuntimeError(f"{label}: expected one regex match, found {count}")
    return updated


path = "app/main.py"
text = read(path)
text = replace_once(
    text,
    "from .services.operational import (\n"
    "    build_case_history,\n"
    "    build_learning_suggestions,\n"
    "    build_operational_overview,\n"
    "    build_operational_report,\n"
    "    build_practice_summaries,\n"
    ")\n",
    "from .services.operational import (\n"
    "    build_case_history,\n"
    "    build_learning_suggestions,\n"
    "    build_operational_overview,\n"
    "    build_operational_report,\n"
    "    build_practice_summaries,\n"
    ")\n"
    "from .services.commercial import build_commercial_catalog, build_integration_pack\n",
    label="commercial import",
)
commercial_routes = '''@app.get("/api/commercial/catalog")
def commercial_catalog(ctx: AuthContext = Depends(current_user)) -> dict:
    return build_commercial_catalog()


@app.get(
    "/api/commercial/integration-pack",
    responses={200: {"content": {"application/zip": {}}}},
)
def commercial_integration_pack(
    ctx: AuthContext = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Response:
    content = build_integration_pack(app.openapi(), RELEASE_VERSION)
    add_audit(
        db,
        ctx.tenant_id,
        "commercial.integration_pack_exported",
        ctx.user_id,
        "tenant",
        ctx.tenant_id,
        {"version": RELEASE_VERSION, "status": "preview_included"},
    )
    db.commit()
    filename = f"ThisTinti-Integration-Pack-{RELEASE_VERSION}-preview.zip"
    return Response(
        content=content,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


'''
if '@app.get("/api/commercial/catalog")' not in text:
    marker = '@app.get(\n    "/api/export",\n'
    if marker not in text:
        raise RuntimeError("commercial routes: export marker not found")
    text = text.replace(marker, commercial_routes + marker, 1)
write(path, text)

path = "app/static/index.html"
text = read(path)
text = replace_once(
    text,
    '        <a class="sidebar-legal-link" href="/legal.html" target="_blank" rel="noopener">Licenza · Privacy · Rischi</a>',
    '        <a class="sidebar-legal-link hidden" data-admin-only href="/commercial.html">Progetto e piani</a>\n'
    '        <a class="sidebar-legal-link" href="/legal.html" target="_blank" rel="noopener">Licenza · Privacy · Rischi</a>',
    label="commercial sidebar link",
)
write(path, text)

version_replacements = {
    "app/version.py": [('RELEASE_VERSION = "3.4.0-alpha.7-rc.11"', 'RELEASE_VERSION = "3.4.0-alpha.7-rc.12"')],
    "app/static/app.js": [("UI_VERSION = '3.4.0-alpha.7-rc.11'", "UI_VERSION = '3.4.0-alpha.7-rc.12'")],
    "pyproject.toml": [('version = "3.4.0a7+rc.11"', 'version = "3.4.0a7+rc.12"')],
    "installer/windows/ThisTinti.iss": [
        ('#define MyAppVersion "3.4.0-alpha.7-rc.11"', '#define MyAppVersion "3.4.0-alpha.7-rc.12"'),
        ("VersionInfoVersion=3.4.0.17", "VersionInfoVersion=3.4.0.18"),
    ],
    "docs/BETA_READINESS_STATUS.md": [
        (
            "ThisTinti è in preparazione interna come `3.4.0-alpha.7-rc.11`. L’ultima Public Preview pubblicata e immutabile è `3.4.0-alpha.7-rc.10`.",
            "ThisTinti è in preparazione interna come `3.4.0-alpha.7-rc.12`. L’ultima Public Preview pubblicata e immutabile è `3.4.0-alpha.7-rc.11`.",
        )
    ],
    "docs/OPERATIONS.md": [
        ("ThisTinti 3.4.0-alpha.7-rc.11 (candidata interna non pubblicata)", "ThisTinti 3.4.0-alpha.7-rc.12 (candidata interna non pubblicata)")
    ],
    "docs/PRODUCTION_READINESS.md": [
        ("ThisTinti 3.4.0-alpha.7-rc.11 (candidata interna non pubblicata)", "ThisTinti 3.4.0-alpha.7-rc.12 (candidata interna non pubblicata)")
    ],
    "docs/THREAT_MODEL.md": [
        ("ThisTinti 3.4.0-alpha.7-rc.11 (candidata interna non pubblicata)", "ThisTinti 3.4.0-alpha.7-rc.12 (candidata interna non pubblicata)")
    ],
    "tests/test_rebrand.py": [
        ('assert RELEASE_VERSION == "3.4.0-alpha.7-rc.11"', 'assert RELEASE_VERSION == "3.4.0-alpha.7-rc.12"')
    ],
    "tests/test_simplified_experience.py": [
        ("assert \"UI_VERSION = '3.4.0-alpha.7-rc.11'\" in loader", "assert \"UI_VERSION = '3.4.0-alpha.7-rc.12'\" in loader")
    ],
}
for file_name, replacements in version_replacements.items():
    text = read(file_name)
    for old, new in replacements:
        text = replace_once(text, old, new, label=f"{file_name} version")
    write(file_name, text)

path = "docs/evidence/beta/external-gates.json"
payload = json.loads(read(path))
payload["candidate_version"] = "3.4.0-alpha.7-rc.12"
write(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")

path = "README.md"
text = read(path)
replacement = '''## Stato del rilascio

Versione di sviluppo: **3.4.0-alpha.7-rc.12 — candidata interna preparazione commerciale leggera**.

Ultima versione pubblica immutabile: **3.4.0-alpha.7-rc.11 — Public Preview**. La RC11 resta disponibile con checksum, provenienza e attestazioni e non viene modificata da questo sviluppo.

La candidata RC12 aggiunge una piccola area amministratore “Progetto e piani”: conta i download pubblici GitHub senza chiamarli utenti o installazioni, mostra metriche pubbliche del repository, offre un Integration Pack tecnico in anteprima e predispone catalogo, sponsor e pagamenti futuri mantenendoli disattivati. Non introduce telemetria, account centrale, pubblicità esterna o checkout.

## Identità e posizionamento'''
text = replace_regex(text, r"## Stato del rilascio\n.*?\n## Identità e posizionamento", replacement, label="README release status")
write(path, text)

path = "RELEASE_NOTES.md"
text = read(path)
rc12_notes = '''# 3.4.0-alpha.7-rc.12 — preparazione commerciale leggera (candidata interna)

- nuova pagina amministratore “Progetto e piani”, separata dal lavoro documentale quotidiano;
- contatore dei download pubblici GitHub per installer, portable e self-hosted, dichiarato esplicitamente distinto da utenti e installazioni attive;
- riepilogo di release, stelle, fork, issue/PR e workflow pubblici richiesto soltanto quando l’amministratore apre o aggiorna la pagina;
- Integration Pack in anteprima con OpenAPI, esempi Python, JavaScript e C# e contratto tecnico di esportazione;
- catalogo minimo Free / Integration Pack / Enterprise senza prezzi o checkout attivi;
- spazio sponsor esclusivamente dimostrativo, privo di reti esterne, profilazione e inserzioni nelle schermate operative;
- politica di acquisto digitale futura predisposta senza rinunce assolute a reclami legittimi o diritti inderogabili;
- nessuna telemetria, nessun documento o dato utente inviato all’autore;
- RC11 resta la Public Preview immutabile finché RC12 non supera i gate e viene pubblicata separatamente.

'''
if not text.startswith("# 3.4.0-alpha.7-rc.12"):
    text = rc12_notes + text
write(path, text)

path = "ROADMAP.md"
text = read(path)
replacement = '''# Roadmap di ThisTinti

## Stato attuale — 3.4.0-alpha.7-rc.12 candidata interna preparazione commerciale leggera

RC12 mantiene il prodotto gratuito e local-first. Aggiunge soltanto una pagina amministratore per metriche pubbliche, un Integration Pack in anteprima e predisposizioni disattivate per piani, sponsor e acquisto digitale. La Public Preview pubblica corrente resta RC11.

## RC8'''
text = replace_regex(text, r"# Roadmap di ThisTinti\n.*?\n## RC8", replacement, label="ROADMAP current state")
write(path, text)

path = "tests/test_release_integrity.py"
text = read(path)
pattern = (
    r'    request = json\.loads\(\(ROOT / "builds" / "public-preview-request\.json"\)\.read_text\(encoding="utf-8"\)\)\n'
    r'    release = json\.loads\(\(ROOT / "builds" / "release-latest\.json"\)\.read_text\(encoding="utf-8"\)\)\n'
    r'.*?'
    r'    assert re\.fullmatch\(r"\[0-9a-f\]\{40\}", request\["target_sha"\]\)\n'
    r'    assert re\.fullmatch\(r"\[0-9\]\+", request\["windows_run_id"\]\)'
)
replacement = '''    request = json.loads((ROOT / "builds" / "public-preview-request.json").read_text(encoding="utf-8"))
    release = json.loads((ROOT / "builds" / "release-latest.json").read_text(encoding="utf-8"))
    windows_latest = json.loads((ROOT / "builds" / "windows-latest.json").read_text(encoding="utf-8"))
    request_version = Version(to_python_package_version(request["version"]))
    published_version = Version(to_python_package_version(release["version"]))
    current_version = Version(PYTHON_PACKAGE_VERSION)

    assert request["schema"] == "thistinti.public-preview-request.v1"
    assert published_version <= request_version <= current_version
    if request_version == published_version:
        assert request["target_sha"] == release["release_commit"]
        assert int(request["windows_run_id"]) == release["build"]["workflow_run"]
    else:
        assert request_version == current_version
        assert windows_latest["version"] == request["version"]
        assert windows_latest["source"]["commit"] == request["target_sha"]
        assert windows_latest["build"]["run_id"] == int(request["windows_run_id"])
    assert re.fullmatch(r"[0-9a-f]{40}", request["target_sha"])
    assert re.fullmatch(r"[0-9]+", request["windows_run_id"])'''
text = replace_regex(text, pattern, replacement, label="release integrity candidate/public boundary")
write(path, text)

path = "site/index.html"
text = read(path)
text = replace_once(
    text,
    '      <a href="#faq">Domande</a>',
    '      <a href="#faq">Domande</a>\n      <a href="project.html">Progetto</a>',
    label="site project navigation",
)
text = replace_once(
    text,
    '<a id="securityLink" href="#">Sicurezza</a><a href="legal.html">Note legali</a>',
    '<a id="securityLink" href="#">Sicurezza</a><a href="project.html">Dashboard progetto</a><a href="legal.html">Note legali</a>',
    label="site project footer",
)
write(path, text)

path = "site/sitemap.xml"
text = read(path)
text = replace_once(
    text,
    '  <url><loc>https://flowrbanbetareports.github.io/ThisTinti/guide.html</loc><priority>0.8</priority></url>',
    '  <url><loc>https://flowrbanbetareports.github.io/ThisTinti/guide.html</loc><priority>0.8</priority></url>\n'
    '  <url><loc>https://flowrbanbetareports.github.io/ThisTinti/project.html</loc><priority>0.7</priority></url>',
    label="site project sitemap",
)
write(path, text)

path = ".github/workflows/pages.yml"
text = read(path)
text = replace_once(
    text,
    "          node --check site/site.js",
    "          node --check site/site.js\n          node --check site/project.js",
    label="pages project js",
)
text = replace_once(
    text,
    "              'social-card.svg', 'robots.txt', 'sitemap.xml',",
    "              'social-card.svg', 'robots.txt', 'sitemap.xml',\n              'project.html', 'project.css', 'project.js',",
    label="pages project files",
)
text = replace_once(
    text,
    "          for name in ['index.html', 'guide.html', 'legal.html', '404.html']:",
    "          for name in ['index.html', 'guide.html', 'legal.html', '404.html', 'project.html']:",
    label="pages project html",
)
write(path, text)

path = ".github/workflows/simplified-experience.yml"
text = read(path)
for old, new, label in (
    (
        '      - "app/static/app.js"',
        '      - "app/static/app.js"\n'
        '      - "app/static/commercial.html"\n'
        '      - "app/static/commercial.css"\n'
        '      - "app/static/commercial.js"',
        "simplified commercial static paths",
    ),
    (
        '      - "app/services/operational.py"',
        '      - "app/services/operational.py"\n      - "app/services/commercial.py"',
        "simplified service paths",
    ),
    (
        '      - "tests/test_product_quality_pass.py"',
        '      - "tests/test_product_quality_pass.py"\n      - "tests/test_commercial_readiness.py"',
        "simplified test paths",
    ),
    (
        '      - "scripts/check_operational_center_live_browser.py"',
        '      - "scripts/check_operational_center_live_browser.py"\n      - "scripts/check_commercial_readiness_browser.py"',
        "simplified browser paths",
    ),
    (
        '      - "docs/RC11_OPERATIONAL_CENTER.md"',
        '      - "docs/RC11_OPERATIONAL_CENTER.md"\n'
        '      - "docs/LIGHT_COMMERCIAL_READINESS.md"\n'
        '      - "docs/DIGITAL_PURCHASE_POLICY_TEMPLATE.md"',
        "simplified docs paths",
    ),
):
    count = text.count(old)
    if count != 2:
        raise RuntimeError(f"{label}: expected two matches, found {count}")
    text = text.replace(old, new)
text = replace_once(
    text,
    "          node --check app/static/app.js",
    "          node --check app/static/app.js\n          node --check app/static/commercial.js",
    label="simplified commercial js",
)
text = replace_once(
    text,
    "      - name: Verify recovery workflow in Chromium",
    "      - name: Verify light commercial readiness against the live app\n"
    "        run: python scripts/check_commercial_readiness_browser.py\n"
    "      - name: Verify recovery workflow in Chromium",
    label="simplified browser step",
)
text = replace_once(
    text,
    "            tests/test_product_quality_pass.py \\",
    "            tests/test_product_quality_pass.py \\\n            tests/test_commercial_readiness.py \\",
    label="simplified pytest",
)
write(path, text)

print("RC12 existing-file updates applied")

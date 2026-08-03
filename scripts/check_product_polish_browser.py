from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app" / "static"


def browser_executable() -> str | None:
    configured = os.getenv("PLAYWRIGHT_CHROMIUM_EXECUTABLE")
    if configured and Path(configured).is_file():
        return configured
    for candidate in ("google-chrome", "chromium", "chromium-browser"):
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    return None


def build_document() -> str:
    css = (STATIC / "product-polish.css").read_text(encoding="utf-8")
    script = (STATIC / "product-polish.js").read_text(encoding="utf-8")
    return f"""<!doctype html>
<html lang="it"><head><meta charset="utf-8"><style>{css}</style></head><body>
<div id="appView">
  <aside class="sidebar"><nav id="mainNav">
    <button data-view="dashboard" class="active">Panoramica</button>
    <button data-view="documents">Documenti</button>
    <button data-view="chains">Catene</button>
    <button data-view="cases">Anomalie</button>
    <button data-view="jobs">Attività</button>
    <button data-view="discovery">Regole proposte</button>
    <button data-view="validation">Validation Lab</button>
    <button data-view="audit">Audit</button>
    <button data-view="users">Utenti</button>
  </nav></aside>
  <main>
    <p id="pageEyebrow"></p><h2 id="pageTitle"></h2>
    <button id="demoButton">Carica esempio</button>
    <button id="guideLoadDemoButton">Prova con esempio</button>
    <aside class="legal-warning">Avviso lungo</aside>
    <strong id="metricDocuments">4</strong>
    <section id="jobsView"><div class="jobs-metrics"></div><table><tbody id="jobsTable"></tbody></table></section>
    <section id="discoveryView">
      <div class="metric-card"><p>Attività rilevata</p></div>
      <div class="metric-card"><p>Confidenza</p></div>
      <div class="metric-card"><p>Regole attive</p></div>
      <div class="metric-card"><p>Domande</p></div>
      <button id="runDiscoveryButton">Rianalizza attività</button>
      <div id="discoveryFields"><div class="detail-card"><p>unit_price</p><strong>100%</strong></div></div>
      <table><thead><tr><th>Regola</th><th>Motivo</th><th>Confidenza</th><th>Stato</th><th></th></tr></thead><tbody id="discoveryRulesTable"><tr><td>Regola</td><td>Motivo</td><td>90%</td><td>Attiva</td><td><button class="discovery-rule-decision" data-rule-decision="rejected">No</button><button class="discovery-rule-decision" data-rule-decision="confirmed">Sì</button></td></tr></tbody></table>
    </section>
    <section id="validationView">
      <div class="metric-card"><p>Precisione</p></div>
      <div class="metric-card"><p>Recall</p></div>
      <div class="metric-card"><p>F1</p></div>
      <div class="metric-card"><p>Gate rilascio</p><small id="validationGateNote">1 FP · 2 FN · MAE €3,00</small></div>
      <table><thead><tr><th>Data</th><th>Motore</th><th>Scenari</th><th>Precisione</th><th>Recall</th><th>F1</th><th>Gate</th></tr></thead><tbody id="validationRunsTable"></tbody></table>
    </section>
    <table><tbody id="casesTable"><tr><td><strong>Caso</strong><small>return_without_credit</small></td></tr></tbody></table>
    <div id="caseDialogBody"><div class="evidence-item"><p><strong>credit_quantity</strong></p><p>Osservato: 5.00000000</p><p>Atteso: 5.00000000</p></div></div>
    <div id="documentDialogBody"><div class="lines-table"><table><tbody><tr><td>1</td><td>A</td><td>—</td><td>5.00000000</td><td>€10</td><td>0.00000000%</td></tr></tbody></table></div></div>
    <div id="chainDialogBody">
      <div class="detail-card"><p>Stima euristica del rischio</p><strong id="chainRiskValue">100/100 · verifica prioritaria</strong><small>€155 potenzialmente coinvolti</small></div>
      <div class="detail-card"><p>Somiglianza</p><strong>100%</strong><small>canonical_safe_baseline</small></div>
      <div class="comparison-table"><table><tbody><tr><td><strong>5.00000000</strong></td></tr></tbody></table></div>
    </div>
    <table><tbody id="auditTable"><tr><td>oggi</td><td><strong>demo.loaded</strong></td><td>tenant</td><td><code>{{"loaded":4}}</code></td></tr></tbody></table>
  </main>
</div>
<script>
const state = {{ user: {{ role: 'admin' }}, documents: [1,2,3,4] }};
const viewMeta = {{}};
function labelStatus(value) {{ return value; }}
function riskDecisionLabel(value) {{ return value; }}
function dateTime(value) {{ return value; }}
function escapeHtml(value) {{ return String(value); }}
async function api(path) {{ if (path === '/api/audit') return [{{action:'demo.loaded',created_at:'2026-08-03T00:00:00Z'}}]; return []; }}
async function loadDashboard() {{}}
async function loadCases() {{}}
async function loadDiscovery() {{}}
async function loadValidation() {{}}
async function loadAudit() {{}}
async function loadJobs() {{}}
async function openCase() {{}}
async function openDocument() {{}}
async function openChain() {{}}
async function openView() {{}}
</script>
<script>{script}</script>
</body></html>"""


def main() -> None:
    executable = browser_executable()
    with sync_playwright() as playwright:
        launch_args: dict[str, object] = {"headless": True}
        if executable:
            launch_args["executable_path"] = executable
        browser = playwright.chromium.launch(**launch_args)
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.set_content(build_document(), wait_until="load")
        page.evaluate("window.loadJobs()")
        page.wait_for_timeout(150)
        result = page.evaluate(
            """() => ({
              legalSummary: document.querySelector('.supervision-note summary')?.textContent.trim(),
              validationNav: document.querySelector('[data-view="validation"]')?.textContent.trim(),
              discoveryNav: document.querySelector('[data-view="discovery"]')?.textContent.trim(),
              caseType: document.querySelector('#casesTable small')?.textContent.trim(),
              evidenceField: document.querySelector('.evidence-item strong')?.textContent.trim(),
              observed: document.querySelectorAll('.evidence-item p')[1]?.textContent.trim(),
              documentQuantity: document.querySelector('#documentDialogBody tbody tr').children[3].textContent.trim(),
              risk: document.querySelector('#chainRiskValue')?.textContent.trim(),
              technicalScore: document.querySelector('.technical-score')?.textContent.trim(),
              baseline: document.querySelector('#chainDialogBody .detail-card:nth-child(2) small')?.textContent.trim(),
              comparisonQuantity: document.querySelector('.comparison-table strong')?.textContent.trim(),
              discoveryField: document.querySelector('#discoveryFields .detail-card p')?.textContent.trim(),
              validationCard: document.querySelector('#validationView .metric-card p')?.textContent.trim(),
              gateNote: document.querySelector('#validationGateNote')?.textContent.trim(),
              auditAction: document.querySelector('#auditTable strong')?.textContent.trim(),
              auditDetails: document.querySelector('#auditTable details summary')?.textContent.trim(),
              activityContext: document.querySelector('#activityContext')?.textContent.trim(),
              demoHidden: getComputedStyle(document.querySelector('#demoButton')).display === 'none',
            })"""
        )
        browser.close()

    expected = {
        "legalSummary": "Uso supervisionatoControlla sempre i documenti originali",
        "validationNav": "✓ Qualità del motore",
        "discoveryNav": "✦ Controlli proposti",
        "caseType": "Reso senza nota di credito collegata",
        "evidenceField": "Quantità accreditata",
        "observed": "Osservato: 5",
        "documentQuantity": "5",
        "risk": "Priorità alta",
        "technicalScore": "Indice tecnico 100/100 · non è una probabilità",
        "baseline": "Configurazione prudenziale",
        "comparisonQuantity": "5",
        "discoveryField": "Prezzo unitario",
        "validationCard": "Segnalazioni corrette",
        "gateNote": "1 falsi allarmi · 2 anomalie mancate · errore medio €3,00",
        "auditAction": "Esempio dimostrativo caricato",
        "auditDetails": "Apri dettagli tecnici",
        "demoHidden": True,
    }
    failures = {key: (result.get(key), value) for key, value in expected.items() if result.get(key) != value}
    if not result.get("activityContext", "").startswith("Ultimo evento applicazione"):
        failures["activityContext"] = (result.get("activityContext"), "starts with Ultimo evento applicazione")
    if failures:
        raise SystemExit(json.dumps({"failures": failures, "result": result}, indent=2, ensure_ascii=False))
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app" / "static"
EVIDENCE = ROOT / "browser-evidence"


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
    css = (STATIC / "operational-center.css").read_text(encoding="utf-8")
    script = (STATIC / "operational-center.js").read_text(encoding="utf-8")
    return f"""<!doctype html>
<html lang="it"><head><meta charset="utf-8"><style>{css}</style></head><body>
<section id="dashboardView">
  <div class="metric-grid"></div><div class="dashboard-grid"></div><div class="panel"></div>
</section>
<section id="casesView" class="hidden"><div class="table-panel"><table><tbody id="casesTable"></tbody></table></div></section>
<div id="caseDialogBody"></div><dialog id="caseDialog"></dialog>
<div id="chainDialogBody"></div><dialog id="chainDialog"></dialog>
<div id="documentDialogBody"><div class="lines-table"><table><thead><tr><th>Riga</th></tr></thead><tbody><tr data-line-id="line-1"><td>1</td><td>GIACCA-145</td><td>Giacca</td><td>120</td><td>43</td><td>0%</td></tr></tbody></table></div></div><dialog id="documentDialog"></dialog>
<script>
const state = {{
  user: {{ role: 'admin' }},
  selectedCase: null,
  selectedDocument: null,
}};
const overview = {{
  metrics: {{documents:4,active_cases:5,critical_cases:0,practices_to_review:1,incomplete_chains:1,amount_indicative:1020.8,amount_may_overlap:true}},
  next_case: {{id:'case-1',chain_id:'chain-1',reference_key:'PO-1049',case_type:'return_without_credit',severity:'high',status:'open',title:'Reso senza nota di credito collegata',explanation:'PANT-220: reso complessivo di 5.00000000 unità senza nota di credito nella catena.',recommended_action:'Verificare il reso.',amount_estimate:155,confidence:.92}},
  practices: [{{chain_id:'chain-1',reference_key:'PO-1049',case_count:5,critical_count:0,high_count:4,amount_indicative:1020.8,amount_may_overlap:true,cases:[{{id:'case-1',chain_id:'chain-1',severity:'high',status:'open',title:'Reso senza nota di credito collegata',amount_estimate:155}}]}}],
  system: {{status:'operational',parsing_failures:0,review_required_documents:0,last_event_at:'2026-08-03T03:00:00Z'}},
}};
const caseDetail = {{...overview.next_case,evidence:[{{observed_value:'0.00000000',expected_value:'5.00000000'}}]}};
const documentDetail = {{id:'doc-1',lines:[{{id:'line-1',sku:'GIACCA-145',description:'Giacca',quantity:120,unit_price:43,discount_rate:0,line_total:5160}}]}};
function escapeHtml(value) {{ return String(value ?? '').replaceAll('&','&amp;').replaceAll('<','&lt;'); }}
function money(value) {{ return new Intl.NumberFormat('it-IT',{{style:'currency',currency:'EUR'}}).format(value || 0); }}
function dateTime(value) {{ return value || ''; }}
function labelStatus(value) {{ return value; }}
function labelSeverity(value) {{ return value === 'high' ? 'Alta' : value; }}
function toast(message, error) {{ window.__toast = {{message,error}}; }}
async function api(path, options={{}}) {{
  if (path === '/api/operational/overview') return overview;
  if (path === '/api/operational/practices') return overview.practices;
  if (path === '/api/operational/report') return {{overview,review:{{confirmed_or_resolved:1,false_positive_proxy:1,average_minutes_to_first_decision:null}},measurement_availability:{{note:'Dati reali non misurati'}},claim_boundary:'Rapporto interno'}};
  if (path === '/api/cases/case-1/history') return [{{decision:'needs_review',note:'Aperta verifica',created_at:'2026-08-03T03:00:00Z'}}];
  if (path === '/api/chains/chain-1') return {{cases:[caseDetail]}};
  if (path === '/api/document-lines/line-1' && options.method === 'PATCH') {{ window.__correction = JSON.parse(options.body); return {{ok:true,affected_chains:['chain-1']}}; }}
  return [];
}}
async function loadDashboard() {{}}
async function loadCases() {{ document.querySelector('#casesView').classList.remove('hidden'); }}
async function loadChains() {{}}
async function loadDocuments() {{}}
async function openView(view) {{ document.querySelector('#dashboardView').classList.toggle('hidden', view !== 'dashboard'); document.querySelector('#casesView').classList.toggle('hidden', view !== 'cases'); }}
async function openCase(id) {{ state.selectedCase = caseDetail; document.querySelector('#caseDialogBody').innerHTML='<div><p>'+caseDetail.explanation+'</p><button data-decision="dismissed">Scarta</button><button data-decision="needs_review">Rivedi</button><button data-decision="confirmed">Conferma</button><button data-decision="resolved">Risolvi</button></div>'; }}
async function openChain(id) {{ document.querySelector('#chainDialogBody').innerHTML='<div class="comparison-table">Confronto documenti</div>'; }}
async function openDocument(id) {{ state.selectedDocument = documentDetail; }}
async function submitDecision() {{}}
</script>
<script>{script}</script>
</body></html>"""


def main() -> None:
    EVIDENCE.mkdir(exist_ok=True)
    executable = browser_executable()
    with sync_playwright() as playwright:
        launch_args: dict[str, object] = {"headless": True}
        if executable:
            launch_args["executable_path"] = executable
        browser = playwright.chromium.launch(**launch_args)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.set_content(build_document(), wait_until="load")
        page.wait_for_selector("#operationalCenter")
        page.screenshot(path=str(EVIDENCE / "rc11-operational-dashboard.png"), full_page=True)

        dashboard = page.evaluate(
            """() => ({
              heading: document.querySelector('#operationalCenter h2')?.textContent.trim(),
              next: document.querySelector('.next-review-card h3')?.textContent.trim(),
              narrative: document.querySelector('.next-review-card p')?.textContent.trim(),
              practiceCount: document.querySelectorAll('.practice-card').length,
              oldDashboardHidden: getComputedStyle(document.querySelector('#dashboardView > .metric-grid')).display === 'none',
              systemCompact: Boolean(document.querySelector('.system-strip')),
              reportButton: document.querySelector('#downloadOperationalReport')?.textContent.trim(),
            })"""
        )

        page.evaluate("window.openCase('case-1')")
        page.wait_for_selector(".case-operational-summary")
        case_view = page.evaluate(
            """() => ({
              workflow: [...document.querySelectorAll('.workflow-step b')].map(item => item.textContent.trim()),
              history: document.querySelector('.case-history summary')?.textContent.trim(),
              dismissed: document.querySelector('[data-decision="dismissed"]')?.textContent.trim(),
              expected: document.querySelector('.case-action-grid article:nth-child(2) strong')?.textContent.trim(),
            })"""
        )

        page.evaluate("window.openDocument('doc-1')")
        page.wait_for_selector(".correct-line-button")
        page.click(".correct-line-button")
        page.fill("#lineCorrectionQuantity", "114")
        page.fill("#lineCorrectionPrice", "42")
        page.fill("#lineCorrectionDiscount", "8")
        page.fill("#lineCorrectionReason", "Controllato sul documento originale")
        page.click("#lineCorrectionForm button[type='submit']")
        page.wait_for_function("window.__correction !== undefined")
        correction = page.evaluate("window.__correction")
        browser.close()

    failures = {}
    if dashboard.get("heading") != "Cosa controllare adesso":
        failures["heading"] = dashboard.get("heading")
    if dashboard.get("next") != "Reso senza nota di credito collegata":
        failures["next"] = dashboard.get("next")
    if "5 unità" not in dashboard.get("narrative", "") or "5.00000000" in dashboard.get("narrative", ""):
        failures["narrative"] = dashboard.get("narrative")
    if dashboard.get("practiceCount") != 1 or not dashboard.get("oldDashboardHidden"):
        failures["dashboardHierarchy"] = dashboard
    if not dashboard.get("systemCompact") or dashboard.get("reportButton") != "Esporta rapporto":
        failures["systemOrReport"] = dashboard
    if case_view.get("workflow") != ["Nuova", "In verifica", "Esito", "Risolta"]:
        failures["workflow"] = case_view.get("workflow")
    if case_view.get("dismissed") != "Segna falso positivo":
        failures["dismissedLabel"] = case_view.get("dismissed")
    if case_view.get("expected") != "0 → 5":
        failures["evidenceFormatting"] = case_view.get("expected")
    expected_correction = {
        "sku": "GIACCA-145",
        "description": "Giacca",
        "quantity": 114,
        "unit_price": 42,
        "discount_rate": 8,
        "line_total": 5160,
        "reason": "Controllato sul documento originale",
    }
    if correction != expected_correction:
        failures["correction"] = correction
    if failures:
        raise SystemExit(json.dumps({"failures": failures, "dashboard": dashboard, "case": case_view}, ensure_ascii=False, indent=2))
    print(json.dumps({"dashboard": dashboard, "case": case_view, "correction": correction}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

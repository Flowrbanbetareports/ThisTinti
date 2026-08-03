from __future__ import annotations

import io
import json
import zipfile
from typing import Any


def build_commercial_catalog() -> dict[str, Any]:
    """Describe a deliberately small, inactive commercial layer.

    The catalogue is informational. It does not activate checkout, advertising,
    telemetry or a managed service and it does not restrict Apache-licensed code.
    """

    return {
        "schema": "thistinti.commercial-catalog.v1",
        "status": "preview_only",
        "checkout_enabled": False,
        "advertising_enabled": False,
        "telemetry_enabled": False,
        "plans": [
            {
                "code": "free",
                "name": "Free",
                "availability": "available",
                "price": None,
                "features": [
                    "Controllo documentale locale",
                    "Centro operativo supervisionato",
                    "Esportazioni di base",
                    "Codice sorgente Apache 2.0",
                ],
            },
            {
                "code": "integration",
                "name": "Integration Pack",
                "availability": "preview_not_for_sale",
                "price": None,
                "features": [
                    "Contratto OpenAPI pronto per i team tecnici",
                    "Esempi Python, JavaScript e C#",
                    "Schema di esportazione e note di integrazione",
                    "Pacchetto mantenuto e versionato in futuro",
                ],
            },
            {
                "code": "enterprise",
                "name": "Enterprise",
                "availability": "future",
                "price": None,
                "features": [
                    "Connettori e configurazioni su richiesta",
                    "Supporto e manutenzione solo con contratto separato",
                    "Nessun servizio gestito attivo nella Public Preview",
                ],
            },
        ],
        "payments": {
            "status": "disabled",
            "provider": None,
            "model_under_consideration": "one_time_digital_integration_pack",
            "future_checkout_rules": [
                "Prezzo e contenuto mostrati prima dell'acquisto",
                "Consegna digitale immediata soltanto dopo consenso espresso",
                "Presa d'atto separata dell'eventuale perdita del recesso ordinario, quando valida",
                "Nessuna rinuncia a diritti inderogabili, rimedi per mancata consegna o non conformità",
                "Rimborsi discrezionali esclusi dopo una consegna corretta, salvo eccezioni dichiarate",
            ],
            "claim_boundary": (
                "Le condizioni future potranno ridurre contestazioni opportunistiche, ma non possono impedire "
                "reclami legittimi, diritti inderogabili o richieste previste dalla legge."
            ),
        },
        "sponsorship": {
            "status": "disabled",
            "placement": "project_page_only",
            "external_scripts": False,
            "tracking": False,
            "operational_views_excluded": True,
        },
        "integration_pack": {
            "status": "preview_included",
            "download_path": "/api/commercial/integration-pack",
            "note": (
                "Il sorgente già pubblicato resta libero secondo Apache 2.0. Un eventuale prodotto a pagamento "
                "riguarderebbe manutenzione, compatibilità, connettori e supporto, non l'accesso al codice esistente."
            ),
        },
    }


def build_integration_pack(openapi_schema: dict[str, Any], release_version: str) -> bytes:
    python_client = """# Minimal ThisTinti client example.
# Configure the base URL and API credential locally.

import json
import urllib.request

BASE_URL = "http://127.0.0.1:8000"
API_TOKEN = "replace-with-local-api-credential"


def get_operational_report():
    request = urllib.request.Request(
        f"{BASE_URL}/api/operational/report",
        headers={"Authorization": f"Bearer {API_TOKEN}", "Accept": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))
"""
    javascript_client = """const baseUrl = 'http://127.0.0.1:8000';
const apiToken = 'replace-with-local-api-credential';

export async function getOperationalReport() {
  const response = await fetch(`${baseUrl}/api/operational/report`, {
    headers: { Authorization: `Bearer ${apiToken}`, Accept: 'application/json' },
  });
  if (!response.ok) throw new Error(`ThisTinti API ${response.status}`);
  return response.json();
}
"""
    csharp_client = """using System.Net.Http.Headers;
using System.Text.Json;

using var client = new HttpClient { BaseAddress = new Uri("http://127.0.0.1:8000") };
client.DefaultRequestHeaders.Authorization =
    new AuthenticationHeaderValue("Bearer", "replace-with-local-api-credential");
var json = await client.GetStringAsync("/api/operational/report");
using var report = JsonDocument.Parse(json);
Console.WriteLine(report.RootElement.GetProperty("schema"));
"""
    readme = f"""# ThisTinti Integration Pack — preview

Versione applicativa: `{release_version}`.

Contenuto:

- contratto OpenAPI completo;
- esempi minimi Python, JavaScript e C#;
- esempio di contratto di esportazione;
- note sui confini tra software libero e servizi futuri.

Questa anteprima non costituisce assistenza, compatibilità garantita, SLA o prodotto acquistato. Le credenziali API vanno create e custodite dall'organizzazione. Non inserire token nei repository.
"""
    contract = {
        "schema": "thistinti.integration-export-contract.v1",
        "description": "Esempio non vincolante per un'integrazione tecnica supervisionata.",
        "recommended_endpoints": [
            "/api/documents",
            "/api/chains",
            "/api/cases",
            "/api/operational/report",
            "/api/export",
        ],
        "rules": [
            "Trattare importi e anomalie come informazioni da verificare",
            "Conservare i documenti originali come fonte primaria",
            "Usare credenziali con privilegi minimi",
            "Non automatizzare pagamenti o contestazioni sulla sola base degli output",
        ],
    }
    commercial_notice = """# Confine commerciale

Il codice già pubblicato resta soggetto alla Apache License 2.0. Un eventuale Integration Pack a pagamento potrà remunerare manutenzione, compatibilità, connettori, documentazione operativa o supporto separato. Non limita i diritti già concessi sul sorgente pubblico.

Nessun pagamento è attivo in questa Public Preview.
"""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("README.md", readme)
        archive.writestr("OPENAPI.json", json.dumps(openapi_schema, ensure_ascii=False, indent=2))
        archive.writestr("clients/python_client.py", python_client)
        archive.writestr("clients/javascript_client.js", javascript_client)
        archive.writestr("clients/CSharpExample.cs", csharp_client)
        archive.writestr(
            "contracts/integration-export-contract.json",
            json.dumps(contract, ensure_ascii=False, indent=2),
        )
        archive.writestr("COMMERCIAL-PREVIEW.md", commercial_notice)
    return buffer.getvalue()

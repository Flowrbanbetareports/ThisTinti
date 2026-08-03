from __future__ import annotations

import json
from pathlib import Path


OLD = "3.4.0-alpha.7-rc.10"
NEW = "3.4.0-alpha.7-rc.11"


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one occurrence of {old!r}, found {count}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


def update_versions() -> None:
    replace_once("app/version.py", f'RELEASE_VERSION = "{OLD}"', f'RELEASE_VERSION = "{NEW}"')
    replace_once("pyproject.toml", 'version = "3.4.0a7+rc.10"', 'version = "3.4.0a7+rc.11"')
    replace_once("app/static/app.js", f"UI_VERSION = '{OLD}'", f"UI_VERSION = '{NEW}'")
    replace_once("tests/test_rebrand.py", f'RELEASE_VERSION == "{OLD}"', f'RELEASE_VERSION == "{NEW}"')
    replace_once(
        "tests/test_simplified_experience.py",
        f"UI_VERSION = '{OLD}'",
        f"UI_VERSION = '{NEW}'",
    )
    replace_once("installer/windows/ThisTinti.iss", f'#define MyAppVersion "{OLD}"', f'#define MyAppVersion "{NEW}"')
    replace_once("installer/windows/ThisTinti.iss", "VersionInfoVersion=3.4.0.16", "VersionInfoVersion=3.4.0.17")
    for name, heading in (
        ("docs/OPERATIONS.md", "Manuale operativo"),
        ("docs/PRODUCTION_READINESS.md", "Production readiness"),
        ("docs/THREAT_MODEL.md", "Threat model"),
    ):
        target = Path(name)
        text = target.read_text(encoding="utf-8")
        old_heading = f"# {heading} — ThisTinti {OLD}"
        if old_heading not in text:
            raise SystemExit(f"{name}: version heading not found")
        target.write_text(text.replace(old_heading, f"# {heading} — ThisTinti {NEW}", 1), encoding="utf-8")


def update_readme() -> None:
    path = Path("README.md")
    text = path.read_text(encoding="utf-8")
    start = text.index("## Stato del rilascio")
    end = text.index("## Identità e posizionamento")
    block = f"""## Stato del rilascio

Versione di sviluppo: **{NEW} — candidata interna Centro operativo**.

Ultima versione pubblica immutabile: **{OLD} — Public Preview**. La RC10 resta disponibile con checksum, provenienza e attestazioni e non viene modificata da questo sviluppo.

La candidata RC11 trasforma la dashboard in un centro operativo supervisionato: raggruppa le segnalazioni per pratica, propone la prossima verifica, mostra il workflow della segnalazione, apre il confronto documentale, permette correzioni controllate dei dati estratti con storico e rianalisi, produce rapporti operativi e formula soltanto suggerimenti di apprendimento soggetti ad approvazione umana.

ThisTinti offre due distribuzioni gratuite: una Local Edition per singola postazione e una Self-Hosted Reference Edition con PostgreSQL, worker scalabili, TLS, scanner malware e strumenti operativi per team tecnici. È adatto a sviluppo, dimostrazioni e **pilot controllati con documenti autorizzati e anonimizzati**. La beta validata richiede ancora pilot reale, collaudo manuale con tecnologie assistive e revisioni indipendenti.

"""
    path.write_text(text[:start] + block + text[end:], encoding="utf-8")


def update_release_notes() -> None:
    path = Path("RELEASE_NOTES.md")
    text = path.read_text(encoding="utf-8")
    if text.startswith(f"# {NEW}"):
        return
    intro = f"""# {NEW} — centro operativo e revisione supervisionata (candidata interna)

- la home indica cosa controllare adesso e propone la prossima verifica in base a gravità, stato, valore indicativo e data;
- le segnalazioni della stessa operazione vengono raggruppate in un unico fascicolo di pratica;
- il workflow distingue nuova, in verifica, confermata, falso positivo e risolta, mantenendo lo storico delle decisioni;
- il confronto della pratica riusa le prove e i documenti collegati esistenti senza creare copie o fonti parallele;
- i revisori possono correggere una riga estratta con motivo obbligatorio, prima/dopo, autore, provenienza e rianalisi delle catene coinvolte;
- i totali vengono ricalcolati coerentemente quando quantità, prezzo o sconto vengono corretti;
- i decimali di memorizzazione non compaiono più nelle nuove descrizioni e nelle evidenze;
- il rapporto operativo è esportabile in JSON e in una vista stampabile/PDF, lasciando nulli i dati di pilot non realmente misurati;
- l’apprendimento propone una revisione delle soglie soltanto dopo almeno cinque decisioni umane coerenti e non applica mai modifiche automatiche;
- Chromium verifica sia la presentazione isolata sia il flusso reale contro API, database, audit e rianalisi;
- RC10 resta la Public Preview immutabile finché RC11 non supera tutti i gate e viene pubblicata separatamente.

"""
    path.write_text(intro + text, encoding="utf-8")


def update_roadmap() -> None:
    path = Path("ROADMAP.md")
    text = path.read_text(encoding="utf-8")
    old = (
        f"## Stato attuale — {OLD} Public Preview\n\n"
        "Release pubblica immutabile: `3.4.0-alpha.7-rc.10`, commit `fe34da4e1f7cc509f19a34573f6145dd7f720762`, build Windows `30777323794`."
    )
    new = (
        f"## Stato attuale — {NEW} candidata interna Centro operativo\n\n"
        f"Ultima Public Preview pubblicata e immutabile: `{OLD}`, commit `fe34da4e1f7cc509f19a34573f6145dd7f720762`, build Windows `30777323794`."
    )
    if old not in text:
        raise SystemExit("ROADMAP: current-state block not found")
    text = text.replace(old, new, 1)
    marker = "- gate contro l’ulteriore crescita dei moduli monolitici.\n"
    addition = marker + (
        "- centro operativo orientato alla prossima verifica e alle pratiche raggruppate;\n"
        "- workflow supervisionato con storico delle decisioni e falsi positivi espliciti;\n"
        "- correzione dei dati estratti con provenienza, audit e rianalisi;\n"
        "- rapporto operativo veritiero e apprendimento sempre soggetto ad approvazione umana.\n"
    )
    if marker not in text:
        raise SystemExit("ROADMAP: feature marker not found")
    path.write_text(text.replace(marker, addition, 1), encoding="utf-8")


def update_beta_status() -> None:
    path = Path("docs/BETA_READINESS_STATUS.md")
    text = path.read_text(encoding="utf-8")
    old = f"ThisTinti `{OLD}` è pubblicata come Public Preview immutabile. La base tecnica include:"
    new = (
        f"ThisTinti è in preparazione interna come `{NEW}`. L’ultima Public Preview pubblicata e immutabile è `{OLD}`. "
        "La base tecnica include:"
    )
    if old not in text:
        raise SystemExit("Beta readiness current-state sentence not found")
    text = text.replace(old, new, 1)
    marker = "- toolkit pilot locale senza comunicazioni o azioni esterne automatiche.\n"
    if marker in text:
        addition = marker + (
            "- centro operativo con pratiche raggruppate, priorità spiegata e storico della revisione;\n"
            "- correzione supervisionata delle righe estratte con audit, provenienza e rianalisi;\n"
            "- prova Chromium reale del percorso operativo e rapporto con misure non inventate;\n"
            "- suggerimenti di apprendimento non automatici e vincolati a decisioni umane sufficienti.\n"
        )
        text = text.replace(marker, addition, 1)
    path.write_text(text, encoding="utf-8")


def update_external_gates() -> None:
    path = Path("docs/evidence/beta/external-gates.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("candidate_version") != OLD:
        raise SystemExit("Unexpected external-gates candidate version")
    payload["candidate_version"] = NEW
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def update_operational_doc() -> None:
    path = Path("docs/RC11_OPERATIONAL_CENTER.md")
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        "The current public release remains the immutable RC10 Public Preview. An RC11 version identity and Windows candidate may be created only after this branch passes the complete application, browser, PostgreSQL, self-hosted and Windows lifecycle gates.",
        f"The current public release remains the immutable `{OLD}` Public Preview. This branch now carries the unreleased `{NEW}` identity; publication remains a separate decision after the complete application, browser, PostgreSQL, self-hosted and Windows lifecycle gates pass on the exact final commit.",
    )
    path.write_text(text, encoding="utf-8")
    Path("docs/RC11_INTERNAL_CANDIDATE.md").write_text(
        f"""# RC11 internal candidate

Version: `{NEW}`.

RC11 is the supervised operational-workflow candidate after the immutable `{OLD}` Public Preview. It groups findings by practice, recommends the next review, exposes a complete review history, supports auditable correction of extracted line values, produces truthful operational reports and limits learning to human-approved proposals.

It does not publish itself, replace RC10 assets, modify original documents, contact external parties, send messages or make accounting, payment or supplier decisions.

## Required gates

- complete repository verification and minimum 90% coverage;
- live Chromium proof against real API, database, correction, audit and reanalysis;
- PostgreSQL tenant isolation and self-hosted proof;
- apparel OCR benchmark and local pilot toolkit;
- Windows build, upgrade from the existing public baseline, installed diagnostics, uninstall and data preservation;
- exact-commit checksums, provenance and attestations before any separate RC11 publication request.
""",
        encoding="utf-8",
    )


def main() -> None:
    update_versions()
    update_readme()
    update_release_notes()
    update_roadmap()
    update_beta_status()
    update_external_gates()
    update_operational_doc()


if __name__ == "__main__":
    main()

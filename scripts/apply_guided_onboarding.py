#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "app" / "static" / "index.html"


def replace_once(text: str, old: str, new: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"Expected source fragment not found: {old[:120]!r}")
    return text.replace(old, new, 1)


def main() -> int:
    text = INDEX.read_text(encoding="utf-8")

    text = replace_once(
        text,
        '  <link rel="stylesheet" href="/styles.css" />',
        '  <link rel="stylesheet" href="/styles.css" />\n  <link rel="stylesheet" href="/guide.css" />',
    )
    text = replace_once(
        text,
        '  <script src="/app.js" defer></script>',
        '  <script src="/app.js" defer></script>\n  <script src="/guide.js" defer></script>',
    )
    text = replace_once(
        text,
        '      <p class="hero-copy">Confronta ordini, consegne, fatture, resi e note di credito. Ogni anomalia resta collegata alle prove originali.</p>',
        '      <p class="hero-copy">Collega documenti, confronta dati e mette in evidenza differenze verificabili. Ogni segnalazione resta collegata alle prove originali.</p>',
    )
    text = replace_once(
        text,
        "        <div><span>01</span><p>Regole verificabili prima dell'automazione.</p></div>",
        "        <div><span>01</span><p>Controlli comprensibili e configurabili.</p></div>",
    )
    text = replace_once(
        text,
        "        <div><span>02</span><p>Nessuna azione economica senza approvazione.</p></div>",
        "        <div><span>02</span><p>Le segnalazioni informano: l'organizzazione decide come usarle.</p></div>",
    )
    text = replace_once(
        text,
        '      <aside class="legal-warning" role="note"><strong>Output automatici da verificare.</strong> Confronta sempre i documenti originali. ThisTinti non autorizza pagamenti e non sostituisce controlli contabili, fiscali o legali. <a href="/legal.html" target="_blank" rel="noopener">Note legali</a></aside>',
        '      <aside class="legal-warning" role="note"><strong>Output informativi da verificare.</strong> Confronta sempre i documenti originali. ThisTinti non sostituisce procedure, professionisti o decisioni dell\'organizzazione. <a href="/legal.html" target="_blank" rel="noopener">Note legali</a></aside>',
    )
    text = replace_once(
        text,
        '<article class="metric-card"><p>Importo potenziale</p><strong id="metricAmount">€0</strong><small>non è un importo garantito</small></article>',
        '<article class="metric-card"><p>Valore segnalato</p><strong id="metricAmount">€0</strong><small>stima informativa da verificare</small></article>',
    )
    text = replace_once(
        text,
        '<div class="panel-heading"><div><h3>Pipeline</h3><p>Dal file originale alla decisione umana.</p></div></div>',
        '<div class="panel-heading"><div><h3>Pipeline</h3><p>Dal file originale alla verifica interna.</p></div></div>',
    )
    text = replace_once(
        text,
        '<div><b>5</b><strong>Revisione</strong><small>Decisione umana</small></div>',
        '<div><b>5</b><strong>Revisione</strong><small>Valutazione dell\'organizzazione</small></div>',
    )

    INDEX.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

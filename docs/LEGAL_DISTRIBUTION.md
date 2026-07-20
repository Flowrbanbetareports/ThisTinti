# Distribuzione legale prudenziale della Local Free Edition

Questa guida descrive il perimetro scelto per ridurre i rischi del progetto originario. Non sostituisce un parere professionale sulla situazione concreta o su future modifiche del modello distributivo.

## Perimetro da conservare

La distribuzione ufficiale dovrebbe restare:

- gratuita e open source;
- non monetizzata dall'autore;
- priva di pubblicità, vendita di dati o corrispettivi in dati personali;
- senza cloud gestito dall'autore;
- senza assistenza, SLA, garanzie o integrazioni promesse;
- senza accesso remoto alle installazioni;
- senza raccolta di documenti, telemetria o log;
- presentata come strumento di supporto e non come sistema certificato.

Un cambiamento di questi elementi richiede una nuova valutazione legale e tecnica prima della pubblicazione.

## Barriere inserite

1. `LICENSE`: Apache License 2.0.
2. `TERMS_OF_USE.md`: scopo, rischi, obblighi dell'utilizzatore, assenza di garanzia e limiti di responsabilità.
3. `DISCLAIMER.md`: avviso sintetico.
4. `PRIVACY.md`: dati locali e ruoli dell'organizzazione.
5. `TRADEMARKS.md`: separazione tra distribuzione ufficiale e versioni modificate.
6. Installer: pagina licenza più approvazione specifica separata.
7. Portable/primo avvio: doppia conferma con versione, data e hash registrati localmente.
8. Registrazione locale: controllo server-side delle conferme.
9. Interfaccia: avviso permanente e avviso accanto alla simulazione economica.
10. Sito: download disabilitato fino alla presa visione dell'avviso.
11. GitHub Release: avviso legale e documenti allegati.
12. CI: controllo automatico di coerenza tra versione, documenti, installer, sito e runtime.

## Comunicazione da evitare

Non usare formulazioni come:

- “responsabilità zero”;
- “impedisce le frodi”;
- “non sbaglia”;
- “garantisce la conformità”;
- “autorizza pagamenti sicuri”;
- “sostituisce il commercialista o il legale”;
- “certificato” o “a norma” senza una base formale.

Usare invece:

- “segnala possibili anomalie”;
- “supporta la revisione”;
- “richiede verifica umana”;
- “dati conservati localmente nella distribuzione ufficiale”;
- “nessuna telemetria del progetto”.

## Trigger di nuova revisione

Prima di procedere, fermare la pubblicazione e richiedere una nuova analisi se viene aggiunto uno dei seguenti elementi:

- prezzo, donazione collegata a benefici, pubblicità o monetizzazione;
- account centrale, telemetria o raccolta di dati;
- cloud, hosting o supporto gestito;
- accesso remoto alle installazioni;
- automazioni che eseguono pagamenti o scritture contabili;
- uso in sanità, lavoro, credito, assicurazioni, giustizia, sicurezza o infrastrutture critiche;
- promesse di risultato, garanzia o tempi di intervento;
- firma digitale dell'autore su build modificate da terzi;
- distribuzione tramite un soggetto commerciale o integrazione in un prodotto venduto.

## Verifica pre-release

Eseguire:

```bash
python scripts/check_legal_distribution.py
```

Il controllo non certifica la conformità legale; impedisce soltanto che una release perda accidentalmente le barriere previste.

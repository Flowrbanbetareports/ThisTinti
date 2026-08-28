# Pilot Procurement — baseline metodologica

## Scopo

Questo protocollo trasforma il pilot Procurement in un esperimento riproducibile. Non certifica ThisTinti, non autorizza automazioni esterne e non consente dichiarazioni generali sull'intero procurement.

La baseline usa due assi distinti:

- stato della pratica: **ATTESO → OSSERVATO → GIUDICATO**;
- catena epistemica: **EVIDENZA → FATTO → INTERPRETAZIONE → GIUDIZIO**.

La provenienza attraversa entrambi. Un fatto deve indicare l'evidenza da cui deriva; un'interpretazione deve indicare i fatti e la regola che l'hanno prodotta; il giudizio umano non cancella il risultato tecnico.

## 1. Campione e separazione

Il pilot usa:

- 5–10 pratiche di **calibrazione**, nelle quali sono consentite modifiche;
- 20–25 pratiche di **blind evaluation**, mai usate per calibrare e analizzate senza modifiche durante il run.

La separazione non deve essere soltanto casuale. `case-register.csv` richiede `source_alias`, `template_family` e `similarity_group`; lo stesso `similarity_group` è vietato nei due gruppi. Questo riduce il rischio di leakage da fornitori, template o famiglie documentali quasi identiche.

## 2. Preregistrazione

`pilot-plan.json` contiene, prima del freeze:

- metriche primarie e secondarie;
- definizione di critical miss;
- soglie/criteri di accettazione;
- criteri di inclusione ed esclusione;
- strategia di campionamento;
- regole di interruzione.

Questi elementi devono essere approvati prima di vedere i risultati blind. Le soglie possono restare esplorative, ma non possono essere scelte retroattivamente per favorire il risultato.

## 3. Preparazione

Esempio:

```bash
python scripts/procurement_pilot_protocol.py prepare ./procurement-pilot-001 \
  --pilot-id PROCUREMENT-PILOT-001 \
  --organization-alias ORG-001 \
  --calibration-count 8 \
  --blind-count 22 \
  --review-mode dual_independent
```

Se esiste realmente un solo revisore qualificato, usare invece:

```bash
--review-mode single_reviewer_with_declared_limitation
```

Il limite metodologico viene registrato; non si deve simulare una doppia revisione inesistente.

## 4. Autorizzazione e inventario privato

Ogni riga di `case-register.csv` deve indicare `authorized=true` solo dopo una reale autorizzazione. I documenti aziendali non vanno aggiunti al repository pubblico.

Dopo aver collocato i documenti autorizzati nelle cartelle `calibration/CAL-*` e `blind/BLD-*`:

```bash
python scripts/procurement_pilot_protocol.py inventory-private ./procurement-pilot-001
```

Il comando crea `private/document-inventory.json` con SHA-256 dei file. Questo inventario è **privato** e non deve essere pubblicato. Il manifest pubblico conserva solo l'hash dell'inventario, non le impronte dei singoli documenti riservati.

## 5. Freeze e Pilot Manifest

Dopo la calibrazione, congelare:

- commit e versione software;
- Practice Model;
- Rule Pack;
- Company Profile;
- Ground Truth Protocol;
- Evaluation Protocol;
- case register;
- inventario privato dei documenti.

Esempio:

```bash
python scripts/procurement_pilot_protocol.py freeze ./procurement-pilot-001 \
  --software-commit <commit> \
  --software-version 3.4.0-alpha.7-rc.15 \
  --practice-model pilot/procurement/practice-model.v0.1.json \
  --practice-model-version 0.1 \
  --rule-pack pilot/procurement/rule-pack.v0.1.json \
  --rule-pack-version 0.1 \
  --company-profile ./procurement-pilot-001/private/company-profile.json \
  --company-profile-version 0.1 \
  --ground-truth-protocol pilot/procurement/ground-truth-protocol.v1.json \
  --ground-truth-protocol-version 1 \
  --evaluation-protocol pilot/procurement/evaluation-protocol.v1.json \
  --evaluation-protocol-version 1
```

Il comando produce `pilot-manifest.json` e `pilot-manifest.seal.json`. Il Manifest contiene versioni e hash degli artefatti ma non percorsi locali sensibili. I percorsi reali degli artefatti restano in `private/frozen-artifact-locations.json`.

**Un Pilot Manifest identifica un singolo esperimento.** Se cambia un artefatto congelato, il run è chiuso: serve un nuovo Manifest e i risultati non vengono mescolati.

## 6. Ground truth cieca

Dopo il freeze:

```bash
python scripts/procurement_pilot_protocol.py create-ground-truth-templates ./procurement-pilot-001
```

In modalità duale, `REV-A` e `REV-B` compilano indipendentemente i propri file in `ground-truth/reviewer-a` e `ground-truth/reviewer-b`. Solo dopo si produce il file adjudicato in `ground-truth/adjudicated`.

Prima del blind run:

```bash
python scripts/procurement_pilot_protocol.py seal-ground-truth ./procurement-pilot-001
```

La ground truth non è sigillabile se:

- una review obbligatoria non è completa;
- manca la dichiarazione che il revisore non ha visto l'output di ThisTinti;
- l'adjudication non è `sealed`;
- un fatto non rimanda all'evidenza;
- un'interpretazione non rimanda a fatti e Rule Pack;
- presenza e sufficienza usano valori non controllati;
- impatto finanziario e stato economico sono mescolati in modo incoerente.

## 7. Check prima del blind run

```bash
python scripts/procurement_pilot_protocol.py check-ready ./procurement-pilot-001
```

Il blind run è metodologicamente valido solo se `ready_for_blind_run=true`. Il controllo verifica nuovamente hash del Manifest, case register, inventario privato, artefatti congelati e ground truth sigillata.

## 8. Blind evaluation

Durante il blind run:

- nessuna modifica a software, Rule Pack, Practice Model o profilo;
- nessuna modifica alla ground truth;
- nessuna correzione degli errori osservati;
- i risultati vengono registrati in `results/blind-results.csv`.

Se emerge un difetto che obbliga a cambiare qualcosa di congelato, il run termina. La correzione appartiene a una versione successiva e a un nuovo Manifest.

## 9. Rapporto

Dopo aver completato esattamente tutti i casi blind:

```bash
python scripts/procurement_pilot_protocol.py evaluate ./procurement-pilot-001
```

Vengono prodotti:

- `results/pilot-result.json`;
- `results/pilot-result.md`;
- `results/blind-backlog.csv`.

Il rapporto mostra prima i conteggi grezzi e poi precision/recall con intervalli Wilson al 95%, risultati per `case_type`, critical miss e metriche economiche. Se esiste una sola valuta, viene calcolata anche una `exposure_weighted_recall` indicativa. Gli importi restano separati in potenziale esposizione, perdita confermata e perdita evitata: un'anomalia non diventa automaticamente una perdita.

La formulazione corretta resta circoscritta, per esempio:

> Nel pilot cieco Procurement v0.x, su 23 pratiche appartenenti al perimetro preregistrato…

Non è consentito trasformarla in una dichiarazione generale di accuratezza sull'intero procurement.

## 10. Modelli provvisori

Il repository contiene:

- `pilot/procurement/practice-model.v0.1.json`;
- `pilot/procurement/rule-pack.v0.1.json`;
- `pilot/procurement/company-profile.template.json`;
- `pilot/procurement/ground-truth-protocol.v1.json`;
- `pilot/procurement/evaluation-protocol.v1.json`.

Practice Model e Rule Pack sono esplicitamente **provvisori e non validati**. Devono essere corretti durante la calibrazione e solo dopo congelati per il blind run. La generalizzazione oltre Procurement viene valutata soltanto dopo evidenza su casi reali.

## 11. Cosa non è automatizzabile ora

Il toolkit prepara e protegge l'esperimento, ma non può creare al posto dell'organizzazione:

- l'autorizzazione sui documenti reali;
- la ground truth professionale;
- l'indipendenza di due revisori;
- il giudizio sull'effettiva materialità economica.

Questi rimangono input umani reali e non devono essere autocertificati dal software.

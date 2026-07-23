# Specifica del dataset pilot

## Scopo

Questa specifica definisce le evidenze minime per classificare una suite del Validation Lab come `anonymized_pilot` o `production`. Una suite sintetica rimane valida per la regressione tecnica, ma non misura l'accuratezza commerciale.

## Requisiti bloccanti

Una suite basata su evidenze reali deve contenere:

- almeno 30 scenari indipendenti;
- conferma esplicita dell'autorizzazione all'uso;
- riferimento interno all'autorizzazione, senza allegare documenti legali al dataset;
- almeno due revisori distinti;
- descrizione del metodo usato per creare la ground truth;
- perimetro del pilot documentato;
- per `anonymized_pilot`, conferma e descrizione del metodo di anonimizzazione.

Il modello Pydantic rifiuta la creazione di una suite reale che non soddisfa questi requisiti. Il gate di automazione resta separato: richiede inoltre esecuzione con il motore corrente, metriche superate e approvazione amministrativa del run esatto.

## Struttura minima

```json
{
  "name": "Pilot controllato",
  "version": "1",
  "evidence_level": "anonymized_pilot",
  "evidence": {
    "authorization_reference": "PILOT-AUTH-001",
    "authorized_use_confirmed": true,
    "anonymization_confirmed": true,
    "anonymization_method": "Descrizione verificabile del processo applicato.",
    "reviewer_refs": ["revisore-a", "revisore-b"],
    "ground_truth_method": "Classificazione indipendente e riconciliazione delle divergenze.",
    "scope": "Settore, formati, fornitori, periodo e limiti inclusi nel pilot.",
    "prepared_at": "2026-07-23T00:00:00Z"
  },
  "gate": {
    "min_precision": 0.95,
    "min_recall": 0.95,
    "min_f1": 0.95,
    "max_amount_mae": 1,
    "require_all_scenarios_pass": true
  },
  "scenarios": []
}
```

## Controllo preliminare da riga di comando

```bash
python scripts/validate_pilot_dataset.py pilot.json --report pilot-inspection.json
```

Il controllo:

- valida lo schema e i requisiti di governance;
- calcola SHA-256 del file;
- riepiloga scenari, documenti, formati e anomalie attese;
- segnala campi e valori che potrebbero contenere email, IBAN, codici fiscali o altri identificatori;
- non certifica che l'anonimizzazione sia sufficiente.

Usare `--fail-on-warning` in una pipeline interna dopo aver definito e documentato le eccezioni ammesse.

## Rapporto di validazione

Ogni run può esportare un rapporto JSON o Markdown. Per impostazione predefinita il rapporto è redatto e non include documenti, nomi fornitori, riferimenti commerciali, descrizioni degli scenari o identificativi interni del run.

Il rapporto include versione, dataset, livello di evidenza, metriche, gate, conteggi per classe di anomalia, fallimenti di parsing, governance sintetica e limiti d'uso. Prima della pubblicazione serve comunque una revisione umana.

## Separazione dei dati

- Conservare autorizzazioni, DPA e documenti originali fuori dal repository.
- Non committare dataset reali, anche se anonimizzati, senza una decisione esplicita e documentata.
- Usare identificativi interni non reversibili nei campi `reviewer_refs` e `authorization_reference`.
- Conservare una copia immutabile del dataset validato e il relativo hash.
- Convertire ogni difetto confermato in un test di regressione sintetico privo di dati aziendali.

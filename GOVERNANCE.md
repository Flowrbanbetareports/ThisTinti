# Governance di ThisTinti

## Identità del progetto

Il nome ufficiale del prodotto e del progetto è **ThisTinti**. `Flowrbanbetareports` è soltanto l'account tecnico GitHub che ospita il repository e non è un secondo marchio, un modulo del prodotto o una denominazione commerciale di ThisTinti.

Il nome, il logo e l'interfaccia restano modificabili nelle versioni future. Finché non sarà completata una verifica professionale di disponibilità del nome e del marchio, non viene dichiarata alcuna registrazione o esclusiva giuridica.

## Obiettivo attuale

ThisTinti è un progetto open source, local-first e self-hosted per il controllo documentale supervisionato. L'obiettivo della fase alpha è:

1. dimostrare il funzionamento tecnico;
2. consentire prove locali senza inviare documenti all'autore;
3. raccogliere evidenze su documenti anonimizzati;
4. preparare eventuali personalizzazioni o pilot aziendali controllati.

Non è attualmente un SaaS, un servizio gestito, un prodotto certificato o un sistema autorizzato a prendere decisioni economiche autonome.

## Modello di sviluppo

- `main` contiene lo stato corrente del progetto;
- ogni modifica sostanziale passa da un branch e da una pull request;
- i tag pubblicati sono immutabili;
- una correzione successiva usa un nuovo numero di versione;
- installer, archivio portable, sorgenti e checksum devono essere generati dalla CI;
- i test di una versione precedente non certificano automaticamente modifiche, fork o infrastrutture successive.

## Decisioni e manutenzione

Il maintainer del repository decide roadmap, integrazione delle modifiche, pubblicazione delle release e gestione dei canali ufficiali. La manutenzione è svolta su base best effort, senza SLA, tempi garantiti o obbligo di continuità.

Le decisioni che possono influire su risultati economici devono preservare:

- tracciabilità delle prove;
- verifica umana;
- possibilità di revisione e annullamento;
- assenza di pagamenti o registrazioni contabili automatiche;
- separazione tra dati originali e dati derivati.

## Canali ufficiali

Sono ufficiali soltanto:

- il repository `Flowrbanbetareports/ThisTinti`;
- la pagina GitHub Pages collegata al repository;
- le release GitHub firmate dal processo di pubblicazione del repository e accompagnate da checksum SHA-256.

Copie, fork, mirror, installer modificati e servizi di terzi sono separati dal progetto originario.

## Gate prima di un uso produttivo

Un utilizzo con dati aziendali sensibili o responsabilità operative richiede almeno:

- pilot documentale reale e anonimizzato;
- verifica di precisione, falsi positivi e falsi negativi;
- penetration test indipendente;
- revisione legale e privacy;
- firma digitale degli artefatti distribuiti;
- backup, ripristino, monitoraggio e risposta agli incidenti verificati sull'infrastruttura reale.

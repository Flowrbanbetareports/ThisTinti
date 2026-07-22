# Stato del nome e dell'identità visiva

## Decisione corrente

Il nome ufficiale del progetto è **ThisTinti**. Dalla versione `3.4.0-alpha.5` l'identità usa un monogramma a doppia T unito da un segno di verifica: le due lettere collegano direttamente il simbolo al nome, mentre il segno centrale richiama il controllo documentale supervisionato.

`Flowrbanbetareports` è soltanto il nome tecnico dell'account GitHub che ospita il repository. Non deve comparire nell'interfaccia, nell'installer, nella pagina di download o nella comunicazione del prodotto come marchio alternativo.

Il simbolo resta un'identità di progetto non registrata e può essere ulteriormente affinato prima della fase commerciale senza cambiare funzionamento o licenza del software.

## Sistema visivo alpha.5

La stessa geometria viene usata per:

- applicazione e schermata di accesso;
- barra laterale;
- favicon e pagina pubblica;
- eseguibile e installer Windows;
- varianti future chiare, scure e monocromatiche.

I token principali sono sfondo `#0d1720`, prima T `#f0b64c`, seconda T `#55b4c3` e verifica `#f7fafc`. Il file SVG dell'applicazione deve restare identico a quello del sito pubblico. L'icona Windows multi-risoluzione viene rigenerata da `scripts/generate_brand_icon.py` durante il packaging, evitando un binario grafico non verificabile nel repository.

Il marchio è progettato per restare leggibile a 16, 32, 64 e 256 pixel e non dipende dall'animazione per essere riconosciuto.

## Animazioni

Il motion system alpha.5 applica transizioni funzionali e discrete:

- durata tipica 150–300 ms;
- ingresso una sola volta per pagine, sezioni, dialoghi e pipeline;
- feedback chiaro su navigazione, focus, caricamento, successo ed errore;
- nessun movimento continuo puramente decorativo;
- supporto a `prefers-reduced-motion`;
- degradazione funzionale quando `IntersectionObserver` non è disponibile;
- nessun ritardo che ostacoli inserimento dati o revisione documentale.

## Verifica del nome

Prima di investimenti commerciali, registrazioni, dominio a pagamento, campagne pubblicitarie o accordi con aziende è necessaria una ricerca professionale di anteriorità e confondibilità nei territori e nelle classi merceologiche rilevanti.

Fino a tale verifica:

- non viene dichiarato che ThisTinti sia un marchio registrato;
- non viene usato il simbolo ®;
- il progetto può continuare a essere distribuito come alpha open source;
- un eventuale cambio di nome resta possibile prima della fase commerciale.

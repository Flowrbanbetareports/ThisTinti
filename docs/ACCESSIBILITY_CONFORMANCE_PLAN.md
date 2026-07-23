# Piano di conformità all'accessibilità

## Obiettivo

Target tecnico: WCAG 2.2 livello AA per applicazione e sito pubblico. Il controllo automatico è un gate di regressione, non una certificazione.

## Controlli automatici

`scripts/static_accessibility_audit.py` verifica almeno:

- lingua del documento, titolo e viewport;
- unicità degli identificatori;
- associazione tra campi e label;
- nomi accessibili di pulsanti e collegamenti;
- sicurezza dei collegamenti aperti in nuove schede;
- assenza di `tabindex` positivo;
- presenza di regioni live per gli esiti operativi;
- struttura base di form, dialoghi, tabelle e navigazione.

## Controlli manuali obbligatori

Prima della beta validata occorre documentare:

1. navigazione completa da tastiera, inclusi dialoghi e ritorno del focus;
2. focus non nascosto e sempre distinguibile;
3. ordine di lettura e annunci con almeno NVDA + Firefox/Chrome su Windows;
4. zoom al 200% e reflow a 320 CSS px;
5. contrasto di testo, controlli, indicatori e grafici;
6. target interattivi e alternative alle azioni di trascinamento;
7. errori identificati, descritti e collegati ai campi;
8. autenticazione senza test cognitivi o trascrizioni obbligatorie;
9. riduzione del movimento con `prefers-reduced-motion`;
10. verifica del sito pubblico e della Local Edition installata.

## Evidenza

Il rapporto deve indicare versione, commit, browser, sistema operativo, tecnologia assistiva, criteri verificati, problemi, gravità, correzioni e retest. L'esito viene registrato in `docs/evidence/beta/external-gates.json` senza inserire dati personali o materiale riservato.

(() => {
  'use strict';

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const DEMO_KEY = 'thistinti_product_demo_loaded_v1';
  let demoRequested = false;
  let auditContextLoading = false;
  let observerScheduled = false;

  const safeStorage = {
    get(key) {
      try { return window.localStorage.getItem(key); } catch (_) { return null; }
    },
    set(key, value) {
      try { window.localStorage.setItem(key, value); } catch (_) { /* local preference only */ }
    },
  };

  const FIELD_LABELS = Object.freeze({
    quantity: 'Quantità',
    expected_quantity: 'Quantità attesa',
    observed_quantity: 'Quantità osservata',
    ordered_quantity: 'Quantità ordinata',
    confirmed_quantity: 'Quantità confermata',
    delivered_quantity: 'Quantità consegnata',
    invoiced_quantity: 'Quantità fatturata',
    return_quantity: 'Quantità resa',
    returned_quantity: 'Quantità resa',
    credit_quantity: 'Quantità accreditata',
    credited_quantity: 'Quantità accreditata',
    unit_price: 'Prezzo unitario',
    expected_unit_price: 'Prezzo unitario atteso',
    observed_unit_price: 'Prezzo unitario osservato',
    discount_rate: 'Sconto',
    expected_discount_rate: 'Sconto atteso',
    observed_discount_rate: 'Sconto osservato',
    line_total: 'Totale riga',
    payment_amount: 'Importo pagato',
    amount: 'Importo',
    sku: 'Codice articolo',
    description: 'Descrizione',
    color: 'Colore',
    size: 'Taglia',
    lot: 'Lotto',
    order_number: 'Numero ordine',
    delivery_number: 'Numero consegna',
    invoice_number: 'Numero fattura',
    credit_note_number: 'Numero nota di credito',
    document_type: 'Tipo documento',
    supplier_name: 'Fornitore',
    document_date: 'Data documento',
  });

  const CASE_LABELS = Object.freeze({
    return_without_credit: 'Reso senza nota di credito collegata',
    partial_credit: 'Nota di credito parziale',
    quantity_mismatch: 'Quantità non coerenti',
    price_mismatch: 'Prezzo non coerente',
    discount_mismatch: 'Sconto non coerente',
    missing_discount: 'Sconto atteso non applicato',
    invoice_without_order: 'Fattura senza ordine collegato',
    invoice_without_delivery: 'Fattura senza consegna collegata',
    delivery_without_order: 'Consegna senza ordine collegato',
    over_delivery: 'Quantità consegnata superiore all’ordine',
    over_invoice: 'Quantità fatturata superiore alla consegna',
    duplicate_document: 'Possibile documento duplicato',
    missing_document: 'Documento atteso mancante',
    amount_mismatch: 'Importo non coerente',
  });

  const STATUS_LABELS = Object.freeze({
    blocked: 'Controllo non superato',
    pending: 'In attesa',
    overdue: 'Scaduto',
    missing_proof: 'Prova mancante',
    satisfied: 'Completo',
    expected: 'Atteso',
    at_risk: 'Da verificare',
    canonical_safe_baseline: 'Configurazione prudenziale',
    auto_active: 'Attivo secondo la configurazione',
    needs_confirmation: 'Da confermare',
    inactive: 'Disattivato',
  });

  const AUDIT_ACTION_LABELS = Object.freeze({
    'demo.loaded': 'Esempio dimostrativo caricato',
    'auth.login': 'Accesso effettuato',
    'auth.logout': 'Sessione chiusa',
    'document.uploaded': 'Documento caricato',
    'document.reprocessed': 'Documento rielaborato',
    'document.archived': 'Documento archiviato',
    'chain.document_attached': 'Documento collegato',
    'chain.document_detached': 'Documento scollegato',
    'case.decision': 'Decisione sulla segnalazione',
    'discovery.run': 'Controlli proposti aggiornati',
    'validation.run': 'Qualità del motore verificata',
    'user.created': 'Utente creato',
    'user.role_updated': 'Ruolo utente aggiornato',
    'user.status_updated': 'Stato utente aggiornato',
  });

  function humanizeIdentifier(value) {
    const raw = String(value ?? '').trim();
    if (!raw) return '—';
    if (FIELD_LABELS[raw]) return FIELD_LABELS[raw];
    if (CASE_LABELS[raw]) return CASE_LABELS[raw];
    if (STATUS_LABELS[raw]) return STATUS_LABELS[raw];
    return raw
      .replace(/[._-]+/g, ' ')
      .replace(/\b(?:id|uuid)\b/gi, 'identificativo')
      .replace(/\bsku\b/gi, 'codice articolo')
      .replace(/\bapi\b/gi, 'API')
      .replace(/\bocr\b/gi, 'OCR')
      .replace(/\bfp\b/gi, 'falsi allarmi')
      .replace(/\bfn\b/gi, 'anomalie mancate')
      .replace(/\s+/g, ' ')
      .trim()
      .replace(/^./, (character) => character.toUpperCase());
  }

  function formatFlexibleNumber(value) {
    if (value === null || value === undefined || value === '') return '—';
    const normalized = String(value).trim().replace(',', '.');
    if (!/^-?\d+(?:\.\d+)?$/.test(normalized)) return String(value);
    const numeric = Number(normalized);
    if (!Number.isFinite(numeric)) return String(value);
    return new Intl.NumberFormat('it-IT', {
      minimumFractionDigits: 0,
      maximumFractionDigits: 4,
    }).format(numeric);
  }

  function formatExactNumberElement(element) {
    if (!element) return;
    const raw = element.textContent.trim();
    const formatted = formatFlexibleNumber(raw);
    if (formatted !== raw && formatted !== '—') element.textContent = formatted;
  }

  function polishEvidenceValues(root) {
    $$('.evidence-item', root).forEach((item) => {
      const field = $('p strong', item);
      if (field) field.textContent = humanizeIdentifier(field.textContent);
      $$('p', item).forEach((paragraph) => {
        const match = paragraph.textContent.match(/^(Osservato|Atteso):\s*(.+)$/);
        if (!match) return;
        const formatted = formatFlexibleNumber(match[2]);
        if (formatted !== match[2]) paragraph.textContent = `${match[1]}: ${formatted}`;
      });
    });
  }

  function polishDocumentDialog() {
    const root = $('#documentDialogBody');
    if (!root) return;
    $$('.lines-table tbody tr', root).forEach((row) => {
      formatExactNumberElement(row.children[3]);
      const discount = row.children[5];
      if (discount && /^-?\d+(?:[.,]\d+)?%?$/.test(discount.textContent.trim())) {
        const numeric = discount.textContent.trim().replace('%', '');
        discount.textContent = `${formatFlexibleNumber(numeric)}%`;
      }
    });
  }

  function priorityFromScore(score, fallback = '') {
    if (/alta|prioritaria|block/i.test(fallback) || score >= 80) return ['Alta', 'risk-priority-high'];
    if (/bassa|allow/i.test(fallback) || score < 35) return ['Bassa', 'risk-priority-low'];
    return ['Media', 'risk-priority-medium'];
  }

  function polishChainDialog() {
    const root = $('#chainDialogBody');
    if (!root) return;
    $$('.comparison-table td strong', root).forEach(formatExactNumberElement);
    $$('.detail-card strong, .detail-card small, .badge', root).forEach((element) => {
      const raw = element.textContent.trim();
      if (STATUS_LABELS[raw]) element.textContent = STATUS_LABELS[raw];
    });

    const riskValue = $('#chainRiskValue', root);
    if (riskValue) {
      const match = riskValue.textContent.match(/(\d+)\s*\/\s*100(?:\s*·\s*(.*))?/);
      if (match) {
        const score = Number(match[1]);
        const [label, className] = priorityFromScore(score, match[2] || '');
        riskValue.textContent = `Priorità ${label.toLowerCase()}`;
        riskValue.classList.remove('risk-priority-high', 'risk-priority-medium', 'risk-priority-low');
        riskValue.classList.add(className);
        const card = riskValue.closest('.detail-card');
        if (card && !$('.technical-score', card)) {
          const technical = document.createElement('small');
          technical.className = 'technical-score';
          technical.textContent = `Indice tecnico ${score}/100 · non è una probabilità`;
          card.appendChild(technical);
        }
        const heading = $('p', card);
        if (heading) heading.textContent = 'Priorità di controllo';
      }
    }
  }

  function polishCasesTable() {
    $$('#casesTable tr').forEach((row) => {
      const type = $('td:first-child small', row);
      if (type) type.textContent = humanizeIdentifier(type.textContent);
    });
  }

  function polishDiscovery() {
    const root = $('#discoveryView');
    if (!root) return;
    const cards = $$('.metric-card', root);
    if (cards[2]) $('p', cards[2]).textContent = 'Controlli attivi';
    if (cards[3]) $('p', cards[3]).textContent = 'Da confermare';

    const fields = $('#discoveryFields', root);
    if (fields) {
      $$('.detail-card p', fields).forEach((label) => { label.textContent = humanizeIdentifier(label.textContent); });
      if (!fields.closest('.discovery-fields-details')) {
        const details = document.createElement('details');
        details.className = 'discovery-fields-details';
        const summary = document.createElement('summary');
        summary.textContent = 'Campi osservati nei documenti';
        fields.before(details);
        details.append(summary, fields);
      }
    }

    if (!$('.product-technical-callout', root)) {
      const callout = document.createElement('aside');
      callout.className = 'product-technical-callout';
      callout.innerHTML = '<strong>Area avanzata.</strong><span>Qui si controllano le regole suggerite dal sistema. Nessuna regola viene presentata come verità automatica.</span>';
      root.prepend(callout);
    }

    const table = $('#discoveryRulesTable', root)?.closest('table');
    if (table) {
      const headings = $$('thead th', table);
      ['Controllo', 'Perché viene proposto', 'Affidabilità', 'Stato', ''].forEach((label, index) => {
        if (headings[index]) headings[index].textContent = label;
      });
      $$('.discovery-rule-decision', table).forEach((button) => {
        if (button.dataset.ruleDecision === 'rejected') button.textContent = 'Rifiuta';
        if (button.dataset.ruleDecision === 'confirmed') button.textContent = 'Conferma';
      });
    }
    const runButton = $('#runDiscoveryButton', root);
    if (runButton && !runButton.disabled) runButton.textContent = 'Aggiorna proposte';
  }

  function polishValidation() {
    const root = $('#validationView');
    if (!root) return;
    if (!$('.product-technical-callout', root)) {
      const callout = document.createElement('aside');
      callout.className = 'product-technical-callout';
      callout.innerHTML = '<strong>Strumento tecnico.</strong><span>Questa sezione serve a misurare regressioni del motore. Non rappresenta da sola una certificazione su documenti reali.</span>';
      root.prepend(callout);
    }
    const cards = $$('.metric-card', root);
    const labels = ['Segnalazioni corrette', 'Anomalie trovate', 'Equilibrio complessivo', 'Controllo rilascio'];
    cards.forEach((card, index) => {
      const label = $('p', card);
      if (label && labels[index]) label.textContent = labels[index];
    });
    const gateNote = $('#validationGateNote', root);
    if (gateNote) {
      gateNote.textContent = gateNote.textContent
        .replace(/(\d+)\s*FP\s*·\s*(\d+)\s*FN\s*·\s*MAE\s*/i, '$1 falsi allarmi · $2 anomalie mancate · errore medio ');
    }
    const runsTable = $('#validationRunsTable', root)?.closest('table');
    if (runsTable) {
      const headings = $$('thead th', runsTable);
      const labelsByColumn = ['Data', 'Motore', 'Scenari', 'Correttezza', 'Copertura', 'Equilibrio', 'Esito'];
      headings.forEach((heading, index) => { if (labelsByColumn[index]) heading.textContent = labelsByColumn[index]; });
    }
  }

  function polishAudit() {
    const table = $('#auditTable');
    if (!table) return;
    $$('tr', table).forEach((row) => {
      const cells = row.children;
      if (cells.length < 4) return;
      const action = $('strong', cells[1]);
      if (action) action.textContent = AUDIT_ACTION_LABELS[action.textContent.trim()] || humanizeIdentifier(action.textContent);
      cells[2].textContent = humanizeIdentifier(cells[2].textContent);
      const code = $('code', cells[3]);
      if (code && !code.closest('details')) {
        const details = document.createElement('details');
        details.className = 'audit-details';
        const summary = document.createElement('summary');
        summary.textContent = 'Apri dettagli tecnici';
        code.before(details);
        details.append(summary, code);
      }
    });
  }

  function latestMeaningfulAudit(events) {
    const preferred = [
      'demo.loaded',
      'document.uploaded',
      'document.reprocessed',
      'chain.document_attached',
      'chain.document_detached',
      'case.decision',
      'discovery.run',
      'validation.run',
    ];
    return (events || []).find((event) => preferred.includes(event.action)) || null;
  }

  async function ensureActivityContext() {
    const root = $('#jobsView');
    if (!root || auditContextLoading) return;
    auditContextLoading = true;
    try {
      let event = null;
      if (typeof api === 'function' && state?.user?.role === 'admin') {
        try { event = latestMeaningfulAudit(await api('/api/audit')); } catch (_) { /* optional context */ }
      }
      const storedDemo = safeStorage.get(DEMO_KEY);
      if (!event && storedDemo) event = { action: 'demo.loaded', created_at: storedDemo };
      let panel = $('#activityContext', root);
      if (!event) {
        panel?.remove();
        return;
      }
      if (!panel) {
        panel = document.createElement('aside');
        panel.id = 'activityContext';
        panel.className = 'activity-context';
        const metrics = $('.jobs-metrics', root);
        metrics?.insertAdjacentElement('afterend', panel);
      }
      const label = AUDIT_ACTION_LABELS[event.action] || humanizeIdentifier(event.action);
      const when = event.created_at && typeof dateTime === 'function' ? dateTime(event.created_at) : '';
      panel.innerHTML = `<div><strong>Ultimo evento applicazione</strong><span>${escapeHtml(label)}${when ? ` · ${escapeHtml(when)}` : ''}</span></div><small>Le attività in tabella mostrano elaborazioni persistenti; il registro amministrativo conserva anche gli altri eventi.</small>`;
    } finally {
      auditContextLoading = false;
    }
  }

  function compactLegalNotice() {
    const warning = $('.legal-warning');
    if (!warning || warning.dataset.productPolish === '1') return;
    warning.dataset.productPolish = '1';
    warning.innerHTML = `
      <details class="supervision-note">
        <summary><strong>Uso supervisionato</strong><span>Controlla sempre i documenti originali</span></summary>
        <p>ThisTinti organizza, collega e segnala possibili differenze. Non autorizza pagamenti, non certifica documenti e non sostituisce controlli contabili, fiscali o legali. <a href="/legal.html" target="_blank" rel="noopener">Note legali</a></p>
      </details>`;
  }

  function setButtonLabel(view, icon, label) {
    const button = $(`#mainNav [data-view="${view}"]`);
    if (!button) return;
    const expected = `${icon} ${label}`;
    if (button.textContent.replace(/\s+/g, ' ').trim() !== expected) {
      button.innerHTML = `<span aria-hidden="true">${icon}</span> ${label}`;
    }
    button.setAttribute('aria-label', label);
  }

  function polishNavigation() {
    setButtonLabel('dashboard', '⌂', 'Inizio');
    setButtonLabel('documents', '▤', 'Documenti');
    setButtonLabel('chains', '⌘', 'Collegamenti');
    setButtonLabel('cases', '△', 'Da controllare');
    setButtonLabel('jobs', '↻', 'Attività');
    setButtonLabel('discovery', '✦', 'Controlli proposti');
    setButtonLabel('validation', '✓', 'Qualità del motore');
    setButtonLabel('audit', '◎', 'Registro attività');
    setButtonLabel('users', '◇', 'Utenti');

    const guideCards = $$('#guideView .guide-grid article h3');
    guideCards.forEach((heading) => {
      if (heading.textContent.trim() === 'Regole proposte') heading.textContent = 'Controlli proposti';
      if (heading.textContent.trim() === 'Strumenti amministrativi') heading.textContent = 'Qualità e amministrazione';
    });

    if (typeof viewMeta !== 'undefined') {
      viewMeta.dashboard = ['Riepilogo operativo', 'Inizio'];
      viewMeta.documents = ['Archivio locale', 'Documenti'];
      viewMeta.chains = ['Flusso documentale', 'Collegamenti'];
      viewMeta.cases = ['Controllo umano', 'Da controllare'];
      viewMeta.jobs = ['Elaborazione', 'Attività'];
      viewMeta.discovery = ['Configurazione', 'Controlli proposti'];
      viewMeta.validation = ['Qualità tecnica', 'Qualità del motore'];
      viewMeta.audit = ['Tracciabilità', 'Registro attività'];
      viewMeta.users = ['Accessi', 'Utenti'];
    }
  }

  function updateDemoVisibility() {
    const documentCount = Number($('#metricDocuments')?.textContent || state?.documents?.length || 0);
    if (demoRequested && documentCount > 0) {
      safeStorage.set(DEMO_KEY, new Date().toISOString());
      demoRequested = false;
    }
    const hasData = documentCount > 0 || Boolean(safeStorage.get(DEMO_KEY));
    document.documentElement.classList.toggle('has-business-data', hasData);
    $('#demoButton')?.classList.toggle('hidden', hasData);
    $('#guideLoadDemoButton')?.classList.toggle('hidden', hasData);
  }

  function applyProductPolish() {
    compactLegalNotice();
    polishNavigation();
    polishCasesTable();
    polishDocumentDialog();
    polishEvidenceValues($('#caseDialogBody') || document);
    polishChainDialog();
    polishDiscovery();
    polishValidation();
    polishAudit();
    updateDemoVisibility();
  }

  function schedulePolish() {
    if (observerScheduled) return;
    observerScheduled = true;
    window.requestAnimationFrame(() => {
      observerScheduled = false;
      applyProductPolish();
    });
  }

  function wrapAsync(name, after) {
    const original = window[name];
    if (typeof original !== 'function' || original.__productPolished) return;
    const wrapped = async function (...args) {
      const result = await original.apply(this, args);
      await after(...args);
      return result;
    };
    wrapped.__productPolished = true;
    window[name] = wrapped;
  }

  function init() {
    const baseStatus = typeof window.labelStatus === 'function' ? window.labelStatus : (value) => value || '—';
    window.labelStatus = (value) => STATUS_LABELS[value] || baseStatus(value);
    window.riskDecisionLabel = (value) => ({ allow: 'Priorità bassa', review: 'Priorità media', block: 'Priorità alta' })[value] || 'Priorità da definire';

    wrapAsync('loadDashboard', async () => { updateDemoVisibility(); });
    wrapAsync('loadCases', async () => { polishCasesTable(); });
    wrapAsync('loadDiscovery', async () => { polishDiscovery(); });
    wrapAsync('loadValidation', async () => { polishValidation(); });
    wrapAsync('loadAudit', async () => { polishAudit(); });
    wrapAsync('loadJobs', async () => { await ensureActivityContext(); });
    wrapAsync('openCase', async () => { polishEvidenceValues($('#caseDialogBody') || document); });
    wrapAsync('openDocument', async () => { polishDocumentDialog(); });
    wrapAsync('openChain', async () => { polishChainDialog(); });
    wrapAsync('openView', async (view) => {
      polishNavigation();
      if (view === 'jobs') await ensureActivityContext();
      schedulePolish();
    });

    $('#demoButton')?.addEventListener('click', () => { demoRequested = true; });

    const root = $('#appView') || document.body;
    const observer = new MutationObserver(schedulePolish);
    observer.observe(root, { childList: true, subtree: true, characterData: true });
    applyProductPolish();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, { once: true });
  else init();
})();

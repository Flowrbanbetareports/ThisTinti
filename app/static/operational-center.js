(() => {
  'use strict';

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  let dashboardBusy = false;
  let queueBusy = false;

  const workflowLabel = (value) => ({
    open: 'Nuova', needs_review: 'In verifica', confirmed: 'Confermata',
    dismissed: 'Falso positivo', resolved: 'Risolta', superseded: 'Superata',
  })[value] || labelStatus(value);

  function cleanNumber(raw, digits = 4) {
    const value = Number(String(raw).replace(',', '.'));
    if (!Number.isFinite(value)) return String(raw);
    return new Intl.NumberFormat('it-IT', { maximumFractionDigits: digits }).format(value);
  }

  function cleanNarrative(raw) {
    return String(raw || '')
      .replace(/€\s*(-?\d+(?:[.,]\d+)?)/g, (_, value) => money(Number(value.replace(',', '.'))))
      .replace(/(-?\d+(?:[.,]\d+)?)%/g, (_, value) => `${cleanNumber(value, 2)}%`)
      .replace(/(?<![A-Za-z0-9_-])(-?\d+\.\d{3,})(?![A-Za-z0-9_-])/g, (_, value) => cleanNumber(value));
  }

  function severityDot(value) {
    return `<span class="severity-dot ${['critical', 'high', 'medium', 'low'].includes(value) ? value : 'medium'}"></span>`;
  }

  function practiceCard(practice) {
    const title = practice.reference_key || `Pratica ${practice.chain_id.slice(0, 8)}`;
    const cases = (practice.cases || []).slice(0, 4).map(item => `
      <button class="practice-case-link" type="button" data-case-id="${item.id}">
        ${severityDot(item.severity)}<span><strong>${escapeHtml(cleanNarrative(item.title))}</strong><small>${escapeHtml(workflowLabel(item.status))} · ${money(item.amount_estimate)}</small></span>
      </button>`).join('');
    return `<article class="practice-card">
      <div class="practice-card-heading"><div><span class="practice-kicker">Pratica</span><h4>${escapeHtml(title)}</h4></div><strong>${money(practice.amount_indicative)}</strong></div>
      <p>${practice.case_count} ${practice.case_count === 1 ? 'controllo aperto' : 'controlli aperti'} · ${practice.critical_count || practice.high_count} prioritari</p>
      <div class="practice-case-list">${cases}</div>
      <div class="practice-card-footer"><small>${practice.amount_may_overlap ? 'Il valore può includere differenze sovrapposte.' : 'Valore indicativo della pratica.'}</small><button class="secondary-button compact open-practice" type="button" data-chain-id="${practice.chain_id}">Apri confronto</button></div>
    </article>`;
  }

  function bindPracticeActions(root) {
    $$('.open-practice, [data-open-practice]', root).forEach(button => button.addEventListener('click', event => {
      event.stopPropagation();
      openChain(button.dataset.chainId);
    }));
    $$('.practice-case-link, [data-open-case]', root).forEach(button => button.addEventListener('click', event => {
      event.stopPropagation();
      openCase(button.dataset.caseId);
    }));
  }

  async function renderOperationalDashboard() {
    const view = $('#dashboardView');
    if (!view || view.classList.contains('hidden') || dashboardBusy) return;
    dashboardBusy = true;
    try {
      const data = await api('/api/operational/overview');
      const metrics = data.metrics || {};
      const next = data.next_case;
      let root = $('#operationalCenter', view);
      if (!root) {
        root = document.createElement('section');
        root.id = 'operationalCenter';
        view.prepend(root);
      }
      view.classList.add('rc11-operational-dashboard');
      root.innerHTML = `
        <div class="operational-header">
          <div><p class="eyebrow">Centro operativo</p><h2>Cosa controllare adesso</h2><p>Priorità calcolata da gravità, stato, valore indicativo e data.</p></div>
          <div class="system-strip ${data.system?.status === 'attention' ? 'attention' : ''}"><span></span><strong>${data.system?.status === 'attention' ? 'Sistema operativo con elementi da rivedere' : 'Sistema operativo'}</strong><small>${data.system?.parsing_failures || 0} errori parser · ${data.system?.review_required_documents || 0} documenti da rivedere</small></div>
        </div>
        <section class="operational-metrics">
          <article class="operational-metric"><span>Pratiche da controllare</span><strong>${metrics.practices_to_review || 0}</strong><small>${metrics.active_cases || 0} segnalazioni attive</small></article>
          <article class="operational-metric"><span>Valore indicativo</span><strong>${money(metrics.amount_indicative || 0)}</strong><small>${metrics.amount_may_overlap ? 'Può includere sovrapposizioni' : 'Somma delle segnalazioni'}</small></article>
          <article class="operational-metric"><span>Collegamenti incompleti</span><strong>${metrics.incomplete_chains || 0}</strong><small>Pratiche aperte o in revisione</small></article>
          <article class="operational-metric"><span>Documenti disponibili</span><strong>${metrics.documents || 0}</strong><small>Conservati in locale</small></article>
        </section>
        ${next ? `<article class="next-review-card"><div class="next-review-copy"><span class="practice-kicker">Prossima verifica consigliata</span><h3>${escapeHtml(cleanNarrative(next.title))}</h3><p>${escapeHtml(cleanNarrative(next.explanation))}</p><div class="next-review-meta"><span class="badge ${next.severity}">${labelSeverity(next.severity)}</span><strong>${money(next.amount_estimate)}</strong><span>${escapeHtml(next.reference_key || 'Pratica')}</span></div></div><div class="next-review-actions"><button class="primary-button" type="button" data-open-case data-case-id="${next.id}">Apri verifica</button><button class="secondary-button" type="button" data-open-practice data-chain-id="${next.chain_id}">Confronta documenti</button></div></article>` : '<article class="next-review-card empty"><div><span class="practice-kicker">Coda operativa</span><h3>Nessuna verifica aperta</h3><p>I documenti presenti non generano segnalazioni attive.</p></div></article>'}
        <section class="practice-section"><div class="section-title-row"><div><h3>Pratiche prioritarie</h3><p>Le anomalie della stessa operazione vengono trattate insieme.</p></div><div><button id="downloadOperationalReport" class="secondary-button compact" type="button">Esporta rapporto</button><button id="showAllPractices" class="text-button" type="button">Vedi tutte</button></div></div><div class="practice-grid">${(data.practices || []).slice(0, 6).map(practiceCard).join('') || '<div class="empty-state">Nessuna pratica da controllare.</div>'}</div></section>`;
      bindPracticeActions(root);
      $('#showAllPractices', root)?.addEventListener('click', () => openView('cases'));
      $('#downloadOperationalReport', root)?.addEventListener('click', downloadReport);
    } catch (error) {
      console.error('Centro operativo non disponibile', error);
    } finally {
      dashboardBusy = false;
    }
  }

  async function renderPracticeQueue() {
    const view = $('#casesView');
    if (!view || view.classList.contains('hidden') || queueBusy) return;
    queueBusy = true;
    try {
      const practices = await api('/api/operational/practices');
      let root = $('#practiceQueue', view);
      if (!root) {
        root = document.createElement('section');
        root.id = 'practiceQueue';
        root.className = 'practice-queue';
        view.prepend(root);
      }
      root.innerHTML = `<div class="section-title-row"><div><p class="eyebrow">Coda per pratica</p><h3>${practices.length} ${practices.length === 1 ? 'pratica aperta' : 'pratiche aperte'}</h3><p>Ordine, consegna, fattura, reso e nota di credito restano nello stesso fascicolo.</p></div></div><div class="practice-grid">${practices.map(practiceCard).join('') || '<div class="empty-state">Nessuna pratica aperta.</div>'}</div><details class="individual-case-table"><summary>Mostra le singole segnalazioni</summary></details>`;
      const panel = $('.table-panel', view);
      const details = $('.individual-case-table', root);
      if (panel && details && panel.parentElement !== details) details.appendChild(panel);
      bindPracticeActions(root);
    } catch (error) {
      console.error('Coda pratiche non disponibile', error);
    } finally {
      queueBusy = false;
    }
  }

  async function downloadReport() {
    const popup = window.open('', '_blank', 'noopener,noreferrer');
    if (popup) {
      popup.document.write('<!doctype html><html lang="it"><head><meta charset="utf-8"><title>Preparazione rapporto…</title></head><body><p>Preparazione del rapporto operativo…</p></body></html>');
      popup.document.close();
    }
    try {
      const report = await api('/api/operational/report');
      const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `ThisTinti-rapporto-operativo-${new Date().toISOString().slice(0, 10)}.json`;
      link.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
      if (popup) {
        const metrics = report.overview?.metrics || {};
        const review = report.review || {};
        popup.document.write(`<!doctype html><html lang="it"><head><meta charset="utf-8"><title>Rapporto operativo</title><style>body{font-family:Arial;margin:40px;color:#14202b}.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}.card{border:1px solid #ddd;border-radius:12px;padding:16px}.card strong{display:block;font-size:24px;margin-top:8px}@media print{button{display:none}}</style></head><body><h1>ThisTinti — Rapporto operativo</h1><div class="grid"><div class="card">Pratiche aperte<strong>${metrics.practices_to_review || 0}</strong></div><div class="card">Segnalazioni attive<strong>${metrics.active_cases || 0}</strong></div><div class="card">Valore indicativo<strong>${money(metrics.amount_indicative || 0)}</strong></div><div class="card">Confermate o risolte<strong>${review.confirmed_or_resolved || 0}</strong></div><div class="card">Falsi positivi<strong>${review.false_positive_proxy || 0}</strong></div><div class="card">Tempo medio prima decisione<strong>${review.average_minutes_to_first_decision == null ? 'Non misurato' : `${review.average_minutes_to_first_decision} min`}</strong></div></div><p>${escapeHtml(report.measurement_availability?.note || '')}</p><p><strong>${escapeHtml(report.claim_boundary || '')}</strong></p><button onclick="window.print()">Stampa / Salva PDF</button></body></html>`);
        popup.document.close();
      }
    } catch (error) {
      if (popup) popup.close();
      toast(error.message, true);
    }
  }

  async function enhanceCase(id) {
    const root = $('#caseDialogBody');
    if (!root || !state.selectedCase || state.selectedCase.id !== id || $('.case-operational-summary', root)) return;
    try {
      const history = await api(`/api/cases/${id}/history`);
      const item = state.selectedCase;
      const evidence = item.evidence?.find(value => value.observed_value != null || value.expected_value != null);
      const section = document.createElement('section');
      section.className = 'case-operational-summary';
      section.innerHTML = `<div class="workflow-strip"><span class="workflow-step ${item.status === 'open' ? 'current' : ''}">1<b>Nuova</b></span><span class="workflow-step ${item.status === 'needs_review' ? 'current' : ''}">2<b>In verifica</b></span><span class="workflow-step ${['confirmed','dismissed'].includes(item.status) ? 'current' : ''}">3<b>Esito</b></span><span class="workflow-step ${item.status === 'resolved' ? 'current' : ''}">4<b>Risolta</b></span></div><div class="case-action-grid"><article><span>Cosa è successo</span><strong>${escapeHtml(cleanNarrative(item.title))}</strong></article><article><span>Differenza concreta</span><strong>${escapeHtml(cleanNarrative(evidence?.observed_value || '—'))} → ${escapeHtml(cleanNarrative(evidence?.expected_value || '—'))}</strong></article><article><span>Impatto indicativo</span><strong>${money(item.amount_estimate)}</strong></article><article><span>Prossima azione</span><strong>${escapeHtml(cleanNarrative(item.recommended_action))}</strong></article></div><div class="case-operational-actions"><button id="openCasePractice" class="primary-button" type="button">Confronta i documenti della pratica</button></div><details class="case-history"><summary>Storico della verifica (${history.length})</summary>${history.length ? `<ol>${history.map(entry => `<li><strong>${escapeHtml(workflowLabel(entry.decision))}</strong><span>${dateTime(entry.created_at)}</span>${entry.note ? `<p>${escapeHtml(entry.note)}</p>` : ''}</li>`).join('')}</ol>` : '<p>Nessuna decisione registrata.</p>'}</details>`;
      root.prepend(section);
      $('#openCasePractice', section).addEventListener('click', () => { $('#caseDialog').close(); openChain(item.chain_id); });
      const labels = { dismissed: 'Segna falso positivo', needs_review: 'Metti in verifica', confirmed: 'Conferma anomalia', resolved: 'Segna risolta' };
      $$('#caseDialog [data-decision]').forEach(button => { button.textContent = labels[button.dataset.decision] || button.textContent; });
      $$('#caseDialogBody p, #caseDialogBody strong').forEach(node => { node.textContent = cleanNarrative(node.textContent); });
    } catch (error) { console.error('Storico non disponibile', error); }
  }

  async function enhanceChain(id) {
    const root = $('#chainDialogBody');
    if (!root || $('.chain-case-summary', root)) return;
    try {
      const detail = await api(`/api/chains/${id}`);
      const cases = (detail.cases || []).filter(item => ['open','needs_review','confirmed'].includes(item.status));
      const section = document.createElement('section');
      section.className = 'chain-case-summary';
      section.innerHTML = `<div class="section-title-row"><div><p class="eyebrow">Pratica completa</p><h3>${cases.length} ${cases.length === 1 ? 'controllo aperto' : 'controlli aperti'}</h3><p>Le differenze vengono verificate insieme.</p></div><strong>${money(cases.reduce((sum, item) => sum + Number(item.amount_estimate || 0), 0))}</strong></div><div class="chain-case-chips">${cases.map(item => `<button type="button" data-case-id="${item.id}">${severityDot(item.severity)}${escapeHtml(cleanNarrative(item.title))}</button>`).join('') || '<span>Nessuna segnalazione attiva.</span>'}</div>`;
      root.prepend(section);
      $$('[data-case-id]', section).forEach(button => button.addEventListener('click', () => { $('#chainDialog').close(); openCase(button.dataset.caseId); }));
    } catch (error) { console.error('Riepilogo pratica non disponibile', error); }
  }

  function ensureCorrectionDialog() {
    if ($('#lineCorrectionDialog')) return;
    const dialog = document.createElement('dialog');
    dialog.id = 'lineCorrectionDialog';
    dialog.className = 'modal';
    dialog.innerHTML = `<form id="lineCorrectionForm" class="modal-card"><div class="modal-heading"><div><p class="eyebrow">Correzione supervisionata</p><h3>Correggi la riga estratta</h3></div><button class="icon-button" type="button" data-close-correction>×</button></div><input id="lineCorrectionId" type="hidden"><div class="form-grid"><div><label>Codice articolo</label><input id="lineCorrectionSku"></div><div><label>Descrizione</label><input id="lineCorrectionDescription"></div><div><label>Quantità</label><input id="lineCorrectionQuantity" type="number" step="any"></div><div><label>Prezzo unitario</label><input id="lineCorrectionPrice" type="number" step="any" min="0"></div><div><label>Sconto %</label><input id="lineCorrectionDiscount" type="number" step="any" min="0" max="100"></div><div><label>Totale riga</label><input id="lineCorrectionTotal" type="number" step="any" min="0"></div><div class="full"><label>Motivo della correzione</label><textarea id="lineCorrectionReason" rows="3" minlength="3" required></textarea><small>Il valore precedente resta nello storico; il documento originale non viene modificato.</small></div></div><div class="modal-actions"><button class="secondary-button" type="button" data-close-correction>Annulla</button><button class="primary-button" type="submit">Salva e ricalcola</button></div></form>`;
    document.body.appendChild(dialog);
    $$('[data-close-correction]', dialog).forEach(button => button.addEventListener('click', () => dialog.close()));
    $('#lineCorrectionForm', dialog).addEventListener('submit', submitCorrection);
  }

  function enhanceDocument(id) {
    const root = $('#documentDialogBody');
    if (!root || state.selectedDocument?.id !== id || !['admin','reviewer'].includes(state.user?.role)) return;
    ensureCorrectionDialog();
    const heading = $('.lines-table thead tr', root);
    if (heading && !$('.line-correction-heading', heading)) heading.insertAdjacentHTML('beforeend', '<th class="line-correction-heading">Verifica</th>');
    $$('.lines-table tbody tr[data-line-id]', root).forEach(row => {
      if ($('.correct-line-button', row)) return;
      row.insertAdjacentHTML('beforeend', `<td class="line-correction-cell"><button class="text-button correct-line-button" type="button">Correggi estrazione</button></td>`);
      $('.correct-line-button', row).addEventListener('click', () => openCorrection(row.dataset.lineId));
    });
  }

  function openCorrection(lineId) {
    const line = state.selectedDocument?.lines?.find(item => item.id === lineId);
    if (!line) return;
    $('#lineCorrectionId').value = line.id;
    $('#lineCorrectionSku').value = line.sku || '';
    $('#lineCorrectionDescription').value = line.description || '';
    $('#lineCorrectionQuantity').value = line.quantity ?? '';
    $('#lineCorrectionPrice').value = line.unit_price ?? '';
    $('#lineCorrectionDiscount').value = line.discount_rate ?? '';
    $('#lineCorrectionTotal').value = line.line_total ?? '';
    $('#lineCorrectionReason').value = '';
    $('#lineCorrectionDialog').showModal();
  }

  async function submitCorrection(event) {
    event.preventDefault();
    const number = selector => $(selector).value === '' ? null : Number($(selector).value);
    const lineId = $('#lineCorrectionId').value;
    const documentId = state.selectedDocument.id;
    try {
      await api(`/api/document-lines/${lineId}`, { method: 'PATCH', body: JSON.stringify({ sku: $('#lineCorrectionSku').value || null, description: $('#lineCorrectionDescription').value || null, quantity: number('#lineCorrectionQuantity'), unit_price: number('#lineCorrectionPrice'), discount_rate: number('#lineCorrectionDiscount'), line_total: number('#lineCorrectionTotal'), reason: $('#lineCorrectionReason').value.trim() }) });
      $('#lineCorrectionDialog').close();
      $('#documentDialog').close();
      toast('Correzione registrata e pratica ricalcolata.');
      await Promise.allSettled([loadDashboard(), loadCases(), loadChains(), loadDocuments()]);
      await openDocument(documentId, lineId);
    } catch (error) { toast(error.message, true); }
  }

  function wrapAsync(name, after) {
    const original = window[name];
    if (typeof original !== 'function' || original.__rc11Operational) return;
    const wrapped = async function (...args) { const result = await original.apply(this, args); await after(...args); return result; };
    wrapped.__rc11Operational = true;
    window[name] = wrapped;
  }

  function init() {
    wrapAsync('loadDashboard', renderOperationalDashboard);
    wrapAsync('loadCases', renderPracticeQueue);
    wrapAsync('openCase', enhanceCase);
    wrapAsync('openChain', enhanceChain);
    wrapAsync('openDocument', enhanceDocument);
    wrapAsync('openView', async view => { if (view === 'dashboard') await renderOperationalDashboard(); if (view === 'cases') await renderPracticeQueue(); });
    wrapAsync('submitDecision', async () => Promise.allSettled([renderOperationalDashboard(), renderPracticeQueue()]));
    ensureCorrectionDialog();
    renderOperationalDashboard();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, { once: true });
  else init();
})();

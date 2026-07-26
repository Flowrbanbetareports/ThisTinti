const state = {
  user: null,
  documents: [],
  cases: [],
  chains: [],
  users: [],
  validationDatasets: [],
  validationRuns: [],
  discoveryProfile: null,
  discoveryRules: [],
  jobs: [],
  jobsTotal: 0,
  jobsOffset: 0,
  jobsLimit: 25,
  jobsTimer: null,
  selectedCase: null,
  selectedDocument: null,
  selectedJob: null,
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
const money = (value) => new Intl.NumberFormat('it-IT', { style: 'currency', currency: 'EUR' }).format(Number(value || 0));
const moneyOrDash = (value) => value === null || value === undefined ? '—' : money(value);
const numberOrDash = (value) => value === null || value === undefined ? '—' : value;
const percentOrDash = (value) => value === null || value === undefined ? '—' : `${value}%`;
function messageFrom(value, fallback = 'Operazione non riuscita.') {
  if (value === null || value === undefined || value === '') return fallback;
  if (value instanceof Error) return messageFrom(value.message, fallback);
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') return String(value);
  if (Array.isArray(value)) {
    const messages = value.map(item => {
      if (item && typeof item === 'object') {
        const location = Array.isArray(item.loc)
          ? item.loc.filter(part => !['body', 'query', 'path'].includes(String(part))).join('.')
          : '';
        const detail = messageFrom(item.msg ?? item.message ?? item.detail ?? item.error, '');
        return [location, detail].filter(Boolean).join(': ');
      }
      return messageFrom(item, '');
    }).filter(Boolean);
    return messages.join(' · ') || fallback;
  }
  if (typeof value === 'object') {
    for (const key of ['detail', 'message', 'msg', 'error', 'errors', 'title']) {
      if (value[key] !== undefined && value[key] !== value) {
        const rendered = messageFrom(value[key], '');
        if (rendered) return rendered;
      }
    }
  }
  return fallback;
}

function dateTime(value) {
  if (!value) return '—';
  const raw = String(value).trim();
  const hasTimezone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(raw);
  const parsed = new Date(hasTimezone ? raw : `${raw}Z`);
  if (Number.isNaN(parsed.getTime())) return raw;
  return new Intl.DateTimeFormat('it-IT', { dateStyle: 'short', timeStyle: 'short' }).format(parsed);
}
const escapeHtml = (value) => String(value ?? '').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
const getCookie = (name) => document.cookie.split('; ').find(row => row.startsWith(`${name}=`))?.split('=').slice(1).join('=') || '';
const csrfHeaders = () => { const token = getCookie('thistinti_csrf'); return token ? { 'X-CSRF-Token': decodeURIComponent(token) } : {}; };

function toast(message, error = false) {
  const el = $('#toast');
  el.textContent = messageFrom(message);
  el.className = `toast visible${error ? ' error' : ''}`;
  clearTimeout(window.__toastTimer);
  window.__toastTimer = setTimeout(() => el.className = 'toast', 3200);
}

async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  const method = String(options.method || 'GET').toUpperCase();
  if (!['GET', 'HEAD', 'OPTIONS'].includes(method)) {
    const csrf = getCookie('thistinti_csrf');
    if (csrf) headers.set('X-CSRF-Token', decodeURIComponent(csrf));
  }
  if (!(options.body instanceof FormData) && options.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');
  const response = await fetch(path, { ...options, headers, credentials: 'same-origin' });
  if (response.status === 401) {
    clearSession(false);
    throw new Error('Sessione scaduta. Accedi nuovamente.');
  }
  const payload = response.headers.get('content-type')?.includes('application/json') ? await response.json() : await response.text();
  if (!response.ok) throw new Error(messageFrom(payload, `Errore ${response.status}`));
  return payload;
}

function switchAuth(mode) {
  const login = mode === 'login';
  $('#loginForm').classList.toggle('hidden', !login);
  $('#registerForm').classList.toggle('hidden', login);
  $('#loginTab').classList.toggle('active', login);
  $('#registerTab').classList.toggle('active', !login);
  $('#authView').classList.toggle('register-mode', !login);
}

async function authenticate(path, payload) {
  const result = await api(path, { method: 'POST', body: JSON.stringify(payload) });
  state.user = result.user;
  showApp();
  await refreshAll();
}

function clearSession(showMessage = true) {
  state.user = null;
  $('#appView').classList.add('hidden');
  $('#authView').classList.remove('hidden');
  if (showMessage) toast('Sessione chiusa.');
}

async function logout(showMessage = true) {
  try {
    await fetch('/api/auth/logout', {
      method: 'POST',
      credentials: 'same-origin',
      headers: csrfHeaders(),
    });
  } finally {
    clearSession(showMessage);
  }
}

function showApp() {
  $('#authView').classList.add('hidden');
  $('#appView').classList.remove('hidden');
  const org = state.user?.organization || 'Organizzazione';
  $('#tenantName').textContent = org;
  $('#tenantInitial').textContent = org.charAt(0).toUpperCase();
  $('#userEmail').textContent = state.user?.email || '';
  const role = state.user?.role || 'viewer';
  $$('[data-admin-only]').forEach(el => el.classList.toggle('hidden', role !== 'admin'));
  $$('[data-reviewer-only]').forEach(el => el.classList.toggle('hidden', !['admin','reviewer'].includes(role)));
  const currentView = document.querySelector('#mainNav button.active')?.dataset.view || 'dashboard';
  updateViewChrome(currentView);
}

const operationalViews = new Set(['dashboard', 'documents', 'chains', 'cases', 'jobs', 'discovery']);

function updateViewChrome(view) {
  const role = state.user?.role || 'viewer';
  const operational = operationalViews.has(view);
  const canReview = ['admin', 'reviewer'].includes(role);
  $('#exportButton')?.classList.toggle('hidden', role !== 'admin' || !operational);
  $('#demoButton')?.classList.toggle('hidden', !canReview || !operational);
  $('#openUploadButton')?.classList.toggle('hidden', !canReview || !operational);
  document.querySelector('.legal-warning')?.classList.toggle('hidden', !operational);
}

const viewMeta = {
  dashboard: ['Controllo documentale', 'Panoramica'],
  documents: ['Archivio', 'Documenti'],
  chains: ['Operazioni', 'Catene documentali'],
  cases: ['Revisione', 'Anomalie'],
  jobs: ['Elaborazione', 'Attività'],
  discovery: ['Adattamento', 'Autopilota'],
  validation: ['Qualità', 'Validation Lab'],
  audit: ['Governance', 'Audit log'],
  users: ['Accessi', 'Utenti e ruoli'],
};

async function openView(view) {
  updateViewChrome(view);
  $$('.view-panel').forEach(el => el.classList.add('hidden'));
  $(`#${view}View`).classList.remove('hidden');
  $$('#mainNav button').forEach(el => el.classList.toggle('active', el.dataset.view === view));
  $('#pageEyebrow').textContent = viewMeta[view][0];
  $('#pageTitle').textContent = viewMeta[view][1];
  if (view === 'documents') await loadDocuments();
  if (view === 'chains') await loadChains();
  if (view === 'cases') await loadCases();
  if (view === 'jobs') await loadJobs();
  if (view === 'discovery') await loadDiscovery();
  if (view === 'validation') await loadValidation();
  if (view === 'audit') await loadAudit();
  if (view === 'users') await loadUsers();
}

async function refreshAll() {
  await Promise.all([loadDashboard(), loadDocuments(), loadChains(), loadCases()]);
}

async function loadDashboard() {
  const data = await api('/api/dashboard');
  $('#metricDocuments').textContent = data.documents;
  $('#metricCases').textContent = data.cases_open;
  $('#metricChains').textContent = data.chains;
  $('#metricAmount').textContent = money(data.amount_potential);
  $('#parserDot').className = `status-dot ${data.parsing_failures ? 'warn' : 'ok'}`;
  $('#parserStatus').textContent = data.parsing_failures ? `${data.parsing_failures} file richiedono intervento` : 'Nessun errore rilevato';
  const cases = await api('/api/cases');
  state.cases = cases;
  const activeCases = cases.filter(c => ['open','needs_review','confirmed'].includes(c.status));
  $('#metricCriticalCases').textContent = activeCases.filter(c => c.severity === 'critical').length;
  renderPriorityCases(activeCases.slice(0, 5));
}

function renderPriorityCases(cases) {
  const target = $('#priorityCases');
  if (!cases.length) { target.className = 'list-stack empty-state'; target.textContent = 'Nessuna anomalia disponibile.'; return; }
  target.className = 'list-stack';
  target.innerHTML = cases.map(c => `<div class="case-item" data-case-id="${c.id}"><span class="severity-icon ${c.severity}">${severitySymbol(c.severity)}</span><div><strong>${escapeHtml(c.title)}</strong><small>${escapeHtml(c.explanation)}</small></div><span class="case-amount">${money(c.amount_estimate)}</span></div>`).join('');
  target.querySelectorAll('[data-case-id]').forEach(el => el.addEventListener('click', () => openCase(el.dataset.caseId)));
}

async function loadDocuments() {
  const type = $('#documentTypeFilter')?.value || '';
  const status = $('#documentStatusFilter')?.value || '';
  const qs = new URLSearchParams();
  if (type) qs.set('document_type', type);
  if (status) qs.set('parse_status', status);
  state.documents = await api(`/api/documents?${qs}`);
  const body = $('#documentsTable');
  if (!state.documents.length) { body.innerHTML = `<tr><td colspan="6" class="empty-state">Nessun documento.</td></tr>`; return; }
  body.innerHTML = state.documents.map(d => `<tr data-document-id="${d.id}"><td><strong>${escapeHtml(d.number || d.source_filename)}</strong><small>${escapeHtml(d.source_filename)}</small></td><td>${escapeHtml(d.supplier || '—')}</td><td>${labelType(d.document_type)}</td><td>${d.line_count}</td><td>${Math.round(d.confidence * 100)}%</td><td><span class="badge ${d.parse_status}">${labelStatus(d.parse_status)}</span></td></tr>`).join('');
  body.querySelectorAll('[data-document-id]').forEach(row => row.addEventListener('click', () => openDocument(row.dataset.documentId)));
}

async function loadChains() {
  state.chains = await api('/api/chains');
  const body = $('#chainsTable');
  if (!state.chains.length) { body.innerHTML = `<tr><td colspan="9" class="empty-state">Nessuna catena.</td></tr>`; return; }
  body.innerHTML = state.chains.map(c => `<tr data-chain-id="${c.id}"><td><strong>${escapeHtml(c.reference_key || c.id.slice(0,8))}</strong><small>${Math.round(c.confidence * 100)}% confidenza</small></td><td>${markList(c.documents.proposal)}</td><td>${markList(c.documents.order)}</td><td>${markList(c.documents.delivery)}</td><td>${markList(c.documents.invoice)}</td><td>${markList(c.documents.payment)}</td><td>${markList(c.documents.return)}</td><td>${markList(c.documents.credit_note)}</td><td><span class="badge ${c.status}">${labelStatus(c.status)}</span></td></tr>`).join('');
  body.querySelectorAll('[data-chain-id]').forEach(row => row.addEventListener('click', () => openChain(row.dataset.chainId)));
}


function comparisonCell(value) {
  if (!value) return '<span class="muted-dash">—</span>';
  return `<strong>${numberOrDash(value.quantity)}</strong><small>${moneyOrDash(value.unit_price)} · sconto ${percentOrDash(value.discount_rate)}</small>`;
}

function linkReasonLabel(value) {
  return ({
    manual: 'Collegamento confermato manualmente',
    explicit_reference: 'Riferimento esplicito',
    line_overlap: 'Righe compatibili',
    same_supplier: 'Stesso fornitore',
    available: 'Documento disponibile',
    new_chain: 'Catena creata dal documento',
  })[value] || 'Motivo non specificato';
}

function renderChainLinkManagement(options, canReview) {
  const linked = options.linked || [];
  const candidates = options.candidates || [];
  const linkedHtml = linked.length
    ? linked.map(item => `<div class="link-document-row" data-linked-document-id="${item.document_id}"><div><span class="badge parsed">${labelType(item.role)}</span><strong>${escapeHtml(item.number || item.source_filename)}</strong><small>${escapeHtml(item.source_filename)} · ${Math.round(Number(item.match_confidence || 0) * 100)}% · ${escapeHtml(linkReasonLabel(item.match_reason))}</small></div><div class="row-actions"><button class="secondary-button open-linked-document" type="button" data-document-id="${item.document_id}">Apri</button>${canReview ? `<button class="secondary-button detach-linked-document" type="button" data-document-id="${item.document_id}">Scollega</button>` : ''}</div></div>`).join('')
    : '<div class="empty-state">Nessun documento collegato.</div>';
  const candidateHtml = candidates.length
    ? candidates.map(item => `<div class="link-document-row candidate" data-candidate-document-id="${item.document_id}"><div><span class="badge ${item.confidence >= .8 ? 'parsed' : item.confidence >= .5 ? 'medium' : 'open'}">${Math.round(Number(item.confidence || 0) * 100)}%</span><strong>${escapeHtml(item.number || item.source_filename)}</strong><small>${labelType(item.role)} · ${escapeHtml(item.supplier || 'Fornitore non indicato')} · ${escapeHtml(linkReasonLabel(item.reason))}</small></div><div class="row-actions"><button class="secondary-button open-candidate-document" type="button" data-document-id="${item.document_id}">Apri</button>${canReview ? `<button class="primary-button attach-candidate-document" type="button" data-document-id="${item.document_id}" data-role="${item.role}">Collega</button>` : ''}</div></div>`).join('')
    : '<div class="empty-state">Nessun documento non collegato compatibile.</div>';
  return `<section class="detail-section chain-link-section"><div class="panel-heading"><div><h3>Documenti collegati</h3><p>Ogni collegamento mostra origine e affidabilità. Puoi verificarlo sull’originale prima di modificarlo.</p></div></div><div class="link-document-list">${linkedHtml}</div><details class="candidate-links"><summary>Collegamenti proposti (${candidates.length})</summary><p class="section-helper">Sono suggerimenti ordinati per compatibilità, non decisioni automatiche.</p><div class="link-document-list">${candidateHtml}</div></details></section>`;
}

async function openChain(id) {
  try {
    const [chain, linkOptions] = await Promise.all([
      api(`/api/chains/${id}`),
      api(`/api/chains/${id}/link-options`),
    ]);
    const comparison = chain.comparison;
    $('#chainDialogTitle').textContent = chain.reference_key || chain.id.slice(0, 8);
    const rows = comparison.rows || [];
    const intelligence = chain.intelligence || {};
    const risk = intelligence.risk || { score: 0, decision: 'review', amount_at_risk: 0, reasons: [] };
    const expectations = intelligence.expectations || [];
    const pending = expectations.filter(item => item.status !== 'satisfied');
    const expectationHtml = pending.length
      ? pending.map(item => `<div class="case-item"><span class="severity-icon ${item.status === 'missing_proof' ? 'high' : 'medium'}">${item.status === 'missing_proof' ? '!' : '·'}</span><div><strong>${escapeHtml(item.label)}</strong><small>${escapeHtml(item.rationale)}</small></div><span class="badge ${item.status === 'missing_proof' ? 'high' : 'medium'}">${escapeHtml(item.status)}</span></div>`).join('')
      : '<div class="empty-state">Nessun documento fondamentale mancante.</div>';
    const canReview = ['admin', 'reviewer'].includes(state.user?.role);
    const actionButtons = canReview ? `<div class="modal-actions intelligence-actions"><button id="simulateChainButton" class="secondary-button" type="button">Stima rischio della catena</button><button id="redTeamChainButton" class="secondary-button" type="button">Prova a ingannare ThisTinti</button></div>` : '';
    $('#chainDialogBody').innerHTML = `<div class="detail-grid"><div class="detail-card"><p>Stato</p><strong>${labelStatus(chain.status)}</strong></div><div class="detail-card"><p>Stima euristica del rischio</p><strong id="chainRiskValue">${risk.score}/100 · ${escapeHtml(risk.decision)}</strong><small id="chainRiskAmount">${money(risk.amount_at_risk)} potenzialmente coinvolti</small></div><div class="detail-card"><p>Controllo incrociato</p><strong>${escapeHtml(intelligence.triangulation?.status || '—')}</strong><small>estrazione · calcoli · grafo</small></div><div class="detail-card"><p>Somiglianza al processo osservato</p><strong>${Math.round((intelligence.process_conformance?.score || 0) * 100)}%</strong><small>${escapeHtml(intelligence.process_conformance?.baseline_source || 'baseline prudenziale')}</small></div></div>${actionButtons}<div id="chainIntelligenceResult" aria-live="polite"></div>${renderChainLinkManagement(linkOptions, canReview)}<section class="detail-section"><div class="panel-heading"><div><h3>Documenti attesi</h3><p>Cosa manca o dovrebbe accadere dopo.</p></div></div><div class="list-stack">${expectationHtml}</div></section><div class="lines-table comparison-table"><table><thead><tr><th>Articolo</th><th>Riferimento commerciale</th><th>Consegna</th><th>Fattura</th><th>Reso</th><th>Nota credito</th><th>Esito</th></tr></thead><tbody>${rows.length ? rows.map(row => `<tr><td><strong>${escapeHtml(row.sku || row.description || row.key)}</strong><small>${escapeHtml([row.description,row.color,row.size,row.lot].filter(Boolean).join(' · '))}</small></td><td>${comparisonCell(row.values.confirmation || row.values.order || row.values.proposal)}</td><td>${comparisonCell(row.values.delivery)}</td><td>${comparisonCell(row.values.invoice)}</td><td>${comparisonCell(row.values.return)}</td><td>${comparisonCell(row.values.credit_note)}</td><td><span class="badge ${row.status === 'ok' ? 'parsed' : row.status === 'issue' ? 'high' : 'medium'}">${row.status === 'ok' ? 'Coerente' : escapeHtml(row.reasons.join(', ') || 'Da verificare')}</span></td></tr>`).join('') : '<tr><td colspan="7" class="empty-state">Nessuna riga confrontabile.</td></tr>'}</tbody></table></div>`;
    $('#simulateChainButton')?.addEventListener('click', async () => {
      try {
        const result = await api(`/api/chains/${id}/simulate`, { method: 'POST', body: JSON.stringify({ action: 'approve_invoice' }) });
        $('#chainRiskValue').textContent = `${result.score}/100 · ${result.decision}`;
        $('#chainRiskAmount').textContent = `${money(result.amount_at_risk)} potenzialmente coinvolti`;
        $('#chainIntelligenceResult').innerHTML = `<div class="intelligence-callout"><strong>Simulazione: ${escapeHtml(result.decision)}</strong><p>${escapeHtml(result.reasons.slice(0, 3).join(' · ') || 'Nessun rischio rilevante.')}</p><small>Indicazione automatica: verificare i documenti originali prima di qualsiasi decisione economica.</small></div>`;
      } catch (error) { toast(error.message, true); }
    });
    $('#redTeamChainButton')?.addEventListener('click', async () => {
      try {
        const result = await api(`/api/chains/${id}/red-team`, { method: 'POST' });
        $('#chainIntelligenceResult').innerHTML = `<div class="intelligence-callout"><strong>Test sintetico degli errori: ${Math.round(result.coverage * 100)}%</strong><p>${result.detected}/${result.applicable || result.total} scenari applicabili intercettati; ${result.total} famiglie disponibili. Stato: ${escapeHtml(result.status)}.</p></div>`;
      } catch (error) { toast(error.message, true); }
    });
    $$('.open-linked-document, .open-candidate-document').forEach(button => button.addEventListener('click', () => {
      $('#chainDialog').close();
      openDocument(button.dataset.documentId);
    }));
    $$('.attach-candidate-document').forEach(button => button.addEventListener('click', async () => {
      button.disabled = true;
      try {
        await api(`/api/chains/${id}/attach`, { method: 'POST', body: JSON.stringify({ document_id: button.dataset.documentId, role: button.dataset.role }) });
        toast('Documento collegato. La catena è stata rianalizzata.');
        await Promise.allSettled([loadChains(), loadDashboard()]);
        await openChain(id);
      } catch (error) { toast(error.message, true); } finally { button.disabled = false; }
    }));
    $$('.detach-linked-document').forEach(button => button.addEventListener('click', async () => {
      if (!window.confirm('Scollegare questo documento dalla catena? Le segnalazioni verranno ricalcolate.')) return;
      button.disabled = true;
      try {
        await api(`/api/chains/${id}/documents/${button.dataset.documentId}`, { method: 'DELETE' });
        toast('Documento scollegato. La catena è stata rianalizzata.');
        await Promise.allSettled([loadChains(), loadDashboard()]);
        await openChain(id);
      } catch (error) { toast(error.message, true); } finally { button.disabled = false; }
    }));
    if (!$('#chainDialog').open) $('#chainDialog').showModal();
  } catch (error) { toast(error.message, true); }
}

async function loadCases() {
  const status = $('#caseStatusFilter')?.value || '';
  const severity = $('#caseSeverityFilter')?.value || '';
  const qs = new URLSearchParams();
  if (status) qs.set('status', status);
  if (severity) qs.set('severity', severity);
  state.cases = await api(`/api/cases?${qs}`);
  const body = $('#casesTable');
  if (!state.cases.length) { body.innerHTML = `<tr><td colspan="5" class="empty-state">Nessuna anomalia.</td></tr>`; return; }
  body.innerHTML = state.cases.map(c => `<tr data-case-id="${c.id}"><td><strong>${escapeHtml(c.title)}</strong><small>${escapeHtml(c.case_type)}</small></td><td><span class="badge ${c.severity}">${labelSeverity(c.severity)}</span></td><td>${money(c.amount_estimate)}</td><td>${Math.round(c.confidence * 100)}%</td><td><span class="badge ${c.status}">${labelStatus(c.status)}</span></td></tr>`).join('');
  body.querySelectorAll('[data-case-id]').forEach(row => row.addEventListener('click', () => openCase(row.dataset.caseId)));
}

function jobTypeLabel(value) {
  return ({
    ingest_document: 'Caricamento documento',
    ingest_batch: 'Caricamento archivio',
    reprocess_document: 'Rielaborazione documento',
    reanalyze_tenant: 'Rianalisi collegamenti',
    red_team_tenant: 'Verifica capacità',
  })[value] || value || 'Attività';
}

function jobObjectLabel(job) {
  if (job.context?.filename) return job.context.filename;
  if (job.context?.document_id) return `Documento ${job.context.document_id.slice(0, 8)}`;
  if (job.context?.retry_of) return `Nuovo tentativo di ${job.context.retry_of.slice(0, 8)}`;
  return job.id.slice(0, 8);
}

function jobStatusLabel(value) {
  return ({ queued: 'In attesa', running: 'In corso', completed: 'Completata', failed: 'Fallita', cancelled: 'Annullata' })[value] || value;
}

function renderJobActions(job) {
  const canReview = ['admin', 'reviewer'].includes(state.user?.role);
  const actions = [`<button class="secondary-button compact job-detail-button" data-job-id="${escapeHtml(job.id)}" type="button">Dettagli</button>`];
  if (job.context?.document_id) actions.push(`<button class="secondary-button compact job-document-button" data-document-id="${escapeHtml(job.context.document_id)}" type="button">Documento</button>`);
  if (canReview && job.can_retry) actions.push(`<button class="primary-button compact job-retry-button" data-job-id="${escapeHtml(job.id)}" type="button">Riprova</button>`);
  if (canReview && job.can_cancel) actions.push(`<button class="secondary-button compact job-cancel-button" data-job-id="${escapeHtml(job.id)}" type="button">Annulla</button>`);
  return `<div class="job-actions">${actions.join('')}</div>`;
}

async function loadJobs(resetOffset = false) {
  if (resetOffset) state.jobsOffset = 0;
  clearTimeout(state.jobsTimer);
  const qs = new URLSearchParams({ limit: String(state.jobsLimit), offset: String(state.jobsOffset) });
  const status = $('#jobStatusFilter')?.value || '';
  const type = $('#jobTypeFilter')?.value || '';
  const query = $('#jobSearchInput')?.value.trim() || '';
  if (status) qs.set('status', status);
  if (type) qs.set('job_type', type);
  if (query) qs.set('query', query);
  const data = await api(`/api/jobs?${qs}`);
  state.jobs = data.items;
  state.jobsTotal = data.total;
  $('#jobsQueued').textContent = data.status_counts.queued || 0;
  $('#jobsRunning').textContent = data.status_counts.running || 0;
  $('#jobsFailed').textContent = data.status_counts.failed || 0;
  $('#jobsCompleted').textContent = data.status_counts.completed || 0;
  const body = $('#jobsTable');
  if (!state.jobs.length) {
    body.innerHTML = '<tr><td colspan="8" class="empty-state">Nessuna attività corrisponde ai filtri.</td></tr>';
  } else {
    body.innerHTML = state.jobs.map(job => `<tr data-job-row="${escapeHtml(job.id)}"><td>${dateTime(job.created_at)}</td><td><strong>${escapeHtml(jobTypeLabel(job.job_type))}</strong><small>${escapeHtml(job.id.slice(0, 8))}</small></td><td>${escapeHtml(jobObjectLabel(job))}</td><td><span class="badge ${escapeHtml(job.status)}">${escapeHtml(jobStatusLabel(job.status))}</span></td><td>${job.attempts}/${job.max_attempts}</td><td><div class="job-progress" aria-label="Avanzamento ${Number(job.progress || 0)} percento"><span style="width:${Math.max(0, Math.min(100, Number(job.progress || 0)))}%"></span></div><small>${Number(job.progress || 0)}%</small></td><td class="job-error-cell">${job.error_message ? escapeHtml(job.error_message) : '<span class="muted-dash">—</span>'}</td><td>${renderJobActions(job)}</td></tr>`).join('');
    body.querySelectorAll('.job-detail-button').forEach(button => button.addEventListener('click', () => openJob(button.dataset.jobId)));
    body.querySelectorAll('.job-document-button').forEach(button => button.addEventListener('click', () => openDocument(button.dataset.documentId)));
    body.querySelectorAll('.job-retry-button').forEach(button => button.addEventListener('click', () => retryJob(button.dataset.jobId, button)));
    body.querySelectorAll('.job-cancel-button').forEach(button => button.addEventListener('click', () => cancelJob(button.dataset.jobId, button)));
  }
  const first = state.jobsTotal ? state.jobsOffset + 1 : 0;
  const last = Math.min(state.jobsOffset + state.jobsLimit, state.jobsTotal);
  $('#jobsPageText').textContent = `${first}–${last} di ${state.jobsTotal} attività`;
  $('#jobsPreviousButton').disabled = state.jobsOffset <= 0;
  $('#jobsNextButton').disabled = state.jobsOffset + state.jobsLimit >= state.jobsTotal;
  if (state.jobs.some(job => ['queued', 'running'].includes(job.status)) && !$('#jobsView').classList.contains('hidden')) {
    state.jobsTimer = window.setTimeout(() => loadJobs(false).catch(error => toast(error.message, true)), 3000);
  }
}

async function openJob(id) {
  try {
    const job = await api(`/api/jobs/${id}`);
    state.selectedJob = job;
    $('#jobDialogTitle').textContent = `${jobTypeLabel(job.job_type)} · ${job.id.slice(0, 8)}`;
    const result = job.result && Object.keys(job.result).length ? `<pre class="job-result">${escapeHtml(JSON.stringify(job.result, null, 2))}</pre>` : '<p class="empty-state">Nessun risultato disponibile.</p>';
    $('#jobDialogBody').innerHTML = `<div class="detail-grid"><div class="detail-card"><p>Stato</p><strong><span class="badge ${escapeHtml(job.status)}">${escapeHtml(jobStatusLabel(job.status))}</span></strong></div><div class="detail-card"><p>Tentativi</p><strong>${job.attempts}/${job.max_attempts}</strong></div><div class="detail-card"><p>Avanzamento</p><strong>${Number(job.progress || 0)}%</strong></div></div>${job.error_message ? `<div class="persistent-error" role="alert"><strong>Errore registrato</strong><p>${escapeHtml(job.error_message)}</p></div>` : ''}<div class="detail-grid detail-spaced"><div class="detail-card"><p>Creata</p><strong>${dateTime(job.created_at)}</strong></div><div class="detail-card"><p>Avviata</p><strong>${dateTime(job.started_at)}</strong></div><div class="detail-card"><p>Completata</p><strong>${dateTime(job.completed_at)}</strong></div></div><section class="detail-section"><h4>Risultato tecnico</h4>${result}</section><div class="modal-actions">${renderJobActions(job)}</div>`;
    $('#jobDialogBody').querySelectorAll('.job-document-button').forEach(button => button.addEventListener('click', () => openDocument(button.dataset.documentId)));
    $('#jobDialogBody').querySelectorAll('.job-retry-button').forEach(button => button.addEventListener('click', () => retryJob(button.dataset.jobId, button)));
    $('#jobDialogBody').querySelectorAll('.job-cancel-button').forEach(button => button.addEventListener('click', () => cancelJob(button.dataset.jobId, button)));
    $('#jobDialogBody').querySelectorAll('.job-detail-button').forEach(button => button.remove());
    $('#jobDialog').showModal();
  } catch (error) { toast(error.message, true); }
}

async function retryJob(id, button) {
  if (button) button.disabled = true;
  try {
    const result = await api(`/api/jobs/${id}/retry`, { method: 'POST' });
    $('#jobDialog')?.close();
    toast(`Nuovo tentativo creato: ${result.job.id.slice(0, 8)}.`);
    await loadJobs(false);
  } catch (error) { toast(error.message, true); }
  finally { if (button) button.disabled = false; }
}

async function cancelJob(id, button) {
  if (button) button.disabled = true;
  try {
    await api(`/api/jobs/${id}`, { method: 'DELETE' });
    $('#jobDialog')?.close();
    toast('Attività annullata.');
    await loadJobs(false);
  } catch (error) { toast(error.message, true); }
  finally { if (button) button.disabled = false; }
}

function openReprocessDialog(document) {
  state.selectedDocument = document;
  $('#reprocessDocumentId').value = document.id;
  $('#reprocessDocumentType').value = document.document_type;
  $('#reprocessNumber').value = document.number || '';
  $('#reprocessSupplier').value = document.supplier || '';
  $('#reprocessDate').value = document.document_date || '';
  $('#reprocessMessage').textContent = document.parse_message
    ? `Errore corrente: ${document.parse_message}`
    : 'La rielaborazione usa il file originale e conserva l’ultima estrazione valida se il nuovo tentativo fallisce.';
  $('#reprocessDialog').showModal();
}

async function submitReprocess(event) {
  event.preventDefault();
  const button = $('#reprocessSubmitButton');
  button.disabled = true;
  try {
    const documentId = $('#reprocessDocumentId').value;
    const payload = {
      document_type: $('#reprocessDocumentType').value || null,
      number: $('#reprocessNumber').value.trim() || null,
      supplier_name: $('#reprocessSupplier').value.trim() || null,
      document_date: $('#reprocessDate').value || null,
    };
    const result = await api(`/api/jobs/documents/${documentId}/reprocess`, {
      method: 'POST',
      headers: { 'Idempotency-Key': window.crypto?.randomUUID?.() || `reprocess-${Date.now()}` },
      body: JSON.stringify(payload),
    });
    $('#reprocessDialog').close();
    $('#documentDialog').close();
    toast(`Rielaborazione in coda: ${result.job.id.slice(0, 8)}.`);
    await openView('jobs');
  } catch (error) { toast(error.message, true); }
  finally { button.disabled = false; }
}

async function loadAudit() {
  const events = await api('/api/audit');
  const body = $('#auditTable');
  if (!events.length) { body.innerHTML = `<tr><td colspan="4" class="empty-state">Nessun evento.</td></tr>`; return; }
  body.innerHTML = events.map(e => `<tr><td>${dateTime(e.created_at)}</td><td><strong>${escapeHtml(e.action)}</strong></td><td>${escapeHtml(e.entity_type || '—')}</td><td><code>${escapeHtml(JSON.stringify(e.payload))}</code></td></tr>`).join('');
}

async function loadUsers() {
  state.users = await api('/api/users');
  const body = $('#usersTable');
  if (!state.users.length) { body.innerHTML = `<tr><td colspan="5" class="empty-state">Nessun utente.</td></tr>`; return; }
  body.innerHTML = state.users.map(u => `<tr><td><strong>${escapeHtml(u.email)}</strong>${u.id === state.user?.id ? '<small>Account corrente</small>' : ''}</td><td>${u.id === state.user?.id ? labelRole(u.role) : `<select class="compact-select user-role-select" data-user-id="${u.id}" aria-label="Ruolo di ${escapeHtml(u.email)}"><option value="viewer" ${u.role === 'viewer' ? 'selected' : ''}>Sola lettura</option><option value="reviewer" ${u.role === 'reviewer' ? 'selected' : ''}>Revisore</option><option value="admin" ${u.role === 'admin' ? 'selected' : ''}>Amministratore</option></select>`}</td><td><span class="badge ${u.active ? 'parsed' : 'dismissed'}">${u.active ? 'Attivo' : 'Disattivato'}</span></td><td>${dateTime(u.created_at)}</td><td>${u.id === state.user?.id ? '' : `<button class="secondary-button user-status-button" data-user-id="${u.id}" data-active="${u.active}">${u.active ? 'Disattiva' : 'Riattiva'}</button>`}</td></tr>`).join('');
  body.querySelectorAll('.user-status-button').forEach(btn => btn.addEventListener('click', () => toggleUser(btn.dataset.userId, btn.dataset.active === 'true')));
  body.querySelectorAll('.user-role-select').forEach(select => select.addEventListener('change', () => updateUserRole(select.dataset.userId, select.value)));
}

async function createUser(event) {
  event.preventDefault();
  try {
    await api('/api/users', { method: 'POST', body: JSON.stringify({ email: $('#userEmailInput').value, password: $('#userPasswordInput').value, role: $('#userRoleInput').value }) });
    $('#userDialog').close();
    event.currentTarget.reset();
    toast('Utente creato.');
    await loadUsers();
  } catch (error) { toast(error.message, true); }
}

async function toggleUser(id, active) {
  try {
    await api(`/api/users/${id}/status`, { method: 'PATCH', body: JSON.stringify({ active: !active }) });
    toast(active ? 'Utente disattivato.' : 'Utente riattivato.');
    await loadUsers();
  } catch (error) { toast(error.message, true); }
}

async function updateUserRole(id, role) {
  try {
    await api(`/api/users/${id}/role`, { method: 'PATCH', body: JSON.stringify({ role }) });
    toast('Ruolo aggiornato.');
    await loadUsers();
  } catch (error) {
    toast(error.message, true);
    await loadUsers();
  }
}


async function loadDiscovery() {
  const [profilePayload, rules] = await Promise.all([
    api('/api/discovery/profile'),
    api('/api/discovery/rules'),
  ]);
  state.discoveryProfile = profilePayload;
  state.discoveryRules = rules;
  const profile = profilePayload.profile;
  $('#discoveryActivity').textContent = profile.activity_label || 'Dati insufficienti';
  $('#discoveryActivityNote').textContent = `${profile.document_count || 0} documenti · ${profile.line_count || 0} righe · ${labelDiscoveryStatus(profile.status)}`;
  $('#confirmActivityButton').classList.toggle('hidden', profile.status !== 'needs_confirmation');
  $('#discoveryConfidence').textContent = percentMetric(profile.confidence);
  $('#discoveryActiveRules').textContent = profilePayload.summary.active_rules || 0;
  $('#discoveryQuestions').textContent = profilePayload.summary.questions || 0;
  renderDiscoveryFields(profile.field_profile || {});
  renderDiscoveryRules();
}

function labelDiscoveryStatus(value) {
  return ({ learning: 'sta ancora imparando', ready: 'profilo pronto', needs_confirmation: 'profilo da confermare' })[value] || value || 'in apprendimento';
}

function renderDiscoveryFields(fieldProfile) {
  const target = $('#discoveryFields');
  const coverage = Object.entries(fieldProfile.coverage || {}).sort((a, b) => b[1] - a[1]).slice(0, 12);
  if (!coverage.length) {
    target.innerHTML = '<p class="empty-state">Carica almeno alcuni documenti per permettere a ThisTinti di capire il flusso.</p>';
    return;
  }
  target.innerHTML = coverage.map(([field, value]) => `<div class="detail-card"><p>${escapeHtml(field)}</p><strong>${percentMetric(value)}</strong><small>presenza nelle righe osservate</small></div>`).join('');
}

function renderDiscoveryRules() {
  const body = $('#discoveryRulesTable');
  if (!state.discoveryRules.length) {
    body.innerHTML = '<tr><td colspan="5" class="empty-state">Nessuna regola proposta. Carica documenti o avvia una nuova analisi.</td></tr>';
    return;
  }
  const canDecide = ['admin', 'reviewer'].includes(state.user?.role);
  body.innerHTML = state.discoveryRules.map(rule => {
    const uncertain = rule.status === 'needs_confirmation';
    const actions = canDecide && uncertain
      ? `<div class="decision-row"><button class="secondary-button discovery-rule-decision" data-rule-id="${rule.id}" data-rule-decision="rejected" type="button">No</button><button class="primary-button compact discovery-rule-decision" data-rule-id="${rule.id}" data-rule-decision="confirmed" type="button">Sì</button></div>`
      : canDecide && ['auto_active', 'confirmed'].includes(rule.status)
        ? `<button class="ghost-button discovery-rule-decision" data-rule-id="${rule.id}" data-rule-decision="inactive" type="button">Disattiva</button>`
        : '';
    return `<tr><td><strong>${escapeHtml(rule.title)}</strong><small>${escapeHtml(rule.description)}</small></td><td>${escapeHtml(rule.rationale)}</td><td>${percentMetric(rule.confidence)}</td><td><span class="badge ${rule.status === 'needs_confirmation' ? 'medium' : ['auto_active','confirmed'].includes(rule.status) ? 'parsed' : 'dismissed'}">${labelRuleStatus(rule.status)}</span></td><td>${actions}</td></tr>`;
  }).join('');
  body.querySelectorAll('.discovery-rule-decision').forEach(button => button.addEventListener('click', () => decideDiscoveryRule(button.dataset.ruleId, button.dataset.ruleDecision)));
}

function labelRuleStatus(value) {
  return ({ auto_active: 'Automatica', needs_confirmation: 'Da confermare', confirmed: 'Confermata', rejected: 'Rifiutata', inactive: 'Disattivata' })[value] || value;
}

async function runDiscovery() {
  const button = $('#runDiscoveryButton');
  button.disabled = true;
  const original = button.textContent;
  button.textContent = 'Analisi…';
  try {
    const result = await api('/api/discovery/run', {
      method: 'POST',
      body: JSON.stringify({ minimum_documents: 3, auto_activate_threshold: 0.92, confirmation_threshold: 0.68 }),
    });
    toast(`Attività analizzata: ${result.run.auto_activated_rules} regole automatiche, ${result.run.uncertain_rules} da confermare.`);
    await Promise.all([loadDiscovery(), loadCases(), loadDashboard()]);
  } catch (error) { toast(error.message, true); }
  finally { button.disabled = false; button.textContent = original; }
}

async function decideActivityProfile(decision) {
  const payload = { decision };
  if (decision === 'corrected') {
    const label = window.prompt("Descrivi in poche parole l'attività corretta:", state.discoveryProfile?.profile?.activity_label || '');
    if (!label) return;
    payload.activity_label = label.trim();
    payload.activity_type = label.trim().toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '').slice(0, 120) || 'custom_activity';
  }
  try {
    await api('/api/discovery/profile/decision', { method: 'POST', body: JSON.stringify(payload) });
    toast(decision === 'confirmed' ? 'Attività confermata.' : 'Profilo attività corretto.');
    await loadDiscovery();
  } catch (error) { toast(error.message, true); }
}

async function decideDiscoveryRule(ruleId, decision) {
  try {
    await api(`/api/discovery/rules/${ruleId}/decision`, {
      method: 'POST',
      body: JSON.stringify({ decision, note: null }),
    });
    toast(decision === 'confirmed' ? 'Regola confermata.' : decision === 'rejected' ? 'Regola rifiutata.' : 'Regola disattivata.');
    await Promise.all([loadDiscovery(), loadCases(), loadDashboard()]);
  } catch (error) { toast(error.message, true); }
}

async function loadValidation() {
  const [datasets, runs] = await Promise.all([
    api('/api/validation/datasets'),
    api('/api/validation/runs?limit=50'),
  ]);
  state.validationDatasets = datasets;
  state.validationRuns = runs;
  renderValidationSummary(runs[0] || null);
  renderValidationDatasets();
  renderValidationRuns();
}

function percentMetric(value) {
  return Number.isFinite(Number(value)) ? `${(Number(value) * 100).toFixed(1)}%` : '—';
}

function renderValidationSummary(run) {
  $('#validationPrecision').textContent = run ? percentMetric(run.precision) : '—';
  $('#validationRecall').textContent = run ? percentMetric(run.recall) : '—';
  $('#validationF1').textContent = run ? percentMetric(run.f1_score) : '—';
  $('#validationGate').textContent = run ? (run.gate_passed ? 'PASS' : 'STOP') : '—';
  $('#validationGate').className = run ? (run.gate_passed ? 'validation-pass' : 'validation-stop') : '';
  $('#validationGateNote').textContent = run ? `${run.false_positives} FP · ${run.false_negatives} FN · MAE ${money(run.amount_mae)}` : 'nessuna esecuzione';
}

function validationEvidenceLabel(value) {
  return value === 'production' ? 'Produzione' : value === 'anonymized_pilot' ? 'Pilot anonimizzato' : 'Sintetica';
}

function renderValidationDatasets() {
  const body = $('#validationDatasetsTable');
  if (!state.validationDatasets.length) {
    body.innerHTML = `<tr><td colspan="7" class="empty-state">Nessuna suite. Un amministratore può caricare la suite base.</td></tr>`;
    return;
  }
  const canRun = ['admin','reviewer'].includes(state.user?.role);
  const isAdmin = state.user?.role === 'admin';
  body.innerHTML = state.validationDatasets.map(dataset => {
    const actions = [];
    if (canRun && dataset.status === 'active') actions.push(`<button class="primary-button compact validation-run-button" data-dataset-id="${dataset.id}" type="button">Esegui</button>`);
    if (isAdmin && dataset.status === 'active' && dataset.evidence_level !== 'synthetic') {
      actions.push(`<button class="secondary-button compact validation-automation-button" data-dataset-id="${dataset.id}" data-enabled="${dataset.automation_eligible ? 'false' : 'true'}" type="button">${dataset.automation_eligible ? 'Revoca' : 'Approva'}</button>`);
    }
    return `<tr data-validation-dataset-id="${dataset.id}"><td><strong>${escapeHtml(dataset.name)}</strong><small>${escapeHtml(dataset.description || '')}</small></td><td>${escapeHtml(dataset.version)}</td><td>${escapeHtml(validationEvidenceLabel(dataset.evidence_level))}</td><td><span class="badge ${dataset.status === 'active' ? 'parsed' : 'dismissed'}">${dataset.status === 'active' ? 'Attiva' : 'Archiviata'}</span></td><td><span class="badge ${dataset.automation_eligible ? 'parsed' : 'dismissed'}">${dataset.automation_eligible ? 'Approvata' : 'Disattiva'}</span></td><td>${dataset.run_count || 0}</td><td><div class="filter-row">${actions.join('')}</div></td></tr>`;
  }).join('');
  body.querySelectorAll('.validation-run-button').forEach(button => button.addEventListener('click', () => executeValidationDataset(button.dataset.datasetId, button)));
  body.querySelectorAll('.validation-automation-button').forEach(button => button.addEventListener('click', () => openValidationAutomationDialog(button.dataset.datasetId, button.dataset.enabled === 'true')));
}

function openValidationAutomationDialog(datasetId, enabled) {
  $('#validationAutomationDatasetId').value = datasetId;
  $('#validationAutomationEnabled').value = enabled ? 'true' : 'false';
  $('#validationAutomationTitle').textContent = enabled ? 'Approva automazione supervisionata' : 'Revoca approvazione';
  $('#validationAutomationExplanation').textContent = enabled
    ? 'Sono richiesti pilot reale, almeno 30 scenari, gate superato e versione corrente. La decisione viene registrata.'
    : 'La revoca ha effetto immediato sulle future valutazioni di automazione.';
  $('#validationAutomationSubmit').textContent = enabled ? 'Approva' : 'Revoca';
  $('#validationAutomationNote').value = '';
  $('#validationAutomationDialog').showModal();
}

async function submitValidationAutomation(event) {
  event.preventDefault();
  const datasetId = $('#validationAutomationDatasetId').value;
  const enabled = $('#validationAutomationEnabled').value === 'true';
  const note = $('#validationAutomationNote').value.trim();
  try {
    await api(`/api/validation/datasets/${datasetId}/automation`, {
      method: 'POST',
      body: JSON.stringify({ enabled, note }),
    });
    $('#validationAutomationDialog').close();
    toast(enabled ? 'Automazione supervisionata approvata.' : 'Approvazione revocata.');
    await loadValidation();
  } catch (error) { toast(error.message, true); }
}


function renderValidationRuns() {
  const body = $('#validationRunsTable');
  if (!state.validationRuns.length) {
    body.innerHTML = `<tr><td colspan="7" class="empty-state">Nessuna esecuzione disponibile.</td></tr>`;
    return;
  }
  body.innerHTML = state.validationRuns.map(run => `<tr data-validation-run-id="${run.id}"><td>${dateTime(run.created_at)}</td><td>${escapeHtml(run.engine_version)}</td><td>${run.scenario_count}</td><td>${percentMetric(run.precision)}</td><td>${percentMetric(run.recall)}</td><td>${percentMetric(run.f1_score)}</td><td><span class="badge ${run.gate_passed ? 'parsed' : 'high'}">${run.gate_passed ? 'PASS' : 'STOP'}</span></td></tr>`).join('');
  body.querySelectorAll('[data-validation-run-id]').forEach(row => row.addEventListener('click', () => openValidationRun(row.dataset.validationRunId)));
}

async function executeValidationDataset(datasetId, button) {
  const original = button.textContent;
  button.disabled = true;
  button.textContent = 'Esecuzione…';
  try {
    const run = await api(`/api/validation/datasets/${datasetId}/run`, { method: 'POST' });
    toast(run.gate_passed ? 'Gate di validazione superato.' : 'Regressione rilevata: rilascio bloccato.', !run.gate_passed);
    await loadValidation();
    await openValidationRun(run.id);
  } catch (error) {
    toast(error.message, true);
  } finally {
    button.disabled = false;
    button.textContent = original;
  }
}

async function loadDefaultValidationDataset() {
  const button = $('#loadDefaultValidationButton');
  button.disabled = true;
  try {
    await api('/api/validation/load-default', { method: 'POST' });
    toast('Suite base caricata.');
    await loadValidation();
  } catch (error) { toast(error.message, true); }
  finally { button.disabled = false; }
}

async function createValidationDataset(event) {
  event.preventDefault();
  try {
    const payload = JSON.parse($('#validationDatasetJson').value);
    await api('/api/validation/datasets', { method: 'POST', body: JSON.stringify(payload) });
    $('#validationDatasetDialog').close();
    event.currentTarget.reset();
    toast('Suite di validazione salvata.');
    await loadValidation();
  } catch (error) {
    toast(error instanceof SyntaxError ? 'JSON non valido.' : error.message, true);
  }
}

async function downloadValidationReport(runId, format, button) {
  const original = button.textContent;
  button.disabled = true;
  button.textContent = 'Preparazione…';
  try {
    const response = await fetch(`/api/validation/runs/${runId}/report?format=${encodeURIComponent(format)}&redacted=true`, { credentials: 'same-origin' });
    if (!response.ok) {
      const payload = response.headers.get('content-type')?.includes('application/json') ? await response.json() : await response.text();
      throw new Error(messageFrom(payload, `Errore ${response.status}`));
    }
    const blob = await response.blob();
    const disposition = response.headers.get('content-disposition') || '';
    const filename = disposition.match(/filename="?([^";]+)"?/i)?.[1] || `thistinti-validation-report.${format === 'markdown' ? 'md' : 'json'}`;
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    toast('Rapporto di validazione esportato.');
  } catch (error) {
    toast(error.message, true);
  } finally {
    button.disabled = false;
    button.textContent = original;
  }
}


async function openValidationRun(runId) {
  try {
    const run = await api(`/api/validation/runs/${runId}`);
    const details = run.details || {};
    const scenarios = details.scenarios || [];
    $('#validationRunDialogTitle').textContent = `${run.gate_passed ? 'PASS' : 'STOP'} · ${dateTime(run.created_at)}`;
    $('#validationRunDialogBody').innerHTML = `<div class="detail-grid"><div class="detail-card"><p>Precisione</p><strong>${percentMetric(run.precision)}</strong></div><div class="detail-card"><p>Recall</p><strong>${percentMetric(run.recall)}</strong></div><div class="detail-card"><p>F1</p><strong>${percentMetric(run.f1_score)}</strong></div><div class="detail-card"><p>Errore importi</p><strong>${money(run.amount_mae)}</strong></div></div><div class="modal-actions report-actions"><button class="secondary-button validation-report-button" data-report-format="json" type="button">Esporta rapporto JSON</button><button class="secondary-button validation-report-button" data-report-format="markdown" type="button">Esporta rapporto Markdown</button></div><div class="validation-scenarios"><h4>Scenari</h4>${scenarios.map(scenario => `<article class="validation-scenario ${scenario.passed ? 'passed' : 'failed'}"><div><strong>${escapeHtml(scenario.id)}</strong><small>${escapeHtml(scenario.description || '')}</small></div><span class="badge ${scenario.passed ? 'parsed' : 'high'}">${scenario.passed ? 'PASS' : 'FAIL'}</span><p>${scenario.true_positives || 0} TP · ${(scenario.false_positives || []).length} FP · ${(scenario.false_negatives || []).length} FN</p>${scenario.error ? `<code>${escapeHtml(scenario.error)}</code>` : ''}</article>`).join('')}</div>`;
    $('#validationRunDialogBody').querySelectorAll('.validation-report-button').forEach(button => button.addEventListener('click', () => downloadValidationReport(runId, button.dataset.reportFormat, button)));
    $('#validationRunDialog').showModal();
  } catch (error) { toast(error.message, true); }
}

async function exportData() {
  try {
    const response = await fetch('/api/export', { credentials: 'same-origin' });
    if (!response.ok) { const data = await response.json(); throw new Error(data.detail || 'Export non riuscito'); }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url; link.download = 'thistinti-export.zip'; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    toast('Export creato.');
  } catch (error) { toast(error.message, true); }
}

function evidenceActions(evidence) {
  if (!evidence.document_id) return '<p class="empty-state">Documento sorgente non più disponibile.</p>';
  const lineAction = evidence.document_line_id
    ? `<button class="secondary-button evidence-line-button" data-document-id="${escapeHtml(evidence.document_id)}" data-line-id="${escapeHtml(evidence.document_line_id)}" type="button">Apri riga estratta</button>`
    : `<button class="secondary-button evidence-line-button" data-document-id="${escapeHtml(evidence.document_id)}" type="button">Apri documento</button>`;
  return `<div class="evidence-actions">${lineAction}<button class="secondary-button evidence-original-button" data-document-id="${escapeHtml(evidence.document_id)}" type="button">Apri originale</button></div>`;
}

async function openOriginalDocument(documentId, button) {
  const originalLabel = button?.textContent || 'Apri originale';
  if (button) { button.disabled = true; button.textContent = 'Apertura…'; }
  const preview = window.open('about:blank', '_blank');
  if (preview) preview.opener = null;
  try {
    const response = await fetch(`/api/documents/${encodeURIComponent(documentId)}/file`, { credentials: 'same-origin' });
    if (!response.ok) {
      const payload = response.headers.get('content-type')?.includes('application/json') ? await response.json() : await response.text();
      throw new Error(messageFrom(payload, `Documento non disponibile (${response.status})`));
    }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    if (preview) preview.location.replace(url);
    else {
      const link = document.createElement('a');
      link.href = url;
      link.target = '_blank';
      link.rel = 'noopener';
      link.click();
    }
    window.setTimeout(() => URL.revokeObjectURL(url), 60000);
  } catch (error) {
    if (preview) preview.close();
    toast(error.message, true);
  } finally {
    if (button) { button.disabled = false; button.textContent = originalLabel; }
  }
}

async function openCase(id) {
  try {
    const c = await api(`/api/cases/${id}`);
    state.selectedCase = c;
    $('#caseDialogTitle').textContent = c.title;
    $('#caseDialogBody').innerHTML = `<div class="detail-grid"><div class="detail-card"><p>Gravità</p><strong><span class="badge ${c.severity}">${labelSeverity(c.severity)}</span></strong></div><div class="detail-card"><p>Importo stimato</p><strong>${money(c.amount_estimate)}</strong></div><div class="detail-card"><p>Confidenza</p><strong>${Math.round(c.confidence * 100)}%</strong></div></div><div class="detail-card detail-spaced"><p>Spiegazione</p><strong>${escapeHtml(c.explanation)}</strong></div><div class="detail-card detail-spaced"><p>Azione proposta</p><strong>${escapeHtml(c.recommended_action)}</strong></div><div class="evidence-list"><h4>Prove collegate</h4>${c.evidence.length ? c.evidence.map(e => `<div class="evidence-item"><p><strong>${escapeHtml(e.field_name)}</strong></p><p>Osservato: ${escapeHtml(e.observed_value || '—')}</p><p>Atteso: ${escapeHtml(e.expected_value || '—')}</p>${e.note ? `<small>${escapeHtml(e.note)}</small>` : ''}${evidenceActions(e)}</div>`).join('') : '<p class="empty-state">Nessuna prova strutturata.</p>'}</div>`;
    $('#caseDialogBody').querySelectorAll('.evidence-line-button').forEach(button => button.addEventListener('click', () => openDocument(button.dataset.documentId, button.dataset.lineId || null)));
    $('#caseDialogBody').querySelectorAll('.evidence-original-button').forEach(button => button.addEventListener('click', () => openOriginalDocument(button.dataset.documentId, button)));
    $('#reviewNote').value = '';
    $('#caseDialog').showModal();
  } catch (error) { toast(error.message, true); }
}

async function openDocument(id, lineId = null) {
  try {
    const d = await api(`/api/documents/${id}`);
    state.selectedDocument = d;
    $('#documentDialogTitle').textContent = d.number || d.source_filename;
    const canReview = ['admin', 'reviewer'].includes(state.user?.role);
    const errorPanel = d.parse_message ? `<div class="persistent-error" role="alert"><strong>${d.parse_status === 'failed' ? 'Il documento richiede intervento' : 'Messaggio di elaborazione'}</strong><p>${escapeHtml(d.parse_message)}</p></div>` : '';
    const actions = `<div class="document-actions"><button id="documentOriginalButton" class="secondary-button" type="button">Apri originale</button>${canReview ? '<button id="documentReprocessButton" class="primary-button" type="button">Correggi e rielabora</button>' : ''}</div>`;
    $('#documentDialogBody').innerHTML = `<div class="detail-grid"><div class="detail-card"><p>Tipo</p><strong>${labelType(d.document_type)}</strong></div><div class="detail-card"><p>Fornitore</p><strong>${escapeHtml(d.supplier || '—')}</strong></div><div class="detail-card"><p>Stato</p><strong>${labelStatus(d.parse_status)}</strong></div></div>${errorPanel}${actions}<div class="lines-table"><table><thead><tr><th>Riga</th><th>Articolo</th><th>Variante</th><th>Quantità</th><th>Prezzo</th><th>Sconto</th></tr></thead><tbody>${d.lines.length ? d.lines.map(l => `<tr data-line-id="${escapeHtml(l.id)}" class="${lineId === l.id ? 'document-row-highlight' : ''}"><td>${l.line_no}</td><td><strong>${escapeHtml(l.sku || '—')}</strong><small>${escapeHtml(l.description || '')}</small></td><td>${escapeHtml([l.color,l.size,l.lot].filter(Boolean).join(' / ') || '—')}</td><td>${numberOrDash(l.quantity)}</td><td>${moneyOrDash(l.unit_price)}</td><td>${percentOrDash(l.discount_rate)}</td></tr>`).join('') : `<tr><td colspan="6" class="empty-state">Nessuna riga estratta.</td></tr>`}</tbody></table></div>`;
    $('#documentOriginalButton')?.addEventListener('click', event => openOriginalDocument(d.id, event.currentTarget));
    $('#documentReprocessButton')?.addEventListener('click', () => openReprocessDialog(d));
    $('#documentDialog').showModal();
    if (lineId) {
      const selected = $('#documentDialogBody').querySelector(`[data-line-id="${CSS.escape(lineId)}"]`);
      if (selected) window.requestAnimationFrame(() => selected.scrollIntoView({ block: 'center' }));
      else toast('La riga collegata non è più disponibile nel documento corrente.', true);
    }
  } catch (error) { toast(error.message, true); }
}

async function submitDecision(decision) {
  if (!state.selectedCase) return;
  try {
    await api(`/api/cases/${state.selectedCase.id}/decision`, { method: 'POST', body: JSON.stringify({ decision, note: $('#reviewNote').value || null }) });
    $('#caseDialog').close();
    toast('Decisione registrata nell’audit log.');
    await Promise.all([loadDashboard(), loadCases(), loadAudit()]);
  } catch (error) { toast(error.message, true); }
}


async function waitForJob(jobId, progressElement, maxWaitMs = 300000) {
  const started = Date.now();
  while (Date.now() - started < maxWaitMs) {
    const job = await api(`/api/jobs/${jobId}`);
    const progress = Math.max(0, Math.min(100, Number(job.progress || 0)));
    progressElement.textContent = job.status === 'queued'
      ? 'Documento in coda persistente…'
      : job.status === 'running'
        ? `Analisi in corso… ${progress}%`
        : `Stato: ${labelStatus(job.status)}`;
    if (job.status === 'completed') return job;
    if (job.status === 'failed') throw new Error(job.error_message || 'Elaborazione non riuscita');
    if (job.status === 'cancelled') throw new Error('Elaborazione annullata');
    await new Promise(resolve => window.setTimeout(resolve, 750));
  }
  return null;
}

async function uploadDocument(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const data = new FormData(form);
  const selectedFile = $('#documentFile').files[0];
  const isBatch = selectedFile && selectedFile.name.toLowerCase().endsWith('.zip');
  if (isBatch) {
    for (const key of [...data.keys()]) data.delete(key);
    data.append('file', selectedFile);
  }
  const progressRow = $('#uploadProgress');
  const progressText = progressRow.querySelector('p');
  progressText.textContent = 'Caricamento nella coda persistente…';
  progressRow.classList.remove('hidden');
  form.querySelector('button[type="submit"]').disabled = true;
  let queuedJobId = null;
  try {
    const idempotencyKey = window.crypto?.randomUUID?.() || `upload-${Date.now()}-${Math.random()}`;
    const queued = await api(isBatch ? '/api/jobs/batches' : '/api/jobs/documents', {
      method: 'POST',
      body: data,
      headers: { 'Idempotency-Key': idempotencyKey },
    });
    queuedJobId = queued.job.id;
    const completed = await waitForJob(queuedJobId, progressText);
    $('#uploadDialog').close();
    form.reset();
    if (!completed) {
      toast('Documento acquisito: il job continua nella coda persistente.');
    } else if (isBatch) {
      const counts = completed.result.counts || {};
      const failures = Number(counts.parse_failed || 0) + Number(counts.failed || 0);
      toast(`ZIP elaborato: ${counts.ingested || 0} nuovi, ${counts.duplicates || 0} duplicati, ${failures} da rivedere.`, failures > 0);
    } else if (completed.result.outcome === 'parse_failed') {
      toast('Documento acquisito, ma richiede revisione.', true);
    } else if (completed.result.outcome === 'duplicate') {
      toast('Documento già presente: nessun duplicato creato.');
    } else {
      toast('Documento analizzato e collegato.');
    }
    await refreshAll();
  } catch (error) {
    toast(error.message, true);
    if (queuedJobId) {
      $('#uploadDialog').close();
      await openView('jobs');
    }
  }
  finally {
    progressText.textContent = 'Analisi in corso…';
    progressRow.classList.add('hidden');
    form.querySelector('button[type="submit"]').disabled = false;
  }
}


async function loadDemo() {
  $('#demoButton').disabled = true;
  try {
    const result = await api('/api/demo/load', { method: 'POST' });
    toast(`${result.loaded} documenti dimostrativi elaborati.`);
    await refreshAll();
  } catch (error) { toast(error.message, true); }
  finally { $('#demoButton').disabled = false; }
}

function labelType(value) { return ({proposal:'Proposta',order:'Ordine',confirmation:'Conferma',delivery:'Consegna',invoice:'Fattura',payment:'Pagamento',return:'Reso',credit_note:'Nota credito'})[value] || value || '—'; }
function labelSeverity(value) { return ({critical:'Critica',high:'Alta',medium:'Media',low:'Bassa'})[value] || value; }
function severitySymbol(value) { return ({critical:'!!',high:'!',medium:'·',low:'i'})[value] || '?'; }
function labelRole(value) { return ({admin:'Amministratore',reviewer:'Revisore',viewer:'Sola lettura'})[value] || value; }
function labelStatus(value) { return ({queued:'In attesa',running:'In corso',completed:'Completata',cancelled:'Annullata',parsed:'Letto',review_required:'Da rivedere',failed:'Fallito',open:'Aperta',needs_review:'Da rivedere',confirmed:'Confermata',dismissed:'Scartata',resolved:'Risolta',superseded:'Superata',review:'In revisione',clear:'Regolare',processing:'In elaborazione'})[value] || value || '—'; }
function markList(values) { const count = Array.isArray(values) ? values.length : 0; return count ? `<span class="badge parsed">${count}</span>` : '<span class="muted-dash">—</span>'; }

$('#loginTab').addEventListener('click', () => switchAuth('login'));
$('#registerTab').addEventListener('click', () => switchAuth('register'));
$('#loginForm').addEventListener('submit', async (e) => { e.preventDefault(); try { await authenticate('/api/auth/login', { email: $('#loginEmail').value, password: $('#loginPassword').value }); } catch (error) { toast(error.message, true); } });
$('#registerForm').addEventListener('submit', async (e) => { e.preventDefault(); try { await authenticate('/api/auth/register', { organization_name: $('#organizationName').value, email: $('#registerEmail').value, password: $('#registerPassword').value, legal_notice_version: '2026-07-20-v2', accepted_terms: $('#acceptTerms').checked, accepted_specific_clauses: $('#acceptSpecificClauses').checked }); } catch (error) { toast(error.message, true); } });
$('#logoutButton').addEventListener('click', () => logout());
$('#mainNav').addEventListener('click', (e) => { const button = e.target.closest('[data-view]'); if (button) openView(button.dataset.view); });
$$('[data-go]').forEach(el => el.addEventListener('click', () => openView(el.dataset.go)));
$('#openUploadButton').addEventListener('click', () => $('#uploadDialog').showModal());
$('#uploadForm').addEventListener('submit', uploadDocument);
$('#reprocessForm').addEventListener('submit', submitReprocess);
$('#demoButton').addEventListener('click', loadDemo);
$('#exportButton').addEventListener('click', exportData);
$('#runDiscoveryButton').addEventListener('click', runDiscovery);
$('#confirmActivityButton').addEventListener('click', () => decideActivityProfile('confirmed'));
$('#correctActivityButton').addEventListener('click', () => decideActivityProfile('corrected'));
$('#loadDefaultValidationButton').addEventListener('click', loadDefaultValidationDataset);
$('#openValidationDatasetButton').addEventListener('click', () => $('#validationDatasetDialog').showModal());
$('#validationDatasetForm').addEventListener('submit', createValidationDataset);
$('#validationAutomationForm').addEventListener('submit', submitValidationAutomation);
$('#openUserButton').addEventListener('click', () => $('#userDialog').showModal());
$('#userForm').addEventListener('submit', createUser);
$$('[data-close-dialog]').forEach(el => el.addEventListener('click', () => $(`#${el.dataset.closeDialog}`).close()));
$$('[data-decision]').forEach(el => el.addEventListener('click', () => submitDecision(el.dataset.decision)));
$('#documentTypeFilter').addEventListener('change', loadDocuments);
$('#documentStatusFilter').addEventListener('change', loadDocuments);
$('#caseStatusFilter').addEventListener('change', loadCases);
$('#caseSeverityFilter').addEventListener('change', loadCases);
$('#jobStatusFilter').addEventListener('change', () => loadJobs(true));
$('#jobTypeFilter').addEventListener('change', () => loadJobs(true));
$('#refreshJobsButton').addEventListener('click', () => loadJobs(false));
$('#jobsPreviousButton').addEventListener('click', () => { state.jobsOffset = Math.max(0, state.jobsOffset - state.jobsLimit); loadJobs(false); });
$('#jobsNextButton').addEventListener('click', () => { state.jobsOffset += state.jobsLimit; loadJobs(false); });
let jobSearchTimer = null;
$('#jobSearchInput').addEventListener('input', () => { clearTimeout(jobSearchTimer); jobSearchTimer = window.setTimeout(() => loadJobs(true), 300); });

(async function boot() {
  try {
    const health = await api('/api/health');
    if (health.edition === 'local') $('#localEditionBadge').classList.remove('hidden');
  } catch (_) { /* health is best-effort; authentication below remains authoritative */ }
  try {
    state.user = await api('/api/auth/me');
    showApp();
    await refreshAll();
  } catch (error) {
    clearSession(false);
  }
})();

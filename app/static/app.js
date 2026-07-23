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
  selectedCase: null,
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
const money = (value) => new Intl.NumberFormat('it-IT', { style: 'currency', currency: 'EUR' }).format(Number(value || 0));
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

const operationalViews = new Set(['dashboard', 'documents', 'chains', 'cases', 'discovery']);

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
  renderPriorityCases(cases.filter(c => ['open','needs_review','confirmed'].includes(c.status)).slice(0, 5));
}

function renderPriorityCases(cases) {
  const target = $('#priorityCases');
  if (!cases.length) { target.className = 'list-stack empty-state'; target.textContent = 'Nessuna anomalia disponibile.'; return; }
  target.className = 'list-stack';
  target.innerHTML = cases.map(c => `<div class="case-item" data-case-id="${c.id}"><span class="severity-icon ${c.severity}">${c.severity === 'high' ? '!' : c.severity === 'medium' ? '·' : 'i'}</span><div><strong>${escapeHtml(c.title)}</strong><small>${escapeHtml(c.explanation)}</small></div><span class="case-amount">${money(c.amount_estimate)}</span></div>`).join('');
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
  return `<strong>${value.quantity}</strong><small>${money(value.unit_price)} · sconto ${value.discount_rate}%</small>`;
}

async function openChain(id) {
  try {
    const chain = await api(`/api/chains/${id}`);
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
    const actionButtons = canReview ? `<div class="modal-actions intelligence-actions"><button id="simulateChainButton" class="secondary-button" type="button">Simula approvazione</button><button id="redTeamChainButton" class="secondary-button" type="button">Prova a ingannare ThisTinti</button></div>` : '';
    $('#chainDialogBody').innerHTML = `<div class="detail-grid"><div class="detail-card"><p>Stato</p><strong>${labelStatus(chain.status)}</strong></div><div class="detail-card"><p>Rischio preventivo</p><strong id="chainRiskValue">${risk.score}/100 · ${escapeHtml(risk.decision)}</strong><small id="chainRiskAmount">${money(risk.amount_at_risk)} potenzialmente coinvolti</small></div><div class="detail-card"><p>Tripla verifica</p><strong>${escapeHtml(intelligence.triangulation?.status || '—')}</strong><small>estrazione · calcoli · grafo</small></div><div class="detail-card"><p>Conformità processo</p><strong>${Math.round((intelligence.process_conformance?.score || 0) * 100)}%</strong><small>${escapeHtml(intelligence.process_conformance?.baseline_source || 'baseline prudenziale')}</small></div></div>${actionButtons}<div id="chainIntelligenceResult" aria-live="polite"></div><section class="detail-section"><div class="panel-heading"><div><h3>Sentinel Twin</h3><p>Cosa manca o dovrebbe accadere dopo.</p></div></div><div class="list-stack">${expectationHtml}</div></section><div class="lines-table comparison-table"><table><thead><tr><th>Articolo</th><th>Riferimento commerciale</th><th>Consegna</th><th>Fattura</th><th>Reso</th><th>Nota credito</th><th>Esito</th></tr></thead><tbody>${rows.length ? rows.map(row => `<tr><td><strong>${escapeHtml(row.sku || row.description || row.key)}</strong><small>${escapeHtml([row.description,row.color,row.size,row.lot].filter(Boolean).join(' · '))}</small></td><td>${comparisonCell(row.values.confirmation || row.values.order || row.values.proposal)}</td><td>${comparisonCell(row.values.delivery)}</td><td>${comparisonCell(row.values.invoice)}</td><td>${comparisonCell(row.values.return)}</td><td>${comparisonCell(row.values.credit_note)}</td><td><span class="badge ${row.status === 'ok' ? 'parsed' : row.status === 'issue' ? 'high' : 'medium'}">${row.status === 'ok' ? 'Coerente' : escapeHtml(row.reasons.join(', ') || 'Da verificare')}</span></td></tr>`).join('') : '<tr><td colspan="7" class="empty-state">Nessuna riga confrontabile.</td></tr>'}</tbody></table></div>`;
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
        $('#chainIntelligenceResult').innerHTML = `<div class="intelligence-callout"><strong>Self-red-team: ${Math.round(result.coverage * 100)}%</strong><p>${result.detected}/${result.applicable || result.total} scenari applicabili intercettati; ${result.total} famiglie disponibili. Stato: ${escapeHtml(result.status)}.</p></div>`;
      } catch (error) { toast(error.message, true); }
    });
    $('#chainDialog').showModal();
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

async function openCase(id) {
  const c = await api(`/api/cases/${id}`);
  state.selectedCase = c;
  $('#caseDialogTitle').textContent = c.title;
  $('#caseDialogBody').innerHTML = `<div class="detail-grid"><div class="detail-card"><p>Gravità</p><strong>${labelSeverity(c.severity)}</strong></div><div class="detail-card"><p>Importo stimato</p><strong>${money(c.amount_estimate)}</strong></div><div class="detail-card"><p>Confidenza</p><strong>${Math.round(c.confidence * 100)}%</strong></div></div><div class="detail-card detail-spaced"><p>Spiegazione</p><strong>${escapeHtml(c.explanation)}</strong></div><div class="detail-card detail-spaced"><p>Azione proposta</p><strong>${escapeHtml(c.recommended_action)}</strong></div><div class="evidence-list"><h4>Prove collegate</h4>${c.evidence.length ? c.evidence.map(e => `<div class="evidence-item"><p><strong>${escapeHtml(e.field_name)}</strong></p><p>Osservato: ${escapeHtml(e.observed_value || '—')}</p><p>Atteso: ${escapeHtml(e.expected_value || '—')}</p>${e.note ? `<small>${escapeHtml(e.note)}</small>` : ''}</div>`).join('') : '<p class="empty-state">Nessuna prova strutturata.</p>'}</div>`;
  $('#reviewNote').value = '';
  $('#caseDialog').showModal();
}

async function openDocument(id) {
  const d = await api(`/api/documents/${id}`);
  $('#documentDialogTitle').textContent = d.number || d.source_filename;
  $('#documentDialogBody').innerHTML = `<div class="detail-grid"><div class="detail-card"><p>Tipo</p><strong>${labelType(d.document_type)}</strong></div><div class="detail-card"><p>Fornitore</p><strong>${escapeHtml(d.supplier || '—')}</strong></div><div class="detail-card"><p>Stato</p><strong>${labelStatus(d.parse_status)}</strong></div></div>${d.parse_message ? `<div class="detail-card detail-spaced"><p>Messaggio parser</p><strong>${escapeHtml(d.parse_message)}</strong></div>` : ''}<div class="lines-table"><table><thead><tr><th>Riga</th><th>Articolo</th><th>Variante</th><th>Quantità</th><th>Prezzo</th><th>Sconto</th></tr></thead><tbody>${d.lines.length ? d.lines.map(l => `<tr><td>${l.line_no}</td><td><strong>${escapeHtml(l.sku || '—')}</strong><small>${escapeHtml(l.description || '')}</small></td><td>${escapeHtml([l.color,l.size,l.lot].filter(Boolean).join(' / ') || '—')}</td><td>${l.quantity}</td><td>${money(l.unit_price)}</td><td>${l.discount_rate}%</td></tr>`).join('') : `<tr><td colspan="6" class="empty-state">Nessuna riga estratta.</td></tr>`}</tbody></table></div>`;
  $('#documentDialog').showModal();
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
  try {
    const idempotencyKey = window.crypto?.randomUUID?.() || `upload-${Date.now()}-${Math.random()}`;
    const queued = await api(isBatch ? '/api/jobs/batches' : '/api/jobs/documents', {
      method: 'POST',
      body: data,
      headers: { 'Idempotency-Key': idempotencyKey },
    });
    const completed = await waitForJob(queued.job.id, progressText);
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
  } catch (error) { toast(error.message, true); }
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
function labelSeverity(value) { return ({high:'Alta',medium:'Media',low:'Bassa'})[value] || value; }
function labelRole(value) { return ({admin:'Amministratore',reviewer:'Revisore',viewer:'Sola lettura'})[value] || value; }
function labelStatus(value) { return ({parsed:'Letto',review_required:'Da rivedere',failed:'Fallito',open:'Aperta',needs_review:'Da rivedere',confirmed:'Confermata',dismissed:'Scartata',resolved:'Risolta',superseded:'Superata',review:'In revisione',clear:'Regolare',processing:'In elaborazione'})[value] || value || '—'; }
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

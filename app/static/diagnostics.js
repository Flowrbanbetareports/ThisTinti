'use strict';

const report = {
  schema: 'thistinti.local-diagnostics.v1',
  started_at: null,
  completed_at: null,
  user_agent: navigator.userAgent,
  location: window.location.origin,
  mode: null,
  overall: 'NON ESEGUITO',
  version: null,
  checks: [],
  observed: {},
};

const byId = (id) => document.getElementById(id);
const sleep = (ms) => new Promise((resolve) => window.setTimeout(resolve, ms));

function getCookie(name) {
  return document.cookie
    .split('; ')
    .find((row) => row.startsWith(`${name}=`))
    ?.split('=')
    .slice(1)
    .join('=') || '';
}

function csrfHeaders() {
  const token = getCookie('thistinti_csrf');
  return token ? { 'X-CSRF-Token': decodeURIComponent(token) } : {};
}

function messageFrom(value, fallback = 'Operazione non riuscita.') {
  if (value === null || value === undefined || value === '') return fallback;
  if (value instanceof Error) return messageFrom(value.message, fallback);
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') return String(value);
  if (Array.isArray(value)) return value.map((item) => messageFrom(item, '')).filter(Boolean).join(' · ') || fallback;
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

async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  const method = String(options.method || 'GET').toUpperCase();
  if (!['GET', 'HEAD', 'OPTIONS'].includes(method)) {
    for (const [key, value] of Object.entries(csrfHeaders())) headers.set(key, value);
  }
  const response = await fetch(path, { ...options, headers, credentials: 'same-origin' });
  const contentType = response.headers.get('content-type') || '';
  const payload = contentType.includes('application/json') ? await response.json() : await response.text();
  if (!response.ok) {
    const error = new Error(messageFrom(payload, `Errore ${response.status}`));
    error.status = response.status;
    error.payload = payload;
    throw error;
  }
  return payload;
}

function setBusy(busy) {
  byId('runReadOnly').disabled = busy;
  byId('runActive').disabled = busy;
  byId('downloadReport').disabled = busy || !report.completed_at;
  byId('copySummary').disabled = busy || !report.completed_at;
}

function reset(mode) {
  report.started_at = new Date().toISOString();
  report.completed_at = null;
  report.mode = mode;
  report.overall = 'IN CORSO';
  report.version = null;
  report.checks = [];
  report.observed = {};
  byId('resultsBody').innerHTML = '';
  byId('progressBar').value = 0;
  byId('progressText').textContent = 'Avvio dei controlli…';
  renderSummary();
}

function renderSummary() {
  const failures = report.checks.filter((item) => item.status === 'FAIL').length;
  byId('overallStatus').textContent = report.overall;
  byId('overallStatus').dataset.overall = report.overall;
  byId('appVersion').textContent = report.version || '—';
  byId('checkCount').textContent = String(report.checks.length);
  byId('failureCount').textContent = String(failures);
  byId('observedData').textContent = JSON.stringify(report.observed, null, 2);
}

function renderCheck(check) {
  const row = document.createElement('tr');
  const name = document.createElement('td');
  const statusCell = document.createElement('td');
  const detail = document.createElement('td');
  const duration = document.createElement('td');
  const badge = document.createElement('span');

  name.textContent = check.name;
  badge.className = `status ${check.status.toLowerCase()}`;
  badge.textContent = check.status;
  statusCell.appendChild(badge);
  detail.textContent = check.detail;
  duration.textContent = `${check.duration_ms} ms`;
  row.append(name, statusCell, detail, duration);
  byId('resultsBody').appendChild(row);
}

async function runCheck(name, task, options = {}) {
  const started = performance.now();
  let status = 'PASS';
  let detail = 'Completato.';
  let data = null;
  try {
    const result = await task();
    if (result && typeof result === 'object' && 'status' in result) {
      status = result.status;
      detail = result.detail || detail;
      data = result.data ?? null;
    } else if (result !== undefined) {
      data = result;
      detail = options.successDetail || detail;
    }
  } catch (error) {
    status = options.optional ? 'SKIPPED' : 'FAIL';
    detail = messageFrom(error);
    data = error?.payload ?? null;
  }
  const check = {
    name,
    status,
    detail,
    duration_ms: Math.round(performance.now() - started),
    data,
  };
  report.checks.push(check);
  renderCheck(check);
  renderSummary();
  return check;
}

function arrayFromPayload(payload) {
  if (Array.isArray(payload)) return payload;
  for (const key of ['items', 'results', 'jobs', 'data']) {
    if (Array.isArray(payload?.[key])) return payload[key];
  }
  return [];
}

async function pollJob(jobId, timeoutMs = 120000) {
  const started = Date.now();
  let last = null;
  while (Date.now() - started < timeoutMs) {
    last = await api(`/api/jobs/${encodeURIComponent(jobId)}`);
    if (['failed', 'completed', 'cancelled'].includes(last.status)) return last;
    await sleep(750);
  }
  return { ...last, status: last?.status || 'timeout', timed_out: true };
}

async function activeNumericRecoveryTest() {
  const diagnosticId = `DIAG-${new Date().toISOString().replace(/[-:.TZ]/g, '').slice(0, 14)}`;
  const invalidDocument = {
    document_type: 'invoice',
    number: diagnosticId,
    document_date: new Date().toISOString().slice(0, 10),
    supplier_name: 'ThisTinti Diagnostic Test',
    supplier_vat: 'IT00000000000',
    references: { order_numbers: [`PO-${diagnosticId}`] },
    lines: [{
      line_no: 1,
      sku: 'DIAG-INVALID-NUMERIC',
      description: 'Test diagnostico con quantità non numerica',
      quantity: 'cinque',
      unit_price: 10,
      discount_rate: 0,
    }],
  };
  const form = new FormData();
  form.append('file', new Blob([JSON.stringify(invalidDocument, null, 2)], { type: 'application/json' }), `${diagnosticId}.json`);
  const queued = await api('/api/jobs/documents', {
    method: 'POST',
    body: form,
    headers: { 'Idempotency-Key': window.crypto?.randomUUID?.() || diagnosticId },
  });
  const jobId = queued?.job?.id || queued?.id;
  if (!jobId) return { status: 'FAIL', detail: 'Il caricamento non ha restituito un job identificabile.', data: queued };

  const job = await pollJob(jobId);
  report.observed.diagnostic_job = job;
  const serialized = JSON.stringify(job).toLowerCase();
  const hasField = serialized.includes('quantity') || serialized.includes('quantità');
  const hasValue = serialized.includes('cinque');
  const hasReason = ['invalid', 'non numer', 'numero', 'decimal', 'convert'].some((needle) => serialized.includes(needle));
  const outcome = job?.result?.outcome;
  const rejected = job.status === 'failed' || outcome === 'parse_failed';

  if (rejected && hasField && hasValue && hasReason) {
    return {
      status: 'PASS',
      detail: `Input non numerico rifiutato e registrato nel job ${jobId}; campo, valore e motivo risultano consultabili.`,
      data: job,
    };
  }
  if (rejected) {
    return {
      status: 'PARTIAL',
      detail: `Input rifiutato nel job ${jobId}, ma il dettaglio strutturato non contiene chiaramente campo, valore e motivo.`,
      data: job,
    };
  }
  return {
    status: 'FAIL',
    detail: `Il documento diagnostico non è stato rifiutato come previsto; stato finale: ${job.status || outcome || 'sconosciuto'}.`,
    data: job,
  };
}

async function run(mode) {
  reset(mode);
  setBusy(true);
  const steps = mode === 'active' ? 9 : 8;
  let completed = 0;
  const advance = (label) => {
    completed += 1;
    byId('progressBar').value = Math.round((completed / steps) * 100);
    byId('progressText').textContent = label;
  };

  await runCheck('Servizio e versione', async () => {
    const spec = await api('/openapi.json');
    report.version = spec?.info?.version || 'non dichiarata';
    report.observed.openapi = { title: spec?.info?.title, version: report.version };
    return { status: 'PASS', detail: `Servizio raggiungibile; versione dichiarata ${report.version}.` };
  });
  advance('Versione verificata.');

  await runCheck('Sessione e dashboard', async () => {
    const dashboard = await api('/api/dashboard');
    report.observed.dashboard = dashboard;
    return { status: 'PASS', detail: 'Sessione valida e dashboard disponibile.', data: dashboard };
  });
  advance('Dashboard verificata.');

  await runCheck('Documenti', async () => {
    const payload = await api('/api/documents');
    const items = arrayFromPayload(payload);
    report.observed.documents = { count: items.length };
    return { status: 'PASS', detail: `${items.length} documenti leggibili dalla sessione corrente.` };
  });
  advance('Documenti verificati.');

  await runCheck('Collegamenti', async () => {
    const payload = await api('/api/chains');
    const items = arrayFromPayload(payload);
    report.observed.chains = { count: items.length };
    const malformed = items.filter((item) => !item.id || !item.documents).length;
    return malformed
      ? { status: 'PARTIAL', detail: `${items.length} catene lette; ${malformed} non hanno la struttura attesa.` }
      : { status: 'PASS', detail: `${items.length} catene lette con struttura coerente.` };
  });
  advance('Collegamenti verificati.');

  await runCheck('Segnalazioni ed evidenze', async () => {
    const payload = await api('/api/cases');
    const items = arrayFromPayload(payload);
    report.observed.cases = {
      count: items.length,
      critical: items.filter((item) => item.severity === 'critical').length,
    };
    const missingEvidence = items.filter((item) => !item.explanation && !item.evidence).length;
    return missingEvidence
      ? { status: 'PARTIAL', detail: `${items.length} segnalazioni lette; ${missingEvidence} senza spiegazione o evidenza esplicita.` }
      : { status: 'PASS', detail: `${items.length} segnalazioni lette; spiegazioni/evidenze presenti.` };
  });
  advance('Segnalazioni verificate.');

  await runCheck('Attività persistenti', async () => {
    const payload = await api('/api/jobs?limit=25');
    const items = arrayFromPayload(payload);
    report.observed.jobs = { count_visible: items.length, total: payload?.total ?? items.length };
    return { status: 'PASS', detail: `${payload?.total ?? items.length} attività consultabili.` };
  });
  advance('Attività verificate.');

  await runCheck('Layout e tastiera della diagnostica', async () => {
    const focusables = [...document.querySelectorAll('button:not([disabled]), a[href], input, select, textarea')];
    const overflow = document.documentElement.scrollWidth > document.documentElement.clientWidth + 2;
    report.observed.accessibility = {
      focusable_controls: focusables.length,
      page_horizontal_overflow: overflow,
      reduced_motion_requested: window.matchMedia('(prefers-reduced-motion: reduce)').matches,
      viewport: { width: window.innerWidth, height: window.innerHeight, device_pixel_ratio: window.devicePixelRatio },
    };
    return overflow
      ? { status: 'FAIL', detail: 'La pagina diagnostica produce scorrimento orizzontale globale.' }
      : { status: 'PASS', detail: `${focusables.length} controlli raggiungibili; nessun overflow orizzontale globale.` };
  });
  advance('Layout verificato.');

  await runCheck('Persistenza browser locale', async () => {
    const key = 'thistinti_diagnostics_probe';
    const value = `${Date.now()}`;
    localStorage.setItem(key, value);
    const restored = localStorage.getItem(key);
    localStorage.removeItem(key);
    return restored === value
      ? { status: 'PASS', detail: 'Scrittura e rilettura locale del browser riuscite.' }
      : { status: 'FAIL', detail: 'Il browser non ha riletto il valore locale appena scritto.' };
  });
  advance('Persistenza locale verificata.');

  if (mode === 'active') {
    await runCheck('Recupero errore numerico', activeNumericRecoveryTest);
    advance('Test attivo completato.');
  }

  const failures = report.checks.filter((item) => item.status === 'FAIL').length;
  const partials = report.checks.filter((item) => ['PARTIAL', 'SKIPPED'].includes(item.status)).length;
  report.overall = failures ? 'FAIL' : partials ? 'PARZIALE' : 'PASS';
  report.completed_at = new Date().toISOString();
  byId('progressBar').value = 100;
  byId('progressText').textContent = `Collaudo concluso: ${report.overall}.`;
  renderSummary();
  setBusy(false);
}

function downloadReport() {
  const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' });
  const link = document.createElement('a');
  link.href = URL.createObjectURL(blob);
  link.download = `ThisTinti-diagnostics-${new Date().toISOString().replace(/[:.]/g, '-')}.json`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(link.href);
}

function summaryText() {
  const lines = [
    `ThisTinti diagnostica: ${report.overall}`,
    `Versione: ${report.version || '—'}`,
    `Avvio: ${report.started_at || '—'}`,
    `Fine: ${report.completed_at || '—'}`,
    '',
    ...report.checks.map((item) => `${item.status} — ${item.name}: ${item.detail}`),
  ];
  return lines.join('\n');
}

byId('runReadOnly').addEventListener('click', () => run('read-only'));
byId('runActive').addEventListener('click', () => run('active'));
byId('downloadReport').addEventListener('click', downloadReport);
byId('copySummary').addEventListener('click', async () => {
  try {
    await navigator.clipboard.writeText(summaryText());
    byId('progressText').textContent = 'Riepilogo copiato negli appunti.';
  } catch (error) {
    byId('progressText').textContent = `Copia non riuscita: ${messageFrom(error)}`;
  }
});

renderSummary();

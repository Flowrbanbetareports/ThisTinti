(() => {
  'use strict';

  const operationalViews = new Set(['dashboard', 'documents', 'chains', 'cases', 'discovery']);

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
      return fallback;
    }

    return fallback;
  }

  const baseToast = window.toast;
  window.toast = function patchedToast(message, error = false) {
    return baseToast(messageFrom(message), error);
  };

  window.api = async function patchedApi(path, options = {}) {
    const headers = new Headers(options.headers || {});
    const method = String(options.method || 'GET').toUpperCase();
    if (!['GET', 'HEAD', 'OPTIONS'].includes(method)) {
      const token = document.cookie.split('; ').find(row => row.startsWith('thistinti_csrf='))?.split('=').slice(1).join('=') || '';
      if (token) headers.set('X-CSRF-Token', decodeURIComponent(token));
    }
    if (!(options.body instanceof FormData) && options.body && !headers.has('Content-Type')) {
      headers.set('Content-Type', 'application/json');
    }

    const response = await fetch(path, { ...options, headers, credentials: 'same-origin' });
    if (response.status === 401) {
      clearSession(false);
      throw new Error('Sessione scaduta. Accedi nuovamente.');
    }

    const payload = response.headers.get('content-type')?.includes('application/json')
      ? await response.json()
      : await response.text();
    if (!response.ok) throw new Error(messageFrom(payload, `Errore ${response.status}`));
    return payload;
  };

  function localDateTime(value) {
    if (!value) return '—';
    const raw = String(value).trim();
    const hasTimezone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(raw);
    const parsed = new Date(hasTimezone ? raw : `${raw}Z`);
    if (Number.isNaN(parsed.getTime())) return raw;
    return new Intl.DateTimeFormat('it-IT', { dateStyle: 'short', timeStyle: 'short' }).format(parsed);
  }

  window.loadAudit = async function patchedLoadAudit() {
    const events = await api('/api/audit');
    const body = $('#auditTable');
    if (!events.length) {
      body.innerHTML = '<tr><td colspan="4" class="empty-state">Nessun evento.</td></tr>';
      return;
    }
    body.innerHTML = events.map(event => `<tr><td>${localDateTime(event.created_at)}</td><td><strong>${escapeHtml(event.action)}</strong></td><td>${escapeHtml(event.entity_type || '—')}</td><td><code>${escapeHtml(JSON.stringify(event.payload))}</code></td></tr>`).join('');
  };

  window.loadUsers = async function patchedLoadUsers() {
    state.users = await api('/api/users');
    const body = $('#usersTable');
    if (!state.users.length) {
      body.innerHTML = '<tr><td colspan="5" class="empty-state">Nessun utente.</td></tr>';
      return;
    }
    body.innerHTML = state.users.map(user => `<tr><td><strong>${escapeHtml(user.email)}</strong>${user.id === state.user?.id ? '<small>Account corrente</small>' : ''}</td><td>${user.id === state.user?.id ? labelRole(user.role) : `<select class="compact-select user-role-select" data-user-id="${user.id}" aria-label="Ruolo di ${escapeHtml(user.email)}"><option value="viewer" ${user.role === 'viewer' ? 'selected' : ''}>Sola lettura</option><option value="reviewer" ${user.role === 'reviewer' ? 'selected' : ''}>Revisore</option><option value="admin" ${user.role === 'admin' ? 'selected' : ''}>Amministratore</option></select>`}</td><td><span class="badge ${user.active ? 'parsed' : 'dismissed'}">${user.active ? 'Attivo' : 'Disattivato'}</span></td><td>${localDateTime(user.created_at)}</td><td>${user.id === state.user?.id ? '' : `<button class="secondary-button user-status-button" data-user-id="${user.id}" data-active="${user.active}">${user.active ? 'Disattiva' : 'Riattiva'}</button>`}</td></tr>`).join('');
    body.querySelectorAll('.user-status-button').forEach(button => button.addEventListener('click', () => toggleUser(button.dataset.userId, button.dataset.active === 'true')));
    body.querySelectorAll('.user-role-select').forEach(select => select.addEventListener('change', () => updateUserRole(select.dataset.userId, select.value)));
  };

  window.renderValidationRuns = function patchedRenderValidationRuns() {
    const body = $('#validationRunsTable');
    if (!state.validationRuns.length) {
      body.innerHTML = '<tr><td colspan="7" class="empty-state">Nessuna esecuzione disponibile.</td></tr>';
      return;
    }
    body.innerHTML = state.validationRuns.map(run => `<tr data-validation-run-id="${run.id}"><td>${localDateTime(run.created_at)}</td><td>${escapeHtml(run.engine_version)}</td><td>${run.scenario_count}</td><td>${percentMetric(run.precision)}</td><td>${percentMetric(run.recall)}</td><td>${percentMetric(run.f1_score)}</td><td><span class="badge ${run.gate_passed ? 'parsed' : 'high'}">${run.gate_passed ? 'PASS' : 'STOP'}</span></td></tr>`).join('');
    body.querySelectorAll('[data-validation-run-id]').forEach(row => row.addEventListener('click', () => openValidationRun(row.dataset.validationRunId)));
  };

  const baseOpenValidationRun = window.openValidationRun;
  window.openValidationRun = async function patchedOpenValidationRun(runId) {
    await baseOpenValidationRun(runId);
    const title = $('#validationRunDialogTitle');
    const run = state.validationRuns.find(item => String(item.id) === String(runId));
    if (title && run) title.textContent = `${run.gate_passed ? 'PASS' : 'STOP'} · ${localDateTime(run.created_at)}`;
  };

  function updateViewChrome(view) {
    const role = state.user?.role || 'viewer';
    const operational = operationalViews.has(view);
    const canReview = ['admin', 'reviewer'].includes(role);
    $('#exportButton')?.classList.toggle('hidden', role !== 'admin' || !operational);
    $('#demoButton')?.classList.toggle('hidden', !canReview || !operational);
    $('#openUploadButton')?.classList.toggle('hidden', !canReview || !operational);
    document.querySelector('.legal-warning')?.classList.toggle('hidden', !operational);
  }

  const baseOpenView = window.openView;
  window.openView = async function patchedOpenView(view) {
    updateViewChrome(view);
    return baseOpenView(view);
  };

  const baseShowApp = window.showApp;
  window.showApp = function patchedShowApp() {
    baseShowApp();
    const current = document.querySelector('#mainNav button.active')?.dataset.view || 'dashboard';
    updateViewChrome(current);
  };

  const baseSwitchAuth = window.switchAuth;
  window.switchAuth = function patchedSwitchAuth(mode) {
    baseSwitchAuth(mode);
    $('#authView')?.classList.toggle('register-mode', mode === 'register');
  };

  const authEyebrow = document.querySelector('.auth-brand .eyebrow');
  if (authEyebrow) authEyebrow.textContent = 'Piattaforma di integrità documentale';

  const currentView = document.querySelector('#mainNav button.active')?.dataset.view || 'dashboard';
  updateViewChrome(currentView);
})();

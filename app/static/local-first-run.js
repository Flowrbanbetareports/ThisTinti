(() => {
  'use strict';

  const $ = (selector) => document.querySelector(selector);
  const storageKey = 'thistinti_local_setup_complete';

  function safeMessage(value, fallback = 'Operazione non riuscita.') {
    if (typeof window.messageFrom === 'function') return window.messageFrom(value, fallback);
    if (value instanceof Error) return value.message || fallback;
    return typeof value === 'string' ? value : fallback;
  }

  function ensureStatus() {
    let status = $('#authStatus');
    if (status) return status;
    status = document.createElement('p');
    status.id = 'authStatus';
    status.className = 'auth-status hidden';
    status.setAttribute('role', 'status');
    status.setAttribute('aria-live', 'polite');
    $('.segmented')?.insertAdjacentElement('afterend', status);
    return status;
  }

  function showStatus(message = '', error = false) {
    const status = ensureStatus();
    status.textContent = safeMessage(message, '');
    status.classList.toggle('hidden', !status.textContent);
    status.classList.toggle('error', Boolean(error));
  }

  function setPending(form, pending) {
    const button = form?.querySelector('button[type="submit"]');
    if (!button) return;
    if (!button.dataset.idleLabel) button.dataset.idleLabel = button.textContent;
    button.disabled = pending;
    button.textContent = pending ? 'Attendi…' : button.dataset.idleLabel;
  }

  function choose(mode) {
    const registerTab = $('#registerTab');
    const segmented = registerTab?.closest('.segmented');
    const login = mode === 'login';
    registerTab?.classList.toggle('hidden', login);
    segmented?.classList.toggle('single-option', login);
    (login ? $('#loginTab') : registerTab)?.click();
    if (login) {
      showStatus('Su questo computer esiste già uno spazio. Accedi con l’email e la password già create.');
      $('#loginEmail')?.focus();
    } else if (mode === 'create') {
      showStatus('Primo avvio: crea lo spazio locale e l’utente amministratore.');
      $('#organizationName')?.focus();
    } else {
      showStatus('Scegli Accedi se hai già creato lo spazio, oppure Crea spazio al primo utilizzo.');
    }
  }

  function initialMode() {
    try {
      if (localStorage.getItem(storageKey) === 'true') return 'login';
    } catch (_) { /* Private browser storage may be unavailable. */ }
    const requested = new URLSearchParams(window.location.search).get('local_setup');
    return ['create', 'login'].includes(requested) ? requested : 'choose';
  }

  const originalAuthenticate = window.authenticate;
  if (typeof originalAuthenticate === 'function') {
    window.authenticate = async function guidedAuthenticate(path, payload) {
      const form = path.includes('/register') ? $('#registerForm') : $('#loginForm');
      showStatus();
      setPending(form, true);
      try {
        const result = await originalAuthenticate(path, payload);
        try { localStorage.setItem(storageKey, 'true'); } catch (_) { /* Best effort only. */ }
        return result;
      } catch (error) {
        const message = safeMessage(error);
        showStatus(message, true);
        if (/già registrata|already registered|esiste già uno spazio/i.test(message)) choose('login');
        throw error;
      } finally {
        setPending(form, false);
      }
    };
  }

  $('#loginTab')?.addEventListener('click', () => {
    if (!$('#registerTab')?.classList.contains('hidden')) showStatus('Inserisci le credenziali dello spazio già creato.');
  });
  $('#registerTab')?.addEventListener('click', () => showStatus('Crea lo spazio soltanto al primo utilizzo su questo computer.'));
  $('#logoutButton')?.addEventListener('click', () => window.setTimeout(() => choose('login'), 0));

  choose(initialMode());
})();

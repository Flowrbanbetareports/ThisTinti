(() => {
  'use strict';

  const byId = (id) => document.getElementById(id);

  async function request(path) {
    const response = await fetch(path, { credentials: 'same-origin', headers: { Accept: 'application/json' } });
    const payload = response.headers.get('content-type')?.includes('application/json')
      ? await response.json()
      : await response.text();
    if (!response.ok) throw new Error(typeof payload === 'string' ? payload : payload.detail || `Errore ${response.status}`);
    return payload;
  }

  function renderPlans(plans) {
    const container = byId('planCards');
    container.replaceChildren(...plans.map((plan) => {
      const card = document.createElement('article');
      card.className = 'plan-card';
      const title = document.createElement('h3');
      title.textContent = plan.name;
      const state = document.createElement('div');
      state.className = 'plan-state';
      state.textContent = plan.availability.replaceAll('_', ' ');
      const list = document.createElement('ul');
      for (const feature of plan.features || []) {
        const item = document.createElement('li');
        item.textContent = feature;
        list.appendChild(item);
      }
      card.append(title, state, list);
      return card;
    }));
  }

  function renderCatalog(catalog) {
    renderPlans(catalog.plans || []);
    const list = byId('paymentRules');
    list.replaceChildren(...(catalog.payments?.future_checkout_rules || []).map((rule) => {
      const item = document.createElement('li');
      item.textContent = rule;
      return item;
    }));
  }

  async function start() {
    const notice = byId('accessNotice');
    try {
      const user = await request('/api/auth/me');
      if (user.role !== 'admin') throw new Error('Questa pagina è riservata agli amministratori dello spazio.');
      const catalog = await request('/api/commercial/catalog');
      renderCatalog(catalog);
      notice.textContent = `Sessione amministratore · ${user.organization || user.email}`;
      notice.className = 'commercial-notice ok';
      byId('commercialContent').classList.remove('hidden');
    } catch (error) {
      notice.textContent = error.message || 'Accesso non disponibile.';
      notice.className = 'commercial-notice error';
    }
  }

  start();
})();

(() => {
  'use strict';

  const $ = (selector, root = document) => root.querySelector(selector);
  let loading = false;

  function labelCaseType(value) {
    const labels = {
      return_without_credit: 'Reso senza nota di credito',
      credit_below_return: 'Accredito inferiore al reso',
      invoiced_over_received: 'Quantità fatturata superiore',
      price_over_order: 'Prezzo fatturato superiore',
      discount_missing: 'Sconto non applicato',
      unmatched_invoice_line: 'Riga fattura non collegata',
    };
    return labels[value] || String(value || '').replaceAll('_', ' ');
  }

  async function renderLearningSuggestions() {
    const center = $('#operationalCenter');
    if (!center || loading) return;
    loading = true;
    try {
      const suggestions = await api('/api/operational/learning-suggestions');
      let section = $('#operationalLearning', center);
      if (!section) {
        section = document.createElement('section');
        section.id = 'operationalLearning';
        section.className = 'operational-learning';
        center.appendChild(section);
      }
      if (!suggestions.length) {
        section.innerHTML = '<div class="learning-empty"><div><span class="practice-kicker">Apprendimento supervisionato</span><h3>Nessuna modifica proposta</h3><p>Servono almeno cinque decisioni umane sullo stesso controllo. ThisTinti non cambia soglie o regole autonomamente.</p></div><span class="badge">Prudente</span></div>';
        return;
      }
      section.innerHTML = `<div class="section-title-row"><div><span class="practice-kicker">Apprendimento supervisionato</span><h3>Controlli da rivedere</h3><p>Le proposte derivano dalle decisioni degli utenti e richiedono sempre approvazione.</p></div></div><div class="learning-grid">${suggestions.map(item => `<article class="learning-card"><div><span>${escapeHtml(labelCaseType(item.case_type))}</span><strong>${Math.round(item.dismissed_rate * 100)}% falsi positivi</strong><small>${item.sample_size} decisioni considerate</small></div><p>${escapeHtml(item.reason)}</p><div class="learning-card-footer"><span class="badge">Nessuna modifica automatica</span><button class="secondary-button compact" type="button" data-view-rules>Apri controlli proposti</button></div></article>`).join('')}</div>`;
      section.querySelectorAll('[data-view-rules]').forEach(button => button.addEventListener('click', () => openView('discovery')));
    } catch (error) {
      console.error('Suggerimenti supervisionati non disponibili', error);
    } finally {
      loading = false;
    }
  }

  const originalDashboard = window.loadDashboard;
  if (typeof originalDashboard === 'function') {
    window.loadDashboard = async function (...args) {
      const result = await originalDashboard.apply(this, args);
      await renderLearningSuggestions();
      return result;
    };
  }
  const observer = new MutationObserver(() => {
    if ($('#operationalCenter') && !$('#operationalLearning')) renderLearningSuggestions();
  });
  observer.observe(document.documentElement, { childList: true, subtree: true });
  renderLearningSuggestions();
})();

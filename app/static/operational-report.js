(() => {
  'use strict';

  const root = document.querySelector('#reportRoot');
  const generatedAt = document.querySelector('#reportGeneratedAt');
  const downloadButton = document.querySelector('#downloadReportJson');
  const printButton = document.querySelector('#printReport');
  let report = null;

  const escapeHtml = value => String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');

  const money = value => new Intl.NumberFormat('it-IT', {
    style: 'currency',
    currency: 'EUR',
  }).format(Number(value || 0));

  const number = value => value == null
    ? 'Non misurato'
    : new Intl.NumberFormat('it-IT', { maximumFractionDigits: 2 }).format(Number(value));

  function metric(label, value, note = '') {
    return `<article class="report-card"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong>${note ? `<small>${escapeHtml(note)}</small>` : ''}</article>`;
  }

  function render(payload) {
    report = payload;
    const metrics = payload.overview?.metrics || {};
    const review = payload.review || {};
    const availability = payload.measurement_availability || {};
    const suggestions = payload.learning_suggestions || [];
    generatedAt.textContent = `Generato ${new Date(payload.generated_at).toLocaleString('it-IT')}`;
    root.innerHTML = `
      <section class="report-grid">
        ${metric('Pratiche da controllare', metrics.practices_to_review || 0, `${metrics.active_cases || 0} segnalazioni attive`)}
        ${metric('Valore indicativo', money(metrics.amount_indicative || 0), metrics.amount_may_overlap ? 'Può contenere sovrapposizioni' : 'Somma delle segnalazioni')}
        ${metric('Collegamenti incompleti', metrics.incomplete_chains || 0)}
        ${metric('Segnalazioni con decisione', review.cases_with_decision || 0, `su ${review.total_cases || 0} totali`)}
        ${metric('Confermate o risolte', review.confirmed_or_resolved || 0)}
        ${metric('Falsi positivi registrati', review.false_positive_proxy || 0)}
      </section>
      <section class="report-section">
        <h2>Tempi e qualità della revisione</h2>
        <table class="report-table">
          <thead><tr><th>Misura</th><th>Valore disponibile</th></tr></thead>
          <tbody>
            <tr><td>Tempo medio fino alla prima decisione</td><td>${review.average_minutes_to_first_decision == null ? 'Non misurato' : `${number(review.average_minutes_to_first_decision)} minuti`}</td></tr>
            <tr><td>Tempo manuale prima di ThisTinti</td><td>${availability.manual_time_before == null ? 'Non misurato' : number(availability.manual_time_before)}</td></tr>
            <tr><td>Tempo assistito con ThisTinti</td><td>${availability.assisted_time_after == null ? 'Non misurato' : number(availability.assisted_time_after)}</td></tr>
            <tr><td>Falsi negativi conosciuti</td><td>${availability.known_false_negatives == null ? 'Non misurati' : number(availability.known_false_negatives)}</td></tr>
            <tr><td>Giudizio utilizzatori</td><td>${availability.user_score == null ? 'Non raccolto' : number(availability.user_score)}</td></tr>
          </tbody>
        </table>
        <p class="report-note">${escapeHtml(availability.note || 'Le misure non disponibili richiedono un pilot umano autorizzato.')}</p>
      </section>
      <section class="report-section">
        <h2>Apprendimento supervisionato</h2>
        ${suggestions.length ? `<table class="report-table"><thead><tr><th>Controllo</th><th>Campione</th><th>Falsi positivi</th><th>Proposta</th></tr></thead><tbody>${suggestions.map(item => `<tr><td>${escapeHtml(item.case_type)}</td><td>${item.sample_size}</td><td>${Math.round(item.dismissed_rate * 100)}%</td><td>${escapeHtml(item.proposal)}</td></tr>`).join('')}</tbody></table>` : '<p>Nessuna modifica proposta: non esiste ancora un campione sufficiente di decisioni umane.</p>'}
      </section>
      <p class="report-boundary">${escapeHtml(payload.claim_boundary || '')}</p>`;
  }

  function downloadJson() {
    if (!report) return;
    const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `ThisTinti-rapporto-operativo-${new Date().toISOString().slice(0, 10)}.json`;
    link.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  async function load() {
    try {
      const response = await fetch('/api/operational/report', {
        credentials: 'same-origin',
        headers: { Accept: 'application/json' },
      });
      if (!response.ok) throw new Error(`Rapporto non disponibile (${response.status})`);
      render(await response.json());
    } catch (error) {
      generatedAt.textContent = 'Rapporto non disponibile';
      root.innerHTML = `<p class="report-error">${escapeHtml(error.message)}</p>`;
    }
  }

  downloadButton.addEventListener('click', downloadJson);
  printButton.addEventListener('click', () => window.print());
  load();
})();

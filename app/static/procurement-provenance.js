(() => {
  'use strict';

  viewMeta.procurementProvenance = ['Procurement', 'Provenance Procurement'];
  operationalViews.add('procurementProvenance');

  function statusLabel(value) {
    return ({
      complete: 'Completa',
      incomplete: 'Incompleta',
      unsupported: 'Non supportata',
    })[value] || value;
  }

  function ensureShell() {
    if ($('#procurementProvenanceView')) return;

    const nav = document.createElement('button');
    nav.type = 'button';
    nav.dataset.view = 'procurementProvenance';
    nav.innerHTML = '<span>⛓</span> Provenance Procurement';
    const validationButton = $('#mainNav [data-view="validation"]');
    $('#mainNav').insertBefore(nav, validationButton || null);

    const view = document.createElement('div');
    view.id = 'procurementProvenanceView';
    view.className = 'view-panel hidden';
    view.innerHTML = '<div id="procurementProvenanceBody" class="empty-state">Caricamento…</div>';
    document.querySelector('.workspace').appendChild(view);

    nav.addEventListener('click', () => loadMatrix().catch(error => toast(error.message, true)));
  }

  async function loadMatrix() {
    ensureShell();
    const body = $('#procurementProvenanceBody');
    body.innerHTML = '<div class="empty-state">Aggiornamento matrice…</div>';
    const matrix = await api('/api/rc15/procurement/provenance-matrix');
    const completeRules = matrix.rules.filter(rule => rule.provenance_status === 'complete').length;
    const incompleteRules = matrix.rules.filter(rule => rule.provenance_status === 'incomplete').length;
    const unsupportedFamilies = matrix.families.filter(family => family.provenance_status === 'unsupported').length;
    const ready = matrix.blind_readiness?.ready === true;

    body.innerHTML = `
      <section class="panel">
        <div class="panel-heading">
          <div>
            <p class="eyebrow">Procurement · Rule Pack ${escapeHtml(matrix.rule_pack_version)}</p>
            <h3>Copertura di provenance del pilot</h3>
            <p>Un finding prodotto dal motore non è automaticamente un finding qualificato. Questa matrice separa ciò che esiste da ciò che ha una catena DOCUMENTO → FACT → FINDING → GIUDIZIO completa.</p>
          </div>
          <span class="badge ${ready ? 'confirmed' : 'needs_review'}">${ready ? 'Blind pronto' : 'Blind non pronto'}</span>
        </div>
        <div class="metric-grid">
          <article class="metric-card"><p>Regole mappate</p><strong>${matrix.rules.length}</strong><small>Rule Pack ${escapeHtml(matrix.rule_pack_version)}</small></article>
          <article class="metric-card"><p>Provenance completa</p><strong>${completeRules}</strong><small>qualificate end-to-end</small></article>
          <article class="metric-card"><p>Provenance incompleta</p><strong>${incompleteRules}</strong><small>bloccanti per il blind</small></article>
          <article class="metric-card"><p>Famiglie non supportate</p><strong>${unsupportedFamilies}</strong><small>nessuna regola motore</small></article>
        </div>
      </section>
      <section class="panel table-panel">
        <div class="panel-heading"><div><h3>Famiglie del Rule Pack</h3><p>Lo stato di una famiglia è completo soltanto quando tutte le sue regole lo sono.</p></div></div>
        <div class="table-wrap"><table><thead><tr><th>Famiglia</th><th>Stato</th><th>Regole</th><th>Complete</th></tr></thead><tbody>
          ${matrix.families.map(family => `<tr><td><strong>${escapeHtml(family.id)}</strong></td><td><span class="badge">${escapeHtml(statusLabel(family.provenance_status))}</span></td><td>${family.rule_count}</td><td>${family.complete_rule_count}</td></tr>`).join('')}
        </tbody></table></div>
      </section>
      <section class="panel table-panel">
        <div class="panel-heading"><div><h3>Regole effettive</h3><p>Le regole incomplete possono essere osservate in calibrazione, ma non sostengono una dichiarazione di accuratezza del blind pilot.</p></div></div>
        <div class="table-wrap"><table><thead><tr><th>Case type</th><th>Famiglia</th><th>Provenance</th><th>Blind</th></tr></thead><tbody>
          ${matrix.rules.map(rule => `<tr><td><strong>${escapeHtml(rule.case_type)}</strong><small>${escapeHtml(rule.evidence)}</small></td><td>${escapeHtml(rule.family)}</td><td><span class="badge">${escapeHtml(statusLabel(rule.provenance_status))}</span></td><td>${rule.blind_eligible ? 'Qualificata' : 'Bloccata'}</td></tr>`).join('')}
        </tbody></table></div>
      </section>
      <section class="panel">
        <h3>Confine della prova</h3>
        <p>${escapeHtml(matrix.blind_readiness.policy)}</p>
        ${matrix.blind_readiness.blocking_case_types.length ? `<p><strong>Regole bloccanti:</strong> ${matrix.blind_readiness.blocking_case_types.map(escapeHtml).join(', ')}</p>` : ''}
        ${matrix.blind_readiness.unsupported_families.length ? `<p><strong>Famiglie non ancora implementate:</strong> ${matrix.blind_readiness.unsupported_families.map(escapeHtml).join(', ')}</p>` : ''}
      </section>`;
  }

  ensureShell();
})();

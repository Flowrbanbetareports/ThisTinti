(() => {
  'use strict';

  viewMeta.procurementProvenance = ['Procurement', 'Provenance Procurement'];
  operationalViews.add('procurementProvenance');

  function statusLabel(value) {
    return ({
      complete: 'Completa',
      incomplete: 'Incompleta',
      unsupported: 'Non supportata',
      included: 'Nel target',
      excluded: 'Fuori pilot',
      mixed: 'Mista',
      'calibration-provisional': 'Provvisorio · calibrazione',
      'approved-for-blind': 'Approvato per blind',
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
    const includedRules = matrix.rules.filter(rule => rule.blind_scope === 'included').length;
    const excludedRules = matrix.rules.filter(rule => rule.blind_scope === 'excluded').length;
    const ready = matrix.blind_readiness?.ready === true;
    const targetStatus = matrix.blind_readiness?.target_status || matrix.blind_target?.status || '';

    body.innerHTML = `
      <section class="panel">
        <div class="panel-heading">
          <div>
            <p class="eyebrow">Procurement · Rule Pack ${escapeHtml(matrix.rule_pack_version)}</p>
            <h3>Copertura di provenance del pilot</h3>
            <p>Il Rule Pack decide il Target blind. La matrice mostra separatamente scope e qualificazione probatoria, senza trasformare una regola esclusa in una regola “superata”.</p>
          </div>
          <span class="badge ${ready ? 'confirmed' : 'needs_review'}">${ready ? 'Blind pronto' : 'Blind non pronto'}</span>
        </div>
        <div class="metric-grid">
          <article class="metric-card"><p>Target blind</p><strong>${includedRules}</strong><small>${escapeHtml(statusLabel(targetStatus))}</small></article>
          <article class="metric-card"><p>Fuori pilot</p><strong>${excludedRules}</strong><small>visibili, non bloccanti</small></article>
          <article class="metric-card"><p>Provenance completa</p><strong>${completeRules}</strong><small>qualificate end-to-end</small></article>
          <article class="metric-card"><p>Provenance incompleta</p><strong>${incompleteRules}</strong><small>bloccanti solo se nel target</small></article>
        </div>
      </section>
      <section class="panel table-panel">
        <div class="panel-heading"><div><h3>Famiglie del Rule Pack</h3><p>Una famiglia può restare non supportata senza bloccare il blind soltanto se il Rule Pack la esclude esplicitamente.</p></div></div>
        <div class="table-wrap"><table><thead><tr><th>Famiglia</th><th>Scope</th><th>Provenance</th><th>Nel target</th></tr></thead><tbody>
          ${matrix.families.map(family => `<tr><td><strong>${escapeHtml(family.id)}</strong>${family.exclusion_reason ? `<small>Motivo esclusione: ${escapeHtml(family.exclusion_reason)}</small>` : ''}</td><td><span class="badge">${escapeHtml(statusLabel(family.blind_scope))}</span></td><td><span class="badge">${escapeHtml(statusLabel(family.provenance_status))}</span></td><td>${family.blind_included_rule_count ?? 0}</td></tr>`).join('')}
        </tbody></table></div>
      </section>
      <section class="panel table-panel">
        <div class="panel-heading"><div><h3>Regole effettive</h3><p>Blind eligible è derivato: una regola deve essere sia nel target sia completa.</p></div></div>
        <div class="table-wrap"><table><thead><tr><th>Case type</th><th>Famiglia</th><th>Scope</th><th>Provenance</th><th>Blind</th></tr></thead><tbody>
          ${matrix.rules.map(rule => `<tr><td><strong>${escapeHtml(rule.case_type)}</strong><small>${escapeHtml(rule.evidence)}</small>${rule.exclusion_reason ? `<small>Motivo esclusione: ${escapeHtml(rule.exclusion_reason)}</small>` : ''}</td><td>${escapeHtml(rule.family)}</td><td><span class="badge">${escapeHtml(statusLabel(rule.blind_scope))}</span></td><td><span class="badge">${escapeHtml(statusLabel(rule.provenance_status))}</span></td><td>${rule.blind_scope === 'excluded' ? 'Fuori pilot' : (rule.blind_eligible ? 'Qualificata' : 'Bloccante')}</td></tr>`).join('')}
        </tbody></table></div>
      </section>
      <section class="panel">
        <h3>Confine della prova</h3>
        <p>${escapeHtml(matrix.blind_readiness.policy)}</p>
        <p><strong>Target blind:</strong> ${escapeHtml(statusLabel(targetStatus))}</p>
        ${matrix.blind_readiness.blocking_case_types.length ? `<p><strong>Regole bloccanti nel target:</strong> ${matrix.blind_readiness.blocking_case_types.map(escapeHtml).join(', ')}</p>` : ''}
        ${(matrix.blind_readiness.unsupported_included_families || []).length ? `<p><strong>Famiglie non supportate nel target:</strong> ${matrix.blind_readiness.unsupported_included_families.map(escapeHtml).join(', ')}</p>` : ''}
      </section>`;
  }

  ensureShell();
})();

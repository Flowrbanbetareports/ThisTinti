(() => {
  'use strict';

  const rc15 = {
    intake: [],
    cases: [],
    practices: [],
    chains: [],
    pilots: [],
    profile: null,
    panel: 'intake',
  };

  viewMeta.rc15 = ['Pilot-Ready', 'Centro RC15'];
  operationalViews.add('rc15');

  function ensureShell() {
    if ($('#rc15View')) return;
    const nav = document.createElement('button');
    nav.type = 'button';
    nav.dataset.view = 'rc15';
    nav.innerHTML = '<span>▣</span> Centro RC15';
    const validationButton = $('#mainNav [data-view="validation"]');
    $('#mainNav').insertBefore(nav, validationButton || null);

    const view = document.createElement('div');
    view.id = 'rc15View';
    view.className = 'view-panel hidden rc15-view';
    view.innerHTML = `
      <section class="rc15-hero panel">
        <div>
          <p class="eyebrow">RC15 · Pilot-Ready</p>
          <h3>Dalla pratica al risultato verificabile</h3>
          <p>Acquisizione trasparente, decisioni motivate, importi non inventati, profili versionati e pilot congelabili.</p>
        </div>
        <div id="rc15ReleaseBadge" class="rc15-release-badge">RC15</div>
      </section>
      <nav id="rc15Tabs" class="rc15-tabs" aria-label="Sezioni RC15">
        <button type="button" data-rc15-panel="intake" class="active">Acquisizione</button>
        <button type="button" data-rc15-panel="cases">Segnalazioni</button>
        <button type="button" data-rc15-panel="practices">Pratiche</button>
        <button type="button" data-rc15-panel="pilots">Pilot</button>
        <button type="button" data-rc15-panel="profile">Profilo aziendale</button>
      </nav>
      <div id="rc15Body" class="rc15-body"><div class="empty-state">Caricamento…</div></div>`;
    document.querySelector('.workspace').appendChild(view);

    const dialog = document.createElement('dialog');
    dialog.id = 'rc15Dialog';
    dialog.className = 'modal-card rc15-dialog';
    dialog.innerHTML = '<div id="rc15DialogContent"></div>';
    document.body.appendChild(dialog);

    $('#rc15Tabs').addEventListener('click', event => {
      const button = event.target.closest('[data-rc15-panel]');
      if (!button) return;
      rc15.panel = button.dataset.rc15Panel;
      $('#rc15Tabs').querySelectorAll('button').forEach(item => item.classList.toggle('active', item === button));
      loadRC15Panel().catch(error => toast(error.message, true));
    });

    $('#mainNav').addEventListener('click', event => {
      const button = event.target.closest('[data-view="rc15"]');
      if (button) loadRC15Panel().catch(error => toast(error.message, true));
    });
  }

  function modal(title, body, { wide = false } = {}) {
    const dialog = $('#rc15Dialog');
    dialog.classList.toggle('wide', wide);
    $('#rc15DialogContent').innerHTML = `
      <div class="modal-heading"><div><p class="eyebrow">RC15</p><h3>${escapeHtml(title)}</h3></div><button class="icon-button" id="rc15DialogClose" type="button" aria-label="Chiudi">×</button></div>
      ${body}`;
    $('#rc15DialogClose').addEventListener('click', () => dialog.close());
    dialog.showModal();
    return dialog;
  }

  function rc15StatusLabel(value) {
    return ({
      acquired: 'Acquisito', review_required: 'Da verificare', not_acquired: 'Non acquisito', blocked: 'Bloccato', out_of_scope: 'Fuori ambito',
      draft: 'Preparazione', frozen: 'Ground truth congelata', running: 'In esecuzione', completed: 'Completato', archived: 'Archiviato', deleted: 'Eliminato', active: 'Attiva',
    })[value] || labelStatus(value);
  }

  function classificationBadge(item) {
    const stateName = item?.classification?.state || 'review_required';
    return `<span class="badge rc15-state-${escapeHtml(stateName)}">${escapeHtml(rc15StatusLabel(stateName))}</span>`;
  }

  function downloadBlob(response, fallbackName) {
    return response.blob().then(blob => {
      const disposition = response.headers.get('content-disposition') || '';
      const filename = disposition.match(/filename="?([^";]+)"?/i)?.[1] || fallbackName;
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    });
  }

  async function loadRC15Panel() {
    ensureShell();
    const body = $('#rc15Body');
    body.innerHTML = '<div class="empty-state">Aggiornamento…</div>';
    if (rc15.panel === 'intake') return loadIntake();
    if (rc15.panel === 'cases') return loadRC15Cases();
    if (rc15.panel === 'practices') return loadPractices();
    if (rc15.panel === 'pilots') return loadPilots();
    return loadProfile();
  }

  async function loadIntake() {
    rc15.intake = await api('/api/rc15/intake?include_success=true');
    const counts = { acquired: 0, review_required: 0, not_acquired: 0, blocked: 0, out_of_scope: 0 };
    rc15.intake.forEach(item => { const key = item.classification?.state; if (key in counts) counts[key] += 1; });
    $('#rc15Body').innerHTML = `
      <section class="metric-grid rc15-metrics">
        <article class="metric-card"><p>Acquisiti</p><strong>${counts.acquired}</strong><small>letti normalmente</small></article>
        <article class="metric-card"><p>Da verificare</p><strong>${counts.review_required}</strong><small>estrazione non definitiva</small></article>
        <article class="metric-card"><p>Non acquisiti</p><strong>${counts.not_acquired}</strong><small>restano visibili</small></article>
        <article class="metric-card"><p>Bloccati / fuori ambito</p><strong>${counts.blocked + counts.out_of_scope}</strong><small>separati dai difetti parser</small></article>
      </section>
      <section class="panel table-panel">
        <div class="panel-heading"><div><h3>Centro acquisizione</h3><p>Ogni file resta tracciato con fase, categoria e motivo. Un errore non scompare dal risultato.</p></div><button id="rc15IntakeRefresh" class="secondary-button compact" type="button">Aggiorna</button></div>
        <div class="table-wrap"><table><thead><tr><th>Documento / attività</th><th>Esito</th><th>Fase</th><th>Motivo</th><th>Azioni</th></tr></thead><tbody id="rc15IntakeTable"></tbody></table></div>
      </section>`;
    $('#rc15IntakeRefresh').addEventListener('click', loadIntake);
    const table = $('#rc15IntakeTable');
    if (!rc15.intake.length) {
      table.innerHTML = '<tr><td colspan="5" class="empty-state">Nessun elemento acquisito.</td></tr>';
      return;
    }
    table.innerHTML = rc15.intake.map((item, index) => `
      <tr data-intake-index="${index}">
        <td><strong>${escapeHtml(item.filename || '—')}</strong><small>${item.document_type ? labelType(item.document_type) : item.subject_type === 'job' ? 'Attività di acquisizione' : 'Documento'}</small></td>
        <td>${classificationBadge(item)}<small>${escapeHtml(item.classification?.category || '—')}</small></td>
        <td>${escapeHtml(item.classification?.phase || '—')}</td>
        <td><span class="rc15-reason">${escapeHtml(item.classification?.reason || '—')}</span></td>
        <td><div class="row-actions">${item.can_retry && item.document_id ? `<button type="button" class="secondary-button compact rc15-retry" data-id="${item.document_id}">Riprova</button>` : ''}${['admin','reviewer'].includes(state.user?.role) ? `<button type="button" class="secondary-button compact rc15-classify" data-index="${index}">Classifica</button>` : ''}</div></td>
      </tr>`).join('');
    table.querySelectorAll('.rc15-classify').forEach(button => button.addEventListener('click', () => openIntakeClassification(rc15.intake[Number(button.dataset.index)])));
    table.querySelectorAll('.rc15-retry').forEach(button => button.addEventListener('click', () => retryIntake(button.dataset.id, button)));
  }

  function openIntakeClassification(item) {
    const current = item.classification || {};
    const dialog = modal(`Classifica · ${item.filename}`, `
      <form id="rc15ClassifyForm" class="form-stack">
        <div class="form-grid two"><div><label for="rc15IntakeState">Esito</label><select id="rc15IntakeState"><option value="acquired">Acquisito</option><option value="review_required">Da verificare</option><option value="not_acquired">Non acquisito</option><option value="blocked">Bloccato</option><option value="out_of_scope">Fuori ambito</option></select></div>
        <div><label for="rc15IntakeCategory">Categoria</label><select id="rc15IntakeCategory"><option value="ok">Regolare</option><option value="degraded">Degradato / OCR</option><option value="hostile">Ostile</option><option value="out_of_scope">Fuori ambito</option><option value="parser_limit">Limite parser</option><option value="operator_input">Richiede operatore</option><option value="security_block">Blocco sicurezza</option></select></div></div>
        <div><label for="rc15IntakePhase">Fase</label><input id="rc15IntakePhase" maxlength="80" value="${escapeHtml(current.phase || '')}" placeholder="OCR, parsing, classificazione…" /></div>
        <div><label for="rc15IntakeReason">Motivo verificabile</label><textarea id="rc15IntakeReason" required minlength="3" maxlength="3000">${escapeHtml(current.reason || '')}</textarea></div>
        <div><label for="rc15IntakeNote">Nota operatore</label><textarea id="rc15IntakeNote" maxlength="3000">${escapeHtml(current.note || '')}</textarea></div>
        <div class="modal-actions"><button class="secondary-button" type="button" id="rc15ClassifyCancel">Annulla</button><button class="primary-button" type="submit">Salva classificazione</button></div>
      </form>`);
    $('#rc15IntakeState').value = current.state || 'not_acquired';
    $('#rc15IntakeCategory').value = current.category || 'parser_limit';
    $('#rc15ClassifyCancel').addEventListener('click', () => dialog.close());
    $('#rc15ClassifyForm').addEventListener('submit', async event => {
      event.preventDefault();
      try {
        await api(`/api/rc15/intake/${item.subject_type}/${item.subject_id}/classify`, {
          method: 'POST',
          body: JSON.stringify({
            state: $('#rc15IntakeState').value,
            category: $('#rc15IntakeCategory').value,
            phase: $('#rc15IntakePhase').value.trim() || null,
            reason: $('#rc15IntakeReason').value.trim(),
            note: $('#rc15IntakeNote').value.trim() || null,
          }),
        });
        dialog.close(); toast('Classificazione registrata.'); await loadIntake();
      } catch (error) { toast(error.message, true); }
    });
  }

  async function retryIntake(documentId, button) {
    button.disabled = true;
    try {
      await api(`/api/rc15/intake/documents/${documentId}/retry`, { method: 'POST', body: '{}' });
      toast('Rielaborazione completata.');
    } catch (error) { toast(error.message, true); }
    finally { button.disabled = false; await loadIntake(); }
  }

  async function loadRC15Cases() {
    rc15.cases = await api('/api/cases');
    $('#rc15Body').innerHTML = `
      <section class="panel table-panel">
        <div class="panel-heading"><div><h3>Ciclo completo delle segnalazioni</h3><p>Gravità tecnica, confidenza e impatto economico restano concetti separati. Ogni transizione RC15 richiede una motivazione.</p></div></div>
        <div class="table-wrap"><table><thead><tr><th>Segnalazione</th><th>Gravità</th><th>Confidenza</th><th>Stato</th><th>Impatto</th></tr></thead><tbody id="rc15CasesTable"></tbody></table></div>
      </section>`;
    const table = $('#rc15CasesTable');
    if (!rc15.cases.length) { table.innerHTML = '<tr><td colspan="5" class="empty-state">Nessuna segnalazione.</td></tr>'; return; }
    table.innerHTML = rc15.cases.map(item => `
      <tr data-case-id="${item.id}" tabindex="0">
        <td><strong>${escapeHtml(item.title)}</strong><small>${escapeHtml(item.case_type)}</small></td>
        <td><span class="badge ${item.severity}">${labelSeverity(item.severity)}</span></td>
        <td>${Math.round(Number(item.confidence || 0) * 100)}%</td>
        <td><span class="badge ${item.status}">${labelStatus(item.status)}</span></td>
        <td><button class="secondary-button compact" type="button">Apri</button></td>
      </tr>`).join('');
    table.querySelectorAll('[data-case-id]').forEach(row => {
      const open = () => openRC15Case(row.dataset.caseId);
      row.addEventListener('click', open);
      row.addEventListener('keydown', event => { if (event.key === 'Enter') open(); });
    });
  }

  async function openRC15Case(caseId) {
    const item = await api(`/api/rc15/cases/${caseId}`);
    const econ = item.economic || {};
    const canReview = ['admin','reviewer'].includes(state.user?.role);
    const actions = (item.allowed_actions || []).map(action => `<button type="button" class="secondary-button rc15-case-action" data-action="${action}">${({confirmed:'Conferma',dismissed:'Falso positivo',resolved:'Risolvi',needs_review:'Prendi in carico',reopen:'Riapri'})[action] || action}</button>`).join('');
    const dialog = modal(item.title, `
      <div class="rc15-case-grid">
        <section class="detail-section"><h4>Valutazione tecnica</h4><div class="detail-grid"><div class="detail-card"><p>Gravità</p><strong>${labelSeverity(item.severity)}</strong></div><div class="detail-card"><p>Confidenza</p><strong>${Math.round(item.confidence * 100)}%</strong></div><div class="detail-card"><p>Stato</p><strong>${labelStatus(item.status)}</strong></div></div><p>${escapeHtml(item.explanation)}</p></section>
        <section class="detail-section"><h4>Impatto economico</h4><div class="detail-grid"><div class="detail-card"><p>Potenzialmente coinvolto</p><strong>${econ.potential_exposure === null ? 'Sconosciuto' : money(econ.potential_exposure)}</strong></div><div class="detail-card"><p>Perdita confermata</p><strong>${econ.confirmed_loss === null ? 'Sconosciuta' : money(econ.confirmed_loss)}</strong></div></div><small>L’importo storico del motore (${moneyOrDash(item.legacy_amount_estimate)}) resta indicativo e non equivale a una perdita confermata.</small></section>
        ${canReview ? `<form id="rc15EconomicForm" class="detail-section form-stack"><h4>Aggiorna impatto</h4><div class="form-grid two"><div><label>Importo potenziale</label><input id="rc15PotentialExposure" type="number" min="0" step="0.01" value="${econ.potential_exposure ?? ''}" placeholder="Sconosciuto" /></div><div><label>Perdita confermata</label><input id="rc15ConfirmedLoss" type="number" min="0" step="0.01" value="${econ.confirmed_loss ?? ''}" placeholder="Sconosciuta" /></div></div><div><label>Motivazione</label><textarea id="rc15EconomicNote" required minlength="3">${escapeHtml(econ.note || '')}</textarea></div><button class="primary-button" type="submit">Registra impatto</button></form>` : ''}
        <section class="detail-section"><h4>Cronologia decisioni</h4>${item.history.length ? item.history.map(entry => `<div class="rc15-history"><strong>${labelStatus(entry.decision)}</strong><span>${dateTime(entry.created_at)}</span><p>${escapeHtml(entry.note || '—')}</p></div>`).join('') : '<p class="empty-state">Nessuna decisione umana registrata.</p>'}</section>
      </div>
      ${canReview && actions ? `<div class="rc15-transition-box"><label for="rc15TransitionNote">Motivazione della decisione</label><textarea id="rc15TransitionNote" minlength="3" placeholder="Perché stai cambiando lo stato?"></textarea><div class="modal-actions">${actions}</div></div>` : ''}`, { wide: true });
    if (canReview && $('#rc15EconomicForm')) {
      $('#rc15EconomicForm').addEventListener('submit', async event => {
        event.preventDefault();
        const parse = id => { const raw = $(id).value.trim(); return raw === '' ? null : Number(raw); };
        try {
          await api(`/api/rc15/cases/${caseId}/economic`, { method: 'PUT', body: JSON.stringify({ potential_exposure: parse('#rc15PotentialExposure'), confirmed_loss: parse('#rc15ConfirmedLoss'), currency: 'EUR', note: $('#rc15EconomicNote').value.trim() }) });
          dialog.close(); toast('Impatto economico registrato.'); await loadRC15Cases(); await openRC15Case(caseId);
        } catch (error) { toast(error.message, true); }
      });
      dialog.querySelectorAll('.rc15-case-action').forEach(button => button.addEventListener('click', async () => {
        const note = $('#rc15TransitionNote').value.trim();
        if (note.length < 3) { toast('Inserisci una motivazione prima della decisione.', true); return; }
        try {
          await api(`/api/rc15/cases/${caseId}/transition`, { method: 'POST', body: JSON.stringify({ action: button.dataset.action, note }) });
          dialog.close(); toast('Decisione registrata.'); await Promise.all([loadRC15Cases(), loadDashboard(), loadCases()]);
        } catch (error) { toast(error.message, true); }
      }));
    }
  }

  async function loadProfile() {
    const [current, versions] = await Promise.all([api('/api/rc15/company-profile'), api('/api/rc15/company-profile/versions')]);
    rc15.profile = current.active;
    const profile = current.active?.config || {};
    $('#rc15Body').innerHTML = `
      <div class="rc15-two-column">
        <section class="panel"><div class="panel-heading"><div><h3>Profilo aziendale v${current.active?.version || '—'}</h3><p>Ogni modifica crea una nuova versione; le pratiche restano legate alla versione usata.</p></div></div>
          ${state.user?.role === 'admin' ? `<form id="rc15ProfileForm" class="form-stack"><div><label>Nome versione</label><input id="rc15ProfileLabel" required minlength="2" value="${escapeHtml(current.active?.label || 'Profilo aziendale')}" /></div><div class="form-grid two"><div><label>Valuta predefinita</label><input id="rc15ProfileCurrency" maxlength="8" value="${escapeHtml(profile.default_currency || 'EUR')}" /></div><div><label>Decimali arrotondamento</label><input id="rc15ProfileDecimals" type="number" min="0" max="6" value="${profile.rounding_decimals ?? 2}" /></div><div><label>Tolleranza prezzo %</label><input id="rc15ProfilePriceTolerance" type="number" min="0" max="100" step="0.01" value="${profile.price_tolerance_percent ?? 1}" /></div><div><label>Tolleranza quantità %</label><input id="rc15ProfileQtyTolerance" type="number" min="0" max="100" step="0.01" value="${profile.quantity_tolerance_percent ?? 0}" /></div></div><div><label>Termini commercialmente significativi</label><textarea id="rc15ProfileTerms" placeholder="uno per riga">${escapeHtml((profile.significant_terms || []).join('\n'))}</textarea><small>Per esempio: black, white, warranty. I numeri e le unità sono già rilevati automaticamente.</small></div><button class="primary-button" type="submit">Crea nuova versione</button></form>` : '<p>Solo un amministratore può creare una nuova versione.</p>'}
        </section>
        <section class="panel"><div class="panel-heading"><div><h3>Versioni</h3><p>Hash immutabile della configurazione.</p></div></div><div class="list-stack">${versions.length ? versions.map(item => `<div class="rc15-version-row"><div><strong>v${item.version} · ${escapeHtml(item.label)}</strong><small>${escapeHtml(item.config_hash.slice(0, 16))}… · ${dateTime(item.created_at)}</small></div><span class="badge ${item.active ? 'parsed' : 'dismissed'}">${item.active ? 'Attiva' : 'Storica'}</span></div>`).join('') : '<div class="empty-state">Nessuna versione.</div>'}</div></section>
      </div>`;
    if ($('#rc15ProfileForm')) $('#rc15ProfileForm').addEventListener('submit', saveProfile);
  }

  async function saveProfile(event) {
    event.preventDefault();
    const previousAliases = rc15.profile?.config?.unit_aliases || {};
    try {
      const result = await api('/api/rc15/company-profile/versions', {
        method: 'POST',
        body: JSON.stringify({
          label: $('#rc15ProfileLabel').value.trim(),
          config: {
            default_currency: $('#rc15ProfileCurrency').value.trim().toUpperCase(),
            rounding_decimals: Number($('#rc15ProfileDecimals').value),
            price_tolerance_percent: Number($('#rc15ProfilePriceTolerance').value),
            quantity_tolerance_percent: Number($('#rc15ProfileQtyTolerance').value),
            unit_aliases: previousAliases,
            significant_terms: $('#rc15ProfileTerms').value.split(/\n+/).map(item => item.trim()).filter(Boolean),
          },
        }),
      });
      toast(result.created ? `Profilo v${result.profile.version} creato.` : 'Configurazione già esistente: versione riattivata.');
      await loadProfile();
    } catch (error) { toast(error.message, true); }
  }

  async function loadPractices() {
    [rc15.practices, rc15.chains] = await Promise.all([api('/api/rc15/practices'), api('/api/chains')]);
    const practicedChains = new Set(rc15.practices.map(item => item.chain_id).filter(Boolean));
    const available = rc15.chains.filter(chain => !practicedChains.has(chain.id));
    $('#rc15Body').innerHTML = `
      <section class="panel table-panel">
        <div class="panel-heading"><div><h3>Pratiche</h3><p>Una pratica congela il profilo usato e raccoglie documenti, segnalazioni, prove e differenze testuali.</p></div>${['admin','reviewer'].includes(state.user?.role) && available.length ? `<select id="rc15NewPracticeChain"><option value="">Crea da collegamento…</option>${available.map(chain => `<option value="${chain.id}">${escapeHtml(chain.reference_key || chain.id.slice(0, 8))}</option>`).join('')}</select>` : ''}</div>
        <div class="table-wrap"><table><thead><tr><th>Pratica</th><th>Stato</th><th>Documenti</th><th>Segnalazioni</th><th>Profilo</th><th>Conservazione</th></tr></thead><tbody id="rc15PracticesTable"></tbody></table></div>
      </section>`;
    if ($('#rc15NewPracticeChain')) $('#rc15NewPracticeChain').addEventListener('change', async event => {
      const chainId = event.target.value; if (!chainId) return;
      try { await api(`/api/rc15/practices/from-chain/${chainId}`, { method: 'POST', body: '{}' }); toast('Pratica creata.'); await loadPractices(); }
      catch (error) { toast(error.message, true); event.target.value = ''; }
    });
    const table = $('#rc15PracticesTable');
    if (!rc15.practices.length) { table.innerHTML = '<tr><td colspan="6" class="empty-state">Nessuna pratica. Crea prima una catena documentale e poi trasformala in pratica.</td></tr>'; return; }
    table.innerHTML = rc15.practices.map(item => `<tr data-practice-id="${item.id}" tabindex="0"><td><strong>${escapeHtml(item.reference_key || item.id.slice(0,8))}</strong><small>${item.text_differences?.length || 0} differenze strutturate</small></td><td><span class="badge ${item.status === 'active' ? 'parsed' : 'dismissed'}">${rc15StatusLabel(item.status)}</span></td><td>${item.documents.length}</td><td>${item.cases.length}</td><td>v${item.profile?.version || '—'}</td><td>${item.retention_end ? escapeHtml(item.retention_end) : 'Non impostata'}${item.retention_expired ? '<small class="danger-text">Scaduta: revisione richiesta</small>' : ''}</td></tr>`).join('');
    table.querySelectorAll('[data-practice-id]').forEach(row => row.addEventListener('click', () => openPractice(row.dataset.practiceId)));
  }

  async function openPractice(practiceId) {
    const item = await api(`/api/rc15/practices/${practiceId}`);
    const canReview = ['admin','reviewer'].includes(state.user?.role);
    const isAdmin = state.user?.role === 'admin';
    const differences = item.text_differences || [];
    const dialog = modal(`Pratica · ${item.reference_key || item.id.slice(0,8)}`, `
      <div class="detail-grid"><div class="detail-card"><p>Stato</p><strong>${rc15StatusLabel(item.status)}</strong></div><div class="detail-card"><p>Profilo</p><strong>v${item.profile?.version || '—'}</strong></div><div class="detail-card"><p>Documenti</p><strong>${item.documents.length}</strong></div><div class="detail-card"><p>Segnalazioni</p><strong>${item.cases.length}</strong></div></div>
      <section class="detail-section"><h4>Documenti</h4>${item.documents.map(doc => `<div class="rc15-document-row"><div><span class="badge ${doc.parse_status}">${labelType(doc.role)}</span><strong>${escapeHtml(doc.number || doc.filename)}</strong><small>${escapeHtml(doc.filename)} · ${Math.round(doc.confidence * 100)}%</small></div><button class="secondary-button compact rc15-open-original" data-document-id="${doc.id}" type="button">Originale</button></div>`).join('') || '<p class="empty-state">Nessun documento.</p>'}</section>
      <section class="detail-section"><h4>Differenze strutturate</h4>${differences.length ? differences.map(diff => `<article class="rc15-difference"><strong>${diff.kind === 'commercial_text' ? 'Descrizione commerciale' : escapeHtml(diff.field)}</strong><small>${escapeHtml(diff.group)}</small><div>${diff.values.map(value => `<p><b>${labelType(value.role)}</b> ${escapeHtml(value.value ?? value.description ?? (value.tokens || []).join(', '))}</p>`).join('')}</div></article>`).join('') : '<p class="empty-state">Nessuna differenza deterministica rilevata.</p>'}</section>
      <div class="modal-actions rc15-practice-actions"><button class="secondary-button" id="rc15PracticeExport" type="button">Esporta fascicolo</button>${canReview ? `<button class="secondary-button" id="rc15PracticeArchive" type="button">${item.status === 'archived' ? 'Ripristina' : 'Archivia'}</button>` : ''}${isAdmin ? '<button class="danger-button" id="rc15PracticeDelete" type="button">Elimina pratica</button>' : ''}</div>`, { wide: true });
    dialog.querySelectorAll('.rc15-open-original').forEach(button => button.addEventListener('click', async () => {
      const temp = document.createElement('button'); temp.textContent = 'Apri originale';
      await openOriginalDocument(button.dataset.documentId, button, null);
    }));
    $('#rc15PracticeExport').addEventListener('click', async () => {
      const response = await fetch(`/api/rc15/practices/${practiceId}/export?include_originals=false`, { credentials: 'same-origin' });
      if (!response.ok) { const payload = await response.json(); toast(messageFrom(payload), true); return; }
      await downloadBlob(response, `thistinti-practice-${practiceId.slice(0,8)}.zip`); toast('Fascicolo esportato senza originali.');
    });
    if ($('#rc15PracticeArchive')) $('#rc15PracticeArchive').addEventListener('click', async () => {
      try { await api(`/api/rc15/practices/${practiceId}/${item.status === 'archived' ? 'restore' : 'archive'}`, { method: 'POST' }); dialog.close(); toast('Stato pratica aggiornato.'); await loadPractices(); }
      catch (error) { toast(error.message, true); }
    });
    if ($('#rc15PracticeDelete')) $('#rc15PracticeDelete').addEventListener('click', async () => {
      if (!window.confirm('Eliminare definitivamente documenti, estrazioni e segnalazioni della pratica? Verrà conservata soltanto una tombstone non sensibile.')) return;
      try { await api(`/api/rc15/practices/${practiceId}`, { method: 'DELETE', body: JSON.stringify({ confirm_practice_id: practiceId }) }); dialog.close(); toast('Pratica eliminata e tombstone registrata.'); await Promise.all([loadPractices(), loadDocuments(), loadCases(), loadChains(), loadDashboard()]); }
      catch (error) { toast(error.message, true); }
    });
  }

  async function loadPilots() {
    rc15.pilots = await api('/api/rc15/pilots');
    $('#rc15Body').innerHTML = `
      <section class="panel table-panel"><div class="panel-heading"><div><h3>Pilot supervisionati</h3><p>Ground truth, versione dell’app e profilo vengono congelati prima del confronto. Servono almeno 30 pratiche.</p></div>${state.user?.role === 'admin' ? '<button id="rc15NewPilot" class="primary-button compact" type="button">+ Nuovo pilot</button>' : ''}</div>
      <div class="table-wrap"><table><thead><tr><th>Pilot</th><th>Stato</th><th>Pratiche</th><th>Misure complete</th><th>Versione motore</th><th>Esito</th></tr></thead><tbody id="rc15PilotsTable"></tbody></table></div></section>`;
    if ($('#rc15NewPilot')) $('#rc15NewPilot').addEventListener('click', openNewPilot);
    const table = $('#rc15PilotsTable');
    if (!rc15.pilots.length) { table.innerHTML = '<tr><td colspan="6" class="empty-state">Nessun pilot.</td></tr>'; return; }
    table.innerHTML = rc15.pilots.map(item => `<tr data-pilot-id="${item.id}" tabindex="0"><td><strong>${escapeHtml(item.name)} · v${item.version}</strong><small>${item.ground_truth_hash ? escapeHtml(item.ground_truth_hash.slice(0,16)) + '…' : 'ground truth non congelata'}</small></td><td><span class="badge ${item.status === 'completed' ? 'parsed' : item.status === 'draft' ? 'open' : 'medium'}">${rc15StatusLabel(item.status)}</span></td><td>${item.case_count}/30+</td><td>${item.measurement_complete_count}/${item.case_count}</td><td>${escapeHtml(item.engine_version || '—')}</td><td>${escapeHtml(item.result?.decision || '—')}</td></tr>`).join('');
    table.querySelectorAll('[data-pilot-id]').forEach(row => row.addEventListener('click', () => openPilot(row.dataset.pilotId)));
  }

  function openNewPilot() {
    const dialog = modal('Nuovo pilot', `<form id="rc15PilotCreateForm" class="form-stack"><div><label>Nome pilot</label><input id="rc15PilotName" required minlength="2" /></div><div><label>Riferimento autorizzazione</label><input id="rc15PilotAuth" required minlength="3" placeholder="PILOT-AUTH-001" /></div><div class="form-grid two"><div><label>Revisore A</label><input id="rc15PilotReviewerA" required /></div><div><label>Revisore B</label><input id="rc15PilotReviewerB" required /></div></div><div><label>Perimetro</label><textarea id="rc15PilotScope" required minlength="10" placeholder="Settore, fornitori, periodo, tipi di documenti e limiti inclusi."></textarea></div><div><label>Fine conservazione (opzionale)</label><input id="rc15PilotRetention" type="date" /></div><div class="modal-actions"><button class="primary-button" type="submit">Crea pilot</button></div></form>`);
    $('#rc15PilotCreateForm').addEventListener('submit', async event => {
      event.preventDefault();
      try {
        const result = await api('/api/rc15/pilots', { method: 'POST', body: JSON.stringify({ name: $('#rc15PilotName').value.trim(), authorization_reference: $('#rc15PilotAuth').value.trim(), reviewer_primary: $('#rc15PilotReviewerA').value.trim(), reviewer_secondary: $('#rc15PilotReviewerB').value.trim(), scope: $('#rc15PilotScope').value.trim(), retention_end: $('#rc15PilotRetention').value || null }) });
        dialog.close(); toast('Pilot creato.'); await loadPilots(); await openPilot(result.id);
      } catch (error) { toast(error.message, true); }
    });
  }

  function findingsToText(payload) {
    return (payload?.findings || []).map(item => `${item.case_type} | ${item.severity || 'medium'}${item.potential_exposure !== null && item.potential_exposure !== undefined ? ` | ${item.potential_exposure}` : ''}`).join('\n');
  }

  function textToFindings(text) {
    return text.split(/\n+/).map(line => line.trim()).filter(Boolean).map(line => {
      const [caseType, severityRaw, amountRaw] = line.split('|').map(item => item.trim());
      const severity = ['low','medium','high','critical'].includes((severityRaw || '').toLowerCase()) ? severityRaw.toLowerCase() : 'medium';
      const amount = amountRaw === undefined || amountRaw === '' ? null : Number(amountRaw.replace(',', '.'));
      if (!caseType) throw new Error('Ogni riga deve indicare almeno il tipo di anomalia.');
      if (amount !== null && (!Number.isFinite(amount) || amount < 0)) throw new Error(`Importo non valido per ${caseType}.`);
      return { case_type: caseType, severity, potential_exposure: amount };
    });
  }

  async function openPilot(pilotId) {
    const includeGT = state.user?.role === 'admin';
    const [item, practices] = await Promise.all([api(`/api/rc15/pilots/${pilotId}?include_ground_truth=${includeGT ? 'true' : 'false'}`), api('/api/rc15/practices')]);
    const inPilot = new Set(item.cases.map(entry => entry.practice_id));
    const available = practices.filter(practice => practice.status !== 'deleted' && !inPilot.has(practice.id));
    const canReview = ['admin','reviewer'].includes(state.user?.role);
    const isAdmin = state.user?.role === 'admin';
    const metrics = item.result?.metrics || {};
    const dialog = modal(`${item.name} · v${item.version}`, `
      <div class="detail-grid"><div class="detail-card"><p>Stato</p><strong>${rc15StatusLabel(item.status)}</strong></div><div class="detail-card"><p>Pratiche</p><strong>${item.case_count}</strong></div><div class="detail-card"><p>Misure complete</p><strong>${item.measurement_complete_count}</strong></div><div class="detail-card"><p>Profilo</p><strong>v${item.profile?.version || '—'}</strong></div></div>
      ${item.ground_truth_hash ? `<section class="rc15-freeze-banner"><strong>🔒 Ground truth congelata</strong><code>${escapeHtml(item.ground_truth_hash)}</code><small>${escapeHtml(item.engine_version || '')} · ${dateTime(item.frozen_at)}</small></section>` : '<section class="rc15-freeze-banner draft"><strong>Ground truth modificabile</strong><small>Il confronto con ThisTinti non è ancora autorizzato.</small></section>'}
      ${item.result?.decision ? `<section class="detail-section"><h4>Risultato</h4><div class="detail-grid"><div class="detail-card"><p>Decisione</p><strong>${escapeHtml(item.result.decision)}</strong></div><div class="detail-card"><p>Precision</p><strong>${metrics.precision ?? '—'}</strong></div><div class="detail-card"><p>Recall</p><strong>${metrics.recall ?? '—'}</strong></div><div class="detail-card"><p>Tempo risparmiato</p><strong>${metrics.time_saved_percent ?? '—'}%</strong></div></div></section>` : ''}
      ${item.status === 'draft' && canReview ? `<section class="detail-section"><h4>Aggiungi pratica</h4>${available.length ? `<div class="filter-row"><select id="rc15PilotPracticeSelect"><option value="">Seleziona…</option>${available.map(practice => `<option value="${practice.id}">${escapeHtml(practice.reference_key || practice.id.slice(0,8))}</option>`).join('')}</select><button id="rc15PilotAddPractice" class="primary-button compact" type="button">Aggiungi</button></div>` : '<p class="empty-state">Nessun’altra pratica disponibile.</p>'}</section>` : ''}
      <section class="detail-section"><h4>Pratiche del pilot</h4><div class="rc15-pilot-case-list">${item.cases.length ? item.cases.map((entry, index) => `<article class="rc15-pilot-case"><div><strong>Pratica ${index + 1}</strong><small>${escapeHtml(entry.practice_id.slice(0,8))} · ${entry.ground_truth_recorded === false ? 'ground truth da completare' : entry.ground_truth_recorded === true ? 'ground truth registrata' : 'dati interni disponibili'}</small></div>${canReview ? `<button class="secondary-button compact rc15-edit-pilot-case" data-case-index="${index}" type="button">${item.status === 'draft' ? 'Ground truth / tempi' : 'Tempi / voto'}</button>` : ''}</article>`).join('') : '<p class="empty-state">Aggiungi almeno 30 pratiche indipendenti.</p>'}</div></section>
      <div class="modal-actions">${item.status === 'draft' && isAdmin ? '<button id="rc15PilotFreeze" class="primary-button" type="button">Congela ground truth</button>' : ''}${['frozen','completed'].includes(item.status) && canReview ? '<button id="rc15PilotRun" class="primary-button" type="button">Esegui confronto</button>' : ''}${item.ground_truth_hash ? '<button id="rc15PilotReport" class="secondary-button" type="button">Esporta rapporto</button>' : ''}${isAdmin ? '<button id="rc15PilotArchive" class="secondary-button" type="button">Archivia pilot</button>' : ''}</div>`, { wide: true });
    if ($('#rc15PilotAddPractice')) $('#rc15PilotAddPractice').addEventListener('click', async () => {
      const practiceId = $('#rc15PilotPracticeSelect').value; if (!practiceId) return;
      try { await api(`/api/rc15/pilots/${pilotId}/practices`, { method: 'POST', body: JSON.stringify({ practice_id: practiceId }) }); dialog.close(); await openPilot(pilotId); }
      catch (error) { toast(error.message, true); }
    });
    dialog.querySelectorAll('.rc15-edit-pilot-case').forEach(button => button.addEventListener('click', () => openPilotCaseEditor(item, item.cases[Number(button.dataset.caseIndex)])));
    if ($('#rc15PilotFreeze')) $('#rc15PilotFreeze').addEventListener('click', async () => {
      try { await api(`/api/rc15/pilots/${pilotId}/freeze`, { method: 'POST' }); dialog.close(); toast('Ground truth congelata e hash registrato.'); await loadPilots(); await openPilot(pilotId); }
      catch (error) { toast(error.message, true); }
    });
    if ($('#rc15PilotRun')) $('#rc15PilotRun').addEventListener('click', async () => {
      try { await api(`/api/rc15/pilots/${pilotId}/run`, { method: 'POST' }); dialog.close(); toast('Confronto pilot completato.'); await loadPilots(); await openPilot(pilotId); }
      catch (error) { toast(error.message, true); }
    });
    if ($('#rc15PilotReport')) $('#rc15PilotReport').addEventListener('click', async () => {
      const response = await fetch(`/api/rc15/pilots/${pilotId}/report?format=markdown`, { credentials: 'same-origin' });
      if (!response.ok) { toast('Rapporto non disponibile.', true); return; }
      await downloadBlob(response, `thistinti-pilot-${pilotId.slice(0,8)}.md`); toast('Rapporto pilot esportato.');
    });
    if ($('#rc15PilotArchive')) $('#rc15PilotArchive').addEventListener('click', async () => {
      try { await api(`/api/rc15/pilots/${pilotId}/archive`, { method: 'POST' }); dialog.close(); toast('Pilot archiviato.'); await loadPilots(); }
      catch (error) { toast(error.message, true); }
    });
  }

  function openPilotCaseEditor(pilot, entry) {
    const draft = pilot.status === 'draft';
    const dialog = modal('Misurazione pratica pilot', `
      <form id="rc15PilotCaseForm" class="form-stack">
        ${draft ? `<div class="rc15-ground-truth-help"><strong>Formato ground truth</strong><p>Una anomalia per riga: <code>tipo | gravità | importo opzionale</code>. Esempio: <code>quantity_mismatch | high | 120.50</code>. I due revisori devono classificare indipendentemente prima dell’aggiudicazione.</p></div>
        <div><label>Revisore A</label><textarea id="rc15ReviewerA" rows="5">${escapeHtml(findingsToText(entry.reviewer_primary))}</textarea></div><div><label>Revisore B</label><textarea id="rc15ReviewerB" rows="5">${escapeHtml(findingsToText(entry.reviewer_secondary))}</textarea></div><div><label>Ground truth aggiudicata</label><textarea id="rc15Adjudicated" rows="5">${escapeHtml(findingsToText(entry.adjudicated))}</textarea></div>` : '<div class="rc15-freeze-banner"><strong>🔒 Ground truth non modificabile</strong><small>Per correggerla serve una nuova versione del pilot.</small></div>'}
        <div class="form-grid three"><div><label>Tempo manuale (s)</label><input id="rc15ManualSeconds" type="number" min="0.001" step="0.001" value="${entry.manual_seconds ?? ''}" /></div><div><label>Tempo assistito (s)</label><input id="rc15AssistedSeconds" type="number" min="0.001" step="0.001" value="${entry.assisted_seconds ?? ''}" /></div><div><label>Voto utilizzatore 1–5</label><input id="rc15UserScore" type="number" min="1" max="5" value="${entry.user_score ?? ''}" /></div></div>
        <div><label>Note</label><textarea id="rc15PilotCaseNotes">${escapeHtml(entry.notes || '')}</textarea></div>
        <div class="modal-actions"><button class="primary-button" type="submit">Salva pratica pilot</button></div>
      </form>`);
    $('#rc15PilotCaseForm').addEventListener('submit', async event => {
      event.preventDefault();
      try {
        const payload = {
          manual_seconds: $('#rc15ManualSeconds').value ? Number($('#rc15ManualSeconds').value) : null,
          assisted_seconds: $('#rc15AssistedSeconds').value ? Number($('#rc15AssistedSeconds').value) : null,
          user_score: $('#rc15UserScore').value ? Number($('#rc15UserScore').value) : null,
          notes: $('#rc15PilotCaseNotes').value.trim() || null,
        };
        if (draft) {
          payload.reviewer_primary = { findings: textToFindings($('#rc15ReviewerA').value), notes: null };
          payload.reviewer_secondary = { findings: textToFindings($('#rc15ReviewerB').value), notes: null };
          payload.adjudicated = { findings: textToFindings($('#rc15Adjudicated').value), notes: null };
        }
        await api(`/api/rc15/pilots/${pilot.id}/cases/${entry.id}`, { method: 'PATCH', body: JSON.stringify(payload) });
        dialog.close(); toast('Dati pilot salvati.'); $('#rc15Dialog')?.close(); await loadPilots(); await openPilot(pilot.id);
      } catch (error) { toast(error.message, true); }
    });
  }

  ensureShell();
})();

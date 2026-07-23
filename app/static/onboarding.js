(() => {
  'use strict';

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const appView = $('#appView');
  const authView = $('#authView');
  const mainNav = $('#mainNav');
  if (!appView || !authView || !mainNav) return;

  const WELCOME_KEY = 'thistinti_experience_welcome_v1';
  const ADVANCED_KEY = 'thistinti_experience_advanced_v1';
  let welcomeShownThisSession = false;

  const safeStorage = {
    get(key) {
      try { return window.localStorage.getItem(key); } catch (_) { return null; }
    },
    set(key, value) {
      try { window.localStorage.setItem(key, value); } catch (_) { /* local preference only */ }
    },
  };

  function setText(selector, value, root = document) {
    const node = $(selector, root);
    if (node && node.textContent !== value) node.textContent = value;
  }

  function setNodeText(node, value) {
    if (node && node.textContent !== value) node.textContent = value;
  }

  function setNavLabel(view, icon, label) {
    const button = mainNav.querySelector(`[data-view="${view}"]`);
    if (!button) return null;
    button.innerHTML = `<span aria-hidden="true">${icon}</span> ${label}`;
    button.setAttribute('aria-label', label);
    return button;
  }

  function neutralizeLanguage() {
    setText('.hero-copy', 'Carica documenti collegati. ThisTinti li mette in ordine e ti mostra cosa controllare.');

    const principles = $$('.principles div p');
    setNodeText(principles[0], 'Controlli spiegabili e collegati ai documenti.');
    setNodeText(principles[1], 'Informazioni chiare, decisioni lasciate all’organizzazione.');
    setNodeText(principles[2], 'Dati separati per ogni organizzazione.');

    const warning = $('.legal-warning');
    if (warning && warning.dataset.experienceCopy !== '1') {
      warning.innerHTML = '<strong>Risultati informativi da verificare.</strong> ThisTinti organizza, collega e segnala possibili differenze. Confronta sempre i documenti originali e applica le procedure della tua organizzazione. <a href="/legal.html" target="_blank" rel="noopener">Note legali</a>';
      warning.dataset.experienceCopy = '1';
    }

    const metricCards = $$('.metric-card');
    metricCards.forEach((card) => {
      const label = $('p', card);
      if (!label) return;
      if (label.textContent.trim() === 'Anomalie aperte') label.textContent = 'Da controllare';
      if (label.textContent.trim() === 'Catene operative') label.textContent = 'Collegamenti';
      if (label.textContent.trim() === 'Importo potenziale') label.textContent = 'Valore indicativo';
    });

    const priorityHeading = [...$$('.panel-heading h3')].find((node) => node.textContent.includes('Anomalie prioritarie'));
    setNodeText(priorityHeading, 'Segnalazioni prioritarie');

    const pipelineSubtitle = [...$$('.panel-heading p')].find((node) => node.textContent.includes('Dal file originale'));
    setNodeText(pipelineSubtitle, 'Dal documento originale a informazioni più facili da controllare.');

    const pipelineSteps = $$('.pipeline > div');
    if (pipelineSteps[3]) {
      setText('strong', 'Confronto', pipelineSteps[3]);
      setText('small', 'Possibili differenze', pipelineSteps[3]);
    }
    if (pipelineSteps[4]) {
      setText('strong', 'Verifica', pipelineSteps[4]);
      setText('small', 'Controllo della persona', pipelineSteps[4]);
    }

    setText('#documentsView h3', 'Documenti');
    setText('#chainsView h3', 'Collegamenti');
    setText('#casesView h3', 'Da controllare');
    setText('#casesView .panel-heading p', 'Possibili differenze con origine, prove e affidabilità della lettura.');

    const discoveryRuleNote = [...$$('#discoveryView small')]
      .find((node) => node.textContent.includes('attivate senza intervento'));
    setNodeText(discoveryRuleNote, 'attive secondo la configurazione');

    const activeView = mainNav.querySelector('[data-view].active')?.dataset.view;
    const meta = {
      dashboard: ['Partenza e riepilogo', 'Inizio'],
      documents: ['Archivio locale', 'Documenti'],
      cases: ['Verifica', 'Da controllare'],
      chains: ['Relazioni', 'Collegamenti'],
      discovery: ['Adattamento', 'Regole proposte'],
      validation: ['Qualità', 'Verifica delle regole'],
      audit: ['Governance', 'Registro attività'],
      users: ['Accessi', 'Utenti'],
    };
    if (activeView && meta[activeView] && !$('#guideView:not(.hidden)')) {
      setText('#pageEyebrow', meta[activeView][0]);
      setText('#pageTitle', meta[activeView][1]);
    }
  }

  function buildNavigation() {
    if ($('#advancedNavToggle')) return;

    const dashboard = setNavLabel('dashboard', '⌂', 'Inizio');
    const documents = setNavLabel('documents', '▤', 'Documenti');
    const cases = setNavLabel('cases', '△', 'Da controllare');
    const chains = setNavLabel('chains', '⌘', 'Collegamenti');
    const discovery = setNavLabel('discovery', '✦', 'Regole proposte');
    const validation = setNavLabel('validation', '✓', 'Verifica delle regole');
    const audit = setNavLabel('audit', '◎', 'Registro attività');
    const users = setNavLabel('users', '◇', 'Utenti');

    const primaryLabel = document.createElement('p');
    primaryLabel.className = 'nav-section-label';
    primaryLabel.textContent = 'Principale';
    mainNav.insertBefore(primaryLabel, mainNav.firstChild);

    const guideButton = document.createElement('button');
    guideButton.id = 'guideNavButton';
    guideButton.type = 'button';
    guideButton.innerHTML = '<span aria-hidden="true">?</span> Guida';
    guideButton.setAttribute('aria-label', 'Guida');

    if (cases?.nextSibling) mainNav.insertBefore(guideButton, cases.nextSibling);
    else mainNav.appendChild(guideButton);

    const advancedToggle = document.createElement('button');
    advancedToggle.id = 'advancedNavToggle';
    advancedToggle.type = 'button';
    advancedToggle.className = 'advanced-nav-toggle';
    advancedToggle.setAttribute('aria-controls', 'advancedNavPanel');
    advancedToggle.innerHTML = '<span aria-hidden="true">⋯</span><span>Strumenti avanzati</span><b aria-hidden="true">⌄</b>';

    const advancedPanel = document.createElement('div');
    advancedPanel.id = 'advancedNavPanel';
    advancedPanel.className = 'advanced-nav-panel';

    [chains, discovery, validation, audit, users].filter(Boolean).forEach((button) => advancedPanel.appendChild(button));
    mainNav.appendChild(advancedToggle);
    mainNav.appendChild(advancedPanel);

    const setAdvancedOpen = (open, remember = true) => {
      advancedPanel.classList.toggle('open', open);
      advancedToggle.classList.toggle('open', open);
      advancedToggle.setAttribute('aria-expanded', String(open));
      if (remember) safeStorage.set(ADVANCED_KEY, open ? '1' : '0');
    };

    const activeAdvanced = ['chains', 'discovery', 'validation', 'audit', 'users']
      .includes(mainNav.querySelector('[data-view].active')?.dataset.view);
    setAdvancedOpen(activeAdvanced || safeStorage.get(ADVANCED_KEY) === '1', false);

    advancedToggle.addEventListener('click', () => setAdvancedOpen(!advancedPanel.classList.contains('open')));
    advancedPanel.querySelectorAll('[data-view]').forEach((button) => {
      button.addEventListener('click', () => setAdvancedOpen(true));
    });

    guideButton.addEventListener('click', (event) => {
      event.preventDefault();
      event.stopImmediatePropagation();
      openGuide();
    }, true);

    [dashboard, documents, cases].filter(Boolean).forEach((button) => mainNav.insertBefore(button, guideButton));
  }

  function injectGuide() {
    if ($('#guideView')) return;

    const guide = document.createElement('div');
    guide.id = 'guideView';
    guide.className = 'view-panel hidden';
    guide.innerHTML = `
      <section class="guide-hero panel" aria-labelledby="guideTitle">
        <p class="eyebrow">Partenza rapida</p>
        <h3 id="guideTitle" tabindex="-1">Capire ThisTinti in tre passaggi</h3>
        <p>ThisTinti mette in ordine documenti collegati, confronta le informazioni compatibili e mostra possibili differenze insieme alle prove.</p>
        <div class="guide-steps">
          <article><b>1</b><h4>Carica</h4><p>Parti dai documenti dimostrativi oppure da file autorizzati.</p></article>
          <article><b>2</b><h4>Collega</h4><p>Il programma riunisce i documenti che sembrano parlare della stessa attività.</p></article>
          <article><b>3</b><h4>Controlla</h4><p>Apri una segnalazione e confrontala con i documenti originali.</p></article>
        </div>
        <div class="modal-actions guide-actions">
          <button id="guideLoadDemoButton" class="primary-button" type="button">Prova con esempio</button>
          <button id="guideUploadButton" class="secondary-button" type="button">Carica documenti</button>
        </div>
      </section>
      <section class="guide-example panel">
        <p class="eyebrow">Esempio</p>
        <h3>Tre documenti, una differenza</h3>
        <div class="example-documents" aria-label="Esempio: ordine 10 pezzi, consegna 8 pezzi, fattura 10 pezzi">
          <div><small>ORDINE</small><strong>10 pezzi</strong></div>
          <span aria-hidden="true">→</span>
          <div class="different"><small>CONSEGNA</small><strong>8 pezzi</strong></div>
          <span aria-hidden="true">→</span>
          <div><small>FATTURA</small><strong>10 pezzi</strong></div>
        </div>
        <p>ThisTinti non stabilisce quale documento sia corretto. Evidenzia la differenza e mostra dove verificarla.</p>
      </section>
      <section class="guide-grid" aria-label="Pagine di ThisTinti">
        <article class="panel"><h3>Inizio</h3><p>Riepilogo e prossimo passo consigliato.</p></article>
        <article class="panel"><h3>Documenti</h3><p>File caricati e informazioni riconosciute.</p></article>
        <article class="panel"><h3>Da controllare</h3><p>Possibili differenze collegate alle prove.</p></article>
        <article class="panel"><h3>Collegamenti</h3><p>Documenti che sembrano appartenere alla stessa attività.</p></article>
        <article class="panel"><h3>Regole proposte</h3><p>Controlli suggeriti che possono essere accettati, corretti o disattivati.</p></article>
        <article class="panel"><h3>Strumenti amministrativi</h3><p>Verifica delle regole, registro attività e utenti.</p></article>
      </section>
      <section class="panel guide-boundaries">
        <h3>Il confine da ricordare</h3>
        <p><strong>ThisTinti organizza, collega, confronta e segnala.</strong></p>
        <p>Non certifica documenti, non decide chi abbia ragione e non sostituisce le procedure dell’organizzazione.</p>
      </section>`;

    const usersView = $('#usersView');
    (usersView || $('.workspace')).insertAdjacentElement(usersView ? 'beforebegin' : 'beforeend', guide);

    $('#guideLoadDemoButton')?.addEventListener('click', () => $('#demoButton')?.click());
    $('#guideUploadButton')?.addEventListener('click', () => $('#openUploadButton')?.click());
  }

  function openGuide() {
    $$('.view-panel').forEach((panel) => panel.classList.add('hidden'));
    $('#guideView')?.classList.remove('hidden');
    mainNav.querySelectorAll('button').forEach((button) => button.classList.toggle('active', button.id === 'guideNavButton'));
    setText('#pageEyebrow', 'Aiuto');
    setText('#pageTitle', 'Guida');
    ['#exportButton', '#demoButton', '#openUploadButton', '.legal-warning'].forEach((selector) => $(selector)?.classList.add('hidden'));
    $('#guideTitle')?.focus();
  }

  function injectPreAuthPreview() {
    if ($('#previewDialog')) return;

    const intro = document.createElement('div');
    intro.className = 'auth-preview-entry';
    intro.innerHTML = '<p>Non sai ancora se fa per te?</p><button id="openPreviewButton" class="secondary-button" type="button">Guarda come funziona</button>';
    $('.auth-card')?.appendChild(intro);

    const dialog = document.createElement('dialog');
    dialog.id = 'previewDialog';
    dialog.className = 'modal experience-preview-modal';
    dialog.setAttribute('aria-labelledby', 'previewTitle');
    dialog.innerHTML = `
      <article class="modal-card">
        <div class="modal-heading"><div><p class="eyebrow">Anteprima senza account</p><h3 id="previewTitle">Che cosa fa ThisTinti</h3></div><button class="icon-button" type="button" data-experience-close="previewDialog" aria-label="Chiudi anteprima">×</button></div>
        <p class="preview-lead">Questa è una spiegazione visuale. Non crea account, non carica file e non modifica il database.</p>
        <div class="preview-flow" aria-label="Flusso: carica, collega, controlla">
          <div><b>1</b><strong>Carica</strong><span>Tre documenti della stessa attività.</span></div>
          <i aria-hidden="true">→</i>
          <div><b>2</b><strong>Collega</strong><span>Ordine, consegna e fattura vengono riuniti.</span></div>
          <i aria-hidden="true">→</i>
          <div><b>3</b><strong>Controlla</strong><span>Una quantità diversa viene evidenziata.</span></div>
        </div>
        <div class="example-documents preview-documents" aria-label="Esempio: ordine 10 pezzi, consegna 8 pezzi, fattura 10 pezzi">
          <div><small>ORDINE</small><strong>10 pezzi</strong></div>
          <span aria-hidden="true">≈</span>
          <div class="different"><small>CONSEGNA</small><strong>8 pezzi</strong></div>
          <span aria-hidden="true">≈</span>
          <div><small>FATTURA</small><strong>10 pezzi</strong></div>
        </div>
        <aside class="experience-callout"><strong>Il risultato è una segnalazione, non una decisione.</strong><span>La persona apre le prove e verifica i documenti originali.</span></aside>
        <div class="modal-actions"><button id="previewCreateSpaceButton" class="primary-button" type="button">Crea il mio spazio locale</button><button class="secondary-button" type="button" data-experience-close="previewDialog">Chiudi</button></div>
      </article>`;
    document.body.appendChild(dialog);

    $('#openPreviewButton')?.addEventListener('click', () => dialog.showModal());
    $('#previewCreateSpaceButton')?.addEventListener('click', () => {
      dialog.close();
      $('#registerTab')?.click();
      $('#organizationName')?.focus();
    });
  }

  function injectWelcome() {
    if ($('#welcomeDialog')) return;

    const dialog = document.createElement('dialog');
    dialog.id = 'welcomeDialog';
    dialog.className = 'modal welcome-modal';
    dialog.setAttribute('aria-labelledby', 'welcomeTitle');
    dialog.innerHTML = `
      <article class="modal-card">
        <div class="welcome-brand"><div class="brand-mark small" aria-hidden="true">T</div><div><p class="eyebrow">Benvenuto</p><h3 id="welcomeTitle">Il primo risultato in pochi minuti</h3></div></div>
        <p class="welcome-lead">Parti dall’esempio: vedrai come ThisTinti collega tre documenti e mostra una differenza da controllare.</p>
        <div class="guide-steps compact">
          <article><b>1</b><h4>Carica</h4><p>Usa file dimostrativi.</p></article>
          <article><b>2</b><h4>Osserva</h4><p>Apri i collegamenti.</p></article>
          <article><b>3</b><h4>Verifica</h4><p>Controlla le prove.</p></article>
        </div>
        <label class="welcome-dismiss"><input id="welcomeDoNotShow" type="checkbox"> <span>Non mostrare più questa introduzione su questo browser</span></label>
        <div class="modal-actions">
          <button id="welcomeDemoButton" class="primary-button" type="button">Prova con esempio</button>
          <button id="welcomeUploadButton" class="secondary-button" type="button">Carica documenti</button>
          <button id="welcomeGuideButton" class="ghost-button" type="button">Apri guida</button>
          <button id="welcomeCloseButton" class="ghost-button" type="button">Chiudi</button>
        </div>
      </article>`;
    document.body.appendChild(dialog);

    const remember = () => {
      if ($('#welcomeDoNotShow')?.checked) safeStorage.set(WELCOME_KEY, '1');
      welcomeShownThisSession = true;
    };
    const close = () => { remember(); dialog.close(); };

    $('#welcomeCloseButton')?.addEventListener('click', close);
    $('#welcomeGuideButton')?.addEventListener('click', () => { close(); openGuide(); });
    $('#welcomeDemoButton')?.addEventListener('click', () => { close(); $('#demoButton')?.click(); });
    $('#welcomeUploadButton')?.addEventListener('click', () => { close(); $('#openUploadButton')?.click(); });
    dialog.addEventListener('close', () => { welcomeShownThisSession = true; });
  }

  function injectStartPanel() {
    if ($('#gettingStartedPanel')) return;
    const dashboard = $('#dashboardView');
    const metrics = $('#dashboardView .metric-grid');
    if (!dashboard || !metrics) return;

    const panel = document.createElement('section');
    panel.id = 'gettingStartedPanel';
    panel.className = 'panel getting-started-panel';
    panel.setAttribute('aria-labelledby', 'gettingStartedTitle');
    panel.innerHTML = `
      <div class="getting-started-copy">
        <p class="eyebrow">Percorso consigliato</p>
        <h3 id="gettingStartedTitle">Inizia dai documenti dimostrativi</h3>
        <p id="gettingStartedDescription">Vedrai il funzionamento senza usare dati personali o aziendali.</p>
        <div class="modal-actions guide-actions">
          <button id="startDemoButton" class="primary-button" type="button">Prova con esempio</button>
          <button id="startUploadButton" class="secondary-button" type="button">Carica documenti</button>
          <button id="startCasesButton" class="secondary-button hidden" type="button">Apri “Da controllare”</button>
        </div>
      </div>
      <ol class="start-checklist" aria-label="Avanzamento della prima prova">
        <li data-start-step="documents"><b>1</b><span><strong>Documenti</strong><small>Carica l’esempio.</small></span></li>
        <li data-start-step="chains"><b>2</b><span><strong>Collegamenti</strong><small>Osserva quali file appartengono alla stessa attività.</small></span></li>
        <li data-start-step="cases"><b>3</b><span><strong>Da controllare</strong><small>Apri una segnalazione e verifica le prove.</small></span></li>
      </ol>`;
    dashboard.insertBefore(panel, metrics);

    $('#startDemoButton')?.addEventListener('click', () => $('#demoButton')?.click());
    $('#startUploadButton')?.addEventListener('click', () => $('#openUploadButton')?.click());
    $('#startCasesButton')?.addEventListener('click', () => mainNav.querySelector('[data-view="cases"]')?.click());
  }

  function numericText(selector) {
    const value = Number.parseInt($(selector)?.textContent || '0', 10);
    return Number.isFinite(value) ? value : 0;
  }

  function updateStartPanel() {
    const panel = $('#gettingStartedPanel');
    if (!panel) return;

    const counts = {
      documents: numericText('#metricDocuments'),
      chains: numericText('#metricChains'),
      cases: numericText('#metricCases'),
    };
    const complete = counts.documents > 0 && counts.chains > 0 && counts.cases > 0;

    Object.entries(counts).forEach(([key, value]) => {
      const item = panel.querySelector(`[data-start-step="${key}"]`);
      item?.classList.toggle('complete', value > 0);
    });

    setText('#gettingStartedTitle', complete ? 'La prima prova è pronta' : counts.documents > 0 ? 'I documenti sono stati elaborati' : 'Inizia dai documenti dimostrativi');
    setText('#gettingStartedDescription', complete
      ? 'Apri “Da controllare”, scegli una segnalazione e confronta le prove.'
      : counts.documents > 0
        ? 'Controlla i collegamenti e le eventuali segnalazioni disponibili.'
        : 'Vedrai il funzionamento senza usare dati personali o aziendali.');

    $('#startDemoButton')?.classList.toggle('hidden', counts.documents > 0);
    $('#startCasesButton')?.classList.toggle('hidden', counts.cases === 0);
  }

  function improveEmptyStates() {
    const updates = [
      ['#documentsTable td.empty-state', 'Nessun documento. Prova l’esempio oppure carica file autorizzati.'],
      ['#chainsTable td.empty-state', 'Nessun collegamento. Comparirà quando due o più documenti condivideranno riferimenti compatibili.'],
      ['#casesTable td.empty-state', 'Nessuna segnalazione. Non sono state trovate differenze oppure i documenti disponibili non sono ancora sufficienti.'],
    ];
    updates.forEach(([selector, value]) => {
      const node = $(selector);
      if (node && node.textContent !== value) node.textContent = value;
    });

    const priorityEmpty = $('#priorityCases.empty-state');
    const priorityCopy = 'Nessuna segnalazione prioritaria. Carica l’esempio o altri documenti per iniziare il confronto.';
    if (priorityEmpty && priorityEmpty.textContent !== priorityCopy) priorityEmpty.textContent = priorityCopy;
  }

  function bindExperienceCloseButtons() {
    $$('[data-experience-close]').forEach((button) => {
      if (button.dataset.experienceBound === '1') return;
      button.dataset.experienceBound = '1';
      button.addEventListener('click', () => $(`#${button.dataset.experienceClose}`)?.close());
    });
  }

  function maybeShowWelcome() {
    if (welcomeShownThisSession || safeStorage.get(WELCOME_KEY) === '1') return;
    if (appView.classList.contains('hidden')) return;
    const dialog = $('#welcomeDialog');
    if (!dialog || dialog.open) return;

    const canUseDemo = !$('#demoButton')?.classList.contains('hidden');
    $('#welcomeDemoButton')?.classList.toggle('hidden', !canUseDemo);
    $('#welcomeUploadButton')?.classList.toggle('hidden', !canUseDemo);
    welcomeShownThisSession = true;
    window.setTimeout(() => {
      if (!appView.classList.contains('hidden') && !dialog.open) dialog.showModal();
    }, 250);
  }

  neutralizeLanguage();
  buildNavigation();
  injectGuide();
  injectPreAuthPreview();
  injectWelcome();
  injectStartPanel();
  improveEmptyStates();
  bindExperienceCloseButtons();
  updateStartPanel();

  const observer = new MutationObserver(() => {
    neutralizeLanguage();
    improveEmptyStates();
    bindExperienceCloseButtons();
    updateStartPanel();
    maybeShowWelcome();
  });
  observer.observe(document.body, {
    subtree: true,
    childList: true,
    characterData: true,
    attributes: true,
    attributeFilter: ['class'],
  });

  maybeShowWelcome();
})();

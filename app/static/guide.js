(() => {
  'use strict';

  const INTRO_STORAGE_KEY = 'thistinti.guided-intro.v1';
  const q = (selector, root = document) => root.querySelector(selector);
  const qa = (selector, root = document) => [...root.querySelectorAll(selector)];

  const guideMarkup = `
    <div id="guideView" class="view-panel hidden">
      <div class="guide-shell">
        <section class="guide-hero">
          <div>
            <p class="guide-kicker">Guida semplice</p>
            <h3>Capire ThisTinti in meno di due minuti</h3>
            <p>ThisTinti mette in ordine documenti collegati, confronta le informazioni e mostra differenze da verificare. Non decide al posto dell'organizzazione: rende piu facile capire dove guardare.</p>
          </div>
          <div class="guide-actions">
            <button id="guideDemoButton" class="secondary-button" type="button">Carica esempio</button>
            <button id="guideUploadButton" class="primary-button compact" type="button">+ Primo documento</button>
          </div>
        </section>

        <section class="guide-step-grid" aria-label="Primi passi">
          <article class="guide-step"><span>1</span><div><h4>Carica</h4><p>Inserisci alcuni documenti oppure usa l'esempio gia preparato.</p></div></article>
          <article class="guide-step"><span>2</span><div><h4>Collega</h4><p>ThisTinti cerca riferimenti comuni e riunisce i documenti della stessa operazione.</p></div></article>
          <article class="guide-step"><span>3</span><div><h4>Verifica</h4><p>Controlla le differenze segnalate e confrontale con i documenti originali.</p></div></article>
        </section>

        <section class="panel guide-panel">
          <div class="panel-heading"><div><h3>Cosa trovi nel menu</h3><p>Ogni sezione risponde a una domanda precisa.</p></div></div>
          <div class="guide-section-grid">
            <article><strong>Panoramica</strong><p>Quanti documenti, collegamenti e segnalazioni ci sono?</p></article>
            <article><strong>Documenti</strong><p>Quali file sono stati letti e quali richiedono attenzione?</p></article>
            <article><strong>Catene</strong><p>Quali documenti sembrano appartenere alla stessa operazione?</p></article>
            <article><strong>Anomalie</strong><p>Dove sono state trovate differenze o informazioni mancanti?</p></article>
            <article><strong>Autopilota</strong><p>Quali controlli ricorrenti propone ThisTinti osservando i documenti?</p></article>
            <article><strong>Validation Lab</strong><p>Come si misura se le regole funzionano senza introdurre nuovi errori?</p></article>
            <article><strong>Audit</strong><p>Chi ha fatto cosa e quando?</p></article>
            <article><strong>Utenti</strong><p>Chi puo amministrare, revisionare oppure leggere?</p></article>
          </div>
        </section>

        <section class="guide-two-columns">
          <article class="panel guide-panel">
            <div class="panel-heading"><div><h3>Un esempio elementare</h3><p>Tre documenti raccontano la stessa operazione.</p></div></div>
            <div class="guide-example-flow">
              <div><small>ORDINE</small><strong>10 pezzi</strong></div>
              <span>→</span>
              <div><small>CONSEGNA</small><strong>8 pezzi</strong></div>
              <span>→</span>
              <div><small>FATTURA</small><strong>10 pezzi</strong></div>
            </div>
            <p class="guide-callout">ThisTinti non stabilisce chi ha ragione. Mostra che i numeri non coincidono e indica quali prove controllare.</p>
          </article>

          <article class="panel guide-panel">
            <div class="panel-heading"><div><h3>Che cosa significa confidenza?</h3><p>E una misura di sicurezza del collegamento o della lettura.</p></div></div>
            <div class="guide-confidence">
              <div><span class="guide-confidence-dot high"></span><strong>Alta</strong><p>Gli indizi coincidono bene.</p></div>
              <div><span class="guide-confidence-dot medium"></span><strong>Media</strong><p>Il risultato e plausibile, ma va controllato.</p></div>
              <div><span class="guide-confidence-dot low"></span><strong>Bassa</strong><p>Mancano informazioni o ci sono dubbi.</p></div>
            </div>
          </article>
        </section>

        <section class="guide-two-columns">
          <article class="panel guide-panel guide-positive">
            <div class="panel-heading"><div><h3>Cosa fa</h3></div></div>
            <ul>
              <li>organizza documenti e dati;</li>
              <li>crea collegamenti spiegabili;</li>
              <li>segnala possibili incoerenze;</li>
              <li>conserva le prove e le revisioni;</li>
              <li>si adatta a regole e tolleranze dell'organizzazione.</li>
            </ul>
          </article>
          <article class="panel guide-panel guide-neutral">
            <div class="panel-heading"><div><h3>Cosa non fa</h3></div></div>
            <ul>
              <li>non decide come deve lavorare l'azienda;</li>
              <li>non certifica automaticamente che un documento sia corretto;</li>
              <li>non sostituisce procedure o competenze professionali;</li>
              <li>non rende una stima una certezza.</li>
            </ul>
          </article>
        </section>

        <section class="panel guide-panel">
          <div class="panel-heading"><div><h3>Come si adatta alle aziende</h3><p>La struttura resta la stessa, mentre controlli e processi possono cambiare.</p></div></div>
          <div class="guide-customization-grid">
            <div><strong>Documenti</strong><p>L'organizzazione sceglie quali tipi usare.</p></div>
            <div><strong>Regole</strong><p>Definisce che cosa confrontare e quali differenze accettare.</p></div>
            <div><strong>Ruoli</strong><p>Stabilisce chi puo vedere, revisionare o amministrare.</p></div>
            <div><strong>Esportazioni</strong><p>Usa i risultati nei propri flussi interni.</p></div>
          </div>
        </section>

        <section class="guide-final-note" role="note">
          <strong>In una frase:</strong> ThisTinti aiuta a capire se piu documenti raccontano la stessa storia, lasciando all'organizzazione il controllo sul loro utilizzo.
        </section>
      </div>
    </div>`;

  const introMarkup = `
    <dialog id="guidedIntroDialog" class="modal guide-intro-dialog">
      <article class="modal-card">
        <div class="guide-intro-heading">
          <div class="guide-intro-mark" aria-hidden="true"><span>T</span><span>T</span><i>✓</i></div>
          <div><p class="guide-kicker">Primo accesso</p><h3>Inizia senza dover conoscere il programma</h3></div>
        </div>
        <p class="guide-intro-copy">Il percorso base e semplice: carica alcuni documenti, guarda come vengono collegati e verifica le differenze trovate.</p>
        <div class="guide-intro-steps">
          <div><b>1</b><span><strong>Carica</strong><small>un esempio o i tuoi file</small></span></div>
          <div><b>2</b><span><strong>Esplora</strong><small>documenti e catene</small></span></div>
          <div><b>3</b><span><strong>Controlla</strong><small>segnalazioni e prove</small></span></div>
        </div>
        <div class="modal-actions guide-intro-actions">
          <button id="introStartButton" class="ghost-button" type="button">Inizia da solo</button>
          <button id="introGuideButton" class="secondary-button" type="button">Apri la guida</button>
          <button id="introDemoButton" class="primary-button" type="button">Prova con l'esempio</button>
        </div>
        <small class="guide-intro-note">Questa introduzione viene mostrata una sola volta. La guida resta sempre disponibile nel menu.</small>
      </article>
    </dialog>`;

  function addGuideInterface() {
    const mainNav = q('#mainNav');
    if (mainNav && !q('[data-view="guide"]', mainNav)) {
      const button = document.createElement('button');
      button.type = 'button';
      button.dataset.view = 'guide';
      button.innerHTML = '<span>?</span> Guida semplice';
      mainNav.appendChild(button);
    }

    const workspace = q('.workspace');
    if (workspace && !q('#guideView')) workspace.insertAdjacentHTML('beforeend', guideMarkup);
    if (!q('#guidedIntroDialog')) document.body.insertAdjacentHTML('beforeend', introMarkup);

    const authCard = q('.auth-card');
    if (authCard && !q('.auth-guide-link', authCard)) {
      const link = document.createElement('button');
      link.type = 'button';
      link.className = 'text-button auth-guide-link';
      link.textContent = 'Che cos e ThisTinti?';
      link.addEventListener('click', () => showStandaloneIntro());
      authCard.appendChild(link);
    }
  }

  function showGuide() {
    const guide = q('#guideView');
    if (!guide) return;
    qa('.view-panel').forEach((panel) => panel.classList.add('hidden'));
    guide.classList.remove('hidden');
    qa('#mainNav [data-view]').forEach((button) => button.classList.toggle('active', button.dataset.view === 'guide'));
    const eyebrow = q('#pageEyebrow');
    const title = q('#pageTitle');
    if (eyebrow) eyebrow.textContent = 'Primi passi';
    if (title) title.textContent = 'Guida semplice';
    qa('.topbar-actions > *').forEach((element) => element.classList.add('hidden'));
    q('.legal-warning')?.classList.add('hidden');
    syncGuideActions();
    q('.workspace')?.scrollTo({ top: 0, behavior: 'smooth' });
  }

  function syncGuideActions() {
    const demo = q('#demoButton');
    const upload = q('#openUploadButton');
    q('#guideDemoButton')?.classList.toggle('hidden', !demo || demo.classList.contains('hidden'));
    q('#guideUploadButton')?.classList.toggle('hidden', !upload || upload.classList.contains('hidden'));
    q('#introDemoButton')?.classList.toggle('hidden', !demo || demo.classList.contains('hidden'));
  }

  function markIntroSeen() {
    try { window.localStorage.setItem(INTRO_STORAGE_KEY, '1'); } catch (_) { /* storage is optional */ }
  }

  function introWasSeen() {
    try { return window.localStorage.getItem(INTRO_STORAGE_KEY) === '1'; } catch (_) { return false; }
  }

  function openIntro() {
    const dialog = q('#guidedIntroDialog');
    if (!dialog || dialog.open) return;
    syncGuideActions();
    dialog.showModal();
  }

  function showStandaloneIntro() {
    addGuideInterface();
    openIntro();
  }

  function maybeShowIntro() {
    const app = q('#appView');
    if (!app || app.classList.contains('hidden') || introWasSeen()) return;
    window.setTimeout(openIntro, 450);
  }

  function closeIntro(action) {
    markIntroSeen();
    q('#guidedIntroDialog')?.close();
    if (action === 'guide') showGuide();
    if (action === 'demo') q('#demoButton')?.click();
  }

  function neutralizeProductLanguage() {
    const hero = q('.hero-copy');
    if (hero) hero.textContent = 'Collega documenti, confronta dati e mette in evidenza differenze verificabili. Ogni segnalazione resta collegata alle prove originali.';
    const principles = qa('.principles p');
    if (principles[0]) principles[0].textContent = 'Controlli comprensibili e configurabili.';
    if (principles[1]) principles[1].textContent = "Le segnalazioni informano: l'organizzazione decide come usarle.";
    const warning = q('.legal-warning');
    if (warning) warning.innerHTML = '<strong>Output informativi da verificare.</strong> Confronta sempre i documenti originali. ThisTinti non sostituisce procedure, professionisti o decisioni dell\'organizzazione. <a href="/legal.html" target="_blank" rel="noopener">Note legali</a>';
    const metricCards = qa('#dashboardView .metric-card');
    if (metricCards[3]) {
      q('p', metricCards[3]).textContent = 'Valore segnalato';
      q('small', metricCards[3]).textContent = 'stima informativa da verificare';
    }
    const pipelineHeading = q('#dashboardView .pipeline')?.closest('.panel')?.querySelector('.panel-heading p');
    if (pipelineHeading) pipelineHeading.textContent = 'Dal file originale alla verifica interna.';
    const pipelineSteps = qa('#dashboardView .pipeline > div');
    if (pipelineSteps[4]) q('small', pipelineSteps[4]).textContent = "Valutazione dell'organizzazione";
  }

  function improveEmptyStates() {
    const replacements = new Map([
      ['Nessuna anomalia disponibile.', 'Nessuna segnalazione da mostrare. Carica un esempio oppure aggiungi documenti per iniziare.'],
      ['Nessun documento.', 'Nessun documento. Usa “Carica esempio” oppure aggiungi il primo file.'],
      ['Nessuna catena.', 'Nessuna catena. Comparira quando piu documenti avranno riferimenti comuni.'],
      ['Nessuna esecuzione disponibile.', 'Nessuna esecuzione. Il Validation Lab serve a misurare le regole prima di usarle su processi reali.'],
    ]);
    qa('.empty-state').forEach((element) => {
      const current = element.textContent.trim();
      if (replacements.has(current)) element.textContent = replacements.get(current);
    });
  }

  function translateVisibleMessages() {
    const translations = new Map([
      ['Email already registered', 'Questa email e gia registrata. Usa la scheda Accedi.'],
      ['Invalid credentials', 'Email o password non corrette.'],
      ['Not authenticated', 'Sessione non valida. Accedi nuovamente.'],
    ]);
    const toast = q('#toast');
    if (toast && translations.has(toast.textContent.trim())) toast.textContent = translations.get(toast.textContent.trim());
    qa('button').forEach((button) => {
      if (button.textContent.trim() === 'Simula approvazione') button.textContent = 'Prova scenario';
    });
  }

  function refreshGuidance() {
    neutralizeProductLanguage();
    improveEmptyStates();
    translateVisibleMessages();
  }

  function bindEvents() {
    q('#mainNav')?.addEventListener('click', (event) => {
      const button = event.target.closest('[data-view="guide"]');
      if (!button) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      showGuide();
    }, true);

    q('#guideDemoButton')?.addEventListener('click', () => q('#demoButton')?.click());
    q('#guideUploadButton')?.addEventListener('click', () => q('#openUploadButton')?.click());
    q('#introStartButton')?.addEventListener('click', () => closeIntro('start'));
    q('#introGuideButton')?.addEventListener('click', () => closeIntro('guide'));
    q('#introDemoButton')?.addEventListener('click', () => closeIntro('demo'));
    q('#guidedIntroDialog')?.addEventListener('cancel', markIntroSeen);
  }

  function observeApplication() {
    const app = q('#appView');
    if (app) {
      new MutationObserver(() => {
        syncGuideActions();
        maybeShowIntro();
      }).observe(app, { attributes: true, attributeFilter: ['class'] });
    }

    let scheduled = false;
    new MutationObserver(() => {
      if (scheduled) return;
      scheduled = true;
      window.requestAnimationFrame(() => {
        scheduled = false;
        refreshGuidance();
      });
    }).observe(document.body, { childList: true, subtree: true, characterData: true });
  }

  document.addEventListener('DOMContentLoaded', () => {
    addGuideInterface();
    bindEvents();
    refreshGuidance();
    observeApplication();
    maybeShowIntro();
    window.showThisTintiGuide = showGuide;
  });
})();

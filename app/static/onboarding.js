(() => {
  const $ = (selector) => document.querySelector(selector);
  const appView = $('#appView');
  const mainNav = $('#mainNav');
  if (!appView || !mainNav) return;

  let shownThisSession = false;

  function neutralizeLanguage() {
    const principles = document.querySelectorAll('.principles div p');
    if (principles[1]) principles[1].textContent = 'Informazioni chiare, decisioni lasciate all’organizzazione.';

    const warning = document.querySelector('.legal-warning');
    if (warning) {
      warning.innerHTML = '<strong>Output informativi da verificare.</strong> Confronta sempre i documenti originali. ThisTinti organizza, collega e segnala: l’organizzazione decide come usare i risultati. <a href="/legal.html" target="_blank" rel="noopener">Note legali</a>';
    }

    const pipelineSubtitle = [...document.querySelectorAll('.panel-heading p')]
      .find((node) => node.textContent.includes('Dal file originale'));
    if (pipelineSubtitle) pipelineSubtitle.textContent = 'Dal file originale a informazioni più facili da controllare.';

    const discoveryRuleNote = [...document.querySelectorAll('#discoveryView small')]
      .find((node) => node.textContent.includes('attivate senza intervento'));
    if (discoveryRuleNote) discoveryRuleNote.textContent = 'attive secondo la configurazione';
  }

  function injectGuide() {
    if ($('#guideView')) return;

    const usersView = $('#usersView');
    const guide = document.createElement('div');
    guide.id = 'guideView';
    guide.className = 'view-panel hidden';
    guide.innerHTML = `
      <section class="guide-hero panel">
        <p class="eyebrow">Partenza rapida</p>
        <h3>Capire ThisTinti in tre passaggi</h3>
        <p>ThisTinti mette in ordine documenti collegati, confronta i dati e mostra possibili differenze con le relative prove.</p>
        <div class="guide-steps">
          <article><b>1</b><h4>Carica</h4><p>Inserisci documenti di esempio o file autorizzati.</p></article>
          <article><b>2</b><h4>Collega</h4><p>Il programma riunisce i documenti che parlano della stessa attività.</p></article>
          <article><b>3</b><h4>Controlla</h4><p>Apri le segnalazioni e confrontale con i documenti originali.</p></article>
        </div>
        <div class="modal-actions guide-actions">
          <button id="guideLoadDemoButton" class="primary-button" type="button">Carica un esempio</button>
          <button id="guideUploadButton" class="secondary-button" type="button">Carica documenti</button>
        </div>
      </section>
      <section class="guide-grid">
        <article class="panel"><h3>Documenti</h3><p>L’archivio dei file caricati e delle informazioni lette.</p></article>
        <article class="panel"><h3>Catene</h3><p>I gruppi di documenti che sembrano appartenere alla stessa operazione o attività.</p></article>
        <article class="panel"><h3>Anomalie</h3><p>Possibili differenze da controllare, sempre collegate alle prove.</p></article>
        <article class="panel"><h3>Autopilota</h3><p>Osserva i dati e propone controlli che l’organizzazione può accettare, correggere o disattivare.</p></article>
        <article class="panel"><h3>Validation Lab</h3><p>Misura il comportamento delle regole usando esempi con risultati già conosciuti.</p></article>
        <article class="panel"><h3>Audit e utenti</h3><p>Registrano le azioni e stabiliscono chi può amministrare, revisionare o leggere.</p></article>
      </section>
      <section class="panel guide-example">
        <h3>Esempio semplice</h3>
        <p>Ordine: 10 pezzi. Consegna: 8 pezzi. Fattura: 10 pezzi. ThisTinti non decide quale documento sia corretto: mostra la differenza e i dati da verificare.</p>
      </section>
      <section class="panel guide-boundaries">
        <h3>Cosa fa e cosa non fa</h3>
        <p><strong>Fa:</strong> organizza, collega, confronta e segnala.</p>
        <p><strong>Non fa:</strong> non certifica, non decide e non sostituisce le procedure dell’organizzazione.</p>
      </section>`;

    (usersView || appView.querySelector('.workspace')).insertAdjacentElement(usersView ? 'beforebegin' : 'beforeend', guide);

    const guideButton = document.createElement('button');
    guideButton.dataset.view = 'guide';
    guideButton.type = 'button';
    guideButton.innerHTML = '<span>?</span> Guida semplice';
    mainNav.appendChild(guideButton);

    guideButton.addEventListener('click', (event) => {
      event.preventDefault();
      event.stopImmediatePropagation();
      openGuide();
    }, true);

    $('#guideLoadDemoButton')?.addEventListener('click', () => $('#demoButton')?.click());
    $('#guideUploadButton')?.addEventListener('click', () => $('#openUploadButton')?.click());
  }

  function injectWelcome() {
    if ($('#welcomeDialog')) return;
    const dialog = document.createElement('dialog');
    dialog.id = 'welcomeDialog';
    dialog.className = 'modal welcome-modal';
    dialog.innerHTML = `
      <article class="modal-card">
        <div class="welcome-brand"><div class="brand-mark small">T</div><div><p class="eyebrow">Benvenuto</p><h3>ThisTinti in 30 secondi</h3></div></div>
        <p class="welcome-lead">Il programma aiuta a mettere in ordine documenti collegati e a trovare punti che meritano un controllo.</p>
        <div class="guide-steps compact">
          <article><b>1</b><h4>Carica</h4><p>Parti da un esempio.</p></article>
          <article><b>2</b><h4>Collega</h4><p>Osserva le catene.</p></article>
          <article><b>3</b><h4>Controlla</h4><p>Apri le prove.</p></article>
        </div>
        <label class="welcome-dismiss"><input id="welcomeDoNotShow" type="checkbox"> Non mostrare più questa introduzione</label>
        <div class="modal-actions">
          <button id="welcomeGuideButton" class="secondary-button" type="button">Apri guida</button>
          <button id="welcomeDemoButton" class="primary-button" type="button">Carica esempio</button>
          <button id="welcomeCloseButton" class="ghost-button" type="button">Inizia</button>
        </div>
      </article>`;
    document.body.appendChild(dialog);

    const remember = () => {
      if ($('#welcomeDoNotShow')?.checked) localStorage.setItem('thistinti_welcome_seen', '1');
      shownThisSession = true;
    };
    $('#welcomeCloseButton')?.addEventListener('click', () => { remember(); dialog.close(); });
    $('#welcomeGuideButton')?.addEventListener('click', () => { remember(); dialog.close(); openGuide(); });
    $('#welcomeDemoButton')?.addEventListener('click', () => { remember(); dialog.close(); $('#demoButton')?.click(); });
  }

  function openGuide() {
    document.querySelectorAll('.view-panel').forEach((panel) => panel.classList.add('hidden'));
    $('#guideView')?.classList.remove('hidden');
    mainNav.querySelectorAll('[data-view]').forEach((button) => button.classList.toggle('active', button.dataset.view === 'guide'));
    const eyebrow = $('#pageEyebrow');
    const title = $('#pageTitle');
    if (eyebrow) eyebrow.textContent = 'Aiuto';
    if (title) title.textContent = 'Guida semplice';
    ['#exportButton', '#demoButton', '#openUploadButton', '.legal-warning'].forEach((selector) => $(selector)?.classList.add('hidden'));
  }

  function improveEmptyStates() {
    const documentsEmpty = $('#documentsTable td.empty-state');
    if (documentsEmpty && documentsEmpty.textContent.trim() === 'Nessun documento.') {
      documentsEmpty.textContent = 'Nessun documento. Carica un esempio oppure aggiungi file autorizzati per iniziare.';
    }
    const chainsEmpty = $('#chainsTable td.empty-state');
    if (chainsEmpty && chainsEmpty.textContent.trim() === 'Nessuna catena.') {
      chainsEmpty.textContent = 'Nessuna catena. Comparirà quando più documenti condivideranno riferimenti compatibili.';
    }
    const casesEmpty = $('#casesTable td.empty-state');
    if (casesEmpty && casesEmpty.textContent.trim() === 'Nessuna anomalia.') {
      casesEmpty.textContent = 'Nessuna anomalia. Le segnalazioni appariranno dopo il confronto dei documenti.';
    }
  }

  function maybeShowWelcome() {
    if (shownThisSession || localStorage.getItem('thistinti_welcome_seen') === '1') return;
    if (appView.classList.contains('hidden')) return;
    const dialog = $('#welcomeDialog');
    if (dialog && !dialog.open) {
      shownThisSession = true;
      window.setTimeout(() => dialog.showModal(), 250);
    }
  }

  neutralizeLanguage();
  injectGuide();
  injectWelcome();
  improveEmptyStates();

  const observer = new MutationObserver(() => {
    neutralizeLanguage();
    improveEmptyStates();
    maybeShowWelcome();
  });
  observer.observe(appView, { subtree: true, childList: true, attributes: true, attributeFilter: ['class'] });
  maybeShowWelcome();
})();

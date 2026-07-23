(() => {
  const config = window.THISTINTI_SITE || {};
  const repo = config.repository;
  const installer = document.querySelector('#downloadInstaller');
  const portable = document.querySelector('#downloadPortable');
  const checksum = document.querySelector('#downloadChecksum');
  const status = document.querySelector('#releaseStatus');
  const releasePill = document.querySelector('#releasePill');
  const source = document.querySelector('#sourceLink');
  const acceptance = document.querySelector('#downloadRiskAcceptance');
  const enterpriseSource = document.querySelector('#enterpriseSourceLink');
  const securityLink = document.querySelector('#securityLink');
  const copyShareButton = document.querySelector('#copyShareButton');
  const whatsappShareButton = document.querySelector('#whatsappShareButton');
  const shareFeedback = document.querySelector('#shareFeedback');
  let assets = {};

  function initializeSectionReveals() {
    const sections = [...document.querySelectorAll('.reveal-section')];
    if (!sections.length) return;
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reducedMotion || !('IntersectionObserver' in window)) {
      sections.forEach(section => section.classList.add('is-visible'));
      return;
    }
    const observer = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add('is-visible');
        observer.unobserve(entry.target);
      });
    }, { threshold: 0.1, rootMargin: '0px 0px -6% 0px' });
    sections.forEach(section => observer.observe(section));
  }

  function applyDownloadState() {
    if (!installer) return;
    const accepted = Boolean(acceptance?.checked);
    if (!assets.setup) return;
    installer.textContent = accepted ? 'Scarica gratis per Windows' : 'Accetta l’avviso per scaricare';
    installer.classList.toggle('disabled', !accepted);
    installer.setAttribute('aria-disabled', String(!accepted));
    installer.href = accepted ? assets.setup : '#';
    if (portable) {
      portable.href = accepted && assets.portable ? assets.portable : '#';
      portable.classList.toggle('disabled', !accepted);
    }
  }

  function siteUrl() {
    const url = new URL(window.location.href);
    url.hash = '';
    url.search = '';
    return url.toString();
  }

  function shareMessage() {
    return [
      'Ti mando ThisTinti, un programma sperimentale che collega e confronta documenti e mostra possibili differenze da controllare.',
      '',
      'Funziona in locale sul tuo PC: al primo avvio crei il tuo spazio con nome organizzazione, email e password. Per iniziare senza usare documenti personali premi “Carica esempio”.',
      '',
      siteUrl(),
    ].join('\n');
  }

  async function copyShareMessage() {
    const message = shareMessage();
    try {
      await navigator.clipboard.writeText(message);
      if (shareFeedback) shareFeedback.textContent = 'Messaggio copiato. Ora puoi incollarlo su WhatsApp.';
    } catch (_) {
      const area = document.createElement('textarea');
      area.value = message;
      area.setAttribute('readonly', '');
      area.style.position = 'fixed';
      area.style.opacity = '0';
      document.body.appendChild(area);
      area.select();
      document.execCommand('copy');
      area.remove();
      if (shareFeedback) shareFeedback.textContent = 'Messaggio copiato.';
    }
  }

  initializeSectionReveals();
  acceptance?.addEventListener('change', applyDownloadState);
  copyShareButton?.addEventListener('click', copyShareMessage);
  if (whatsappShareButton) {
    whatsappShareButton.href = `https://wa.me/?text=${encodeURIComponent(shareMessage())}`;
  }

  if (!repo || !repo.includes('/')) {
    if (status) status.textContent = 'Repository non ancora configurato.';
    return;
  }

  if (source) source.href = `https://github.com/${repo}`;
  if (enterpriseSource) enterpriseSource.href = `https://github.com/${repo}/blob/main/docs/ENTERPRISE_SELF_HOSTED.md`;
  if (securityLink) securityLink.href = `https://github.com/${repo}/blob/main/SECURITY.md`;

  fetch(`https://api.github.com/repos/${repo}/releases?per_page=10`, {
    headers: { Accept: 'application/vnd.github+json' },
  })
    .then(response => {
      if (!response.ok) throw new Error('release unavailable');
      return response.json();
    })
    .then(releases => {
      if (!Array.isArray(releases)) throw new Error('invalid release response');
      const release = releases.find(item => {
        if (item.draft) return false;
        const releaseAssets = Array.isArray(item.assets) ? item.assets : [];
        return releaseAssets.some(asset => /ThisTinti-Setup-.*-x64\.exe$/i.test(asset.name));
      });
      if (!release) throw new Error('installer unavailable');

      const releaseAssets = Array.isArray(release.assets) ? release.assets : [];
      const setup = releaseAssets.find(asset => /ThisTinti-Setup-.*-x64\.exe$/i.test(asset.name));
      const zip = releaseAssets.find(asset => /ThisTinti-Portable-.*-x64\.zip$/i.test(asset.name));
      const setupHash = releaseAssets.find(asset => /ThisTinti-Setup-.*-x64\.exe\.sha256$/i.test(asset.name));
      assets = {
        setup: setup.browser_download_url,
        portable: zip?.browser_download_url,
      };

      if (zip && portable) portable.classList.remove('hidden');
      if (setupHash && checksum) {
        checksum.href = setupHash.browser_download_url;
        checksum.classList.remove('hidden');
      }
      const channel = release.prerelease ? 'Public Preview' : 'Release';
      if (releasePill) releasePill.textContent = `${channel} · Local Edition`;
      if (status) status.textContent = `${release.tag_name} · ${setup.download_count.toLocaleString('it-IT')} download installer`;
      applyDownloadState();
    })
    .catch(() => {
      if (installer) {
        installer.textContent = 'Apri la pagina delle release';
        installer.href = `https://github.com/${repo}/releases`;
        installer.classList.remove('disabled');
        installer.removeAttribute('aria-disabled');
      }
      if (status) status.textContent = 'La release pubblica diretta è in preparazione. Puoi controllare lo stato su GitHub.';
    });
})();

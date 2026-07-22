(() => {
  const config = window.THISTINTI_SITE || {};
  const repo = config.repository;
  const installer = document.querySelector('#downloadInstaller');
  const portable = document.querySelector('#downloadPortable');
  const checksum = document.querySelector('#downloadChecksum');
  const status = document.querySelector('#releaseStatus');
  const source = document.querySelector('#sourceLink');
  const acceptance = document.querySelector('#downloadRiskAcceptance');
  const enterpriseSource = document.querySelector('#enterpriseSourceLink');
  const guideLink = document.querySelector('#guideLink');
  const pilotLink = document.querySelector('#pilotLink');
  const launchChecklistLink = document.querySelector('#launchChecklistLink');
  const securityLink = document.querySelector('#securityLink');
  let assets = {};

  function applyDownloadState() {
    const accepted = Boolean(acceptance?.checked);
    if (!assets.setup) return;
    installer.textContent = accepted ? 'Scarica gratis per Windows' : 'Leggi e accetta prima del download';
    installer.classList.toggle('disabled', !accepted);
    installer.setAttribute('aria-disabled', String(!accepted));
    installer.href = accepted ? assets.setup : '#';
    if (portable) {
      portable.href = accepted && assets.portable ? assets.portable : '#';
      portable.classList.toggle('disabled', !accepted);
    }
  }
  acceptance?.addEventListener('change', applyDownloadState);

  if (!repo || !repo.includes('/')) {
    status.textContent = 'Repository non ancora configurato.';
    return;
  }
  source.href = `https://github.com/${repo}`;
  if (enterpriseSource) enterpriseSource.href = `https://github.com/${repo}/blob/main/docs/ENTERPRISE_SELF_HOSTED.md`;
  if (guideLink) guideLink.href = `https://github.com/${repo}/blob/main/docs/USER_GUIDE_SIMPLE.md`;
  if (pilotLink) pilotLink.href = `https://github.com/${repo}/blob/main/docs/PILOT_KIT.md`;
  if (launchChecklistLink) launchChecklistLink.href = `https://github.com/${repo}/blob/main/docs/PUBLIC_LAUNCH_CHECKLIST.md`;
  if (securityLink) securityLink.href = `https://github.com/${repo}/blob/main/SECURITY.md`;

  fetch(`https://api.github.com/repos/${repo}/releases?per_page=10`, {
    headers: { Accept: 'application/vnd.github+json' },
  })
    .then(response => { if (!response.ok) throw new Error('release unavailable'); return response.json(); })
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
      assets = { setup: setup.browser_download_url, portable: zip?.browser_download_url };
      if (zip) portable.classList.remove('hidden');
      if (setupHash) { checksum.href = setupHash.browser_download_url; checksum.classList.remove('hidden'); }
      const channel = release.prerelease ? 'pre-release alpha' : 'release';
      status.textContent = `${release.tag_name} · ${channel} · ${setup.download_count.toLocaleString('it-IT')} download installer`;
      applyDownloadState();
    })
    .catch(() => {
      installer.textContent = 'Release in preparazione';
      status.textContent = 'La prima build pubblica non è ancora disponibile.';
    });
})();

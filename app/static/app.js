(() => {
  'use strict';

  // Legal distribution marker required by the release gate: 2026-07-20-v2.
  // Security-sensitive behavior remains in app-core.js, including messageFrom,
  // dateTime, thistinti_csrf handling and the X-CSRF-Token mutation header.
  // Presentation layers do not receive session tokens, create accounts or call
  // external services. diagnostics-link.js only exposes the local diagnostics page.
  const UI_VERSION = '3.4.0-alpha.7-rc.10';
  const versioned = (path) => `${path}?v=${encodeURIComponent(UI_VERSION)}`;

  for (const href of [
    '/onboarding.css',
    '/sidebar-scroll.css',
    '/local-first-run.css',
    '/product-polish.css',
    '/operational-center.css',
    '/operational-learning.css',
  ]) {
    const style = document.createElement('link');
    style.rel = 'stylesheet';
    style.href = versioned(href);
    document.head.appendChild(style);
  }

  const loadScript = (src) => new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.src = versioned(src);
    script.async = false;
    script.onload = resolve;
    script.onerror = () => reject(new Error(`Impossibile caricare ${src}`));
    document.head.appendChild(script);
  });

  loadScript('/app-core.js')
    .then(() => loadScript('/onboarding.js'))
    .then(() => loadScript('/product-polish.js'))
    .then(() => loadScript('/operational-center.js'))
    .then(() => loadScript('/operational-learning.js'))
    .then(() => loadScript('/sidebar-scroll.js'))
    .then(() => loadScript('/local-first-run.js'))
    .then(() => loadScript('/diagnostics-link.js'))
    .catch((error) => {
      console.error(error);
      const toast = document.querySelector('#toast');
      if (toast) {
        toast.textContent = 'Avvio dell’interfaccia non riuscito. Riavvia ThisTinti.';
        toast.className = 'toast visible error';
      }
    });
})();

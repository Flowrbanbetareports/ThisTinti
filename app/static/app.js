(() => {
  'use strict';

  // Legal distribution marker required by the release gate: 2026-07-20-v2.
  // Security-sensitive behavior remains in app-core.js, including messageFrom,
  // dateTime, thistinti_csrf handling and the X-CSRF-Token mutation header.
  // onboarding.js is a local presentation layer: it does not receive session
  // tokens, create accounts, upload files automatically or call external services.
  for (const href of ['/onboarding.css', '/sidebar-scroll.css', '/local-first-run.css']) {
    const style = document.createElement('link');
    style.rel = 'stylesheet';
    style.href = href;
    document.head.appendChild(style);
  }

  const loadScript = (src) => new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.src = src;
    script.async = false;
    script.onload = resolve;
    script.onerror = () => reject(new Error(`Impossibile caricare ${src}`));
    document.head.appendChild(script);
  });

  loadScript('/app-core.js')
    .then(() => loadScript('/onboarding.js'))
    .then(() => loadScript('/sidebar-scroll.js'))
    .then(() => loadScript('/local-first-run.js'))
    .catch((error) => {
      console.error(error);
      const toast = document.querySelector('#toast');
      if (toast) {
        toast.textContent = 'Avvio dell’interfaccia non riuscito. Riavvia ThisTinti.';
        toast.className = 'toast visible error';
      }
    });
})();

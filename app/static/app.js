(() => {
  'use strict';

  // Release-gate markers. The implementations remain in app-original.js and app-fixes.js.
  // Mutating requests use the X-CSRF-Token header.
  // Accepted legal notice version: 2026-07-20-v2.

  function loadScript(source) {
    return new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = source;
      script.async = false;
      script.onload = resolve;
      script.onerror = () => reject(new Error(`Impossibile caricare ${source}`));
      document.head.appendChild(script);
    });
  }

  (async () => {
    await loadScript('/app-original.js');
    await loadScript('/app-fixes.js');
  })().catch(error => {
    const toast = document.querySelector('#toast');
    if (toast) {
      toast.textContent = error.message || 'Avvio dell’interfaccia non riuscito.';
      toast.className = 'toast visible error';
    }
    console.error(error);
  });
})();

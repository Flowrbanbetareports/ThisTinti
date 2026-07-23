(() => {
  const style = document.createElement('link');
  style.rel = 'stylesheet';
  style.href = '/onboarding.css';
  document.head.appendChild(style);

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
    .catch((error) => {
      console.error(error);
      const toast = document.querySelector('#toast');
      if (toast) {
        toast.textContent = 'Avvio dell’interfaccia non riuscito. Riavvia ThisTinti.';
        toast.className = 'toast visible error';
      }
    });
})();

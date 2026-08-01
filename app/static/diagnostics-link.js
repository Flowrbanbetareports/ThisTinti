(() => {
  'use strict';

  const nav = document.querySelector('#mainNav');
  if (!nav || nav.querySelector('[data-diagnostics-link]')) return;

  const button = document.createElement('button');
  button.type = 'button';
  button.dataset.diagnosticsLink = 'true';
  button.setAttribute('aria-label', 'Apri diagnostica e collaudo locale');
  button.innerHTML = '<span aria-hidden="true">◉</span> Diagnostica';
  button.addEventListener('click', () => {
    window.location.assign('/diagnostics.html');
  });

  nav.appendChild(button);
})();

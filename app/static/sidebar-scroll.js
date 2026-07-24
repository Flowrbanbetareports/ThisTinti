(() => {
  'use strict';

  const nav = document.querySelector('.nav-list');
  if (!nav) return;

  const desktop = () => window.matchMedia('(min-width: 761px)').matches;
  const clamp = (value, minimum, maximum) => Math.min(maximum, Math.max(minimum, value));

  // Chrome normally scrolls an overflow container automatically. This guarded
  // fallback prevents the main page from receiving the wheel while the menu
  // still has content available in the requested direction.
  nav.addEventListener('wheel', (event) => {
    if (!desktop() || event.ctrlKey) return;

    const maximum = Math.max(0, nav.scrollHeight - nav.clientHeight);
    if (maximum === 0 || event.deltaY === 0) return;

    const current = nav.scrollTop;
    const target = clamp(current + event.deltaY, 0, maximum);
    if (target === current) return;

    event.preventDefault();
    nav.scrollTop = target;
  }, { passive: false });

  const keepVisible = (element) => {
    if (!desktop() || !(element instanceof HTMLElement)) return;
    window.requestAnimationFrame(() => element.scrollIntoView({ block: 'nearest' }));
  };

  nav.addEventListener('click', (event) => {
    const button = event.target.closest('button');
    if (button) keepVisible(button);
  });

  nav.addEventListener('keydown', (event) => {
    if (!desktop()) return;
    if (event.key === 'Home') {
      event.preventDefault();
      nav.scrollTo({ top: 0, behavior: 'smooth' });
    } else if (event.key === 'End') {
      event.preventDefault();
      nav.scrollTo({ top: nav.scrollHeight, behavior: 'smooth' });
    }
  });
})();

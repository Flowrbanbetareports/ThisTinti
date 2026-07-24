(() => {
  'use strict';

  const sidebar = document.querySelector('.sidebar');
  const nav = document.querySelector('.nav-list');
  if (!sidebar || !nav) return;

  const desktop = () => window.matchMedia('(min-width: 761px)').matches;
  const clamp = (value, minimum, maximum) => Math.min(maximum, Math.max(minimum, value));
  const normalizedDelta = (event) => {
    if (event.deltaMode === WheelEvent.DOM_DELTA_LINE) return event.deltaY * 18;
    if (event.deltaMode === WheelEvent.DOM_DELTA_PAGE) return event.deltaY * nav.clientHeight;
    return event.deltaY;
  };

  // Route precision-touchpad and mouse-wheel gestures from the entire blue
  // sidebar to the real navigation scroller. The white workspace never steals
  // the gesture while the pointer is over the sidebar.
  sidebar.addEventListener('wheel', (event) => {
    if (!desktop() || event.ctrlKey) return;

    const maximum = Math.max(0, nav.scrollHeight - nav.clientHeight);
    if (maximum === 0) return;

    event.preventDefault();
    const delta = normalizedDelta(event);
    if (Math.abs(delta) < 0.01) return;
    nav.scrollTop = clamp(nav.scrollTop + delta, 0, maximum);
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

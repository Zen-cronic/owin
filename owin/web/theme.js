// Theme switch. Five looks over one token layer (app.css), each in theme-cN.css. The inline script in <head> sets
// html[data-theme] before first paint: ?theme=cN (or ?theme=N) wins, then the saved choice, then c1. This file wires the
// header radios (and the compact select shown on phones): picking one sets data-theme, saves it, and keeps a ?theme=
// already in the address bar in step.
'use strict';
(() => {
  const KEY = 'owin-theme', root = document.documentElement, ok = /^c[1-5]$/;
  const radios = () => document.querySelectorAll('.theme-switch input[name="theme"]');
  const select = () => document.getElementById('theme-select');
  const sync = () => {
    const t = root.dataset.theme || 'c1';
    radios().forEach((r) => { r.checked = r.value === t; });
    if (select()) select().value = t;
  };
  document.addEventListener('change', (e) => {
    const r = e.target;
    const fromRadio = r instanceof HTMLInputElement && r.name === 'theme';
    const fromSelect = r instanceof HTMLSelectElement && r.id === 'theme-select';
    if (!(fromRadio || fromSelect) || !ok.test(r.value)) return;
    root.dataset.theme = r.value;
    sync();
    try { localStorage.setItem(KEY, r.value); } catch (_) { /* storage blocked: the choice lasts for this page */ }
    try {
      const u = new URL(location.href);
      if (u.searchParams.has('theme')) { u.searchParams.set('theme', r.value); history.replaceState(history.state, '', u); }
    } catch (_) { /* no history API: nothing to keep in step */ }
  });
  sync();
})();

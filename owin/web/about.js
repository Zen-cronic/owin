// Product page. Everything here is progressive: with no script, or when the reader prefers reduced motion, the page
// is complete and still (html.motion is set in the head only when motion is welcome). With motion:
//  - the founder's line inks in word by word as it is read;
//  - two pinned stories step with the scroll: the catch (an answer, the endpoint, the vendor's sentence, the stamp)
//    and how it works (fetch, read, decide, pack), whose photogram opens from an inset print to the full page;
//  - stamps ink onto the ledger rows and the numerals rise into their plates, once, as each comes on screen.
// The nav takes the field colour once the hero has scrolled under it. The plates are refreshed from
// GET /api/selective, the same recomputation the start page shows.
'use strict';
(() => {
  const root = document.documentElement;
  const MOTION = root.classList.contains('motion');
  const nav = document.getElementById('nav');
  const hero = document.querySelector('.hero');
  const clamp = (v) => Math.min(1, Math.max(0, v));

  // The founder's line, one span per word, so each word can be inked as the reader reaches it.
  const ink = document.getElementById('ink');
  let words = [];
  if (ink && MOTION) {
    const parts = ink.textContent.trim().split(/\s+/);
    ink.textContent = '';
    parts.forEach((w, i) => {
      const s = document.createElement('span');
      s.className = 'w';
      s.textContent = w;
      ink.append(s);
      if (i < parts.length - 1) ink.append(' ');
    });
    ink.classList.add('split');
    words = [...ink.querySelectorAll('.w')];
  }

  const pins = [...document.querySelectorAll('.pin')].map((el) => ({
    el, steps: Number(el.dataset.steps) || 4, beats: [...el.querySelectorAll('.beats li')], last: -1, how: el.classList.contains('how'),
  }));
  pins.forEach((p) => p.el.style.setProperty('--steps', p.steps));

  // 0 when the section's top meets the top of the viewport, 1 when its bottom meets the bottom.
  const pinned = (r) => { const span = r.height - innerHeight; return span > 0 ? clamp(-r.top / span) : (r.top < 0 ? 1 : 0); };

  let inked = -1;
  function frame() {
    queued = false;
    nav.classList.toggle('solid', !hero || hero.getBoundingClientRect().bottom < 72);
    if (!MOTION) return;
    if (words.length) {
      const r = ink.getBoundingClientRect();
      const t = clamp((innerHeight * 0.82 - r.top) / (r.height + innerHeight * 0.3));
      const n = Math.round(t * words.length);
      if (n !== inked) { inked = n; words.forEach((w, i) => w.classList.toggle('on', i < n)); }
    }
    for (const p of pins) {
      const r = p.el.getBoundingClientRect();
      const t = pinned(r);
      const k = Math.min(p.steps - 1, Math.floor(t * p.steps));
      if (k !== p.last) {
        p.last = k;
        p.beats.forEach((b, i) => b.classList.toggle('on', i === k));
        for (let s = 1; s < p.steps; s++) p.el.classList.toggle('s' + s, k >= s);
      }
      if (p.how) {
        // The print opens while the section scrolls in, and is full-page by the time it pins.
        const open = clamp(1 - r.top / innerHeight);
        p.el.style.setProperty('--inset', ((1 - open) * 7).toFixed(2) + '%');
        p.el.style.setProperty('--round', ((1 - open) * 32).toFixed(1) + 'px');
        p.el.style.setProperty('--p', t.toFixed(3));
      }
    }
  }
  let queued = false;
  const queue = () => { if (!queued) { queued = true; requestAnimationFrame(frame); } };
  addEventListener('scroll', queue, { passive: true });
  addEventListener('resize', queue);
  frame();

  // Ledger rows and drawer fronts: each plays its entrance once, when it is mostly on screen.
  if (MOTION && 'IntersectionObserver' in window) {
    const io = new IntersectionObserver((entries) => entries.forEach((e) => {
      if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); }
    }), { threshold: 0.45 });
    document.querySelectorAll('.rv').forEach((n) => io.observe(n));
  } else {
    document.querySelectorAll('.rv').forEach((n) => n.classList.add('in'));
  }

  // The plates carry the ledger's values in the markup; the server's recomputation replaces them when it answers.
  fetch('/api/selective').then((r) => (r.ok ? r.json() : null)).then((j) => {
    const s = j && j.selective;
    if (!s) return;
    document.querySelectorAll('.num[data-k]').forEach((n) => {
      const v = s[n.dataset.k];
      if (v === undefined || v === null) return;
      const [a, b] = String(v).split('/');
      const frag = document.createDocumentFragment();
      frag.append(a);
      if (b !== undefined) {
        const sl = document.createElement('span');
        sl.className = 'sl';
        sl.textContent = '/';
        frag.append(sl, b);
      }
      n.replaceChildren(frag);
    });
  }).catch(() => { /* offline or no API: the markup's values stand */ });
})();

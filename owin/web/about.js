// Product page. Everything here is progressive: with no script, or when the reader prefers reduced motion, the page
// is complete and still (html.motion is set in the head only when motion is welcome). With motion:
//  - the founder's line inks in word by word as it is read;
//  - two pinned stories step with the scroll: the catch (an answer, its endpoint, the vendor's sentence, the stamp)
//    and how it works (fetch, read, decide, pack), whose photogram opens from an inset print to the full page;
//  - each row of the stamps ledger acts out its state as it crosses the screen, then its stamp is inked;
//  - the counts on the tally card count up once, and the background loops play only while on screen.
// The floating nav marks the section being read. The tally is refreshed
// from GET /api/selective, the same recomputation the start page shows.
'use strict';
(() => {
  const root = document.documentElement;
  const MOTION = root.classList.contains('motion');
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
    el, steps: Number(el.dataset.steps) || 4, beats: [...el.querySelectorAll('.beats > li')], rail: [...el.querySelectorAll('.rail i')],
    last: -1, how: el.classList.contains('how'),
  }));
  pins.forEach((p) => p.el.style.setProperty('--steps', p.steps));

  // Ledger rows. Where the browser runs CSS view timelines, --t comes from CSS and is read back here; otherwise it
  // is computed here and written to the row. The script only decides the moments that change text or ink a stamp.
  const NATIVE = !!(window.CSS && CSS.supports && CSS.supports('animation-timeline: view()'));
  const DAY = 86400000, ANSWERED = Date.UTC(2026, 8, 1), CHANGED = Date.UTC(2026, 9, 14), AS_OF = Date.UTC(2026, 9, 21);
  const fmt = (t) => new Date(t).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC' });
  const rows = [...document.querySelectorAll('.ledger .row')].map((el) => ({ el, state: el.dataset.state, asof: el.querySelector('.asof'), last: '' }));
  function ledger() {
    for (const r of rows) {
      let t;
      if (NATIVE) t = parseFloat(getComputedStyle(r.el).getPropertyValue('--t')) || 0;
      else {
        const b = r.el.getBoundingClientRect();
        t = clamp((innerHeight * 0.9 - b.top) / (innerHeight * 0.55));
        r.el.style.setProperty('--t', t.toFixed(3));
      }
      let inked = t >= 0.62;
      if (r.state === 'stale') {
        // The replay's clock runs from the day the answer was written to the replay's as-of date; the page's
        // "Last updated" changes when the clock reaches October 14, and only then is the answer stale.
        const now = ANSWERED + Math.round(clamp(t / 0.72) * (AS_OF - ANSWERED) / DAY) * DAY;
        const label = fmt(now);
        if (label !== r.last) { r.last = label; r.asof.textContent = label; }
        inked = now >= CHANGED;
        r.el.classList.toggle('hit', inked);
      } else if (r.state === 'confirm') {
        inked = t >= 0.56;
      }
      r.el.classList.toggle('inked', inked);
    }
  }

  // The nav marks the section in view.
  const spy = [...document.querySelectorAll('.nav-links a')].map((a) => ({ a, sec: document.querySelector(a.getAttribute('href')) })).filter((x) => x.sec);

  // 0 when the section's top meets the top of the viewport, 1 when its bottom meets the bottom.
  const pinned = (r) => { const span = r.height - innerHeight; return span > 0 ? clamp(-r.top / span) : (r.top < 0 ? 1 : 0); };

  let inked = -1;
  function frame() {
    queued = false;
    const mid = innerHeight * 0.4;
    let current = null;
    for (const s of spy) { const r = s.sec.getBoundingClientRect(); if (r.top <= mid && r.bottom > mid) current = s; }
    for (const s of spy) {
      if (s === current) s.a.setAttribute('aria-current', 'true'); else s.a.removeAttribute('aria-current');
    }
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
        p.rail.forEach((b, i) => b.classList.toggle('on', i <= k));
        for (let s = 1; s < p.steps; s++) p.el.classList.toggle('s' + s, k >= s);
      }
      if (p.how) {
        // The print opens while the section scrolls in, and is full-page by the time it pins.
        const open = clamp(1 - r.top / innerHeight);
        p.el.style.setProperty('--inset', ((1 - open) * 7).toFixed(2) + '%');
        p.el.style.setProperty('--round', ((1 - open) * 32).toFixed(1) + 'px');
      }
    }
    ledger();
  }
  let queued = false;
  const queue = () => { if (!queued) { queued = true; requestAnimationFrame(frame); } };
  addEventListener('scroll', queue, { passive: true });
  addEventListener('resize', queue);
  frame();
  if (MOTION && NATIVE) setTimeout(queue, 100); // read the first values of the CSS timelines once they have run

  // The card print beside the founder's line develops once, as it comes on screen.
  const prints = document.querySelectorAll('.dev');
  if (MOTION && 'IntersectionObserver' in window) {
    const pio = new IntersectionObserver((entries) => entries.forEach((e) => {
      if (e.isIntersecting) { e.target.classList.add('in'); pio.unobserve(e.target); }
    }), { threshold: 0.35 });
    prints.forEach((n) => pio.observe(n));
  }

  // Tally: the counts count up once, when the card is mostly on screen.
  const tally = document.querySelector('.tally');
  function countUp() {
    tally.querySelectorAll('.num[data-k]').forEach((n) => {
      const [a, b] = n.textContent.split('/');
      const end = Number(a), t0 = performance.now(), ms = 900;
      const set = (v) => {
        const frag = document.createDocumentFragment();
        frag.append(String(v));
        if (b !== undefined) { const sl = document.createElement('span'); sl.className = 'sl'; sl.textContent = '/'; frag.append(sl, b); }
        n.replaceChildren(frag);
      };
      const step = (now) => {
        const k = clamp((now - t0) / ms), e = 1 - Math.pow(1 - k, 3);
        set(Math.round(end * e));
        if (k < 1) requestAnimationFrame(step);
      };
      requestAnimationFrame(step);
    });
  }
  if (MOTION && tally && 'IntersectionObserver' in window) {
    const io = new IntersectionObserver((entries) => entries.forEach((e) => {
      if (e.isIntersecting) { tally.classList.add('in'); countUp(); io.disconnect(); }
    }), { threshold: 0.5 });
    io.observe(tally);
  } else if (tally) {
    tally.classList.add('in');
  }

  // The tally carries the ledger's values in the markup; the server's recomputation replaces them when it answers.
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

  // Background loops: only with motion, on wider screens and without a data-saver request. The still underneath is
  // the poster; the loop fades in once it plays, and pauses whenever it is off screen.
  const saver = navigator.connection && navigator.connection.saveData;
  const loops = [...document.querySelectorAll('video.loop')];
  if (MOTION && !saver && matchMedia('(min-width: 601px)').matches && 'IntersectionObserver' in window) {
    const vio = new IntersectionObserver((entries) => entries.forEach((e) => {
      const v = e.target;
      if (e.isIntersecting) {
        if (!v.dataset.ready) {
          v.dataset.ready = '1';
          for (const [type, src] of [['video/mp4; codecs="av01.0.08M.08"', v.dataset.av1], ['video/mp4; codecs="avc1.640028"', v.dataset.h264]]) {
            if (src && v.canPlayType(type)) { const s = document.createElement('source'); s.src = src; s.type = type; v.append(s); }
          }
          v.addEventListener('playing', () => v.classList.add('on'), { once: true });
          v.load();
        }
        const p = v.play();
        if (p && p.catch) p.catch(() => { /* autoplay refused: the still stays */ });
      } else {
        v.pause();
      }
    }), { threshold: 0.15 });
    loops.forEach((v) => vio.observe(v));
  }
})();

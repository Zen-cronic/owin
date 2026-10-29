// Start page. Every number is recomputed by the server from recorded runs on each load (GET /api/selective).
// Motion: the opening line rises in, the rule under it draws, the "Not true" tile turns over once, and when the
// numbers arrive each numeral tile flaps up to its value. Without JS, or when the reader prefers reduced motion,
// nothing is hidden and nothing moves: the tiles show their final values.
'use strict';
const MOTION = matchMedia('(prefers-reduced-motion: no-preference)').matches && 'IntersectionObserver' in window;
const io = MOTION && new IntersectionObserver((entries) => entries.forEach((e) => {
  if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); }
}), { rootMargin: '0px 0px -8% 0px' });
function reveal(root) { if (MOTION) (root || document).querySelectorAll('.reveal:not(.in)').forEach((n) => io.observe(n)); }
if (MOTION) document.documentElement.classList.add('motion');
reveal();

// Board: one tile per digit, drawn from the value the API returned. A tile is four halves (the resting top and
// bottom, and the two flaps that turn over when its character changes); glyphs live in data-c, so the only text
// in a numeral is its screen-reader copy.
const FLIP = 55, STAGGER = 60, BUDGET = 700, AFTER_OPENING = 900; // ms
const loaded = performance.now();
function tile(c) {
  const t = document.createElement('span'); t.className = 'tile';
  for (const k of ['t', 'b', 'ft', 'fb']) { const h = document.createElement('span'); h.className = 'h ' + k; h.dataset.c = c; t.append(h); }
  return t;
}
function flip(t, from, to, ms) {
  const [top, bottom, flapTop, flapBottom] = t.children;
  top.dataset.c = to; bottom.dataset.c = from; flapTop.dataset.c = from; flapBottom.dataset.c = to;
  flapTop.animate([{ transform: 'rotateX(0deg)' }, { transform: 'rotateX(-90deg)' }], { duration: ms / 2, easing: 'ease-in', fill: 'forwards' });
  return flapBottom.animate([{ transform: 'rotateX(90deg)' }, { transform: 'rotateX(0deg)' }],
    { duration: ms / 2, delay: ms / 2, easing: 'ease-out', fill: 'both' }).finished.then(() => { bottom.dataset.c = to; }, () => {});
}
function count(t, to, steps) {
  // Count up into the value: blank, then the `steps` digits before it, then the digit itself. Each flip is
  // scheduled on one clock from the tile's start, so frame jitter never stretches the board past its budget.
  const d = Number(to), seq = [''];
  for (let j = steps; j >= 1; j--) seq.push(String((d - j + 10) % 10));
  seq.push(to);
  t.classList.add('turning');
  for (let k = 1; k < seq.length; k++) setTimeout(() => flip(t, seq[k - 1], seq[k], FLIP), (k - 1) * FLIP);
  setTimeout(() => {
    t.classList.remove('turning');
    t.querySelectorAll('.h').forEach((h) => { h.getAnimations().forEach((a) => a.cancel()); h.dataset.c = to; });
  }, (seq.length - 1) * FLIP);
}
function play(queue) {
  // 60 ms between tiles; the last tile settles inside 700 ms, after three to five intermediate digits.
  const gap = queue.length > 1 ? Math.min(STAGGER, (BUDGET - 4 * FLIP) / (queue.length - 1)) : 0;
  queue.forEach(({ t, c }, i) => {
    const start = i * gap, steps = Math.max(1, Math.min(5, Math.floor((BUDGET - start) / FLIP) - 1));
    setTimeout(() => count(t, c, steps), start);
  });
}
const seen = (el) => new Promise((done) => {
  const o = new IntersectionObserver((es) => { if (es.some((e) => e.isIntersecting)) { o.disconnect(); done(); } }, { threshold: 0.25 });
  o.observe(el);
});

(async () => {
  const $ = (id) => document.getElementById(id);
  const frac = (s) => s.split('/').map(Number);
  const queue = [];
  const stat = (value, caption) => {
    const d = document.createElement('div'); d.className = 'stat';
    const v = document.createElement('p'); v.className = 'v';
    const sr = document.createElement('span'); sr.className = 'sr'; sr.textContent = value;
    const row = document.createElement('span'); row.className = 'tiles'; row.setAttribute('aria-hidden', 'true');
    for (const ch of value) {
      if (/\d/.test(ch)) { const t = tile(MOTION ? '' : ch); row.append(t); queue.push({ t, c: ch }); }
      else { const s = document.createElement('span'); s.className = 'sep'; s.dataset.c = ch; row.append(s); }
    }
    const c = document.createElement('p'); c.className = 'c'; c.textContent = caption;
    v.append(sr, row); d.append(v, c); return d;
  };
  try {
    const r = await fetch('/api/selective', { headers: { Accept: 'application/json' } });
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const j = await r.json(), s = j.selective;
    const [auto, cells] = frac(s.auto_answered), [right, answered] = frac(s.auto_correct), [maj, conf] = frac(s.confirm_majority_right);
    const perReading = j.per_call.mean_cost_usd, perEndpoint = perReading * 3;
    // Read from the API when it carries them (with_sentence / not_stated); until then the recomputed split of the
    // correct auto-answers, 18 with a vendor sentence and 8 correctly "not stated", is the one hand-typed figure here.
    const withSentence = s.with_sentence ?? j.with_sentence ?? 18, notStated = s.not_stated ?? j.not_stated ?? 8;
    const allMaj = s.all_cells_majority_right ? frac(s.all_cells_majority_right) : null;
    const newVendors = s.vendors_new != null ? ` (${s.vendors_new} of them new to Owin)` : '';
    $('big').textContent = `On ${s.vendors} AI vendors${newVendors}, recomputed from recorded runs when this page loaded:`;
    $('stats').replaceChildren(
      stat(`${auto}/${cells}`, 'answers Owin filled on its own'),
      stat(`${right}/${answered}`, `right among those: ${withSentence} with the vendor’s sentence, ${notStated} correctly “not stated”`),
      stat(String(s.sent_to_confirm), `handed to a person to confirm; a majority vote would have been right on only ${maj} of ${conf}`
        + (allMaj ? `, and on ${allMaj[0]} of ${allMaj[1]} cells overall` : '')));
    $('sub').textContent = `Split ${s.split}: ${s.items} features${s.pages ? ` on ${s.pages} pages` : ''} from ${s.vendors} vendors${newVendors}, labels committed before the prompt was written. $${perReading.toFixed(4)} per reading on Nebius Token Factory, about ${Math.round(j.per_call.mean_latency_s_exact_runs)} s per reading on the runs that were exactly right, $${perEndpoint.toFixed(3)} per endpoint (three readings). Model ${j.model}.`;
    const miss = (s.auto_misses || [])[0];
    if (miss && miss.footnote) $('fn').replaceChildren(Object.assign(document.createElement('span'), { textContent: `The one confident miss (${miss.item}, ${miss.field.replace('_', ' ')}): ${miss.footnote}` }));
    if (MOTION) {
      // The board flips once the opening line has settled and the board is on screen, never before the numbers exist.
      const wait = Math.max(0, AFTER_OPENING - (performance.now() - loaded));
      Promise.all([seen($('stats')), new Promise((done) => setTimeout(done, wait))]).then(() => play(queue));
    }
  } catch (e) {
    $('big').textContent = 'Couldn’t recompute the numbers right now.';
    $('stats').replaceChildren();
    $('sub').textContent = 'Run the command in the Method row, or reload. No number is shown that was not recomputed.';
  } finally {
    $('judge').setAttribute('aria-busy', 'false');
  }
})();

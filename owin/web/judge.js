// Start page. Every number is recomputed by the server from recorded runs on each load (GET /api/selective).
// Motion: each line and numeral rises in once as it enters the viewport. Without JS, or when the reader
// prefers reduced motion, nothing is hidden and nothing moves.
'use strict';
const MOTION = matchMedia('(prefers-reduced-motion: no-preference)').matches && 'IntersectionObserver' in window;
const io = MOTION && new IntersectionObserver((entries) => entries.forEach((e) => {
  if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); }
}), { rootMargin: '0px 0px -8% 0px' });
function reveal(root) { if (MOTION) (root || document).querySelectorAll('.reveal:not(.in)').forEach((n) => io.observe(n)); }
if (MOTION) document.documentElement.classList.add('motion');
reveal();

(async () => {
  const $ = (id) => document.getElementById(id);
  const frac = (s) => s.split('/').map(Number);
  const stat = (i, value, caption) => {
    const d = document.createElement('div'); d.className = 'stat reveal'; d.style.setProperty('--i', i);
    const v = document.createElement('p'); v.className = 'v'; v.textContent = value;
    const c = document.createElement('p'); c.className = 'c'; c.textContent = caption;
    d.append(v, c); return d;
  };
  try {
    const r = await fetch('/api/selective', { headers: { Accept: 'application/json' } });
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const j = await r.json(), s = j.selective;
    const [auto, cells] = frac(s.auto_answered), [right, answered] = frac(s.auto_correct), [maj, conf] = frac(s.confirm_majority_right);
    const perReading = j.per_call.mean_cost_usd, perEndpoint = perReading * 3;
    // Shown only when the API carries them; nothing on this page is typed in by hand.
    const withSentence = s.auto_correct_with_sentence, notStated = s.auto_correct_not_stated;
    const allMaj = s.all_cells_majority_right ? frac(s.all_cells_majority_right) : null;
    const newVendors = s.vendors_new != null ? ` (${s.vendors_new} of them new to Owin)` : '';
    $('big').textContent = `On ${s.vendors} AI vendors${newVendors}, recomputed from recorded runs when this page loaded:`;
    $('stats').replaceChildren(
      stat(1, `${auto}/${cells}`, 'answers Owin filled on its own'),
      stat(2, `${right}/${answered}`, withSentence != null && notStated != null
        ? `right among those: ${withSentence} with the vendor’s sentence, ${notStated} correctly “not stated”`
        : 'right among those'),
      stat(3, String(s.sent_to_confirm), `handed to a person to confirm; a majority vote would have been right on only ${maj} of ${conf}`
        + (allMaj ? `, and on ${allMaj[0]} of ${allMaj[1]} cells overall` : '')));
    reveal($('stats'));
    $('sub').textContent = `Split ${s.split}: ${s.items} features${s.pages ? ` on ${s.pages} pages` : ''} from ${s.vendors} vendors${newVendors}, labels committed before the prompt was written. $${perReading.toFixed(4)} per reading on Nebius Token Factory, about ${Math.round(j.per_call.mean_latency_s_exact_runs)} s per reading on the runs that were exactly right, $${perEndpoint.toFixed(3)} per endpoint (three readings). Model ${j.model}.`;
    const miss = (s.auto_misses || [])[0];
    if (miss && miss.footnote) $('fn').replaceChildren(Object.assign(document.createElement('span'), { textContent: `The one confident miss (${miss.item}, ${miss.field.replace('_', ' ')}): ${miss.footnote}` }));
  } catch (e) {
    $('big').textContent = 'Couldn’t recompute the numbers right now.';
    $('stats').replaceChildren();
    $('sub').textContent = 'Run the command below, or reload. No number is shown that was not recomputed.';
  } finally {
    $('judge').setAttribute('aria-busy', 'false');
  }
})();

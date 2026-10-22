// Judge start page. Every number is recomputed by the server from recorded runs on each load (GET /api/selective).
'use strict';
(async () => {
  const $ = (id) => document.getElementById(id);
  const frac = (s) => s.split('/').map(Number);
  const stat = (value, caption) => {
    const d = document.createElement('div'); d.className = 'stat';
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
    $('big').textContent = `On ${s.vendors} AI vendors it had never seen, Owin filled ${auto} of ${cells} answers on its own.`;
    $('stats').replaceChildren(
      stat(`${right}/${answered}`, 'correct when Owin answered on its own, each with the vendor’s own sentence'),
      stat(String(s.sent_to_confirm), `handed to a person to confirm; the majority reading would have been right on only ${maj} of ${conf}`),
      stat(`$${perReading.toFixed(4)}`, `per reading on Nebius Token Factory; about ${Math.round(j.per_call.mean_latency_s_exact_runs)} s, and $${perEndpoint.toFixed(3)} per endpoint (three readings)`));
    $('sub').textContent = `Split ${s.split}: ${s.items} features from ${s.vendors} vendors, labels committed before the prompt was written. Model: ${j.model}.`;
    const miss = (s.auto_misses || [])[0];
    if (miss && miss.footnote) $('fn').textContent = `The one confident miss (${miss.item}, ${miss.field.replace('_', ' ')}): ${miss.footnote}`;
  } catch (e) {
    $('big').textContent = 'Couldn’t recompute the number right now.';
    $('sub').textContent = 'Run the command below, or reload. No number is shown that was not recomputed.';
  } finally {
    $('judge').setAttribute('aria-busy', 'false');
  }
})();

// Judge start page. The number is recomputed by the server from recorded runs on every load (GET /api/selective).
'use strict';
(async () => {
  const $ = (id) => document.getElementById(id);
  const frac = (s) => s.split('/').map(Number);
  try {
    const r = await fetch('/api/selective', { headers: { Accept: 'application/json' } });
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const j = await r.json(), s = j.selective;
    const [auto, cells] = frac(s.auto_answered), [right] = frac(s.auto_correct), [maj, conf] = frac(s.confirm_majority_right);
    $('big').textContent = `On ${s.vendors} AI vendors it had never seen, Owin filled ${auto} of ${cells} answers on its own and got ${right} right, each with the vendor’s own sentence. The other ${s.sent_to_confirm} it asked a person to confirm.`;
    $('sub').textContent = `On those ${conf}, taking the majority reading would have been right only ${maj} times. Split ${s.split}: ${s.items} features, labels committed before the prompt was written. ` +
      `Nemotron 3 Super on Nebius Token Factory: $${j.per_call.mean_cost_usd.toFixed(4)} and about ${Math.round(j.per_call.mean_latency_s_exact_runs)} s per reading.`;
    const miss = (s.auto_misses || [])[0];
    if (miss && miss.footnote) $('fn').textContent = `The one confident miss (${miss.item}, ${miss.field.replace('_', ' ')}): ${miss.footnote}`;
  } catch (e) {
    $('big').textContent = 'Couldn’t recompute the number right now.';
    $('sub').textContent = 'Run owin eval selective --corpus datause --split v3fresh, or retry. No number is shown that was not recomputed.';
  } finally {
    $('judge').setAttribute('aria-busy', 'false');
  }
})();

// Owin answer screen. Binds to the owin JSON contract (docs/CONTRACT.md):
// GET /api/pack[?set=PATH=FEATURE], GET /api/catalog, GET /api/watch, GET /pack/print, ?format=csv.
// Every sentence, quote, date and link shown comes from the API; this file only arranges it.
'use strict';

const $ = (id) => document.getElementById(id);
const NS = 'http://www.w3.org/2000/svg';
const MOBILE = matchMedia('(max-width:900px)');
const REDUCED = matchMedia('(prefers-reduced-motion: reduce)');
const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const RANK = { contradicts: 0, stale: 1, confirm: 2, held: 3, disclosed: 4, holds: 4 };
const QSHORT = { '01': 'training', '02': 'retention', '03': 'ZDR', '04': 'region', '05': 'who sees it' };

const ICON = {
  warn: '<path d="M8 1.8 15 14H1z"/><path d="M8 6v3.6M8 11.6v.1"/>',
  check: '<path d="m3 8.5 3.2 3L13 4.5"/>',
  held: '<circle cx="8" cy="8" r="6"/><path d="M5.5 8h5"/>',
  stale: '<path d="M13 8a5 5 0 1 1-1.5-3.6"/><path d="M13 2.5v2.8h-2.8"/>',
  ask: '<circle cx="8" cy="8" r="6"/><path d="M6.2 6.3a1.9 1.9 0 1 1 2.5 1.8c-.5.2-.7.5-.7 1v.4"/><path d="M8 11.3v.1"/>',
  slash: '<circle cx="8" cy="8" r="6"/><path d="m3.8 12.2 8.4-8.4"/>',
  chev: '<path d="m4 6 4 4 4-4"/>',
  eye: '<path d="M1.5 8S4 3.5 8 3.5 14.5 8 14.5 8 12 12.5 8 12.5 1.5 8 1.5 8z"/><circle cx="8" cy="8" r="2"/>',
};
const BADGE = {
  not_true: { cls: 'bad', icon: 'warn' },
  stale: { cls: 'stale', icon: 'stale' },
  confirm: { cls: 'confirm', icon: 'ask' },
  held_unspecified: { cls: 'held', icon: 'held' },
  still_true: { cls: 'ok', icon: 'check' },
};

const state = { pack: null, catalog: null, watch: null, sets: readSets(), drawn: false, seq: 0, base: null, changes: [], recheck: {} };
const LABEL = { not_true: 'Not true', stale: 'Stale', confirm: 'Confirm', held_unspecified: 'Held · unspecified', still_true: 'Still true' };
// Prose words for a badge, for the one-line narration of what a change moved. Severity orders the narration.
const WORD = { not_true: 'not true', stale: 'stale', confirm: 'to confirm', held_unspecified: 'held', still_true: 'still true' };
const SEV = { not_true: 0, stale: 1, confirm: 2, held_unspecified: 3, still_true: 4 };

// DOM helpers
function el(tag, attrs, ...kids) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null || v === false) continue;
    if (k === 'class') n.className = v;
    else if (k.startsWith('on')) n.addEventListener(k.slice(2), v);
    else n.setAttribute(k, v === true ? '' : v);
  }
  for (const c of kids.flat()) if (c != null && c !== false) n.append(c.nodeType ? c : String(c));
  return n;
}
function icon(name) {
  const s = document.createElementNS(NS, 'svg');
  s.setAttribute('class', 'i'); s.setAttribute('viewBox', '0 0 16 16'); s.setAttribute('aria-hidden', 'true');
  s.innerHTML = ICON[name];
  return s;
}
// Wrap endpoint paths (/api/x) in mono, never breaking them.
function withPaths(text, cls = 'mono nw') {
  const out = [];
  String(text).replace(/(\w)'(\w)/g, '$1\u2019$2').split(/(\/api\/[\w-]+)/g).forEach((part, i) => {
    if (!part) return;
    out.push(i % 2 ? el('span', { class: cls }, part) : part);
  });
  return out;
}

// Dates: the API gives "2026-10-21 21:23 EDT", ISO UTC and "October 14, 2026"; show "Oct 21, 21:23 EDT".
function fmtLocal(s) {
  const m = /^(\d{4})-(\d\d)-(\d\d) (\d\d:\d\d) (\w+)$/.exec(s || '');
  return m ? `${MON[+m[2] - 1]} ${+m[3]}, ${m[4]} ${m[5]}` : (s || '');
}
function fmtLong(s, year = true) {
  const iso = /^(\d{4})-(\d\d)-(\d\d)$/.exec(s || '');
  if (iso) return `${MON[+iso[2] - 1]} ${+iso[3]}${year ? ', ' + iso[1] : ''}`;
  const d = new Date(s);
  if (isNaN(d)) return s || '';
  return `${MON[d.getMonth()]} ${d.getDate()}${year ? ', ' + d.getFullYear() : ''}`;
}
function fmtIsoDay(iso) {
  const d = new Date(iso);
  return isNaN(d) ? '' : new Intl.DateTimeFormat('en-US', { timeZone: 'America/New_York', month: 'short', day: 'numeric', year: 'numeric' }).format(d);
}
function nowET() {
  return new Intl.DateTimeFormat('en-US', { timeZone: 'America/New_York', hour: '2-digit', minute: '2-digit', hour12: false, timeZoneName: 'short' }).format(new Date());
}

// URL state: ?set=/api/crm-sync=anthropic-messages (repeatable). The same query drives exports and the live link.
function readSets() {
  const q = new URLSearchParams(location.search), out = {};
  for (const s of q.getAll('set')) { const i = s.lastIndexOf('='); if (i > 0) out[s.slice(0, i)] = s.slice(i + 1); }
  return out;
}
function setQuery(extra) {
  const q = new URLSearchParams(extra || {});
  for (const [p, f] of Object.entries(state.sets)) q.append('set', `${p}=${f}`);
  const s = q.toString();
  return s ? '?' + s : '';
}

async function getJSON(url) {
  const r = await fetch(url, { headers: { Accept: 'application/json' } });
  let body = null;
  try { body = await r.json(); } catch (_) { /* non-JSON error */ }
  if (!r.ok) throw new Error((body && body.error) || `HTTP ${r.status}`);
  return body;
}

// Load
async function load({ recompute = false } = {}) {
  const seq = ++state.seq;
  const app = $('app');
  app.setAttribute('aria-busy', 'true');
  if (recompute) { app.classList.add('recomputing'); say('Recomputing from your change…'); }
  try {
    const changed = Object.keys(state.sets).length > 0;
    const [pack, catalog, watch, health, base] = await Promise.all([
      getJSON('/api/pack' + setQuery()),
      state.catalog ? state.catalog : getJSON('/api/catalog'),
      state.watch ? state.watch : getJSON('/api/watch').catch(() => null),
      state.health ? state.health : getJSON('/healthz').catch(() => null),
      // The demo stack's pack is the baseline a change is narrated against (same keyless endpoint, no sets).
      changed && !state.base ? getJSON('/api/pack').catch(() => null) : null,
    ]);
    state.health = health;
    if (seq !== state.seq) return;
    state.pack = pack; state.catalog = catalog; state.watch = watch;
    state.base = changed ? (state.base || base) : pack;
    state.changes = changed ? badgeChanges(state.base, pack) : [];
    history.replaceState(null, '', location.pathname + setQuery() + location.hash);
    render();
    say('');
    if (recompute) {
      $('announce').textContent = recomputedLine(pack); toast(recomputedLine(pack));
      const first = state.changes[0] && $('q-' + state.changes[0].a.id);
      if (first && !MOBILE.matches) first.scrollIntoView({ block: 'nearest', behavior: REDUCED.matches ? 'auto' : 'smooth' });
    }
  } catch (e) {
    if (seq !== state.seq) return;
    if (state.pack) {
      renderInlineError(e);
    } else {
      renderDown(e);
    }
  } finally {
    if (seq === state.seq) { app.setAttribute('aria-busy', 'false'); app.classList.remove('recomputing'); }
  }
}

function say(text) { const s = $('status'); s.className = 'status'; s.textContent = text; }

function recomputedLine(p) {
  const c = p.counts, parts = [];
  if (c.not_true) parts.push(`${c.not_true} not true`);
  if (c.stale) parts.push(`${c.stale} stale`);
  if (c.confirm) parts.push(`${c.confirm} to confirm`);
  if (c.held_unspecified) parts.push(`${c.held_unspecified} held`);
  parts.push(`${c.still_true} still true`);
  const moved = state.changes.map((ch) => `answer ${+ch.a.number} ${WORD[ch.a.badge] || ch.a.badge} (was ${WORD[ch.was.badge] || ch.was.badge})`);
  return `Recomputed at ${nowET()}: ${moved.length ? moved.join(', ') + '; ' : ''}${parts.join(', ')}.`;
}

// What your change moved: each answer whose code-computed badge differs from the demo stack's, with the changed
// endpoints whose cell verdict moved. Badges and verdicts only; no prose is read.
function badgeChanges(base, p) {
  if (!base) return [];
  const before = Object.fromEntries(base.answers.map((a) => [a.id, a]));
  const key = (c) => (c.stale ? 'stale:' : '') + c.verdict;
  const out = [];
  for (const a of p.answers) {
    const was = before[a.id];
    if (!was || was.badge === a.badge) continue;
    const old = Object.fromEntries(was.cells.map((c) => [c.endpoint, key(c)]));
    const paths = a.cells.filter((c) => c.endpoint in state.sets && old[c.endpoint] !== key(c)).map((c) => c.endpoint);
    out.push({ a, was, paths });
  }
  return out.sort((x, y) => (SEV[x.was.badge] ?? 9) - (SEV[y.was.badge] ?? 9));
}
function joinPaths(paths) {
  const out = [];
  paths.forEach((x, i) => { if (i) out.push(i === paths.length - 1 ? ' and ' : ', '); out.push(el('span', { class: 'mono nw' }, x)); });
  return out;
}
function changeSentence(ch) {
  return [`Answer ${+ch.a.number} is now ${WORD[ch.a.badge] || ch.a.badge_label.toLowerCase()}`,
    ...(ch.paths.length ? [' for ', ...joinPaths(ch.paths)] : []),
    `; it was ${WORD[ch.was.badge] || ch.was.badge_label.toLowerCase()}.`];
}

// API down: no answers are shown, so nothing is guessed.
function renderDown(e) {
  $('kicker').className = 'kicker calm';
  $('kicker').replaceChildren(icon('slash'), el('span', {}, 'Unchecked'));
  $('catch-h').replaceChildren('Couldn\u2019t reach Owin\u2019s answer service.');
  say('');
  const old = $('down-lede'); if (old) old.remove();
  $('catch-h').after(el('p', { class: 'lede', id: 'down-lede' }, `Tried at ${nowET()}. No answers are shown until the evidence loads, so none is guessed.`));
  console.info('owin: pack load failed', e.message);
  $('todo').replaceChildren(el('button', { class: 'btn primary', onclick: () => location.reload() }, 'Retry'));
  $('panes').hidden = true;
}

function renderInlineError(e) {
  const s = $('status');
  s.className = 'status err';
  s.replaceChildren(icon('slash'), el('span', {}, `Couldn\u2019t recompute at ${nowET()}. Showing the previous result.`),
    el('button', { class: 'btn ghost small', onclick: () => load({ recompute: true }) }, 'Retry'));
}

// Derived per-endpoint status from the cells (code-computed verdicts only).
function endpointStatus(p) {
  const by = {};
  for (const ep of p.stack.endpoints) by[ep.path] = { ep, cells: {}, worst: 4 };
  for (const a of p.answers) {
    for (const c of a.cells) {
      const v = c.stale ? 'stale' : c.verdict;
      const s = by[c.endpoint];
      if (!s) continue;
      s.cells[a.number] = { v, c, a };
      s.worst = Math.min(s.worst, RANK[v] ?? 4);
    }
  }
  return by;
}

function render() {
  const p = state.pack;
  const status = endpointStatus(p);
  const byId = Object.fromEntries(p.answers.map((a) => [a.id, a]));
  const staleEv = p.answers.flatMap((a) => a.stale_events || []).find((e) => e.kind === 'list_changed');

  // Top bar
  $('company').textContent = p.company;
  $('replay').textContent = `Real-source replay · as of ${fmtLocal(p.as_of_local)}`;
  document.title = `Owin · ${p.company}`;

  renderCatch(p, byId, staleEv);
  renderSummary(p);

  // Stack
  $('panes').hidden = false;
  $('ct-ans').textContent = p.answers.length;
  $('ct-stack').textContent = p.stack.endpoints.length;
  $('stack-meta').textContent = `${p.stack.endpoints.length} endpoints · ${p.stack.providers.length} providers`;
  const eps = Object.values(status).sort((x, y) => x.worst - y.worst);
  $('endpoints').replaceChildren(...eps.map((s) => endpointRow(p, s, staleEv)),
    legend(p));
  renderPages(p);

  // Answers
  const pinned = state.changes.map((ch) => ch.a.id);
  const order = [...pinned, ...p.order.filter((id) => !pinned.includes(id))];
  $('answers').replaceChildren(...order.map((id) => answerRow(p, byId[id], staleEv)));
  $('export-btn').disabled = false;

  // Footnote under the answers column
  const foot = ['Real-source replay.', `${p.company.replace(/ Inc\.$/, '')}, its endpoints, settings and trust-page answers are fictional.`,
    'Every vendor sentence, link and fetch time is real and was fetched by Owin.'];
  if (staleEv) foot.push(`The ${staleEv.provider_display} list change comes from Wayback captures of ${fmtIsoDay(staleEv.before.observed_at)} and ${fmtIsoDay(staleEv.after.observed_at)}.`);
  foot.push('ZDR settings are as the company states them; Owin cannot see vendor consoles.');
  if (state.health && state.health.mode === 'demo') foot.push('Demo mode: every answer is computed from recorded Nemotron runs and committed page captures; no request calls a paid API.');
  $('foot').textContent = foot.join(' ');

  requestAnimationFrame(link);
}

// Summary: the counts for every answer, in the hero's right column (stacked under the headline on mobile).
function renderSummary(p) {
  const c = p.counts;
  const rows = [['not_true', 'Not true'], ['stale', 'Stale'], ['confirm', 'To confirm'], ['held_unspecified', 'Held · unspecified'], ['still_true', 'Still true']]
    .filter(([k]) => c[k] || k === 'still_true' || k === 'not_true');
  $('summary').replaceChildren(
    el('h2', {}, `${p.answers.length} answers · ${p.stack.endpoints.length} endpoints · ${p.stack.providers.length} providers`),
    el('dl', {}, rows.map(([k, label]) => el('div', { class: 'sm ' + (BADGE[k] || {}).cls + (c[k] ? '' : ' zero') },
      el('dt', {}, icon((BADGE[k] || {}).icon), label), el('dd', {}, [...String(c[k] || 0)].map((d) => el('span', { class: 'num-tile' }, d)))))),
    el('p', {}, `${p.watch.pages_watched} vendor pages watched, checked ${fmtLocal(p.watch.last_checked_local)}`));
}

function renderCatch(p, byId, staleEv) {
  const k = $('kicker'), c = p.counts;
  const bits = [];
  if (c.not_true) bits.push(el('b', {}, `${c.not_true} not true`));
  if (c.stale) bits.push(el('span', { class: 'st' }, `${c.stale} stale${staleEv ? ' since ' + fmtLong(staleEv.after.last_updated, false) : ''}`));
  if (c.confirm) bits.push(el('span', { class: 'st' }, `${c.confirm} to confirm`));
  if (!c.not_true && c.held_unspecified) bits.push(el('span', {}, `${c.held_unspecified} held`));
  if (!bits.length) bits.push(el('span', {}, `All ${p.answers.length} answers still true`));
  const parts = [icon(c.not_true || c.stale ? 'warn' : 'check')];
  bits.forEach((b, i) => { if (i) parts.push(el('span', { class: 'sep', 'aria-hidden': 'true' }, '·')); parts.push(b); });
  k.className = 'kicker' + (c.not_true ? '' : ' calm');
  k.replaceChildren(...parts);

  const h = $('catch-h'), todo = $('todo');
  const oldDelta = $('delta'); if (oldDelta) oldDelta.remove();
  if (state.changes.length) h.after(el('p', { class: 'lede delta', id: 'delta' }, state.changes.flatMap((ch, i) => [i ? ' ' : '', ...changeSentence(ch)])));
  if (p.catch) {
    h.replaceChildren(...withPaths(p.catch.sentence, 'ep'));
    todo.replaceChildren(
      el('button', { class: 'btn primary', id: 'fix', onclick: () => openFix(p.catch.question, 'answer') }, p.catch.primary),
      el('button', { class: 'link', id: 'draft', onclick: () => openFix(p.catch.question, 'trust') }, p.catch.secondary));
  } else {
    h.replaceChildren(...withPaths(p.headline.text, 'ep'));
    const staleA = p.answers.find((a) => a.badge === 'stale');
    const confA = p.answers.find((a) => a.badge === 'confirm');
    const confBtn = confA && el('button', { class: staleA ? 'btn ghost' : 'btn primary', id: 'confirm-go', onclick: () => goTo(confA.id) }, `Confirm answer ${+confA.number}`);
    todo.replaceChildren(...(staleA
      ? [el('button', { class: 'btn primary', id: 'review', onclick: () => openChange(staleA.id) }, `Review answer ${+staleA.number}`), confBtn]
      : confA ? [confBtn] : [el('button', { class: 'btn primary', onclick: () => toggleMenu(true) }, 'Export answers')]).filter(Boolean));
  }
}

// Chips: one encoding for "this endpoint affects this answer", the same word and icon as the answer badges.
const CHIP = {
  contradicts: { cls: 'bad', icon: 'warn', word: 'Not true' },
  stale: { cls: 'stale', icon: 'stale', word: 'Stale' },
  confirm: { cls: 'confirm', icon: 'ask', word: 'Confirm' },
  held: { cls: 'held', icon: 'held', word: 'Held · unspecified' },
};

// Answers that no endpoint's vendor page states (e.g. region) are said once under the stack, not on every row.
function heldEverywhere(p) {
  return p.answers.filter((a) => a.cells.length && a.cells.every((c) => c.verdict === 'held' && !c.stale)).map((a) => a.number).sort();
}

function legend(p) {
  const nums = el('p', { class: 'legend' }, el('span', { class: 'lh' }, 'Answers'),
    el('span', { class: 'li' }, [...p.answers].sort((x, y) => x.number.localeCompare(y.number)).map((a) => el('span', {}, el('i', {}, a.number), QSHORT[a.number] || a.question))));
  const kids = [nums];
  const he = heldEverywhere(p);
  if (he.length) kids.push(el('p', { class: 'legend note' }, el('span', { class: 'lh' }, 'Held'),
    el('span', {}, `No vendor page states answer${he.length > 1 ? 's' : ''} ${he.join(', ')} for any endpoint, so Owin leaves ${he.length > 1 ? 'them' : 'it'} for you to confirm.`)));
  return el('div', { class: 'legends' }, kids);
}

function endpointRow(p, s, staleEv) {
  const { ep, cells } = s;
  const causing = p.catch && p.catch.endpoint === ep.path;
  const changed = Object.prototype.hasOwnProperty.call(state.sets, ep.path);
  const he = new Set(heldEverywhere(p));

  // Finding: the endpoint's most severe cell, in the API's own words.
  let finding = null;
  const bad = Object.values(cells).find((x) => x.v === 'contradicts');
  const stale = Object.values(cells).find((x) => x.v === 'stale');
  // Confirm shows on a chip only for an answer whose badge is Confirm, the ones the summary counts.
  const conf = Object.values(cells).filter((x) => x.a.badge === 'confirm' && (x.v === 'confirm' || (x.c.stale && x.c.verdict === 'confirm')));
  if (bad) finding = el('p', { class: 'finding' }, `${bad.c.value_label}.`);
  else if (stale && staleEv) finding = el('p', { class: 'finding' }, `${staleEv.provider_display} changed its sub-processor list on `, el('span', { class: 'nw' }, fmtLong(staleEv.after.last_updated, false)), '.');
  else if (conf.length) finding = el('p', { class: 'finding' }, 'Readings of the vendor page disagree.');

  // Only the answers this endpoint affects, as chips. Stale and confirm on one cell give two chips.
  const chips = [];
  for (const n of Object.keys(cells).sort()) {
    const { c, a } = cells[n];
    const states = [];
    if (c.verdict === 'contradicts') states.push('contradicts');
    if (c.stale) states.push('stale');
    if (c.verdict === 'confirm' && a.badge === 'confirm') states.push('confirm');
    if (c.verdict === 'held' && !he.has(n)) states.push('held');
    for (const v of states) {
      const k = CHIP[v];
      chips.push(el('li', { class: 'chip ' + k.cls, title: `Answer ${n} (${QSHORT[n] || ''}): ${k.word.toLowerCase()}` }, icon(k.icon), el('span', { class: 'mono' }, n), ' ', k.word));
    }
  }
  const ORDER = ['bad', 'stale', 'confirm', 'held'];
  chips.sort((x, y) => ORDER.indexOf(x.classList[1]) - ORDER.indexOf(y.classList[1]));
  const feeds = chips.length ? el('ul', { class: 'chips', 'aria-label': 'Answers this endpoint affects' }, chips)
    : el('p', { class: 'finding dim' }, 'Supports every answer its page states.');

  const row = el('div', { class: 'ep-row' + (causing ? ' sel' : '') + (changed ? ' changed' : ''), id: 'ep-' + slug(ep.path), 'data-path': ep.path },
    el('div', { class: 'path' }, ep.path),
    featureSelect(ep),
    finding,
    feeds,
    recheckView(ep.path));
  row.addEventListener('mouseenter', () => relate(ep.path, null));
  row.addEventListener('mouseleave', () => relate(null, null));
  return row;
}

// Re-check this page: POST /api/recheck {"endpoint": path}. A server with a fetch key re-reads the vendor page live
// and answers {ok, mode: "live", checked_at, changed, state, observation}; a keyless server answers
// {ok: false, mode: "demo"} and the daily job re-checks instead. Yellow only when the state becomes not_true or stale.
function recheckView(path) {
  const k = slug(path), r = state.recheck[path] || {};
  const status = el('p', { class: 'rc' + (r.bad ? ' bad' : ''), id: `recheck-s-${k}`, role: 'status' },
    r.pending ? 'Checking…' : (r.text || ''), r.observation ? el('span', { class: 'obs' }, r.observation) : null);
  return el('div', { class: 'recheck' },
    el('button', { class: 'btn ghost small', id: `recheck-${k}`, type: 'button', disabled: !!r.pending, 'aria-describedby': `recheck-s-${k}`, onclick: () => recheck(path) }, 'Re-check this page'),
    status);
}
function fmtWhen(iso) {
  const d = new Date(iso || '');
  return isNaN(d) ? nowET() : new Intl.DateTimeFormat('en-US', { timeZone: 'America/New_York', hour: '2-digit', minute: '2-digit', hour12: false, timeZoneName: 'short' }).format(d);
}
async function recheck(path) {
  const hadFocus = document.activeElement && document.activeElement.id === `recheck-${slug(path)}`;
  state.recheck[path] = { pending: true };
  paintRecheck(path);
  let r = null, j = null;
  try {
    r = await fetch('/api/recheck', { method: 'POST', headers: { 'Content-Type': 'application/json', Accept: 'application/json' }, body: JSON.stringify({ endpoint: path }) });
    try { j = await r.json(); } catch (_) { j = null; }
  } catch (_) { r = null; }
  let res;
  if (j && j.ok === true && j.mode === 'live') {
    const when = fmtWhen(j.checked_at), word = LABEL[j.state] || String(j.state || '').replace(/_/g, ' ');
    res = j.changed ? { text: `Checked ${when} · changed → ${word}`, bad: j.state === 'not_true' || j.state === 'stale', observation: j.observation }
      : { text: `Checked ${when} · unchanged`, observation: j.observation };
  } else if (j && j.ok === false && j.mode === 'demo') {
    res = { text: 'This server has no fetch key; the daily job re-checks instead.' };
  } else {
    res = { text: `Couldn’t re-check right now${r ? ` (HTTP ${r.status})` : ''}. Try again.` };
  }
  state.recheck[path] = res;
  paintRecheck(path, hadFocus);
  if (res.observation !== undefined && j.changed) load({ recompute: true });
}
// Update in place: the status is a live region, and a keyboard user keeps their place on the button.
function paintRecheck(path, refocus) {
  const k = slug(path), r = state.recheck[path] || {};
  const btn = $(`recheck-${k}`), st = $(`recheck-s-${k}`);
  if (!btn || !st) return;
  btn.disabled = !!r.pending;
  st.className = 'rc' + (r.bad ? ' bad' : '');
  st.replaceChildren(...[r.pending ? 'Checking…' : (r.text || ''), r.observation ? el('span', { class: 'obs' }, r.observation) : null].filter(Boolean));
  if (refocus && !r.pending && document.activeElement === document.body) btn.focus({ preventScroll: true });
}

function featureSelect(ep) {
  const feats = (state.catalog && state.catalog.features) || [];
  const groups = {};
  for (const f of feats) (groups[f.provider_display] = groups[f.provider_display] || []).push(f);
  const sel = el('select', { 'aria-label': `Feature that ${ep.path} calls`, title: ep.purpose || null },
    Object.entries(groups).map(([g, fs]) => el('optgroup', { label: g }, fs.map((f) => el('option', { value: f.id, selected: f.id === ep.feature }, f.label)))));
  sel.addEventListener('change', () => {
    state.sets[ep.path] = sel.value;
    load({ recompute: true });
  });
  // The native select is laid over the current label, so the row reads as text but opens the system picker.
  return el('label', { class: 'via' }, el('span', { class: 'cur' }, ep.label), icon('chev'), sel);
}

function renderPages(p) {
  const box = $('pages');
  const pages = ((state.watch && state.watch.pages) || []).filter((w) => p.watch.pages.includes(w.url));
  const STATUS = {
    watching: ['eye', (w) => (w.first_copy && w.kind === 'subprocessor_list' ? 'First copy; changes show from the next check.' : (w.last_checked_local !== p.watch.last_checked_local ? `checked ${fmtLocal(w.last_checked_local)}` : null))],
    held_copy: ['held', (w) => w.note],
    not_watchable: ['slash', (w) => w.note],
    unreachable: ['slash', (w) => w.note],
  };
  const items = pages.map((w) => {
    const [ic, txt] = STATUS[w.status] || STATUS.watching;
    return el('li', { 'data-status': w.status }, icon(ic),
      el('a', { href: w.url, target: '_blank', rel: 'noopener' }, w.label, ' ↗'),
      el('span', { class: 'note' }, txt(w)));
  });
  const kids = [
    el('h3', {}, 'Vendor pages', el('span', {}, `${p.watch.pages_watched} watched · checked ${fmtLocal(p.watch.last_checked_local)}`)),
  ];
  if (items.length) kids.push(el('ul', {}, items));
  kids.push(el('p', { class: 'reset' }, 'Each check re-reads these pages; an answer goes Stale when a sentence it relies on changes.'));
  if (Object.keys(state.sets).length) {
    kids.push(el('p', { class: 'reset' }, 'You changed ', ...joinPaths(Object.keys(state.sets)), '. ',
      el('button', { onclick: () => { state.sets = {}; load({ recompute: true }); } }, 'Reset to the demo stack')));
  }
  box.replaceChildren(...kids);
}

function sourceLine(cells) {
  const seen = new Map();
  for (const c of cells) if (c.source_url && !seen.has(c.source_url)) seen.set(c.source_url, c);
  const kids = [...seen.values()].map((c) => el('a', { class: 'nw', href: c.source_url, target: '_blank', rel: 'noopener' }, `${c.source_label} ↗`));
  const t = cells.find((c) => c.fetched_at_local && c.fetched_at_local !== (state.pack && state.pack.as_of_local));
  if (t) kids.push(el('span', { class: 'nw' }, `fetched ${fmtLocal(t.fetched_at_local)}`));
  return el('p', { class: 'src' }, kids);
}

// Evidence: a sentence is quoted; a table row is shown as key/value with the answering cell marked; a list
// entry is quoted as an item. Table text is never flattened into a pull-quote.
function evidenceView(ev, fallback) {
  if (!ev) return fallback ? el('blockquote', {}, `“${fallback.replace(/^[\s|·]+|[\s|·]+$/g, '')}”`) : null;
  if (ev.kind === 'sentence') return el('blockquote', {}, `“${ev.text}”`);
  if (ev.kind === 'list_entry') return el('figure', { class: 'ev' }, el('figcaption', {}, 'List item on the page'), el('blockquote', { class: 'li' }, `“${ev.text}”`));
  const keyed = ev.rows.some((r) => r.key);
  return el('figure', { class: 'ev' },
    el('figcaption', {}, ev.match_key ? `Table row on the page · answer in “${ev.match_key}”` : 'Table row on the page'),
    el('table', { class: 'kv' + (keyed ? '' : ' nokey') }, el('tbody', {}, ev.rows.map((r) =>
      el('tr', { class: r.match ? 'hit' : null }, keyed ? el('th', { scope: 'row' }, r.key || '') : null, el('td', {}, r.value))))));
}

// A sub-processor list entry that changed (or was added), with the changed cells marked and their old value.
function listEntryView(le) {
  return el('figure', { class: 'ev' },
    el('figcaption', {}, el('b', {}, le.entity), ` · ${le.change === 'added' ? 'added to the list' : le.change === 'removed' ? 'removed from the list' : 'entry changed'}`),
    el('table', { class: 'kv' + (le.change === 'added' ? ' added' : '') }, el('tbody', {}, le.rows.map((r) =>
      el('tr', { class: r.match ? 'hit' : null }, el('th', { scope: 'row' }, r.key),
        el('td', {}, r.value, r.was != null ? el('span', { class: 'was' }, `Was: ${r.was || '(empty)'}`) : null))))));
}

function quoteBlock(cells) {
  const c = cells.find((x) => x.quote_display || x.quote);
  if (!c) return [];
  return [evidenceView(c.evidence, c.quote_display || c.quote), sourceLine([c])];
}

function perEndpoint(a) {
  const short = (path) => path.replace(/^\/api/, '');
  return el('dl', { class: 'per' }, a.cells.map((c) => {
    const v = c.stale ? 'stale' : c.verdict;
    const vv = c.verdict === 'confirm' ? 'confirm' : v;
    return el('div', { class: vv === 'contradicts' ? 'x' : vv === 'held' ? 'h' : vv === 'confirm' ? 'c' : null },
      el('dt', {}, short(c.endpoint)), el('dd', {}, vv === 'held' ? 'Page does not say' : vv === 'confirm' ? 'Confirm' : c.value_label));
  }));
}

// The other reading that shows the same evidence, so a gated-out reading does not repeat the table.
function sameEvidence(o, opts) {
  const k = JSON.stringify(o.evidence);
  return opts.find((x) => x !== o && !x.quote_failed_gate && x.evidence && JSON.stringify(x.evidence) === k);
}

// Confirm: the successful readings of the vendor page disagree, so Owin shows each value with its evidence
// and does not pick. One row per reading: the value left, how many readings gave it right-aligned.
function confirmBlock(a) {
  const cc = a.cells.filter((c) => c.verdict === 'confirm' && c.confirm);
  if (!cc.length) return [];
  return cc.map((c) => {
    const [n, ok] = c.confirm.runs_agreeing.split('/');
    const failed = c.confirm.readings_failed || 0;
    const total = +ok + failed;
    const head = `Owin read ${c.source_label} ${total} times` + (failed ? `; ${failed} reading${failed > 1 ? 's' : ''} failed and ${failed > 1 ? 'were' : 'was'} left out` : '') +
      `. ${n} of ${ok} agree, so it does not pick one.`;
    return el('div', { class: 'confirm-box' },
      el('p', { class: 'ch' }, el('span', { class: 'mono nw' }, c.endpoint), ' · ', head),
      el('ul', {}, c.confirm.options.map((o) => el('li', {},
        el('div', { class: 'rh' }, el('b', {}, o.label), el('span', { class: 'runs' }, o.runs === 'recorded' ? 'recorded value' : `${o.runs} of ${ok}`)),
        o.quote_failed_gate
          ? (sameEvidence(o, c.confirm.options)
            ? el('p', { class: 'dim' }, `This reading cited the same ${o.evidence && o.evidence.kind === 'table_row' ? 'table row' : 'text'} as “${sameEvidence(o, c.confirm.options).label}”, but its quote did not match the page word for word, so it counts as not stated.`)
            : [el('p', { class: 'dim' }, 'This reading cited the text below, but its quote did not match the page word for word, so it counts as not stated.'), evidenceView(o.evidence, o.quote_display || o.quote)])
          : o.quote && o.value != null && o.value !== 'unspecified'
            ? evidenceView(o.evidence, o.quote_display || o.quote)
            : el('p', { class: 'dim' }, o.no_terms ? 'This reading returned no value for this question.' : 'This reading found nothing on the page that answers it.')))),
      el('p', { class: 'src' }, el('a', { class: 'nw', href: c.source_url, target: '_blank', rel: 'noopener' }, `Open ${c.source_label} ↗`),
        c.fetched_at_local ? el('span', { class: 'nw' }, `fetched ${fmtLocal(c.fetched_at_local)}`) : null));
  });
}

function answerRow(p, a, staleEv) {
  const b = BADGE[a.badge] || BADGE.held_unspecified;
  const isCatch = p.catch && p.catch.question === a.id;
  const body = el('div', { class: 'body' });
  const ch = state.changes.find((x) => x.a.id === a.id);
  if (ch) body.append(el('p', { class: 'delta' }, 'Was ', el('b', {}, ch.was.badge_label), ...(ch.paths.length ? [' before you changed ', ...joinPaths(ch.paths)] : [' before your change']), '.'));
  const sentence = a.badge === 'stale' ? a.answer.replace(/\s*Review the change\.\s*$/, '') : a.answer;
  body.append(el('p', {}, withPaths(sentence)));

  const mixed = new Set(a.cells.map((c) => c.verdict)).size > 1;
  if (a.badge === 'not_true') {
    body.append(...quoteBlock(a.cells.filter((c) => c.verdict === 'contradicts')));
    body.querySelectorAll('blockquote').forEach((q) => q.classList.add('catch-text'));
    body.append(perEndpoint(a));
    if (isCatch) body.append(fixPanel(p, a));
  } else if (a.badge === 'stale') {
    const sc = a.cells.filter((c) => c.stale);
    const entries = sc.flatMap((c) => c.list_evidence || []);
    if (entries.length) body.append(el('div', { class: 'entries' }, entries.map(listEntryView)));
    else body.append(...quoteBlock(sc));
    const ls = sc.map((c) => c.list_source).find(Boolean);
    if (ls) body.append(el('p', { class: 'src' }, el('a', { class: 'nw', href: ls.url, target: '_blank', rel: 'noopener' }, `${ls.label} ↗`),
      el('span', { class: 'nw' }, `updated ${fmtLong(ls.last_updated)} (was ${fmtLong(ls.was, false)})`)));
    const ev = (a.stale_events || [])[0];
    if (ev) {
      body.append(el('p', { class: 'next' }, el('button', { class: 'btn ghost small', id: `review-${a.id}`, 'aria-expanded': 'false', 'aria-controls': `change-${a.id}`, onclick: () => openChange(a.id) }, 'Review the change')));
      body.append(changePanel(a, ev));
    }
  } else if (a.badge === 'confirm') {
    body.append(...confirmBlock(a));
    if (mixed) body.append(perEndpoint(a));
  } else if (a.badge === 'held_unspecified') {
    const reasons = [...new Set(a.cells.filter((c) => c.verdict === 'held' && c.reason).map((c) => c.reason))];
    reasons.forEach((r) => body.append(el('p', { class: 'dim' }, r.charAt(0).toUpperCase() + r.slice(1) + '.')));
    if (mixed) { body.append(...quoteBlock(a.cells.filter((c) => c.verdict === 'holds'))); body.append(perEndpoint(a)); }
  } else {
    const seen = new Set(), picks = [];
    for (const c of a.cells) {
      const q = c.quote_display || c.quote;
      if (q && !seen.has(c.source_url)) { seen.add(c.source_url); picks.push(c); }
    }
    picks.slice(0, 2).forEach((c) => body.append(...quoteBlock([c])));
  }
  // A confirm cell inside an answer whose badge is driven by something else still shows its readings.
  if (a.badge !== 'confirm' && a.cells.some((c) => c.verdict === 'confirm')) {
    const n = a.cells.filter((c) => c.verdict === 'confirm').length;
    body.append(el('details', { class: 'more' }, el('summary', {}, `${n} endpoint reading${n === 1 ? '' : 's'} to confirm`), confirmBlock(a)));
  }

  const art = el('article', { class: 'ans' + (isCatch ? ' sel' : '') + (a.badge === 'stale' ? ' stale' : '') + (ch ? ' changed' : ''), id: 'q-' + a.id, 'data-badge': a.badge, tabindex: '-1', 'aria-labelledby': `h-${a.id}` },
    el('span', { class: 'n' }, a.number),
    el('h3', { id: `h-${a.id}` }, a.question),
    el('span', { class: 'badge ' + b.cls + (a.badge === 'not_true' ? ' catch-mark' : '') }, icon(b.icon), a.badge_label),
    body);
  art.addEventListener('mouseenter', () => relate(null, a));
  art.addEventListener('mouseleave', () => relate(null, null));
  return art;
}

function fixPanel(p, a) {
  const fix = p.catch.fix;
  const ta = el('textarea', { id: `fix-text-${a.id}` });
  ta.value = fix.text;
  const copy = (text, msg) => navigator.clipboard.writeText(text).then(() => toast(msg), () => toast('Copy failed. Select the text and copy it.'));
  return el('div', { class: 'panel', id: `fix-${a.id}`, hidden: true },
    el('h4', {}, `Your trust page, ${fmtLong(p.stated_at)}`),
    el('p', { class: 'was' }, withPaths(a.stated.text)),
    el('label', { for: `fix-text-${a.id}` }, `Answer ${+a.number}, true for every endpoint`),
    ta,
    el('p', { class: 'hint' }, 'Owin wrote this from the per-endpoint values above. Edit it before you send.'),
    el('div', { class: 'row' },
      el('button', { class: 'btn ghost small', id: `copy-answer-${a.id}`, onclick: () => copy(ta.value, 'Answer copied') }, 'Copy answer'),
      el('button', { class: 'btn ghost small', id: `copy-trust-${a.id}`, onclick: () => copy(`Replace:\n${a.stated.text}\n\nWith:\n${ta.value}`, 'Trust-page change copied') }, 'Copy as trust-page change'),
      el('button', { class: 'btn small', onclick: () => closePanel(`fix-${a.id}`, 'fix') }, 'Close')));
}

function changePanel(a, ev) {
  const rows = [];
  if (ev.kind === 'list_changed') {
    const ex = ev.example;
    rows.push(el('dt', {}, 'Changed'), el('dd', {}, ev.changed.join('; ') || 'none'));
    rows.push(el('dt', {}, 'Added'), el('dd', {}, ev.added.join('; ') || 'none'));
    rows.push(el('dt', {}, 'Removed'), el('dd', {}, ev.removed.join('; ') || 'none'));
    rows.push(el('dt', {}, 'Before'), el('dd', {}, el('a', { href: ev.before.url, target: '_blank', rel: 'noopener' }, `“Last updated ${ev.before.last_updated}”, captured ${fmtIsoDay(ev.before.observed_at)} ↗`)));
    rows.push(el('dt', {}, 'After'), el('dd', {}, el('a', { href: ev.after.url, target: '_blank', rel: 'noopener' }, `“Last updated ${ev.after.last_updated}”, captured ${fmtIsoDay(ev.after.observed_at)} ↗`)));
    const lead = `${ev.provider_display} changed ${ev.changed.length} ${ev.changed.length === 1 ? 'entry' : 'entries'}${ex && ex.kind === 'changed' ? `, including ${ex.entity} (${ex.fields.join(', ')})` : ''}, added ${ev.added.length} and removed ${ev.removed.length}.`;
    const held = (ev.held_observations || []).map((o) => el('p', { class: 'hint' }, `A fetch on ${fmtIsoDay(o.observed_at)} served an older copy (“Last updated ${o.last_updated}”). Owin held it and did not use it.`));
    return el('div', { class: 'panel', id: `change-${a.id}`, hidden: true },
      el('h4', {}, `What changed on ${ev.provider_display}’s sub-processor list`),
      el('p', {}, lead), el('dl', { class: 'changes' }, rows), held,
      el('div', { class: 'row' }, el('button', { class: 'btn small', onclick: () => closePanel(`change-${a.id}`, `review-${a.id}`) }, 'Close')));
  }
  return el('div', { class: 'panel', id: `change-${a.id}`, hidden: true }, el('p', {}, ev.text || 'The page changed.'));
}

function openPanel(id) {
  const panel = $(id);
  if (!panel) return null;
  panel.hidden = false;
  panel.classList.remove('open'); void panel.offsetWidth; panel.classList.add('open');
  return panel;
}
function closePanel(id, returnTo) {
  const panel = $(id); if (panel) panel.hidden = true;
  const btn = $(returnTo) || $('fix');
  if (btn) { btn.setAttribute('aria-expanded', 'false'); btn.focus(); }
  requestAnimationFrame(link);
}
function openFix(qid, mode) {
  showTab('t-ans');
  const panel = openPanel(`fix-${qid}`);
  if (!panel) return;
  const target = mode === 'trust' ? $(`copy-trust-${qid}`) : $(`fix-text-${qid}`);
  $(`q-${qid}`).scrollIntoView({ block: 'start', behavior: REDUCED.matches ? 'auto' : 'smooth' });
  target.focus({ preventScroll: true });
  requestAnimationFrame(link);
}
function goTo(qid) {
  showTab('t-ans');
  const art = $(`q-${qid}`);
  art.scrollIntoView({ block: 'start', behavior: REDUCED.matches ? 'auto' : 'smooth' });
  art.focus({ preventScroll: true });
  requestAnimationFrame(link);
}
function openChange(qid) {
  showTab('t-ans');
  const panel = openPanel(`change-${qid}`);
  const btn = $(`review-${qid}`); if (btn) btn.setAttribute('aria-expanded', 'true');
  $(`q-${qid}`).scrollIntoView({ block: 'start', behavior: REDUCED.matches ? 'auto' : 'smooth' });
  if (panel) { panel.setAttribute('tabindex', '-1'); panel.focus({ preventScroll: true }); }
  requestAnimationFrame(link);
}

// Related highlight: hovering an endpoint dims answers it does not affect, and the reverse.
function relate(path, answer) {
  const p = state.pack; if (!p) return;
  const rows = document.querySelectorAll('.ep-row[data-path]'), arts = document.querySelectorAll('#answers .ans');
  rows.forEach((r) => r.classList.remove('dimmed')); arts.forEach((x) => x.classList.remove('dimmed'));
  if (path) {
    const he = new Set(heldEverywhere(p));
    const hit = new Set(p.answers.filter((a) => !he.has(a.number) && a.cells.some((c) => c.endpoint === path && ((c.verdict !== 'holds' && c.verdict !== 'disclosed') || c.stale))).map((a) => 'q-' + a.id));
    if (hit.size) arts.forEach((x) => x.classList.toggle('dimmed', !hit.has(x.id)));
  } else if (answer) {
    const hit = new Set(answer.cells.filter((c) => c.verdict === 'contradicts' || c.stale || c.verdict === 'held' || c.verdict === 'confirm').map((c) => c.endpoint));
    if (hit.size && hit.size < answer.cells.length) rows.forEach((r) => r.classList.toggle('dimmed', !hit.has(r.dataset.path)));
  }
}

function slug(s) { return s.replace(/[^\w]+/g, '-').replace(/^-|-$/g, ''); }

// Connectors: one grammar (1.5px, square elbows, end dot). Yellow joins the endpoint that makes an answer
// not true; grey joins the endpoint whose vendor page changed to the stale answer. Only the yellow one draws in.
function link() {
  const old = $('link'); if (old) old.remove();
  const p = state.pack;
  if (!p || MOBILE.matches || $('panes').hidden) return;
  const panes = $('panes'), pr = panes.getBoundingClientRect();
  const s = document.createElementNS(NS, 'svg'); s.id = 'link'; s.setAttribute('aria-hidden', 'true');
  const pairs = [];
  const staleA = p.answers.find((a) => a.badge === 'stale');
  if (staleA) for (const c of staleA.cells.filter((x) => x.stale)) pairs.push([c.endpoint, staleA.id, 'quiet']);
  if (p.catch) pairs.push([p.catch.endpoint, p.catch.question, '']);
  let yellow = null;
  for (const [path, qid, cls] of pairs) {
    const from = $('ep-' + slug(path)), to = $('q-' + qid);
    if (!from || !to) continue;
    const a = from.getBoundingClientRect(), b = to.getBoundingClientRect();
    const x1 = a.right - pr.left, y1 = a.top - pr.top + 24, x2 = b.left - pr.left, y2 = b.top - pr.top + 24;
    const mx = Math.round((x1 + x2) / 2);
    const path_ = document.createElementNS(NS, 'path');
    if (cls) path_.setAttribute('class', cls);
    path_.setAttribute('d', Math.abs(y1 - y2) < 1 ? `M${x1} ${y1}H${x2}` : `M${x1} ${y1}H${mx}V${y2}H${x2}`);
    const dot = (cx, cy) => { const c = document.createElementNS(NS, 'circle'); if (cls) c.setAttribute('class', cls); c.setAttribute('cx', cx); c.setAttribute('cy', cy); c.setAttribute('r', 4); return c; };
    s.append(path_, dot(x1, y1), dot(x2, y2));
    if (!cls) yellow = path_;
  }
  panes.append(s);
  if (yellow && !state.drawn && !REDUCED.matches) {
    const L = yellow.getTotalLength();
    yellow.style.strokeDasharray = L; yellow.style.strokeDashoffset = L;
    yellow.animate([{ strokeDashoffset: L }, { strokeDashoffset: 0 }], { duration: 450, delay: 200, easing: 'cubic-bezier(.2,.8,.2,1)', fill: 'forwards' });
  }
  if (yellow) state.drawn = true;
}

// Tabs (mobile): roving tabindex, arrow keys.
const tabs = [$('t-ans'), $('t-stack')];
function showTab(id) {
  tabs.forEach((t) => {
    const on = t.id === id;
    t.setAttribute('aria-selected', on); t.tabIndex = on ? 0 : -1;
    $(t.getAttribute('aria-controls')).classList.toggle('off', !on);
  });
}
tabs.forEach((t, i) => {
  t.addEventListener('click', () => showTab(t.id));
  t.addEventListener('keydown', (e) => {
    if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return;
    const n = tabs[(i + (e.key === 'ArrowRight' ? 1 : tabs.length - 1)) % tabs.length];
    showTab(n.id); n.focus(); e.preventDefault();
  });
});
showTab(location.hash === '#stack' ? 't-stack' : 't-ans');

// Export menu
const menuBtn = $('export-btn'), menu = $('export-menu');
const items = () => [...menu.querySelectorAll('[role=menuitem]')];
function toggleMenu(open) {
  if (menuBtn.disabled) return;
  menu.hidden = !open; menuBtn.setAttribute('aria-expanded', open);
  if (open) { showTab('t-ans'); items()[0].focus(); }
}
menuBtn.addEventListener('click', () => toggleMenu(menu.hidden));
menu.addEventListener('keydown', (e) => {
  const list = items(), i = list.indexOf(document.activeElement);
  if (e.key === 'ArrowDown') { list[(i + 1) % list.length].focus(); e.preventDefault(); }
  else if (e.key === 'ArrowUp') { list[(i + list.length - 1) % list.length].focus(); e.preventDefault(); }
  else if (e.key === 'Home') { list[0].focus(); e.preventDefault(); }
  else if (e.key === 'End') { list[list.length - 1].focus(); e.preventDefault(); }
  else if (e.key === 'Escape') { toggleMenu(false); menuBtn.focus(); e.preventDefault(); }
  else if (e.key === 'Tab') { toggleMenu(false); }
});
document.addEventListener('click', (e) => { if (!menu.hidden && !menu.contains(e.target) && e.target !== menuBtn && !menuBtn.contains(e.target)) toggleMenu(false); });
menu.addEventListener('click', (e) => {
  const b = e.target.closest('[role=menuitem]'); if (!b) return;
  const act = b.dataset.act;
  toggleMenu(false); menuBtn.focus();
  if (act === 'link') {
    const url = location.origin + '/pack/print' + setQuery();
    navigator.clipboard.writeText(url).then(() => toast('Live link copied. It shows buyer-facing answers and sources only.'), () => toast(url));
  } else if (act === 'pdf') {
    const w = window.open('/pack/print' + setQuery(), '_blank');
    if (w) w.addEventListener('load', () => w.print(), { once: true });
    else toast('Allow pop-ups to save the PDF.');
  } else if (act === 'csv') {
    const a = el('a', { href: '/api/pack' + setQuery({ format: 'csv' }), download: `${slug((state.pack && state.pack.company) || 'owin').toLowerCase()}-ai-answers.csv` });
    document.body.append(a); a.click(); a.remove();
    toast('CSV downloaded.');
  }
});

let toastTimer;
function toast(msg) {
  const t = $('toast'); t.textContent = msg; t.hidden = false;
  clearTimeout(toastTimer); toastTimer = setTimeout(() => { t.hidden = true; }, 3200);
}

document.fonts.ready.then(() => requestAnimationFrame(link));
addEventListener('resize', () => requestAnimationFrame(link));
addEventListener('scroll', () => requestAnimationFrame(link), { passive: true });
MOBILE.addEventListener('change', () => requestAnimationFrame(link));
load();

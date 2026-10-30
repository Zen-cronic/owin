# Owin data contract (v1)

Owin is a typed Python library (`owin/`) with a JSON CLI (`owin ...`). Every CLI command prints one JSON document to stdout. The UI binds to these shapes, and fields are only ever added, never renamed. The trust split is fixed. The model fills `WindowTerms`. Code validates it, and code alone computes deadlines, states and drafts, reading only structured fields and never model prose.

## WindowTerms (`owin.schema.WindowTerms`)

These are the vendor's DPA terms for objecting to a new sub-processor.

| field | type | set by | meaning |
|---|---|---|---|
| `window_type` | `"window" \| "exit_only" \| "none"` | model | `window` means a stated number of days to object, including objecting by terminating. `exit_only` means objections are addressed but there is no deadline, only terminate / stop using / move. `none` means no provision was found in the fetched text. |
| `window_days` | `int \| null` | model | Required for `window`. It is `null` otherwise. |
| `unit` | `"calendar" \| "business" \| "unspecified" \| "n/a"` | model | It is `calendar` or `business` only when the text says so. Code forces `n/a` when there is no window. |
| `clock_start` | `"notice" \| "page_update" \| "other" \| "n/a"` | model | The event that starts the clock. Code forces `n/a` when there is no window. |
| `clock_start_text` | `str` | model | The trigger in a few words. Display only. |
| `remedy` | `str` | model | The remedy if the objection is not resolved. Display only. |
| `deemed_consent_if_silent` | `bool` | model | The text says that silence means acceptance. |
| `quote` | `str` | model | The clause sentence, quoted verbatim. |
| `quote_verbatim` | `bool` | code | The quote is in the source after markdown stripping and quote/whitespace normalisation (`owin.textnorm.is_verbatim`). |
| `status` | `"ok" \| "held"` | code | `held` if `window_type == "none"` or the quote is not verbatim. A held vendor never gets a countdown. |
| `hold_reasons` | `str[]` | code | Human-readable reasons. |

Model output that breaks the schema, for example `window` without days or `exit_only` with days, is rejected (`SchemaError`) and recorded as an error. It is never repaired by guessing.

## Extraction record (`owin.extract.Extraction`)

The record holds `vendor, model, source_sha256, input_mode ("whole" | "keyword-windows"), input_chars, latency_s, prompt_tokens, completion_tokens, cost_usd, finish_reason, terms (WindowTerms | null), error (str | null)`.

## `owin eval score [--brief] [--file a.json,b.json]`

It returns `{run_files, model, quotes_rechecked_against_source, headline{...}, per_successful_run{successful_runs, total_calls, mean_latency_s, p95_latency_s, cost_per_successful_run_usd, total_cost_usd, tokens_in, tokens_out}, vendors{<id>: {kind, gold_window, runs_window, exact_runs, n_runs, majority_exact, consistent, quote_verbatim_runs, mismatched_fields}}, baseline{...}}`. A successful run is one that is exact on all five scored fields and has a verbatim quote, or, for a negative control, one that is held.

## Usage ledger (`ledger/usage.jsonl`)

Each Token Factory call adds one line: `{ts, purpose, model, prompt_tokens, completion_tokens, cost_usd, latency_s, error, reasoning_tokens, attempts}` (plus `thinking` when the call set Nemotron's reasoning switch). The ledger never contains a key. Two caps read it: `owin eval run` and `owin pack extract` refuse to start when the **lifetime** ledger total is at or above `--budget` (default $3), a cap on experiments; `owin job daily` skips its Nemotron step when **today's (UTC)** spend is at or above `--budget` (`tokenfactory.spent_today`), so a scheduled job is never stopped for good by past spend.

Client behaviour (`owin/tokenfactory.py::chat`): `timeout` is per attempt and `attempts` counts every try (batch defaults 600 s and 3; the live recheck path uses 45 s and 2). Only 429/5xx, timeouts and resets are retried; `Retry-After` is honoured (capped at 30 s); there is no wait after the last attempt. A process-level circuit breaker opens after 3 consecutive failed calls for 120 s (`tokenfactory.available()`); request-path callers check it, batch commands do not.

## Decision layer (`owin.decide`, P2)

The default path follows the reframe of 2026-10-21. Evidence says people rarely miss windows. They ignore the email, and the real pain is on the processor side, telling your own customers. So the default is **accept and notify**, and objecting is the rare path.

### Event (`owin replay [--promise-days N] [--as-of ISO|now] [--decide accepted|objected|dismissed] [--brief]`, `GET /api/replay?promise_days=&as_of=&decision=`)

| field | type | notes |
|---|---|---|
| `vendor`, `vendor_display` | str | |
| `as_of`, `as_of_local` | ISO UTC, `"YYYY-MM-DD HH:MM EDT/EST"` | The replay defaults to the after-snapshot time, so it is deterministic. `now` gives a live countdown. |
| `watch_state` | `watching \| no_change \| changed \| affects_you \| countdown \| window_closed \| exit_only \| held \| not_watchable` | See the rules below. |
| `workflow_state` | `pending \| drafted \| accepted \| objected \| dismissed` | |
| `headline` | `{days_to_object: int\|null, customers_to_warn: int, text}` or null | Example text: `"23 days to object · 3 customers to warn"`. It is null for no_change, changed, held and not_watchable. |
| `actions` | str[] | "What to do", in order. The first action is always accept-and-notify when anything is drafted. |
| `flags` | `{code, message}[]` | Codes: `notice_inversion`, `customer_notice_late`, `unsubscribed`, `new_location`, `deemed_consent`, `exit_only`, `thin_evidence`, `vendor_only_flowdown`. |
| `changes.material` / `changes.other` | `{kind: added\|removed\|changed, entity, key, before, after, changed_fields, added_values, why, new_locations?}[]` | Material means a new entity, or a new processing location, on a service you use. |
| `vendor_terms` | WindowTerms + `source_url, model, quote_sha256, runs_agreeing` | These come from `data/terms/<vendor>.json`, which is exported from the measured runs. |
| `clock` | `{start_date, basis, candidates[], assumptions[], window_days, unit, vendor_deadline_date, vendor_deadline_at, vendor_deadline_local, days_left, closed}` or null | It is null when the vendor is held. |
| `your_notice` | `{promise_days, due_date, days_left, late, slack_days, inversion, why}` or null | This is the notice you owe your own customers. |
| `affected_customers` | `{id, name, contact, region}[]` | |
| `assumptions` | str[] | Every rule the code applied that the documents do not settle. |
| `evidence.before/after` | `{url, retrieved, last_updated, source_kind, content_sha256, entities}` | |
| `drafts` | `{customer_notices[], subprocessor_page, objection?}` | Each draft is `{kind, to, subject, body, send_by, status: "draft"}`. The objection is drafted only while the window is open. |
| `decision_record` | see below | Present when `--decide` is given. |
| `replay` | `{id, label, company_label}` | Real-change and fictional-company labels. |

### Rules (code only; reads structured fields, never model prose)

1. If the after snapshot has no entity table, the state is `not_watchable`.
2. If the entity diff is empty, the state is `no_change`. Owin raises no alert and accepts no decision.
3. If no change is material, the state is `changed`. That covers removals and wording changes, and it means a page update only.
4. If a change is material, the state is `affects_you`. The affected customers are those whose features use this vendor, provided your DPA flows down vendor sub-processors.
5. If the vendor terms are not `ok` (no verbatim quote, `none`, no majority across runs), the state is `held`. Owin shows no deadline and drafts nothing.
6. If the terms are `exit_only`, the state is `exit_only`. There is no countdown, and the customer notice is due now.
7. If the terms are `window`, the **clock start** is the earliest of: the notice email date (if subscribed and known), the vendor page's "Last updated" date, and the date Owin first saw the change. For `page_update` clauses only the page date counts. An `unspecified` unit counts calendar days. A `business` unit skips weekends; holidays are not modelled. The **deadline** is 23:59:59 on the due date in the earlier of your timezone and the vendor's (UTC by default). If that deadline has passed, the state is `window_closed`; otherwise it is `countdown`.
8. **Your notice** is due on the vendor deadline minus your promised notice days, on the assumption that the vendor does not engage before its window closes. **Inversion** means `promise_days > window_days`. A due date in the past is `customer_notice_late`.

### Decision record (`type: "owin.decision_record"`)

The record holds `{record_id, version, decided_at, decided_by{name, role}, decision, note, vendor, watch_state_at_decision, change[], vendor_clause{quote, quote_sha256, source_url, window_days, window_type}, your_clause{quote, quote_sha256}, deadlines{vendor_objection, customer_notice}, customers_notified[], evidence, assumptions[], flags[]}`. `record_id` is a hash of the content. The record can be filed as vendor-review evidence (SOC 2 / ISO 27001). It is not a compliance claim.

## Entity snapshots (`owin.entities`)

`Snapshot{vendor, source_url, retrieved, source_kind: archive|tavily|fixture|live, last_updated, entities: Entity{name, key, services, locations, purpose, section}[], content_sha256}`. Entities are keyed by a normalised name: lower case, no corporate suffix, no punctuation. Cells are compared as token sets, so markdown, links, pagers, duplicated tables and whitespace never produce a diff.

## Sweep (`owin sweep [--no-live] [--only a,b] [--record path] [--seed-archive snapshot.json] [--brief]`, P3)

The command returns `{run_at, tavily_key_present, live_requested, vendors, counts{state: n}, wall_s, rows[]}`. Each row is `{vendor, display, list_url, state, source_kind: tavily|fixture|unfetched, retrieved, latency_s, refetched, parser: html_table|markdown_table|vanta_cards|linked_rows|none, entities, last_updated, prev_last_updated, reason, material?, changes?[{kind, entity, why, new_locations?}], held?}`.

The row `state` is one of `watching` (baseline accepted), `no_change`, `changed`, `stale_source` (held), `date_only_changed`, `not_watchable` or `unfetched`.

- `stale_source` applies when the fetched page's "Last updated" is older than the accepted snapshot's. Owin holds and does not overwrite. This is a real case: on 2026-10-21 Tavily returned OpenAI's list dated July 9, 2026, while Wayback had October 14, 2026.
- A live `no_change` needs a second, advanced-depth extract that agrees with the first. Fixture results say "no live re-fetch".
- Tavily calls use `extract` with no `query`, so the page comes back whole and diffable. Without `TAVILY_API_KEY`, results come from recorded fixtures labelled `fixture`. Vendors with no fixture are `unfetched`.
- The vendor index is `data/index/vendors.json` (29 vendors, each with a `watch_mode` verified on 2026-10-21). Per-vendor state lives in `var/state/` (gitignored, or `OWIN_STATE_DIR`).

## DataUseTerms (`owin.datause.schema.DataUseTerms`, Pivot A, A1)

These are the terms one vendor page states for one AI feature. There is one field per security-questionnaire question, so the answer pack (A3) fills each question from one field and its verbatim quote.

| questionnaire question | field | type | set by |
|---|---|---|---|
| Is our data used to train the provider's models? | `used_for_training`, `training_quote` | `"yes" \| "no" \| "opt_in" \| "opt_out" \| "unspecified"`, str | model |
| How long are prompts and outputs retained? | `retention_days`, `retention_condition`, `retention_quote` | `int \| null` (0 = not retained by default; null = until deleted, unstated, or silent), str, str | model |
| Is zero data retention available for this feature? | `zdr`, `zdr_quote` | `"available" \| "excluded" \| "not_available" \| "unspecified"`, str | model |
| Where is the data processed or stored? | `region`, `region_quote` | str (free text, `"unspecified"` if silent), str | model |
| Which other parties can see it? | `third_party_access`, `third_party_quote` | `"yes" \| "no" \| "unspecified"`, str | model |
| | `verbatim` | `{field: bool}` | code |
| | `model_claimed` | `{field: value}`: answers the model gave that code withheld | code |
| | `status` | `"ok" \| "partial" \| "no_terms"` | code |
| | `hold_reasons` | str[] | code |

- **The trust split:** a field the model asserts (anything other than null or `"unspecified"`) must have a quote found verbatim in the page after markdown stripping (`owin.textnorm.is_verbatim`, minimum 20 characters). Otherwise code resets the field to null or `"unspecified"`, records the claim in `model_claimed` and sets `status: "partial"`. A questionnaire answer is never produced from a withheld field.
- **Labelling rules:** these are in `owin.datause.schema.LABEL_RULES`, and the prompt states the same rules.
- **`owin eval score --corpus datause [--brief] [--file a.json]`:** returns `{corpus, run_files, model, prompt_versions, quotes_rechecked_against_source, acceptance{rule, positive_items_exact, negative_items_held, passed}, headline{positive_items_exact_majority, positive_runs_exact, tuned, heldout, fresh_heldout, negative_items_held, negative_runs_held, raw_model_positive_runs_exact, consistent_items, field_accuracy_positive_runs, baseline_*}, per_successful_run{...}, items{<id>: {kind, split, vendor, feature, gold, runs, exact_runs, n_runs, majority_exact, raw_model_exact_runs, consistent, withheld_fields, mismatched_fields, third_party_runs_exact, errors}}, baseline}`.
- **Corpus:** each item in `eval/datause/corpus.json` is `{id, kind: tuned|heldout|negative, split: tuned|heldout|fresh, source, vendor, feature, url, file, fetched_at, source_sha256, gold{retention_days, used_for_training, zdr}, secondary{retention_condition, region, third_party_access}, evidence{retention, training, zdr, region, third_party}, label_note}`.
- **Label changes after a run:** recorded per item in `label_history` and in `RELABELS` (`owin/datause/evaluate.py`). The first one (2026-10-21, A3): `together-serverless` `used_for_training` went from `opt_in` to `opt_out` under the product-improvement rule in `LABEL_RULES`. The pre-change score is in `eval/datause/v2-before-relabel-score.json`.

## Buyer report (`owin.datause.pack`, A3; `answer_pack` in the API)

### Inputs

**Stack manifest** (`fixtures/demo/stack.json`, `POST /api/pack` body):

```
{company, _label,
 endpoints: [{path, feature, purpose?}],            # feature = an id in data/datause/catalog.json
 settings: {zdr_enabled: {<provider>: bool}, region: {<provider>: str}},   # the startup's own settings
 stated: {stated_at: "YYYY-MM-DD", source,
          answers: {Q01..Q05: {text, claim}}}}
```

| question | `claim` (structured; the only part a rule reads) |
|---|---|
| Q01 Is our data used to train AI models? | `{training: "not_used" \| "used"}` |
| Q02 How long do AI providers retain our data? | `{max_retention_days: int}` |
| Q03 Do you have zero data retention with your AI providers? | `{zdr: bool, exceptions: [endpoint path]}` |
| Q04 Where is our data processed? | `{regions: [str]}` |
| Q05 Which AI providers see our data? | `{providers: [provider id], includes_subprocessors: bool}` |

`text` is copied to the output and never read by a rule.

**Evidence** (both committed, both produced by code from recorded runs and captures):
- `data/datause/catalog.json`: providers, pages `{url, label, kind: datause|subprocessor_list, provider}` and features `{provider, label, short, feature, page, corpus_id, inherits{field: feature}}`. `inherits` applies vendor-wide statements (training, region, third parties) when a feature page is silent. ZDR and retention are never inherited.
- `data/datause/registry.json` (`owin pack registry`): per feature `{origin: a1_recorded|tavily_extraction, measured, run_file, runs_agreeing, model, captured_at, capture_kind, source_sha256, terms{DataUseTerms fields + quotes + verbatim}, live_check{run_file, runs_agreeing, values, quotes, agrees{field: bool}, page_source_kind, page_fetched_at}}`.
- `data/datause/observations.json` (`owin pack refresh`): per page `{url, kind, label, provider, observations: [{observed_at (UTC), source_kind: tavily|urllib|urllib_fallback|archive, method, sha256, chars, quotes_present?{quote_id: "verbatim"|"table_insensitive"|null}, snapshot?, last_updated?, held?}]}`. A `quote_id` is the first 16 hex characters of sha256(match form). A missing key means the quote was not checked; `null` means it was checked and is gone.

### Output (`type: "owin.answer_pack"`, `owin pack build`, `GET /api/pack`)

`{type, version, pack_id, company, label, stated_at, stated_source, as_of, as_of_local, stack{endpoints[{path, feature, provider, provider_display, label, short, purpose}], providers}, counts{not_true, stale, confirm, held_unspecified, still_true}, headline{kicker, text}, catch, answers[], order[], watch{pages, pages_watched, last_checked, last_checked_local}, settings, provenance}`

- **answer:** `{id, number "01".."05", question, field, stated{text, claim}, badge, badge_label, answer (a deterministic sentence), as_of, as_of_local, cells[], stale_events[], endpoints_holding, endpoints}`.
- **cell (one per endpoint):** `{endpoint, feature, feature_label, feature_short, provider, vendor_value, value_label, verdict: holds|disclosed|contradicts|held, reason, quote (verbatim), quote_display (table cells joined by " · "), quote_presence, reanchored, source_label, source_url, fetched_at, fetched_at_local, fetched_via, inherited_from, measured, origin, stale?, list_source?, evidence, list_evidence?}`.
- **evidence (display only, never read by a rule; `owin/datause/evidence.py`, index `data/datause/evidence.json` built by `owin pack evidence` from the gitignored captures):** `{kind: "sentence", text}` | `{kind: "list_entry", text}` | `{kind: "table_row", row_label, match_key, rows[{key, value, match}]}`; `match` marks the cell that answers the question. The UI renders a table row as a key/value table, never as flattened text.
- **list_evidence (Q05 cells whose provider's sub-processor list changed):** `[{kind: "list_entry_table", entity, change: changed|added|removed, rows[{key, value, match, was}]}]`: the changed entry named in the example (OpenAI: Cloudflare, Ltd.) and the added entries (OAI International, Inc.), with changed cells marked and their old value.
- **stale_event:** `{kind: list_changed, page, provider, provider_display, endpoint, before{observed_at, last_updated, url, source_kind, sha256}, after{...}, added[], removed[], changed[], example, held_observations[]}` or `{kind: quote_gone, page_seen, text, endpoint, provider_display}`.
- **catch** (the first not-true answer, in questionnaire order) or null: `{question, number, endpoint, feature, sentence, quote, source_url, source_label, fetched_at, fetched_at_local, primary: "Fix answer N", secondary: "Draft trust-page change", not_true_answers, fix{claim, text}}`.
- `order` lists the answer ids by severity (not true, outdated, needs review, not stated, verified), then by number, for the UI.

### Rules (code only)

1. A vendor field counts only when it is asserted and its quote passed the A1 verbatim gate (`verbatim[field]`). Otherwise the field is null or `unspecified`, after `inherits` is tried.
2. Per-question cell rules:
   - Q01: `no`/`opt_in` means not used, and `yes`/`opt_out` means used. `unspecified` is held.
   - Q02: with `zdr=available` and `settings.zdr_enabled[provider]`, the cell holds (not retained). Otherwise `retention_days <= max_retention_days`. `null` is held.
   - Q03: an endpoint listed in `exceptions` is `disclosed`. `excluded`/`not_available` contradicts. `available` holds when the setting is true, contradicts when it is false, and is held when it is missing. `unspecified` is held.
   - Q04: vendor region text is free text and is never read. Only `settings.region[provider]` can hold or contradict; otherwise the cell is held.
   - Q05: a provider not in `providers` contradicts. `third_party_access=yes` without `includes_subprocessors` contradicts.
3. **Outdated** (badge code `stale`) has two sources. (a) For Q05, the provider's sub-processor list: the entity diff between the last trusted observation on or before `stated_at` and the latest trusted observation is not empty. Observations marked `held` (stale_source: Tavily served an older "Last updated") are never used. (b) For any question, the cell's quote is checked absent (`null`) in the latest capture, and the extraction on that capture (`live_check`) does not reproduce the value with a verbatim quote. If it does reproduce the value, the cell re-anchors to that quote and is not stale.
4. Badge: any `contradicts` gives `not_true`; else any stale event gives `stale`; else any `confirm` gives `confirm`; else any `held` gives `held_unspecified`; else `still_true`. The codes are the API's enum; `badge_label` carries the words a person reads: Not true, Outdated (`stale`), Needs review (`confirm`), Not stated (`held_unspecified`), Verified (`still_true`).
5. Selective answering (P1, `owin/datause/selective.py`): a vendor field reaches a rule only when at least 2 extraction runs succeeded and every successful run agreed on it (registry `features[id].field_agreement[field].state == "auto"`; the runs are the 3 on the latest Tavily capture when they exist, else the 3 recorded A1 runs; an errored run abstains, it neither agrees nor disagrees). Otherwise the cell has `verdict: "confirm"`, `vendor_value: null` and `confirm{runs_agreeing (agreeing/successful), readings_ok, readings_failed, basis, options[{value, label, runs, quote, quote_display, evidence, quote_failed_gate}]}`. There is no exception: a split reading is always `confirm`, the same rule as `owin eval selective`. Region never decides, so it is never `auto` or `confirm`. Buyer exports show a confirm cell as "Being confirmed" with no quote.

`owin eval selective --corpus datause [--split v3fresh] [--file runs.json] [--brief]` recomputes keyless from recorded runs: `auto_answered`, `auto_correct`, `correct_with_sentence` (correct auto cells that assert a value, each with the page's verbatim sentence) and `correct_not_stated` (correct auto cells on a page that says nothing on that field), `sent_to_confirm`, `confirm_majority_right`, `all_cells_majority_right` (what a majority vote would have shipped on every cell), `pages` (distinct URLs), `vendors_new` (vendor families absent from the rest of the corpus; a name is a family up to its first parenthesis), `auto_misses` (with footnotes), negative controls, and labelled non-clean references. `--brief` carries them as `with_sentence`, `not_stated`, `all_cells_majority_right`, `pages`, `vendors_new`; `GET /api/selective` adds `majority_all_cells`, `correct_with_sentence`, `correct_not_stated`, `pages`, `vendors_new` at the top level beside `selective` (the brief).
5. `set_feature(manifest, path, feature)` (`--set PATH=FEATURE`, `?set=PATH=FEATURE`) is the change-one-input path.

### Exports

- `--format csv` / `?format=csv`: one row per (question, endpoint). Columns: `question_number, question, stated_answer, status, endpoint, feature, provider, vendor_value, endpoint_verdict, quote, source_url, fetched_at, as_of, outdated`. `status` is the badge's display word (`badge_label`), and `endpoint_verdict` is a plain phrase (Supports the answer, Disclosed exception, Contradicts the answer, Not stated, Needs review).
- `--format share` / `?format=share`: `{type: "owin.answer_pack.share", version, readonly: true, share_id, pack_id, company, label, as_of, as_of_local, answers[{number, question, answer, status, status_label, as_of, as_of_local, changes[{text}], endpoints[{endpoint, provider, vendor_says, quote, quote_display, source_url, source_label, fetched_at, fetched_at_local}]}]}`. It has no catch, fix, actions or claim.
- `--format html` / `GET /pack/print`: a buyer document in the light print tokens (A4 `@page`) that prints to PDF. It has the same content as share.
- `--format brief`: `{pack_id, as_of_local, headline, counts, badges{Q01..Q05}, catch (short), answers[{id, badge, answer, cells{endpoint: value_label}}]}`.
- Errors: an unknown feature, an unknown endpoint in `--set`, an empty stack or a bad `stated_at` raise `PackError`. The CLI exits 2; the API returns 400. A POST body over 64 KB returns 413.

### Live path

- `owin pack refresh [--pages a,b] [--no-fetch]`: Tavily `extract` (no query, basic, markdown) for each catalog page. On a Tavily failure it uses the stdlib fetcher, labelled `urllib_fallback` with `tavily_error`. Provenance goes to `fixtures/manifest.json` → `datause_tavily`, raw text to the gitignored `fixtures/raw/datause-tavily/`, and observations to `data/datause/observations.json`. Sub-processor lists also get a derived entity snapshot `fixtures/snapshots/<page>-tavily-<yyyymmdd>.json`.
- `owin pack extract [--features a,b] [--runs 3]`: Nemotron on the Tavily captures, recorded in `eval/datause/registry-runs/` and refused at the `--budget` ledger cap. Then `owin pack registry` re-exports.

### Recheck one endpoint now (`POST /api/recheck`, `owin recheck <endpoint>`)

The one request a visitor can make that calls a paid API. Body `{"endpoint": "/api/crm-sync"}` (an endpoint path from the demo stack). With `TAVILY_API_KEY` set the server fetches the page that documents that endpoint's feature through Tavily `extract` (basic depth; if that copy would mark a quoted sentence gone that the last trusted capture still had, one re-fetch at advanced depth, the same caution as the sweep's stale-source rule, and the copy with more of the quoted sentences wins), appends the observation (time, hash, which quoted sentences are present; never page text) to that page's history, rebuilds the pack through the same rules as every other request, and answers:

`200 {ok: true, mode: "live", checked_at (UTC), changed (bool: did any of this endpoint's cells or any answer badge move), state: not_true|stale|confirm|held_unspecified|still_true (the endpoint's own most severe cell), observation (one sentence), credits_used (Tavily credits: 1 basic, +2 advanced), endpoint, feature, page, source_url, page_seen_before, depth, stored: state_dir|process, answers{Q01..Q05: {badge, verdict}}}`.

Without a key: `200 {ok: false, mode: "demo", reason: "no key on this server"}` and no request is made. Guards: `429` at the per-process daily cap (`OWIN_RECHECK_DAILY_CAP`, default 200) and within the 60 s per-endpoint cooldown (`retry_after_s`); `400` for an unknown endpoint or body; `502` when Tavily returns no content (`reason` carries the error; nothing is recorded). The observation goes to `$OWIN_STATE_DIR/data/datause/observations.json` when a state dir is set, else it lives in the server process's memory (the committed file is never written). Every Tavily call writes one line to `ledger/usage.jsonl` (`purpose: "recheck:<endpoint>"`, `model: "tavily/extract"`, `credits`). No new rule and no new parser: the recheck reuses `observations._datause_obs` and `pack.build`.

**Live Nemotron re-reading (additive `readings` field).** When a quoted sentence the last trusted capture had is still gone after the advanced re-fetch, and `TOKEN_FACTORY_API_KEY` is set, Nemotron Super reads the fetched text 3 times (prompt v3, the verbatim gate against the fetched text; the text is never stored). `readings` is `{ran, reason?}` when it did not run (no lost sentence, no key, breaker open, or today's `recheck-read` spend at `OWIN_RECHECK_READ_BUDGET_USD`, default $0.25), else `{ran: true, model, prompt_version, readings, readings_ok, errored_abstained, cost_usd, latency_s, lost_sentences, applied, moved_to_confirm, fields, scope}`. The readings can only move fields of the endpoint's own feature to Confirm (`registry.confirm_moves`): a field already Confirm stays, no value is written, no field becomes auto, no other feature changes; fewer than 2 successful readings apply nothing. The moves shape **this response only** (`state`, `changed`, `answers`); nothing is stored, so the next request reads the recorded registry and one bad copy of a page cannot change what every visitor sees. `observation` gains one sentence only when the readings ran. Each reading writes a ledger line (`purpose: "recheck-read:<feature>"`); 45 s per attempt, 2 attempts.

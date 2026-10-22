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

Each Token Factory call adds one line: `{ts, purpose, model, prompt_tokens, completion_tokens, cost_usd, latency_s, error}`. The ledger never contains a key. `owin eval run` refuses to start when the ledger total is at or above `--budget` (default $3).

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

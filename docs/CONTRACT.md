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

## Decision layer (P2, reframed 2026-10-21)

Sources: the evidence and my own reading of it. People rarely miss windows. They ignore the email, and the real pain is on the processor side, telling your own customers. So the default path is **accept and notify**, and objecting is the rare path.

- **Default hero path:** a vendor change is detected. The person accepts it. Owin drafts **the notice the startup owes its own customers**, quoting the startup's own DPA promise. It drafts the **updated public sub-processor page** and writes a **dated decision record**: who decided, what changed, which clause, the decision and a timestamp. The record can serve as SOC 2 / ISO 27001 vendor-review evidence.
- **Notice-period inversion** is a first-class state. It applies when the vendor's objection window or notice is shorter than the notice the startup promised its customers.
- **The rare path:** an objection draft to the vendor quoting its DPA clause, plus the countdown.
- **States:** the watch states are `watching / changed / affects_you / countdown / held / not_watchable / exit_only / no_change`, and the decision states are `accepted / objected / dismissed`, each with a decision record. Code computes all of these from structured fields.

The shapes for these are added to this file when P2 lands.

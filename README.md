# Owin

**NVIDIA Nemotron Super on Nebius Token Factory read the sub-processor objection terms of 17 real vendor DPAs, all five fields exact with a verbatim quote, in 51 of 51 runs (7 of the 17 held out), at $0.0017 and 6.1 s per successful run. It held 6 of 6 thin-evidence controls rather than inventing a window. A regex baseline tuned on the same documents gets 9 of 17.** Recompute it with `owin eval score`.

Owin (Objection Window) watches the vendors your startup uses. When one changes its sub-processor list, Owin reads that vendor's DPA and shows how many days you have to object and which of your customers you have to tell. It then drafts the notice you owe your own customers and your updated sub-processor page, plus the objection to the vendor for the rare case where you do object. A person sends everything.

## The number

| | Nemotron Super (3 runs each) | Regex baseline |
|---|---|---|
| 10 tuned DPAs (Vercel, Supabase, Mistral, Anthropic, Nebius, OpenAI, Stripe, NVIDIA, AWS, Google), five-field schema | **10/10** vendors, 30/30 runs | 8/10 |
| 7 held-out DPAs (Cloudflare, Linear, Metaview, PostHog, Resend, Salesloft, Sentry), labelled after the prompt was frozen | **7/7** vendors, 21/21 runs | 1/7 |
| Day count only (window type + days), all 17 | 17/17 | 15/17 |
| Thin-evidence controls (live OpenAI page shows headings only; a list page with no clause) | **6/6 held** | 2/2 held |

- **Exact** means all five scored fields match the hand label: `window_type` (window / exit_only / none), `window_days`, `unit`, `clock_start` and `deemed_consent_if_silent`. The quote must also appear verbatim in the source after markdown is stripped. A quote that is not verbatim holds the vendor.
- **Cost and latency** come from the usage that Token Factory returned for all 57 calls ($0.099 in total), priced at list rates of $0.30 / $0.90 per M tokens. p95 latency is 9.0 s.
- **The baseline** takes the first sentence that contains "object" and "N days", and falls back to the first sub-processor sentence that contains "N days". It gets most day counts right. It misses exit-only terms (AWS gives 30 days' notice but no deadline to object), deemed consent and notice-versus-objection splits (PostHog gives 14 days' notice but only 7 days to object).
- Recorded runs are in `eval/runs/`, the labels in `eval/corpus.json` and fixture provenance (URL, method, sha256) in `fixtures/manifest.json`.

```bash
export VIRTUAL_ENV="$HOME/.pyenv/versions/.owin"; export PATH="$VIRTUAL_ENV/bin:$PATH"
poetry install
owin eval score --brief        # recompute from recorded runs, no API key needed
owin eval run --runs 3         # re-run live (needs TOKEN_FACTORY_API_KEY and fixtures/raw/)
pytest -q
```

## What we'll tell you before you find it

- 17 documents is a small corpus. One person labelled them, by reading each clause.
- The prompt and baseline were written after reading the first 10 clauses. Only the 7 held-out DPAs test generalisation.
- The live OpenAI DPA hides its clauses in accordions, so a fetch returns headings only. The scored OpenAI item uses the server-rendered Wayback capture of 2026-10-20. The live page is a negative control, and it holds.
- Raw vendor text in `fixtures/raw/` is not redistributed. Without it, `owin eval score` uses the recorded verbatim checks and says so (`quotes_rechecked_against_source: false`).
- Ultra was not re-run on this schema. In spike S2 it added nothing over Super on extraction, so Super is the default.
- Owin drafts. It gives no legal advice and never says "compliant".

License: MIT.

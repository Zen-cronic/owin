# Owin

**NVIDIA Nemotron Super on Nebius Token Factory read the sub-processor objection terms of 17 real vendor DPAs, all five fields exact with a verbatim quote, in 51 of 51 runs (7 of the 17 held out), at $0.0017 and 6.1 s per successful run. It held 6 of 6 thin-evidence controls rather than inventing a window. A regex baseline tuned on the same documents gets 9 of 17.** Recompute it with `owin eval score`.

Owin (Objection Window) watches the vendors your startup uses. When one changes its sub-processor list, Owin reads that vendor's DPA and shows how many days you have to object and which of your customers you have to tell. It then drafts the notice you owe your own customers and your updated sub-processor page, plus the objection to the vendor for the rare case where you do object. A person sends everything.

## The replay: a real change, start here

`owin replay --brief` (or `owin serve`, then open http://127.0.0.1:8787/)

**OpenAI updated its sub-processor list on 2026-10-14.** The two sides of the change are the Wayback captures of [2026-07-08](https://web.archive.org/web/20260708120959/https://openai.com/policies/sub-processor-list/) ("Last updated June 2, 2026") and [2026-10-21](https://web.archive.org/web/20261021154629/https://openai.com/policies/sub-processor-list/) ("Last updated October 14, 2026"). It added OAI International, Inc. and new processing locations for Microsoft (Belgium, Denmark, Malaysia, New Zealand) and Google Cloud (Singapore). It also removed four entities. The company is fictional, and so are its DPA wording and its five customers ("Lumen Notes", `fixtures/demo/company.json`).

- **The result is `23 days to object · 3 customers to warn`.** OpenAI's DPA ("within 30 days of receiving notice", measured above) runs from the page date, because that is earlier than the date Owin first saw the change. So the objection deadline is 2026-11-13 18:59 EST.
- **The processor-side catch:** Lumen promised its own customers 30 days' notice. OpenAI may engage once its 30-day window ends, so that notice was due 2026-10-14, the day OpenAI updated the page. Lumen is 7 days late, and it is not subscribed to OpenAI's notices.
- **The default action is accept and notify.** Owin drafts three customer notices that quote Lumen's DPA promise word for word, an updated public sub-processor page and a dated decision record with clause and source hashes (`--decide accepted`). The objection to privacy@openai.com, which quotes OpenAI's clause, is the rare path.
- **Change one input:** `--promise-days 10` moves the notice due date to 2026-11-03 (13 days left). `--promise-days 45` raises `notice_inversion`.
- **Safe states, all tested:** no change gives `no_change` and no alert. Thin evidence (the live OpenAI page shows headings only) gives `held` with no deadline. AWS-style terms give `exit_only`. A list that will not parse gives `not_watchable`. A passed deadline gives `window_closed`. Code computes every deadline and state from structured fields, and a test shows that model prose cannot change them.

## The watch: Tavily sweep over 29 vendors

`owin sweep --brief` fetches each vendor's list with Tavily `extract` (no query, whole page) and normalises it to an entity table. It then diffs that table against the last accepted snapshot. Owin reads four list formats: HTML tables (OpenAI), markdown tables, trust-centre cards (Anthropic's Vanta page, 20/20 entities) and linked rows (Stripe, 38). Cookie banners, nav, pagers, link syntax and bold text never produce a diff (tested).

- **It catches stale data.** On 2026-10-21, Tavily returned OpenAI's list dated "July 9, 2026", while Wayback had "October 14, 2026" the same day. Owin marks that `stale_source`, holds, and keeps the newer state. A live "no change" needs a second, advanced-depth fetch that agrees.
- **Without a Tavily key** (true on the build machine today), the sweep uses recorded Tavily fixtures and labels them `fixture`. Vendors with no fixture show as `unfetched` rather than as fake results. Recorded sweeps are in `eval/sweeps/`.

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
- The replay company and its customers are fictional. The vendor, the clause and the change are real.
- Deadline rules that the documents do not settle are assumptions, and each one is listed in the output. Unspecified days count as calendar days. The deadline is end of day in the earlier of your timezone and UTC. Public holidays are not modelled. The vendor is assumed not to engage before its window closes.
- A page diff is evidence, not legal notice.
- What Tavily returned for OpenAI's list on 2026-10-21 was dated "July 9, 2026", while Wayback the same day shows "October 14, 2026". The Tavily result was probably cached. Owin re-fetches before it declares "no change".
- The sweep has run live on recorded Tavily output for 5 of the 29 indexed vendors. The other list URLs answered HTTP 200 but have not been extracted yet, because no Tavily API key is on the build machine. Supabase's list is a PDF and only its date is diffable. Vercel's list is a JS widget and is not watchable.
- Owin drafts. It gives no legal advice and never says "compliant".

License: MIT.

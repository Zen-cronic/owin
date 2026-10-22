# Owin

**Pre-registered split `v3fresh`: on 11 (vendor, feature) documentation pages that no prompt had ever seen (Cohere, Perplexity, xAI, OpenRouter, Cerebras, DeepInfra, Google Vertex), labelled and committed before the prompt was written, NVIDIA Nemotron Super on Nebius Token Factory got retention days, training use and ZDR status all exact, each with a verbatim quote, on 7 of 11. That fails our own pre-registered 80% bar. It held 2 of 2 pages that say nothing on the subject (6/6 runs) rather than guessing, at $0.004 and 9 s per successful run. A keyword baseline gets 4 of 11 and holds 0 of 2. On the older 30-feature corpus (splits `tuned`/`heldout`/`fresh`, not a clean test, because its misses shaped the prompt) prompt v2 scored 23/30 and prompt v3 scores 24/30.** Recompute it with `owin eval score --corpus datause --brief`.

Owin moved (decision of 2026-10-21) from sub-processor notices to **AI data-use terms per feature**: for the AI endpoints a startup actually calls, what the vendor's own page says about retention, training use, zero data retention (ZDR) and region, each with the sentence that says it. The hero output is the AI section of a buyer's security questionnaire, filled in for your stack. The name is a codename for now.

## The number: AI data-use terms per feature

**Clean, pre-registered (split `v3fresh`).** The 13 items were fetched with Tavily and labelled, and the labels were committed in `ffd6ff5` (`eval/datause/preregistration-v3.json`). Prompt v3 was then written from v2's misses on the older items only and frozen in `6434478` before any v3 call. Nothing was edited after scoring.

| split `v3fresh` | Nemotron Super, prompt v3 (3 runs each) | Keyword baseline |
|---|---|---|
| 11 new features, 7 vendors new to the corpus | **7/11** (64%, **fails** the 80% bar), 22/33 runs | 4/11 |
| 2 new negatives (DeepSeek API terms, Perplexity search guide; both hard: data words, no data terms) | **2/2 held**, 6/6 runs | 0/2 |
| Per field, positive runs: retention / training / ZDR | 29/33 / 30/33 / 27/33 | 5/11 / 8/11 / 8/11 |

The misses: the model answered ZDR `available` from a link to another page (Vertex implicit caching) and from "we do not store any prediction data" (Cerebras Predicted Outputs). The verbatim gate withheld a correct xAI Batch `excluded` answer quoted as a table row on 2 of 3 runs. OpenRouter is the fourth miss. We also found one **labelling error of ours** after the run: OpenRouter says "your prompts are not retained unless you specifically opt in to prompt logging", so retention should be 0, not null. The label stays unchanged, as the pre-registration requires. The item still misses with the corrected label (training answered `no` on 2/3 runs), so the score stays 7/11. All of this is in `POST_RUN_TENSIONS` and the label audit.

**Older corpus, for reference (not clean).**

| | prompt v2 | prompt v3 (written from v2's misses here) | Keyword baseline |
|---|---|---|---|
| 13 `tuned` features (prompt written on these) | 13/13 | 12/13 | |
| 11 `heldout` features | 6/11 | 6/11 | 1/11 |
| 6 `fresh` features (labelled before v2) | 4/6 | 6/6 | 0/6 |
| All 30 | 23/30 (24/30 before one disclosed relabel) | 24/30 | 7/30 |
| 7 negatives | 7/7 | 7/7 | 5/7 |
| Pre-registered v1 prompt, first 24 features | 16/24: **failed** | | 7/24 |

- **Scored fields:** `retention_days`, `used_for_training` (yes / no / opt_in / opt_out / unspecified) and `zdr` (available / excluded / not_available / unspecified), per feature. An answer counts only if it matches the hand label. Every field the model asserts must quote the page **verbatim** (after markdown stripping), or code withholds that answer and marks it unspecified.
- **Labels and their evidence:** `eval/datause/label-audit.md` lists every label with the sentence that justifies it, plus five label-rule tensions we found after scoring. One label was changed after the run, on a reviewer's spot-check: Together says prompts "may be used for product improvements" by default, so `used_for_training` is now `opt_out`, not `opt_in` (rule in `owin/datause/schema.py`, before-score in `eval/datause/v2-before-relabel-score.json`). The prompt was not changed, and the model's `opt_in` answer now counts as a miss. One person (the build agent) labelled everything; an independent spot-check is still owed. The same agent labelled `v3fresh` and then wrote v3, so the pre-registration separates them by signed commit order, not by person. While writing v3 we removed four phrasings that echoed the new pages rather than the old misses (they are listed in the A1-v3 checkpoint entry).
- **The questionnaire catch is measured:** Anthropic's MCP connector "is not covered by ZDR arrangements" and Message Batches keep data 29 days. Both are exact in 3 of 3 runs.
- **Cost** is from Token Factory usage: v3 on `v3fresh` took 39 calls, $0.115 in total ($0.30 / $0.90 per M tokens), with p95 latency 16 s. v3 on the older items took 111 calls and $0.421.
- Raw pages are gitignored. Their provenance (URL, fetch time, sha256) is in `fixtures/manifest.json` under `datause`, and `owin eval score --corpus datause` works without them (it then says `quotes_rechecked_against_source: false`). The `v3fresh` pages were fetched with Tavily (`fixtures/raw/datause-tavily/`, also gitignored).

```bash
owin eval score --corpus datause --brief      # recompute, no key
owin eval audit --corpus datause              # rewrite eval/datause/label-audit.md
owin eval run --corpus datause --runs 3       # live; needs TOKEN_FACTORY_API_KEY and fixtures/raw/datause/
```

## The answer pack: your security review, per endpoint (A3)

`owin pack build --format brief` (no key, no network). `owin serve`, then open http://127.0.0.1:8787/ for the answer screen (static HTML/CSS/JS in `owin/web/`, no build step), or `GET /api/pack`, `GET /pack/print` or `POST /api/pack` with your own stack manifest.

Input: a stack manifest (each endpoint mapped to a vendor feature, e.g. `/api/crm-sync -> anthropic-mcp-connector`), your own settings, and the answers your trust page already gives (`fixtures/demo/stack.json`, fictional Lumen Notes). Output: five questionnaire answers, each with a per-endpoint cell, the vendor's verbatim sentence, its link and fetch time, an as-of time and a badge. **Code computes every badge from structured fields; quotes and your answer text are never read by a rule (tested).**

| | Badge | Why |
|---|---|---|
| 01 Training | Still true | All four endpoints: "never used for model training without your express permission" / OpenAI "not used to train or improve ... unless you explicitly opt in" |
| 02 Retention | Held | Anthropic's MCP connector page states no period ("retained according to Anthropic's standard data retention policy") |
| 03 ZDR | **Not true** | You say "zero data retention", but `/api/crm-sync` uses the MCP connector: "The MCP connector is not covered by ZDR arrangements." |
| 04 Region | Held | The vendor pages state no default region; Owin never computes one from free text |
| 05 Who sees it | Stale | OpenAI updated its sub-processor list on October 14, 2026 (was June 2), after the answer was written (2026-09-01). Real Wayback captures; Cloudflare's entry now names Cloudflare Regional Services, OAI International was added |

- **Change one input:** `owin pack build --set /api/crm-sync=anthropic-messages` and Q03 becomes Still true.
- **Exports:** CSV (one row per question and endpoint), a print-ready HTML in the light print tokens (print to PDF; A4), and a read-only share JSON for the live link. The buyer exports never contain the catch or the fix. Examples are in `examples/answer-pack/`.
- **Tavily runs the evidence path:** `owin pack refresh` re-fetches every page the stack relies on with Tavily `extract` (no query, whole page), records sha256 and quote presence in `data/datause/observations.json`, and keeps the stdlib fetcher only as a labelled `urllib_fallback`. `owin pack extract` then runs Nemotron on those Tavily captures; on 2026-10-21 it reproduced the recorded values for all four demo features, 3/3 runs each.
- **Stale means changed after you answered:** a sub-processor list whose entity table differs from the copy in effect when you wrote the answer, or a quoted sentence that is gone from the latest capture when the extraction on that capture does not reproduce the value. When Tavily serves an older copy (OpenAI's list, "July 9, 2026"), Owin holds that copy and does not use it.

## Previous subject: sub-processor objection windows (P1 to P3)

NVIDIA Nemotron Super on Nebius Token Factory read the sub-processor objection terms of 17 real vendor DPAs, all five fields exact with a verbatim quote, in 51 of 51 runs (7 of the 17 held out), at $0.0017 and 6.1 s per successful run. It held 6 of 6 thin-evidence controls rather than inventing a window. A regex baseline tuned on the same documents gets 9 of 17. Recompute it with `owin eval score`.

Owin (Objection Window) watches the vendors your startup uses. When one changes its sub-processor list, Owin reads that vendor's DPA and shows how many days you have to object and which of your customers you have to tell. It then drafts the notice you owe your own customers and your updated sub-processor page, plus the objection to the vendor for the rare case where you do object. A person sends everything.

## The replay: a real change, start here

`owin replay --brief` (or `owin serve`, then open http://127.0.0.1:8787/debug)

**OpenAI updated its sub-processor list on 2026-10-14.** The two sides of the change are the Wayback captures of [2026-07-08](https://web.archive.org/web/20260708120959/https://openai.com/policies/sub-processor-list/) ("Last updated June 2, 2026") and [2026-10-21](https://web.archive.org/web/20261021154629/https://openai.com/policies/sub-processor-list/) ("Last updated October 14, 2026"). It added OAI International, Inc. and new processing locations for Microsoft (Belgium, Denmark, Malaysia, New Zealand) and Google Cloud (Singapore). It also removed four entities. The company is fictional, and so are its DPA wording and its five customers ("Lumen Notes", `fixtures/demo/company.json`).

- **The result is `23 days to object · 3 customers to warn`.** OpenAI's DPA ("within 30 days of receiving notice", measured above) runs from the page date, because that is earlier than the date Owin first saw the change. So the objection deadline is 2026-11-13 18:59 EST.
- **The processor-side catch:** Lumen promised its own customers 30 days' notice. OpenAI may engage once its 30-day window ends, so that notice was due 2026-10-14, the day OpenAI updated the page. Lumen is 7 days late, and it is not subscribed to OpenAI's notices.
- **The default action is accept and notify.** Owin drafts three customer notices that quote Lumen's DPA promise word for word, an updated public sub-processor page and a dated decision record with clause and source hashes (`--decide accepted`). The objection to privacy@openai.com, which quotes OpenAI's clause, is the rare path.
- **Change one input:** `--promise-days 10` moves the notice due date to 2026-11-03 (13 days left). `--promise-days 45` raises `notice_inversion`.
- **Safe states, all tested:** no change gives `no_change` and no alert. Thin evidence (the live OpenAI page shows headings only) gives `held` with no deadline. AWS-style terms give `exit_only`. A list that will not parse gives `not_watchable`. A passed deadline gives `window_closed`. Code computes every deadline and state from structured fields, and a test shows that model prose cannot change them.

## The watch: Tavily sweep over 29 vendors

`owin sweep --brief` fetches each vendor's list with Tavily `extract` (no query, whole page) and normalises it to an entity table. It then diffs that table against the last accepted snapshot. Owin reads four list formats: HTML tables (OpenAI), markdown tables, trust-centre cards (Anthropic's Vanta page, 20/20 entities) and linked rows (Stripe, 38). Cookie banners, nav, pagers, link syntax and bold text never produce a diff (tested).

- **It catches stale data.** On 2026-10-21, Tavily returned OpenAI's list dated "July 9, 2026", while Wayback had "October 14, 2026" the same day. Owin marks that `stale_source`, holds, and keeps the newer state. A live "no change" needs a second, advanced-depth fetch that agrees.
- **Without a Tavily key**, the sweep uses recorded Tavily fixtures and labels them `fixture`. Vendors with no fixture show as `unfetched` rather than as fake results. Recorded sweeps are in `eval/sweeps/`.

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

- **Data-use number:** the clean number is 7/11 on `v3fresh`. That is 11 positives and 2 negatives, labelled by one agent, not independently, and scored in one 3-run sweep. It fails our 80% bar, and one item is worth 9 points. The same agent wrote the labels and then the prompt; the separation is the signed commit order (`ffd6ff5` before `6434478`). One labelling error of ours (OpenRouter retention) was found after the run and left unchanged; it does not change the score. The older 30-feature corpus (9 vendors) is not a clean test of v3 (24/30) or of v2 (23/30, after one post-run relabel), because each prompt was written after reading earlier misses on it. The first pre-registered prompt failed (16/24).
- **The A1 data-use pages were fetched by plain HTTP** (browser user agent, cookie jar) on 2026-10-21. The answer pack's six demo pages were re-fetched with Tavily the same evening; A1 itself has not been re-scored on Tavily captures. The pages are the vendors' own docs. Some describe products the reader may not recognise (for example GPT-6 and Claude Fable models); we report what the page said on the fetch date.
- **Training "no" vs "opt_in":** OpenAI's own table says "Data used for training: No" while its prose says "unless you explicitly opt in". Our label is `opt_in`, so a model giving the table's answer is scored wrong. Both mean "not used by default".
- 17 documents is a small corpus. One person labelled them, by reading each clause.
- The prompt and baseline were written after reading the first 10 clauses. Only the 7 held-out DPAs test generalisation.
- The live OpenAI DPA hides its clauses in accordions, so a fetch returns headings only. The scored OpenAI item uses the server-rendered Wayback capture of 2026-10-20. The live page is a negative control, and it holds.
- Raw vendor text in `fixtures/raw/` is not redistributed. Without it, `owin eval score` uses the recorded verbatim checks and says so (`quotes_rechecked_against_source: false`).
- Ultra was not re-run on this schema. In spike S2 it added nothing over Super on extraction, so Super is the default.
- The replay company and its customers are fictional. The vendor, the clause and the change are real.
- Deadline rules that the documents do not settle are assumptions, and each one is listed in the output. Unspecified days count as calendar days. The deadline is end of day in the earlier of your timezone and UTC. Public holidays are not modelled. The vendor is assumed not to engage before its window closes.
- A page diff is evidence, not legal notice.
- What Tavily returned for OpenAI's list on 2026-10-21 was dated "July 9, 2026", while Wayback the same day shows "October 14, 2026". The Tavily result was probably cached. Owin re-fetches before it declares "no change".
- The sweep has run live on recorded Tavily output for 5 of the 29 indexed vendors. A Tavily key has been on the build machine since 2026-10-21; a failed live extract now reports Tavily's own reason (for example Pinecone: "Failed to fetch url") instead of "no TAVILY_API_KEY". Supabase's list is a PDF and only its date is diffable. Vercel's list is a JS widget and is not watchable.
- Owin drafts. It gives no legal advice and never says "compliant".

License: MIT.

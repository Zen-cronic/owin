<p>
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="owin/web/img/logo-dark.svg">
    <img src="owin/web/img/logo-light.svg" alt="Owin" height="72">
  </picture>
</p>

# Owin

**On 7 AI vendors (6 of them new to Owin; pre-registered split `v3fresh`: 11 features on 8 pages), Owin filled 27 of 33 security-review answers on its own and got 26 right, 18 with the vendor's sentence and 8 correctly "not stated"; the other 6 it handed to a person to review, and on those a majority vote would have been right only 2 times. A plain majority vote over all 33 gets 28; it is wrong on 4 of the 6 Owin hands to a person.** The one confident miss is a label error we found ourselves and kept as pre-registered ([below](#what-well-tell-you-before-you-find-it)). Recompute it with no key: `owin eval selective --corpus datause --split v3fresh`. The headline numbers in this file are in [FACTS.md](FACTS.md), and a test recomputes each one.

## What, who, why (30 seconds)

> Your AI app's data went through six providers last month. Can you prove what each one keeps?

- **Who:** the founder or CTO of a 2–50 person B2B SaaS facing an enterprise buyer's security review. The questionnaire's AI section asks: is our data used for training, how long is it kept, do you have zero data retention (ZDR), where is it processed, who sees it.
- **The problem:** the honest answer is per feature, not per vendor. Anthropic's Messages API can run under ZDR; its MCP connector "is not covered by ZDR arrangements"; Message Batches keep data 29 days. A trust page that says "zero data retention" goes wrong as soon as one endpoint calls the wrong feature, or when a vendor changes its page after you answered.
- **What Owin does:** you list the endpoints you run and the vendor feature each one calls. Owin reads each vendor's own page, fills the five answers per endpoint with the sentence that supports each one, flags the answer that is **not true** for your stack, marks answers **outdated** when a page they rely on changed after you wrote them, and marks answers that **need review** when its readings disagree. It drafts the fix; you send it.
- **What you take to the buyer:** a read-only buyer report (PDF, CSV, or link) with the vendor sentence, link and fetch time behind every answer.

## Run it (one command)

```bash
export VIRTUAL_ENV="$HOME/.pyenv/versions/.owin"; export PATH="$VIRTUAL_ENV/bin:$PATH"   # or any Python 3.12 env
poetry install && poetry run owin serve   # then open http://127.0.0.1:8787/judge  (or: pip install -e . && owin serve)
```

No key, no network, no login: the app and every number run from committed files. With a Tavily key set on the server, "Re-check this page" under an endpoint fetches that vendor page live; without one, the button says so. `/judge` is the start page: the number (recomputed on load), three guided paths, and the evidence.

| Path on `/judge` | What it shows | Label |
|---|---|---|
| Replay a real change | Lumen Notes' answer 3 is **not true** for `/api/crm-sync` (Anthropic MCP connector, outside ZDR); answer 5 is **outdated** since OpenAI updated its sub-processor list on October 14, 2026 | Seeded replay, real vendor text, fictional company |
| Change one input | Point `/api/crm-sync` at Anthropic Messages; the server reruns the rules and answer 3 becomes verified | Live recompute |
| Try thin evidence | Point `/api/crm-sync` at Anthropic's rate-limits page (no data-use terms); every vendor field for it is marked not stated, none invented | Real page, no terms |

CLI equivalents: `owin pack build --format brief`, `--set /api/crm-sync=anthropic-messages`, `--set /api/crm-sync=thin-anthropic-rate-limits`. `pytest -q` runs the tests.

**Container and hosting.** `docker build -t owin . && docker run -p 8080:8080 owin` serves the same app on port 8080. Deploys to a Nebius Serverless AI Endpoint ([DEPLOY.md](DEPLOY.md): `cpu-d3`, `2vcpu-8gb`, the post-deploy check `scripts/smoke.sh <url>`, and the daily refresh job `owin job daily` on Nebius Serverless AI jobs); the container runs keyless unless keys are set, and `GET /healthz` reports the mode.

<!-- LIVE_URL --> Public URL: https://port8080-gq5qwgkze3dq2dm.tunnel.applications.us-north1.nebius.cloud/judge (no login; `scripts/smoke.sh https://port8080-gq5qwgkze3dq2dm.tunnel.applications.us-north1.nebius.cloud` passes).
Product page: https://port8080-gq5qwgkze3dq2dm.tunnel.applications.us-north1.nebius.cloud/about (what Owin does, in one scroll).
Also at https://owin.cloud (product page) and https://owin.cloud/judge (start page), which forward to the same Nebius endpoint.

## The number, in full

[![proof](https://github.com/Zen-cronic/owin/actions/workflows/proof.yml/badge.svg)](.github/workflows/proof.yml) ![auto-answered right](https://img.shields.io/badge/auto--answered%20right%20%28v3fresh%29-26%2F27%20%C2%B7%206%20to%20a%20person-2b6cb0)

The number badge is computed from the recomputed headline (`owin/facts.py::badge_url`) and a test fails if this README carries any other; the `proof` workflow reruns the tests and `owin facts check` from a fresh clone, keyless, on every push.

**Selective answering.** One cell is one (feature, field) pair: retention days, training use, ZDR. Nemotron reads the vendor page three times. A cell is answered automatically only when at least two readings succeeded and every successful reading agrees on it after the verbatim-quote gate; a reading that errored abstains rather than counting as a disagreement (a field without a verbatim sentence from the page becomes "not stated"). Anything else goes to a person as **Needs review**, with each reading's value and sentence. Code applies the rule to structured fields; it never reads model prose.

| split `v3fresh` (clean, pre-registered) | result |
|---|---|
| Answered automatically | **27/33** cells |
| Right among those | **26/27** (18 with the vendor's sentence, 8 correctly "not stated") |
| Handed to a person to review | **6** (a majority vote would have been right on 2/6; over all 33 cells a plain majority vote gets 28/33) |
| Negative controls (pages with no data-use terms) | 6/6 cells answered "not stated", correctly |
| Whole-item score, all three fields exact by majority (the pre-registered metric) | **7/11, which fails our own 80% bar**; keyword baseline 4/11 |
| Negatives correctly left unanswered, whole-item | 2/2; keyword baseline 0/2 |

The labels for `v3fresh` were committed (`42b8994`) before prompt v3 was written and frozen (`8205f8d`); nothing was edited after scoring. The older items are not a clean test because earlier misses on them shaped the prompt. For reference only: v3 there fills 80/90 cells automatically and gets 77/80 right; v2 fills 77/90 and gets 72/77.

```bash
owin eval selective --corpus datause --split v3fresh --brief   # the line-one number
owin eval score --corpus datause --brief                       # the pre-registered whole-item score
owin facts check                                               # every claim in this README, recomputed
```

On a fresh clone (vendor page text is not in the repository) the arithmetic recomputes from the recorded runs, the keyword baseline is replayed from its recorded output per page sha256 (`eval/datause/baseline-outputs.json`, equal to the recomputed output wherever the pages are present), and the verbatim gate uses its recorded results; `quotes_rechecked_against_source` in the output says which.

## Why these sponsors

- **NVIDIA Nemotron 3 Super (`nvidia/nemotron-3-super-120b-a12b`, open-weight) on Nebius Token Factory** reads each vendor page and proposes structured fields plus the sentence for each. Measured on `v3fresh`: **$0.0029 per reading** (39 calls, $0.115 total, list price $0.30 / $0.90 per M tokens), mean 8.8 s, p95 15.9 s over the runs that were exactly right. One endpoint costs about **$0.009** to answer (three readings). **Super and Ultra, measured on this task** (`owin eval ladder --corpus datause --brief`; the arms, the escalation rule and its bar were committed in `eval/datause/escalation-preregistration.json` before Ultra ran). Nemotron 3 Ultra alone, same three-reading rule, answers 30 of 33 cells on its own and gets 29 right, at $0.0136 per reading (4.6× Super), so on this task one larger model does beat three cheap readings. Owin uses both: Super reads every page three times, and Ultra reads only the pages where Super's readings split. With Nemotron Ultra reading only the pages where Super's three readings split (the rule written before Ultra ran), 4 of those 6 cells were answered automatically and right, at $0.035 more per such page; 2 still go to a person. Overall: 31 of 33 answered, 30 right, the one miss still the OpenRouter label below. Agreement across readings is still the confidence signal; Ultra is spent only where Super's readings disagree. The small models, same rule: Nemotron 3 Nano answers 25 cells on its own and gets 24 right at $0.0011 per reading but 44.8 s per reading, and a Nano-first cascade saves nothing per endpoint; Nemotron 3.5 Lightning ran out its 8,000-token budget reasoning on 32 of 39 readings, so it answered nothing on its own. Nemotron's reasoning is what buys that precision, measured: with it off (`chat_template_kwargs.enable_thinking=false`; same prompt, split and rule) a reading costs $0.0014 and takes 3.0 s instead of 9.7 s, but Owin then answers 28 cells on its own and gets only 21 of 28 right, so reasoning stays on everywhere (`eval/thinking-off-vs-on.json`).
- **Tavily `extract`** fetches each vendor page whole (no query) whenever Owin fetches: `owin pack refresh` and `owin sweep` on the CLI, the daily `owin job daily`, and the app's "Re-check this page" button when a Tavily key is set on the server. The pages a judge opens replay recorded captures; no page view calls Tavily. The report's readings run on those captures. When Tavily serves an older copy than one we already trust (OpenAI's list came back dated July 9, 2026 after Wayback showed October 14, 2026), Owin **sets that copy aside** and never uses it: the older-copy rule. `owin sweep` covers 29 vendors per sweep.

## Architecture

```
stack manifest ──► catalog (endpoint → vendor feature → page)
Tavily extract ──► observations (dated captures, hashes, list snapshots)
Nemotron ×3    ──► registry (structured fields + verbatim quotes + per-field agreement)
rules (code)   ──► buyer report ──► app / PDF / CSV / share link
```

- **Tavily** (`owin/tavily.py`, `owin/datause/observations.py`): fetches each vendor page and records when and what it saw, so "outdated" is evidence, not a guess.
- **Nebius Token Factory + Nemotron Super** (`owin/tokenfactory.py`, `owin/datause/extract.py`): turns a page into five fields, each with its sentence; the verbatim gate drops any field it cannot quote.
- **Registry** (`owin/datause/registry.py`, `data/datause/registry.json`): stores the readings and decides, per field, auto or Needs review (`owin/datause/selective.py`).
- **Rules** (`owin/datause/pack.py`): compare vendor fields with the answers you already gave, from enums and integers only, and set Not true / Outdated / Needs review / Not stated / Verified.
- **App and exports** (`owin/server.py`, `owin/web/`, `owin/datause/export.py`): a stdlib HTTP server with no build step; the buyer exports never include internal reasons or fix drafts.

## How Owin meets the judging criteria

- **Technological implementation.** Nemotron on Token Factory is the reader in a measured loop: pre-registered labels, a keyword baseline, negative controls, three readings per page, a verbatim gate, and selective answering recomputed from recorded runs by one command. Cost and latency come from Token Factory's own usage figures. Four Nemotron sizes are measured on the same split and rule (`owin eval ladder`), and a pre-registered escalation sends only Super's split cells to Ultra: 6 hand-offs become 2, no new miss. Nemotron's reasoning switch is measured too and stays on. Code decides every answer; a test shows model prose cannot change a verdict, and on `POST /api/recheck` a live Nemotron re-reading can only hand an answer to a person.
- **Design.** A finished answer screen: the finding first (one sentence, one primary action), endpoints linked to the answers they break, a legend, Needs review / Outdated / Not stated states that never guess, mobile tabs, loading and error states, and a light print copy for the buyer. `/judge` is the guided start.
- **Potential impact.** A named buyer (the founder or CTO in a security review) and a specific failure (a "zero data retention" answer that one endpoint makes false). The demo shows the finding on real vendor text, the fix, and what goes to the buyer.
- **Quality of the idea.** Per-feature terms, not per-vendor: the same vendor can be inside and outside ZDR depending on the endpoint. Owin checks the answers you already gave against each vendor's own sentence, and it knows when not to answer.

## What we'll tell you before you find it

- **Our earlier prompts failed.** Pre-registered prompt v1 scored 16/24 (failed). v2 scored 23/30 on the older items after an honest relabel (Together's "may use them for product improvements" is opt-out, not opt-in), below the bar. Pre-registered v3 scored **7/11** on fresh vendors, also below our 80% bar. Selective answering is the result we stand behind: 26/27 when Owin answers on its own, 6 sent to a person.
- **One labeller, one self-disclosed error.** An AI coding agent labelled every item by reading each fetched page; a second agent pass spot-checked; there has been no independent human audit yet. After the v3 run we found that OpenRouter's page says "your prompts are not retained unless you specifically opt in to prompt logging", so the retention label should be 0, not "not stated". Nemotron answered 0 on 3/3 readings. We kept the label, as the pre-registration requires, so this counts as the one confident miss; with the corrected label it would be 27/27.
- **Small splits.** 11 positive features and 2 negatives in the clean split, one 3-reading sweep. One item moves the whole-item score by 9 points.
- **The demo company is fictional.** Lumen Notes, its endpoints, its trust-page answers and its **ZDR settings are assumed** (Owin cannot see vendor consoles). The vendor sentences, links, fetch times and the OpenAI list change (Wayback captures; OpenAI changed Cloudflare's entry and added OAI International) are real.
- **Region never decides.** Vendor region text is free text, so no rule reads it; answer 4 is marked not stated unless you state your own setting.
- **Some vendor pages are not watchable.** Vercel's sub-processor list is a JavaScript widget; OpenAI's DPA hides its clauses in accordions; Supabase's list is a PDF with only a date to diff. Tavily sometimes serves an older copy; Owin sets it aside.
- **Report readings and the scored corpus differ.** The report's readings and the `v3fresh` corpus pages were both fetched with Tavily `extract` (basic depth, markdown); most of the older corpus pages were fetched by plain HTTP (urllib), some with Tavily. OpenAI Embeddings in the demo is not in the scored corpus.
- **The watch is not scheduled on Nebius yet.** `owin job daily` (sweep, refresh, Nemotron re-reading) has run once for real, on 2026-10-29 from a laptop (records under `eval/sweeps/`). Pages are also re-fetched by command (`owin pack refresh`) or from the app's "Re-check this page" button when a key is set. The Nebius Serverless AI job is written up in [DEPLOY.md](DEPLOY.md) and has not been executed there.
- **Not legal advice.** Owin quotes vendors and compares answers; it does not tell you what you are permitted to do.

## Earlier work in this repo

Owin began as an objection-window tracker for sub-processor changes (the name is from **O**bjection **Win**dow). That engine is still here and tested: Nemotron read 17 real DPAs with all five fields exact (10/10 tuned, 7/7 held out, 51/51 runs) and correctly left 6/6 thin-evidence controls unanswered (`owin eval score --brief`); `owin replay --brief` replays OpenAI's real October 14, 2026 list change; `owin sweep --brief` diffs 29 vendors' lists via Tavily. See `docs/CONTRACT.md`.

License: MIT.

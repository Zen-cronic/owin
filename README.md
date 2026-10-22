# Owin

**On 7 AI vendors it had never seen (pre-registered split `v3fresh`, 11 features), Owin filled 27 of 33 security-review answers on its own and got 26 right, each with the vendor's own sentence; the other 6 it asked a person to confirm, and on those a majority vote would have been right only 2 times.** The one confident miss is a label error we found ourselves and kept as pre-registered ([below](#what-well-tell-you-before-you-find-it)). Recompute it with no key: `owin eval selective --corpus datause --split v3fresh`. Every number in this file is in [FACTS.md](FACTS.md), and a test recomputes each one.

## What, who, why (30 seconds)

> Your AI app's data went through six providers last month. Can you prove what each one keeps?

- **Who:** the founder or CTO of a 2–50 person B2B SaaS facing an enterprise buyer's security review. The questionnaire's AI section asks: is our data used for training, how long is it kept, do you have zero data retention (ZDR), where is it processed, who sees it.
- **The problem:** the honest answer is per feature, not per vendor. Anthropic's Messages API can run under ZDR; its MCP connector "is not covered by ZDR arrangements"; Message Batches keep data 29 days. A trust page that says "zero data retention" goes wrong as soon as one endpoint calls the wrong feature, or when a vendor changes its page after you answered.
- **What Owin does:** you list the endpoints you run and the vendor feature each one calls. Owin reads each vendor's own page, fills the five answers per endpoint with the sentence that supports each one, flags the answer that is **not true** for your stack, marks answers **stale** when a page they rely on changed after you wrote them, and **asks you to confirm** when its readings disagree. It drafts the fix; you send it.
- **What you take to the buyer:** a read-only answer pack (PDF, CSV, or link) with the vendor sentence, link and fetch time behind every answer.

## Run it (one command)

```bash
export VIRTUAL_ENV="$HOME/.pyenv/versions/.owin"; export PATH="$VIRTUAL_ENV/bin:$PATH"   # or any Python 3.12 env
poetry install && owin serve      # then open http://127.0.0.1:8787/judge
```

No key, no network, no login: the app and every number run from committed files. `/judge` is the start page: the number (recomputed on load), three guided paths, and the evidence.

| Path on `/judge` | What it shows | Label |
|---|---|---|
| Replay a real change | Lumen Notes' answer 3 is **not true** for `/api/crm-sync` (Anthropic MCP connector, outside ZDR); answer 5 is **stale** since OpenAI updated its sub-processor list on October 14, 2026 | Seeded replay, real vendor text, fictional company |
| Change one input | Point `/api/crm-sync` at Anthropic Messages; the server reruns the rules and answer 3 becomes still true | Live recompute |
| Try thin evidence | Point `/api/crm-sync` at Anthropic's rate-limits page (no data-use terms); every vendor field for it is held, none invented | Real page, no terms |

CLI equivalents: `owin pack build --format brief`, `--set /api/crm-sync=anthropic-messages`, `--set /api/crm-sync=thin-anthropic-rate-limits`. `pytest -q` runs the tests.

## The number, in full

**Selective answering.** One cell is one (feature, field) pair: retention days, training use, ZDR. Nemotron reads the vendor page three times. A cell is answered automatically only when all three readings agree on it after the verbatim-quote gate (a field without a verbatim sentence from the page becomes "not stated"). Anything else goes to a person as **Confirm**, with each reading's value and sentence. Code applies the rule to structured fields; it never reads model prose.

| split `v3fresh` (clean, pre-registered) | result |
|---|---|
| Answered automatically | **27/33** cells |
| Right among those | **26/27** |
| Sent to a person to confirm | **6** (a majority vote would have been right on 2/6) |
| Negative controls (pages with no data-use terms) | 6/6 cells answered "not stated", correctly |
| Whole-item score, all three fields exact by majority (the pre-registered metric) | **7/11, which fails our own 80% bar**; keyword baseline 4/11 |
| Negatives held, whole-item | 2/2; keyword baseline 0/2 |

The labels for `v3fresh` were committed (`ffd6ff5`) before prompt v3 was written and frozen (`6434478`); nothing was edited after scoring. The older items are not a clean test because earlier misses on them shaped the prompt. For reference only: v3 there fills 80/90 cells automatically and gets 77/80 right; v2 fills 74/90 and gets 69/74.

```bash
owin eval selective --corpus datause --split v3fresh --brief   # the line-one number
owin eval score --corpus datause --brief                       # the pre-registered whole-item score
owin facts check                                               # every claim in this README, recomputed
```

## Why these sponsors

- **NVIDIA Nemotron 3 Super (`nvidia/nemotron-3-super-120b-a12b`, open-weight) on Nebius Token Factory** reads each vendor page and proposes structured fields plus the sentence for each. Measured on `v3fresh`: **$0.0029 per reading** (39 calls, $0.115 total, list price $0.30 / $0.90 per M tokens), mean 8.8 s, p95 15.9 s. One endpoint costs about **$0.009** to answer (three readings). We use three cheap readings and agreement instead of one larger model: in our first spike, Nemotron Ultra did not beat Super on extraction, and agreement across readings is what separates the 26/27 from the 6 that need a person.
- **Tavily `extract`** fetches the vendor pages at runtime (whole page, no query), and the pack's readings run on its captures. When Tavily serves an older copy than one we already trust (OpenAI's list came back dated July 9, 2026 after Wayback showed October 14, 2026), Owin **holds** that copy and never uses it: the stale-source rule. `owin pack refresh` re-fetches; `owin sweep` covers a 29-vendor index.

## Architecture

```
stack manifest ──► catalog (endpoint → vendor feature → page)
Tavily extract ──► observations (dated captures, hashes, list snapshots)
Nemotron ×3    ──► registry (structured fields + verbatim quotes + per-field agreement)
rules (code)   ──► answer pack ──► app / PDF / CSV / share link
```

- **Tavily** (`owin/tavily.py`, `owin/datause/observations.py`): fetches each vendor page and records when and what it saw, so "stale" is evidence, not a guess.
- **Nebius Token Factory + Nemotron Super** (`owin/tokenfactory.py`, `owin/datause/extract.py`): turns a page into five fields, each with its sentence; the verbatim gate drops any field it cannot quote.
- **Registry** (`owin/datause/registry.py`, `data/datause/registry.json`): stores the readings and decides, per field, auto or Confirm (`owin/datause/selective.py`).
- **Rules** (`owin/datause/pack.py`): compare vendor fields with the answers you already gave, from enums and integers only, and set Not true / Stale / Confirm / Held / Still true.
- **App and exports** (`owin/server.py`, `owin/web/`, `owin/datause/export.py`): a stdlib HTTP server with no build step; the buyer exports never include internal reasons or fix drafts.

## How Owin meets the judging criteria

- **Technological implementation.** Nemotron on Token Factory is the reader in a measured loop: pre-registered labels, a keyword baseline, negative controls, three readings per page, a verbatim gate, and selective answering recomputed from recorded runs by one command. Cost and latency come from Token Factory's own usage figures. Code decides every answer; a test shows model prose cannot change a verdict.
- **Design.** A finished answer screen: the catch first (one sentence, one primary action), endpoints linked to the answers they break, a legend, Confirm / Stale / Held states that never guess, mobile tabs, loading and error states, and a light print copy for the buyer. `/judge` is the guided start.
- **Potential impact.** A named buyer (the founder or CTO in a security review) and a specific failure (a "zero data retention" answer that one endpoint makes false). The demo shows the catch on real vendor text, the fix, and what goes to the buyer.
- **Quality of the idea.** Per-feature terms, not per-vendor: the same vendor can be inside and outside ZDR depending on the endpoint. Owin checks the answers you already gave against each vendor's own sentence, and it knows when not to answer.

## What we'll tell you before you find it

- **Our earlier prompts failed.** Pre-registered prompt v1 scored 16/24 (failed). v2 scored 23/30 on the older items after an honest relabel (Together's "may use them for product improvements" is opt-out, not opt-in), below the bar. Pre-registered v3 scored **7/11** on fresh vendors, also below our 80% bar. Selective answering is the result we stand behind: 26/27 when Owin answers on its own, 6 sent to a person.
- **One labeller, one self-disclosed error.** The build agent labelled every item; no independent spot-check has been done yet. After the v3 run we found that OpenRouter's page says "your prompts are not retained unless you specifically opt in to prompt logging", so the retention label should be 0, not "not stated". Nemotron answered 0 on 3/3 readings. We kept the label, as the pre-registration requires, so this counts as the one confident miss; with the corrected label it would be 27/27.
- **Small splits.** 11 positive features and 2 negatives in the clean split, one 3-reading sweep. One item moves the whole-item score by 9 points.
- **The demo company is fictional.** Lumen Notes, its endpoints, its trust-page answers and its **ZDR settings are assumed** (Owin cannot see vendor consoles). The vendor sentences, links, fetch times and the OpenAI list change (Wayback captures; OpenAI changed Cloudflare's entry and added OAI International) are real.
- **Region never decides.** Vendor region text is free text, so no rule reads it; answer 4 is held unless you state your own setting.
- **Some vendor pages are not watchable.** Vercel's sub-processor list is a JavaScript widget; OpenAI's DPA hides its clauses in accordions; Supabase's list is a PDF with only a date to diff. Tavily sometimes serves an older copy; Owin holds it.
- **Answer-pack runs and the scored corpus differ.** The pack's readings run on Tavily captures; the scored corpus pages were fetched by plain HTTP. OpenAI Embeddings in the demo is not in the scored corpus.
- **The watch is not scheduled yet.** Pages are re-fetched by command (`owin pack refresh`); a daily job on Nebius Serverless Jobs is next.
- **Not legal advice.** Owin quotes vendors and compares answers; it does not tell you what you are permitted to do.

## Earlier work in this repo

Owin began as an objection-window tracker for sub-processor changes (the name is from **O**bjection **Win**dow). That engine is still here and tested: Nemotron read 17 real DPAs with all five fields exact (10/10 tuned, 7/7 held out, 51/51 runs) and held 6/6 thin-evidence controls (`owin eval score --brief`); `owin replay --brief` replays OpenAI's real October 14, 2026 list change; `owin sweep --brief` diffs 29 vendors' lists via Tavily. See `docs/CONTRACT.md`.

License: MIT.

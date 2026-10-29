# Product

> Inferred from the README, FACTS.md and the shipped app copy. Every section below restates what the repository already says; nothing here is new product truth. Items marked *open* are undecided.

## Platform

web

## Users

- **Primary:** the founder or CTO of a 2–50 person B2B SaaS company facing an enterprise buyer's security review. The questionnaire's AI section asks five things: is our data used for training, how long is it kept, do you have zero data retention (ZDR), where is it processed, who sees it. They answer it at a desk, usually against a deadline, with the vendor pages open in other tabs.
- **Secondary:** the buyer's security reviewer, who receives the read-only answer pack (PDF, CSV or link) and checks each answer against the vendor sentence behind it.
- **First-time evaluators** arrive at the start page (`/judge`) with no login and no key and need to see the mechanism work within a minute.

## Product Purpose

Owin fills the AI section of a security questionnaire per endpoint, from each AI vendor's own page, with the sentence that supports every answer. It flags the answer that is not true for the stack, marks answers stale when a page they rely on changed, and asks a person to confirm when its readings disagree. Success is a trust page and an answer pack that stay true, with proof a buyer can check.

## Positioning

The honest answer is per feature, not per vendor: one vendor can run one endpoint under ZDR and keep another endpoint's data for 29 days. Owin answers per endpoint, quotes the vendor's own sentence, and holds an answer rather than inventing one when the page does not say. Code, not the model, decides every answer.

## Operating Context

- The answer screen (`/`) shows one company's stack (endpoints and the vendor feature each calls), the five questionnaire answers with a state badge each (Not true, Stale, Confirm, Held · unspecified, Still true), the quoted vendor evidence, a fix draft, and exports.
- The start page (`/judge`) explains why the product exists, shows three recomputed numbers, three guided paths, and the evidence ledger.
- The demo company (Lumen Notes) and its endpoints are fictional; every vendor sentence, link and fetch time is real.
- Artefacts in the user's world: vendor trust pages, sub-processor lists, data-retention policies, the buyer's questionnaire spreadsheet, the PDF answer pack.

## Capabilities and Constraints

- Stdlib Python HTTP server, static vanilla HTML/CSS/JS under `owin/web/`, no build step. Static files are an explicit allowlist in `owin/webui.py`.
- Runs keyless from committed files; "Re-check this page" calls Tavily only when a key is set on the server.
- A demo recorder and the test suite bind to element ids, classes and `aria-busy`; the DOM contract is frozen (see DESIGN.md).
- Five switchable looks (`html[data-theme="c1".."c5"]`), set before first paint from `?theme=`, then saved choice, then the default.
- Buyer exports never include internal reasons or fix drafts.

## Brand Commitments

- Name: Owin, set lowercase as a wordmark.
- Voice: plain, exact, and self-disclosing: numbers carry their denominators, limits are stated before anyone finds them, nothing is called "compliant", and the product is "not legal advice".
- The start page's first-person opening line is kept verbatim; design work never writes, rewrites or extends a first-person line.

## Evidence on Hand

- Recomputed numbers (FACTS.md, tested): 27/33 cells filled on its own, 26/27 right, 6 handed to a person; $0.0029 per reading, about $0.009 per endpoint.
- Real vendor pages and captures for Anthropic and OpenAI under `data/`; the OpenAI sub-processor list change of October 14, 2026.
- No customers, testimonials, or press exist; none may be implied.

## Product Principles

1. Every answer shows the vendor sentence it rests on.
2. Hold rather than invent: an unstated field stays unanswered.
3. Disagreement goes to a person, with each reading shown.
4. Say the limit before the reader finds it.
5. The one thing to act on is unmistakable; everything else is calm.

## Accessibility & Inclusion

WCAG 2.2 AA contrast, visible focus on every control, keyboard-operable menus, tabs and pickers, `prefers-reduced-motion` respected, no horizontal scroll at 390px.

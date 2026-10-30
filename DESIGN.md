---
name: Owin
description: Security review answers per endpoint, filed like a card catalogue.
colors:
  field: "#1B3A5E"
  field-deep: "#122A46"
  frame: "#A4C6DE"
  card-stock: "#FCFBF7"
  card-selected: "#FFFFFF"
  stock-back: "#E9E2D6"
  wash: "#EEF4F6"
  hit: "#F1EADC"
  signal-red: "#B3202A"
  signal-red-deep: "#951A23"
  status-outdated: "#0F6B7F"
  status-needs-review: "#2D3E66"
  status-not-stated: "#5E5A55"
  rule-cyan: "#7FB6CF"
  ruled-line: "#C9DCE4"
  ink: "#1E1A16"
  ink-muted: "#5E5A55"
  ink-cite: "#3A3631"
  edge: "#6A645C"
  on-field: "#FFFFFF"
  on-field-muted: "#C7D8EA"
  link-signal-on-field: "#F4B6AE"
typography:
  display:
    fontFamily: "Parkinsans, Archivo, Arial, system-ui, sans-serif"
    fontSize: "44px"
    fontWeight: 700
    lineHeight: 1.08
    letterSpacing: "-0.012em"
  display-start:
    fontFamily: "Parkinsans, Archivo, Arial, system-ui, sans-serif"
    fontSize: "clamp(30px, 3.3vw, 48px)"
    fontWeight: 700
    lineHeight: 1.1
    letterSpacing: "-0.012em"
  headline:
    fontFamily: "Parkinsans, Archivo, Arial, system-ui, sans-serif"
    fontSize: "30px"
    fontWeight: 700
    lineHeight: 1.1
    letterSpacing: "-0.01em"
  title:
    fontFamily: "Parkinsans, Archivo, Arial, system-ui, sans-serif"
    fontSize: "20px"
    fontWeight: 700
    lineHeight: 1.3
    letterSpacing: "-0.005em"
  numeral:
    fontFamily: "Parkinsans, Archivo, Arial, system-ui, sans-serif"
    fontSize: "clamp(64px, 7.4vw, 112px)"
    fontWeight: 800
    lineHeight: 1
    letterSpacing: "0"
    fontFeature: "\"tnum\""
  body:
    fontFamily: "Atkinson Hyperlegible Next, Atkinson Hyperlegible, system-ui, sans-serif"
    fontSize: "15.5px"
    fontWeight: 400
    lineHeight: 1.55
    letterSpacing: "0"
  label:
    fontFamily: "Parkinsans, Archivo, Arial, system-ui, sans-serif"
    fontSize: "12px"
    fontWeight: 700
    lineHeight: 1.3
    letterSpacing: "0.08em"
  status-label:
    fontFamily: "Parkinsans, Archivo, Arial, system-ui, sans-serif"
    fontSize: "12.5px"
    fontWeight: 700
    lineHeight: 1
    letterSpacing: "0.07em"
  path:
    fontFamily: "Atkinson Hyperlegible Mono, ui-monospace, SF Mono, Menlo, monospace"
    fontSize: "15px"
    fontWeight: 700
    lineHeight: 1.3
rounded:
  none: "0"
  sm: "8px"
  md: "14px"
  card: "20px"
  sheet: "24px"
  pill: "999px"
spacing:
  hair: "1px"
  frame: "2px"
  stack-gap: "14px"
  card-gap: "18px"
  card-pad: "22px"
  column-gap: "24px"
  pane-gap: "56px"
  stack-column: "360px"
  page-gutter: "clamp(16px, 3.4vw, 48px)"
components:
  button-primary:
    backgroundColor: "{colors.card-stock}"
    textColor: "{colors.ink}"
    rounded: "{rounded.pill}"
    padding: "13px 20px"
  button-primary-hover:
    backgroundColor: "{colors.card-selected}"
  button-primary-on-card:
    backgroundColor: "{colors.field}"
    textColor: "{colors.on-field}"
    rounded: "{rounded.pill}"
  button-secondary:
    backgroundColor: "transparent"
    textColor: "{colors.on-field}"
    rounded: "{rounded.pill}"
    padding: "0 20px"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    rounded: "{rounded.pill}"
    padding: "7px 12px"
  button-ghost-hover:
    backgroundColor: "{colors.wash}"
  answer-card:
    backgroundColor: "{colors.card-stock}"
    textColor: "{colors.ink}"
    rounded: "{rounded.card}"
    padding: "20px 22px 24px"
  answer-card-selected:
    backgroundColor: "{colors.card-selected}"
  drawer-label:
    backgroundColor: "{colors.card-stock}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "14px 16px 16px"
  status-not-true:
    backgroundColor: "{colors.signal-red}"
    textColor: "{colors.on-field}"
    typography: "{typography.status-label}"
    rounded: "{rounded.sm}"
    padding: "5px 8px 4px"
  status-outdated:
    backgroundColor: "transparent"
    textColor: "{colors.status-outdated}"
    typography: "{typography.status-label}"
    rounded: "{rounded.sm}"
    padding: "3px 6px 2px"
  status-needs-review:
    backgroundColor: "transparent"
    textColor: "{colors.status-needs-review}"
    typography: "{typography.status-label}"
    rounded: "{rounded.sm}"
    padding: "5px 8px 4px"
  status-not-stated:
    backgroundColor: "transparent"
    textColor: "{colors.status-not-stated}"
    typography: "{typography.status-label}"
    rounded: "{rounded.sm}"
    padding: "6px 8px 5px"
  tally-card:
    backgroundColor: "{colors.card-stock}"
    textColor: "{colors.ink}"
    rounded: "18px"
    padding: "16px 22px 18px"
  numeral-plate:
    backgroundColor: "{colors.card-stock}"
    textColor: "{colors.ink}"
    typography: "{typography.numeral}"
    rounded: "16px"
  drawer-front:
    backgroundColor: "{colors.field}"
    textColor: "{colors.on-field}"
    rounded: "{rounded.sheet}"
    padding: "36px 20px 30px"
---

# Design System: Owin

## Overview

**Creative North Star: "The Card Catalogue"**

Owin files vendor evidence the way a library files its holdings. The page ground is a flat field of Prussian blue, the ground of a cyanotype. Every endpoint is a drawer label held in a pale cyanotype frame; every questionnaire answer is a ruled index card with rounded corners, as library cards have; the state of an answer is a status label marked on that card; the note on the card is the vendor's own sentence. The world is daylight, paper and blueprint ink, read at a desk.

Density is that of a working catalogue: many cards, each short, each ruled. Hierarchy comes from material (blueprint field, card, cyanotype frame, ink) rather than from tint or elevation. Red is reserved for what is not true, so a red mark always means "act here". The system rejects the dark developer dashboard with a single neon accent, blueprint grid texture, glow, and tilted or decorative badges.

This file records theme 1 ("Catalogue"), the default look, which the product page (`/about`) shares. Four alternate themes ship as opt-in and are described under Layout only as far as the theme system binds them.

**Key Characteristics:**
- Flat Prussian-blue field carrying white text; white card stock carrying dark ink.
- Pale cyanotype frames (2px ring, 4px on numeral plates) around labels, never a fill behind body text.
- A 2px cyan ruled header line under every card head; red replaces it on the one card that is not true.
- Status labels whose frame form carries meaning as much as their ink: filled box, double rule, dashed, thin rule, bare tick.
- Parkinsans for entries and marks, Atkinson Hyperlegible Next for reading, Atkinson Hyperlegible Mono for paths and commands.
- Rounded corners on every card, label and plate; pill buttons. No tilt anywhere. No shadow beyond a card's 1px bottom edge.

## Colors

A cool blueprint-and-paper palette: a Prussian-blue field, pale cyanotype frames and white card stock, with one hot signal and three status inks. Signal red is the only warm colour on the page.

### Primary
- **Not True Red** (signal-red): the Not true label, the selected card's frame and header rule, the struck-through wrong text in the fix panel, and the failing cell in the per-endpoint row. Nothing else; buttons are never red.
- **Pressed Red** (signal-red-deep): kept in the token layer for the alternate themes; theme 1 no longer uses it.

### Secondary
- **Cyanotype Line** (frame): label frames around the wordmark, drawer labels, tally card, numeral plates and the export menu; drawer pulls under numerals; the selected theme number; the active mobile tab underline; the rule under the finding. Decorative framing only, never text on the field.

### Tertiary
- **Exposure Teal** (status-outdated, CSS `--stamp-stale`, #0F6B7F): the Outdated label and the "changed" tag. The teal of an under-exposed cyanotype: 5.91:1 on card stock, 6.12:1 on fresh white, 5.51:1 on the wash and 4.76:1 on pushed-back stock. CIEDE2000 distance 22.0 from Needs review navy, 21.3 from Not stated graphite and 55.4 from Not true red, so it is told apart by hue as well as by its double-rule frame. It replaces the earlier violet (#5B3D94), which sat outside the cyanotype palette.
- **Review Navy** (status-needs-review, CSS `--stamp-confirm`): the Needs review label, source links on cards, the review box's dashed frame, and the "to review" disclosure. Doubles as the card-context focus ring.
- **Pencil Grey** (status-not-stated, CSS `--stamp-held`): the Not stated label, drawn as a thin 1px rule.
- **Ruling Cyan** (rule-cyan): the 2px ruled header line of every card, the fix panel's top rule, and source-link underlines.

### Neutral
- **Prussian Blue** (field): the page ground, the drawer fronts, and the primary button when it sits on a card.
- **Deep Prussian** (field-deep): the full-bleed band that houses the drawer fronts on the start page.
- **Index Stock** (card-stock): answer cards, drawer labels, tally, menus, shelf-list cards, and the primary button on the field.
- **Fresh Card** (card-selected): the selected or outdated card, fields, the command line, the primary button's hover.
- **Pushed-Back Stock** (stock-back): a card related away from the current focus or recomputing; it darkens instead of fading.
- **Ruling Wash** (wash): hover and chip wash on cards.
- **Highlighted Row** (hit): the table row that answers the question.
- **Card Ink** (ink), **Card Muted** (ink-muted), **Quoted Ink** (ink-cite), **Control Edge** (edge): text, captions, quoted vendor sentences and control borders on card stock.
- **On Prussian** (on-field) and **On Prussian Muted** (on-field-muted): text set directly on the field, and the outline of secondary pills.
- **Pale Signal** (link-signal-on-field): the connector line from the failing endpoint to its answer, drawn over the field, and the warning icon in the finding line.

### Named Rules

**The Red Means Act Rule.** Signal red marks only Not true. Outdated, Needs review and Not stated each have their own ink; none borrows red, and no button is red.

**The Two Contexts Rule.** Anything set on the field reads the on-field tokens; anything filed on a card reads the card tokens. A component never mixes the two, and switching context is done by re-pointing --ink, --muted, --cite, --edge, --line and --focus, not by new colours.

## Typography

**Display Font:** Parkinsans 500 to 800 (with Archivo, Arial, system-ui), loaded from the theme stylesheet.
**Body Font:** Atkinson Hyperlegible Next (with Atkinson Hyperlegible, system-ui).
**Label/Mono Font:** Atkinson Hyperlegible Mono for endpoint paths, question numbers in rows, and commands.

**Character:** A catalogue's entries in a rounded, sturdy face over a reading face built for legibility. Weight and case do the work: heavy Parkinsans for entries a reader scans to, small Parkinsans capitals for anything that behaves like a status label or a drawer label.

### Hierarchy
- **Display** (700, 44px, 1.08, -0.012em): the finding on the answer screen, set straight on the field. 27px at 900px and below.
- **Display, start page** (700, clamp(30px, 3.3vw, 48px), 1.1): the opening line on the start page, across eleven of twelve columns.
- **Headline** (700, 30px, 1.1): section heads on the start page. 24px on phones.
- **Title** (700, 20px, 1.3): the question on each answer card; 22px for guided-path titles. 18px on phones.
- **Numeral** (800, clamp(64px, 7.4vw, 112px), 1, tabular): the three recomputed numbers on their plates; each digit tile is 0.62em wide for Parkinsans. Tally counts use the same face at 22px.
- **Body** (400, 15.5px, 1.55): answer text, kept to 68ch; quoted vendor sentences at 15px, 70ch.
- **Label** (700, 11.5 to 12px, 0.04 to 0.08em, uppercase): card heads, pane heads, panel labels, the method row label.
- **Status label** (700, 12px, 0.06em, uppercase): badges and chips; chips at 11px.
- **Path** (Mono 700, 15px): endpoint paths on drawer labels; inside a display line the path drops to 0.84em.

### Named Rules

**The Weight Carries Role Rule.** Heavy Parkinsans is for entries a reader scans to (findings, section heads, numerals); small Parkinsans capitals are for marks (status labels, labels). Body copy never uses Parkinsans, and entries never use the body face.

## Layout

The answer screen centres a 1280px column with 32px side padding. Under the header, the finding takes the left column and the tally card a 320px right column, separated by 56px. Below a cyanotype rule, two panes: the stack of drawer labels at 360px (sticky) and the answer cards in the remaining width, 56px apart. Drawer labels stack with a 14px gap, answer cards with 18px; card padding is 22px.

The start page runs on a twelve-column grid inside a 1440px container with a fluid gutter (clamp(16px, 3.4vw, 48px)) and 24px column gaps. The opening line spans eleven columns; the explanation takes columns one to five and the finding card columns seven to twelve. The drawer-front band runs full bleed in deep Prussian blue with three equal drawer fronts. Sections sit 112px apart.

At 900px and below, everything collapses to one column; the answer screen switches to two tabs (Answers, Your stack), the tally card is hidden, connectors are hidden, and drawer fronts become rows with the numeral plate left and its caption right. No layout scrolls horizontally at 390px.

### Theme system

`html[data-theme]` is set before first paint by an inline script: `?theme=cN` (or `?theme=N`) wins and is saved, then the saved choice, then `c1`. Theme 1 is the `:root` default in the token layer, so a page with no attribute renders theme 1; its arrangement, decoration, display face and radii are scoped to `:is(:root:not([data-theme]), :root[data-theme="c1"])`. Themes 2 to 5 (Broadsheet, Ledger, Civic form, Photocopy) are opt-in alternates; each defines all of its own colour, type and radius tokens and never inherits theme 1's look. These tokens belong to theme 1 only and no alternate reads them: `--field`, `--on-field`, `--on-field-muted`, `--frame`, `--rule-cyan`, `--stamp-stale` (Outdated), `--stamp-confirm` (Needs review), `--stamp-held` (Not stated). The CSS token names are kept as they were; only their values and these names in prose changed. Components read tokens only; a new colour or family is added as a token, never as a literal in a component rule.

### Frozen DOM contract

A demo recorder and the test suite bind to these hooks. Their ids, classes, attributes and nesting do not change:

- `#app` and its `aria-busy` attribute (true while the buyer report loads or recomputes).
- Answer cards `#q-Q03` and `#q-Q05`; `#review-Q05` (the Review the change button) and `#change-Q05` (its panel).
- `details.more` (the readings-to-review disclosure) and `.confirm-box` inside it.
- `#pages` (the vendor pages list).
- `#ep-api-crm-sync` and the `select` inside it (the endpoint feature picker).
- `#export-btn` and `#export-menu`.
- `#stats`, `.stat-board`, `.num-tile`, `.num-sep`, `.num-row` (numerals and their housing).
- `.catch-mark`, `.catch-text`, `.catch-phrase` (the Not true label on the finding card, the quoted sentence, its highlighted phrase).
- `.rule-draw` (the drawn rule).
- The theme radios `input[name="theme"]` with values `c1` to `c5`, and `#theme-select`.

### Named Rules

**The Restyle Within The Structure Rule.** Any visual change, in any theme, is made by tokens and CSS on the existing structure. Elements in the frozen contract are never renamed, re-nested, removed or replaced; a theme that needs a new look dresses the hook it is given. The display face is loaded with an `@import` in theme-c1.css so the pages' markup stays as it is.

## Elevation & Depth

Flat. Depth is material, not light: card stock sits on the blueprint field, the selected card goes from stock to fresh white, and a card pushed back darkens to the stock-back tone rather than fading. The only shadow-like values are a card's 1px bottom edge and frames drawn with zero-blur rings, which follow each element's rounded corners.

### Shadow Vocabulary
- **Card edge** (`box-shadow: 0 1px 0 rgba(0,0,0,.25)`): the bottom edge of every answer card and of the primary button on the field.
- **Cyanotype frame** (`box-shadow: 0 0 0 2px var(--frame)`): tally card, wordmark plate, toast. Numeral plates use 4px; drawer labels use a 1px hairline at 60% so the answers column leads.
- **Selected frame** (`box-shadow: 0 0 0 2px var(--act)`): the selected answer card and drawer label.
- **Outline pill** (`box-shadow: inset 0 0 0 1.5px var(--on-field-muted)`): secondary actions on the field.
- **Drawer front bevel** (`box-shadow: inset 0 0 0 1px rgba(0,0,0,.35), inset 0 2px 0 rgba(255,255,255,.07)`): the routed edge of a drawer front.

### Named Rules

**The Frame Not Shadow Rule.** Separation is a zero-blur ring or a 1px edge. Nothing floats on a blurred shadow, and there is no glow.

## Shapes

Rounded, as library index cards are: answer cards 20px, the finding card and guided-path list 22px, drawer fronts 24px, tally card and shelf lists 18px, numeral plates 16px, drawer labels and menus 14px, toast and theme select 12px, the wordmark plate 10px, status labels 8px, chips 6px, changed tags 5px, the command line 8px. Buttons and secondary actions are full pills. Lines are 1px hairlines on cards, 2px for ruled header lines and frames, 4px for numeral-plate frames and the double-rule Outdated label. Nothing is tilted: status labels on answer cards and the Not true count in the tally sit square. There is no drawer pull under the numeral plates.

## Components

### Buttons
Pills, set in the display face (Parkinsans 700, 0.01em).
- **Shape:** full pill (999px).
- **Primary:** card stock with ink text on the field (13px by 20px), with the card edge below; on a card (the finding card on the start page) it is Prussian blue with white text. Never red.
- **Hover / Focus:** primary on the field goes to fresh white, on a card to deep Prussian; focus is a 2px outline offset 2px in the context's focus colour (white on the field, navy on card).
- **Secondary:** an outlined pill, 1.5px on-field-muted ring, white text, a 12% white wash on hover. Standalone actions such as "Start here", "Open the app" and the trust-page draft are secondary pills, never underlined text; links inside running prose stay underlined.
- **Ghost:** 1px edge border, transparent ground, wash on hover; on the field the border and text are white and hover is a 12% white wash. Small ghost: 7px by 12px, 13px text.

### Status labels (badges and chips)
One grammar for every state; the frame form carries the state as much as the ink.
- **Not true:** filled signal red, white capitals. Carries the warning icon.
- **Outdated:** teal ink in a 4px double-rule frame.
- **Needs review:** navy ink in a 2px dashed frame.
- **Not stated:** grey ink in a thin 1px frame.
- **Verified:** a bare tick and word, no frame.
- **Fill:** Outdated, Needs review and Not stated carry a faint fill of their own ink (9%, 7%, 7%), so the set reads as one graded scale; the frame form still carries the state without colour.
- **Motion:** each label appears on its card once on load (scale from 1.35 to 1 with opacity, 0.34s, staggered 60ms per card), always square; static under reduced motion.

### Cards / Containers
- **Corner Style:** rounded, 20px.
- **Background:** index stock; fresh white when selected or outdated.
- **Shadow Strategy:** card edge only (see Elevation & Depth).
- **Border:** none; the head is divided from the body by a 2px ruling-cyan line that runs the card's full width, red on the card that is not true.
- **Internal Padding:** 20px 22px 24px; 16px 14px 32px on phones.

### Drawer labels (endpoints)
A white card with 14px corners held in a 1px cyanotype hairline. The endpoint path in bold mono, the vendor feature as a dotted-underlined picker, the finding, the status chips, and a quiet Re-check pill (wash fill, navy text, no outline). Selected: fresh white with a red frame. Pushed back: stock-back ground with a 45% cyanotype frame.

### Tally card
A filed card at top right of the answer screen in a cyanotype frame with 18px corners, its head in label capitals over a cyan rule, one line per state with a numeral; the Not true count sits in a red box with 7px corners.

### Inputs / Fields
- **Style:** fresh white, 1px edge border, 14px corners, 15px body face.
- **Focus:** 2px navy outline, offset 2px.
- **Endpoint picker:** a native select laid invisibly over the feature line, so the line itself is the control.

### Navigation
The header sits on the field with a hairline below. The wordmark is a Parkinsans 800 plate on card stock with 10px corners in a 2px cyanotype frame. Theme numbers sit in 8px rounded squares; the chosen one is filled pale cyan with dark ink. On phones the radios give way to a compact pill select drawn as a quiet outline on the field, so it never reads as a second wordmark. "Start here" and "Open the app" in the header are secondary pills. Mobile tabs are Parkinsans on the field with a 3px pale cyan underline on the active tab.

### Numeral plates and drawer fronts (signature)
On the start page, three drawer fronts in Prussian blue with 24px corners sit inside a full-bleed deep-Prussian band. Each holds a card-stock plate with 16px corners in a 4px cyanotype frame with the number in Parkinsans 800; the ratio slash is set in muted card ink. The caption sits 22px under the plate in white; there is no pull. On entry each number rises into its plate once (0.55s, 80ms stagger); static under reduced motion.

### Finding card (signature)
The start page's finding is a filed card on the field with 22px corners: the Not true label, a full-width red rule under it, the sentence with its key phrase underlit in pale red, and the primary button in Prussian blue.

## Do's and Don'ts

### Do:
- **Do** keep signal red (#B3202A) to Not true and its selected frame.
- **Do** give every card head a 2px ruling-cyan line, and switch it to red only on the card that is not true.
- **Do** frame labels in pale cyan with a zero-blur ring (2px, 4px on numeral plates).
- **Do** carry state in the status label's frame form (filled, double, dashed, thin, bare) so it reads without colour.
- **Do** round every card, label, plate and field, and make buttons pills.
- **Do** set anything on the field in the on-field tokens and anything on a card in the card tokens.
- **Do** push related-away cards back to stock-back (#E9E2D6) instead of lowering opacity.
- **Do** restyle within the frozen DOM contract; add colours and families as tokens.

### Don't:
- **Don't** add blueprint grids, texture images, glow, or blurred shadows; depth is material and frame.
- **Don't** tilt or rotate any status label, plate or card.
- **Don't** use red for Outdated, Needs review or Not stated, for buttons, or as decoration.
- **Don't** style a standalone action as underlined text; use a secondary pill.
- **Don't** set body copy in Parkinsans, or entries in the body face.
- **Don't** read theme 1 tokens (--field, --frame, --rule-cyan, the status inks) from an alternate theme.
- **Don't** rename, re-nest or remove an element in the frozen DOM contract.

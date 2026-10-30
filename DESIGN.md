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
  stamp-stale: "#5B3D94"
  stamp-confirm: "#2D3E66"
  stamp-held: "#5E5A55"
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
    fontFamily: "Archivo, Arial, system-ui, sans-serif"
    fontSize: "44px"
    fontWeight: 700
    lineHeight: 1.08
    letterSpacing: "-0.012em"
    fontVariation: "\"wdth\" 112"
  display-start:
    fontFamily: "Archivo, Arial, system-ui, sans-serif"
    fontSize: "clamp(30px, 3.3vw, 48px)"
    fontWeight: 700
    lineHeight: 1.1
    letterSpacing: "-0.012em"
    fontVariation: "\"wdth\" 108"
  headline:
    fontFamily: "Archivo, Arial, system-ui, sans-serif"
    fontSize: "30px"
    fontWeight: 700
    lineHeight: 1.1
    letterSpacing: "-0.01em"
    fontVariation: "\"wdth\" 112"
  title:
    fontFamily: "Archivo, Arial, system-ui, sans-serif"
    fontSize: "20px"
    fontWeight: 700
    lineHeight: 1.3
    letterSpacing: "-0.005em"
  numeral:
    fontFamily: "Archivo, Arial, system-ui, sans-serif"
    fontSize: "clamp(64px, 7.4vw, 112px)"
    fontWeight: 800
    lineHeight: 1
    letterSpacing: "0"
    fontFeature: "\"tnum\""
    fontVariation: "\"wdth\" 75"
  body:
    fontFamily: "Atkinson Hyperlegible Next, Atkinson Hyperlegible, system-ui, sans-serif"
    fontSize: "15.5px"
    fontWeight: 400
    lineHeight: 1.55
    letterSpacing: "0"
  label:
    fontFamily: "Archivo, Arial, system-ui, sans-serif"
    fontSize: "12px"
    fontWeight: 700
    lineHeight: 1.3
    letterSpacing: "0.08em"
    fontVariation: "\"wdth\" 75"
  stamp:
    fontFamily: "Archivo, Arial, system-ui, sans-serif"
    fontSize: "12.5px"
    fontWeight: 700
    lineHeight: 1
    letterSpacing: "0.07em"
    fontVariation: "\"wdth\" 75"
  path:
    fontFamily: "Atkinson Hyperlegible Mono, ui-monospace, SF Mono, Menlo, monospace"
    fontSize: "15px"
    fontWeight: 700
    lineHeight: 1.3
rounded:
  none: "0"
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
    backgroundColor: "{colors.signal-red}"
    textColor: "{colors.on-field}"
    rounded: "{rounded.none}"
    padding: "13px 18px"
  button-primary-hover:
    backgroundColor: "{colors.signal-red-deep}"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    padding: "7px 12px"
  button-ghost-hover:
    backgroundColor: "{colors.wash}"
  answer-card:
    backgroundColor: "{colors.card-stock}"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    padding: "20px 22px 24px"
  answer-card-selected:
    backgroundColor: "{colors.card-selected}"
  drawer-label:
    backgroundColor: "{colors.card-stock}"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    padding: "14px 16px 16px"
  stamp-not-true:
    backgroundColor: "{colors.signal-red}"
    textColor: "{colors.on-field}"
    typography: "{typography.stamp}"
    rounded: "{rounded.none}"
    padding: "5px 7px 4px"
  stamp-stale:
    backgroundColor: "transparent"
    textColor: "{colors.stamp-stale}"
    typography: "{typography.stamp}"
    rounded: "{rounded.none}"
    padding: "3px 6px 2px"
  stamp-confirm:
    backgroundColor: "transparent"
    textColor: "{colors.stamp-confirm}"
    typography: "{typography.stamp}"
    rounded: "{rounded.none}"
    padding: "5px 7px 4px"
  stamp-held:
    backgroundColor: "transparent"
    textColor: "{colors.stamp-held}"
    typography: "{typography.stamp}"
    rounded: "{rounded.none}"
    padding: "6px 8px 5px"
  tally-card:
    backgroundColor: "{colors.card-stock}"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    padding: "16px 22px 18px"
  numeral-plate:
    backgroundColor: "{colors.card-stock}"
    textColor: "{colors.ink}"
    typography: "{typography.numeral}"
    rounded: "{rounded.none}"
  drawer-front:
    backgroundColor: "{colors.field}"
    textColor: "{colors.on-field}"
    rounded: "{rounded.none}"
    padding: "36px 20px 30px"
---

# Design System: Owin

## Overview

**Creative North Star: "The Card Catalogue"**

Owin files vendor evidence the way a library files its holdings. The page ground is a flat field of Prussian blue, the ground of a cyanotype. Every endpoint is a drawer label held in a pale cyanotype frame; every questionnaire answer is a ruled index card; the state of an answer is a rubber stamp inked onto that card; the note on the card is the vendor's own sentence. The world is daylight, paper and blueprint ink, read at a desk.

Density is that of a working catalogue: many cards, each short, each ruled. Hierarchy comes from material (blueprint field, card, cyanotype frame, ink) rather than from tint or elevation. Red is reserved for what is not true and for its fix, so a red mark always means "act here". The system rejects the dark developer dashboard with a single neon accent, blueprint grid texture, glow, and rounded soft cards. The field is all cool, so nothing on the page is warm except the signal.

This file records theme 1 ("Catalogue"), the default look. Four alternate themes ship as opt-in and are described under Layout only as far as the theme system binds them.

**Key Characteristics:**
- Flat Prussian-blue field carrying white text; white card stock carrying dark ink.
- Pale cyanotype frames (2px ring, 4px on numeral plates) around labels, never a fill behind body text.
- A 2px cyan ruled header line under every card head; red replaces it on the one card that is not true.
- State stamps whose frame form carries meaning as much as their ink: filled box, double rule, dashed, thin rule, bare tick.
- Archivo in three widths: expanded for entries, normal for titles, condensed for stamp and label caps.
- Square corners everywhere. No shadow beyond a card's 1px bottom edge.

## Colors

A cool blueprint-and-paper palette: a Prussian-blue field, pale cyanotype frames and white card stock, with one hot signal and three stamp inks. Signal red is the only warm colour on the page.

### Primary
- **Not True Red** (signal-red): the Not true stamp, the selected card's frame and header rule, the primary button, the struck-through wrong text in the fix panel, and the failing cell in the per-endpoint row. Nothing else.
- **Pressed Red** (signal-red-deep): hover state of the primary button only.

### Secondary
- **Cyanotype Line** (frame): label frames around the wordmark, drawer labels, tally card, numeral plates and the export menu; drawer pulls under numerals; the selected theme number; the active mobile tab underline; the rule under the finding. Decorative framing only, never text on the field.

### Tertiary
- **Date-Stamp Violet** (stamp-stale): the Stale stamp and the "changed" tag.
- **Confirm Navy** (stamp-confirm): the Confirm stamp, source links on cards, the confirm box's dashed frame, and the "to confirm" disclosure. Doubles as the card-context focus ring.
- **Pencil Grey** (stamp-held): the Held stamp, drawn as a thin 1px rule.
- **Ruling Cyan** (rule-cyan): the 2px ruled header line of every card, the fix panel's top rule, and source-link underlines.

### Neutral
- **Prussian Blue** (field): the page ground and the drawer fronts.
- **Deep Prussian** (field-deep): the full-bleed band that houses the drawer fronts on the start page.
- **Index Stock** (card-stock): answer cards, drawer labels, tally, menus, shelf-list cards.
- **Fresh Card** (card-selected): the selected or stale card, fields, the command line.
- **Pushed-Back Stock** (stock-back): a card related away from the current focus or recomputing; it darkens instead of fading.
- **Ruling Wash** (wash): hover and chip wash on cards.
- **Highlighted Row** (hit): the table row that answers the question.
- **Card Ink** (ink), **Card Muted** (ink-muted), **Quoted Ink** (ink-cite), **Control Edge** (edge): text, captions, quoted vendor sentences and control borders on card stock.
- **On Prussian** (on-field) and **On Prussian Muted** (on-field-muted): text set directly on the field.
- **Pale Signal** (link-signal-on-field): the connector line from the failing endpoint to its answer, drawn over the field, and the warning icon in the finding line.

### Named Rules

**The Red Means Act Rule.** Signal red marks only Not true and its fix. Stale, Confirm and Held each have their own ink; none borrows red.

**The Two Contexts Rule.** Anything set on the field reads the on-field tokens; anything filed on a card reads the card tokens. A component never mixes the two, and switching context is done by re-pointing --ink, --muted, --cite, --edge, --line and --focus, not by new colours.

## Typography

**Display Font:** Archivo (with Arial, system-ui), variable width 62 to 125.
**Body Font:** Atkinson Hyperlegible Next (with Atkinson Hyperlegible, system-ui).
**Label/Mono Font:** Atkinson Hyperlegible Mono for endpoint paths, question numbers in rows, and commands.

**Character:** A catalogue's typeset entries over a reading face built for legibility. Width does the work: expanded Archivo for main entries, condensed Archivo caps for anything that behaves like a stamp or a drawer label.

### Hierarchy
- **Display** (700, 44px, 1.08, width 112): the finding on the answer screen, set straight on the field. 27px at 900px and below.
- **Display, start page** (700, clamp(30px, 3.3vw, 48px), 1.1, width 108): the opening line on the start page, across eleven of twelve columns.
- **Headline** (700, 30px, 1.1, width 112): section heads on the start page. 24px on phones.
- **Title** (700, 20px, 1.3): the question on each answer card; 22px for guided-path titles. 18px on phones.
- **Numeral** (800, clamp(64px, 7.4vw, 112px), 1, width 75, tabular): the three recomputed numbers on their plates. Tally counts use the same face at 22px.
- **Body** (400, 15.5px, 1.55): answer text, kept to 68ch; quoted vendor sentences at 15px, 70ch.
- **Label** (700, 12px, 0.08em, uppercase, width 75): card heads, pane heads, panel labels, the method row label.
- **Stamp** (700, 12.5px, 0.07em, uppercase, width 75): badges and chips; chips at 11.5px.
- **Path** (Mono 700, 15px): endpoint paths on drawer labels; inside a display line the path drops to 0.84em.

### Named Rules

**The Width Carries Role Rule.** Expanded Archivo is for entries a reader scans to (findings, section heads); condensed Archivo caps are for marks (stamps, labels, numerals). Body copy never uses Archivo.

## Layout

The answer screen centres a 1280px column with 32px side padding. Under the header, the finding takes the left column and the tally card a 320px right column, separated by 56px. Below a cyanotype rule, two panes: the stack of drawer labels at 360px (sticky) and the answer cards in the remaining width, 56px apart. Drawer labels stack with a 14px gap, answer cards with 18px; card padding is 22px.

The start page runs on a twelve-column grid inside a 1440px container with a fluid gutter (clamp(16px, 3.4vw, 48px)) and 24px column gaps. The opening line spans eleven columns; the explanation takes columns one to five and the catch card columns seven to twelve. The drawer-front band runs full bleed in deep Prussian blue with three equal drawer fronts. Sections sit 112px apart.

At 900px and below, everything collapses to one column; the answer screen switches to two tabs (Answers, Your stack), the tally card is hidden, connectors are hidden, and drawer fronts become rows with the numeral plate left and its caption right. No layout scrolls horizontally at 390px.

### Theme system

`html[data-theme]` is set before first paint by an inline script: `?theme=cN` (or `?theme=N`) wins and is saved, then the saved choice, then `c1`. Theme 1 is the `:root` default in the token layer, so a page with no attribute renders theme 1; its arrangement and decoration are scoped to `:is(:root:not([data-theme]), :root[data-theme="c1"])`. Themes 2 to 5 (Broadsheet, Ledger, Civic form, Photocopy) are opt-in alternates; each defines all of its own colour and type tokens and never inherits theme 1's look. These tokens belong to theme 1 only and no alternate reads them: `--field`, `--on-field`, `--on-field-muted`, `--frame`, `--rule-cyan`, `--stamp-stale`, `--stamp-confirm`, `--stamp-held`. Components read tokens only; a new colour or family is added as a token, never as a literal in a component rule.

### Frozen DOM contract

A demo recorder and the test suite bind to these hooks. Their ids, classes, attributes and nesting do not change:

- `#app` and its `aria-busy` attribute (true while the pack loads or recomputes).
- Answer cards `#q-Q03` and `#q-Q05`; `#review-Q05` (the Review the change button) and `#change-Q05` (its panel).
- `details.more` (the readings-to-confirm disclosure) and `.confirm-box` inside it.
- `#pages` (the vendor pages list).
- `#ep-api-crm-sync` and the `select` inside it (the endpoint feature picker).
- `#export-btn` and `#export-menu`.
- `#stats`, `.stat-board`, `.num-tile`, `.num-sep`, `.num-row` (numerals and their housing).
- `.catch-mark`, `.catch-text`, `.catch-phrase` (the Not true mark, the quoted sentence, its highlighted phrase).
- `.rule-draw` (the drawn rule).
- The theme radios `input[name="theme"]` with values `c1` to `c5`, and `#theme-select`.

### Named Rules

**The Restyle Within The Structure Rule.** Any visual change, in any theme, is made by tokens and CSS on the existing structure. Elements in the frozen contract are never renamed, re-nested, removed or replaced; a theme that needs a new look dresses the hook it is given.

## Elevation & Depth

Flat. Depth is material, not light: card stock sits on the blueprint field, the selected card goes from stock to fresh white, and a card pushed back darkens to the stock-back tone rather than fading. The only shadow-like values are a card's 1px bottom edge and frames drawn with zero-blur rings.

### Shadow Vocabulary
- **Card edge** (`box-shadow: 0 1px 0 rgba(0,0,0,.25)`): the bottom edge of every answer card.
- **Cyanotype frame** (`box-shadow: 0 0 0 2px var(--frame)`): drawer labels, tally card, wordmark plate, toast. Numeral plates use 4px.
- **Selected frame** (`box-shadow: 0 0 0 2px var(--act)`): the selected answer card and drawer label.
- **Drawer front bevel** (`box-shadow: inset 0 0 0 1px rgba(0,0,0,.35), inset 0 2px 0 rgba(255,255,255,.07)`): the routed edge of a drawer front.

### Named Rules

**The Frame Not Shadow Rule.** Separation is a zero-blur ring or a 1px edge. Nothing floats on a blurred shadow, and there is no glow.

## Shapes

Square corners throughout (0 radius on buttons, cards, stamps, fields and numeral plates). Lines are 1px hairlines on cards, 2px for ruled header lines and frames, 4px for numeral-plate frames and the double-rule Stale stamp. Stamps on answer cards and the Not true count in the tally sit at a -2deg tilt, as if inked by hand. The one curved form is the drawer pull under each numeral plate: a 4px cyanotype U (72px by 16px, 36px bottom radius).

## Components

### Buttons
Square, set in the label face (Archivo 700, 0.01em).
- **Shape:** square corners (0).
- **Primary:** signal red with white text, 13px by 18px. On the field it gains a 2px white ring so it reads as a card-stock button pressed into the field.
- **Hover / Focus:** primary darkens to pressed red; focus is a 2px outline offset 2px in the context's focus colour (white on the field, navy on card).
- **Ghost:** 1px edge border, transparent ground, wash on hover; on the field the border and text are white and hover is a 12% white wash. Small ghost: 7px by 12px, 13px text.
- **Text link action:** the draft link beside the primary button is underlined in pale cyan on the field.

### Stamps (badges and chips)
One grammar for every state; the frame form carries the state as much as the ink.
- **Not true:** filled signal red, white condensed caps. Carries the warning icon.
- **Stale:** violet ink in a 4px double-rule frame.
- **Confirm:** navy ink in a 2px dashed frame.
- **Held:** grey ink in a thin 1px frame.
- **Still true:** a bare tick and word, no frame.
- **Motion:** each stamp inks onto its card once on load (scale from 1.35 and -6deg, settle at -2deg, 0.34s, staggered 60ms per card); static under reduced motion.

### Cards / Containers
- **Corner Style:** square (0).
- **Background:** index stock; fresh white when selected or stale.
- **Shadow Strategy:** card edge only (see Elevation & Depth).
- **Border:** none; the head is divided from the body by a 2px ruling-cyan line that runs the card's full width, red on the card that is not true.
- **Internal Padding:** 20px 22px 24px; 16px 14px 32px on phones.

### Drawer labels (endpoints)
A white card held in a 2px cyanotype frame. The endpoint path in bold mono, the vendor feature as a dotted-underlined picker, the finding, the state chips, and a ghost Re-check button. Selected: fresh white with a red frame. Pushed back: stock-back ground with a 45% cyanotype frame.

### Tally card
A filed card at top right of the answer screen in a cyanotype frame, its head in label caps over a cyan rule, one line per state with a condensed numeral; the Not true count sits in a tilted red box.

### Inputs / Fields
- **Style:** fresh white, 1px edge border, square, 15px body face.
- **Focus:** 2px navy outline, offset 2px.
- **Endpoint picker:** a native select laid invisibly over the feature line, so the line itself is the control.

### Navigation
The header sits on the field with a hairline below. The wordmark is an expanded Archivo 800 plate on card stock in a 2px cyanotype frame. Theme numbers are condensed digits; the chosen one is filled pale cyan with dark ink. On phones the radios give way to a compact select framed in pale cyan. Mobile tabs are condensed Archivo on the field with a 3px pale cyan underline on the active tab.

### Numeral plates and drawer fronts (signature)
On the start page, three drawer fronts in Prussian blue sit inside a full-bleed deep-Prussian band. Each holds a card-stock plate in a 4px cyanotype frame with the number in condensed Archivo 800; the ratio slash is set in muted card ink. A pale cyan pull hangs below and the caption sits under it in white. On entry each number rises into its plate once (0.55s, 80ms stagger); static under reduced motion.

### Catch card (signature)
The start page's catch is a filed card on the field: the tilted Not true stamp, a full-width red rule under it, the sentence with its key phrase underlit in pale red, and the primary button.

## Do's and Don'ts

### Do:
- **Do** keep signal red (#B3202A) to Not true, its selected frame, and its fix.
- **Do** give every card head a 2px ruling-cyan line, and switch it to red only on the card that is not true.
- **Do** frame labels in pale cyan with a zero-blur ring (2px, 4px on numeral plates).
- **Do** carry state in the stamp's frame form (filled, double, dashed, thin, bare) so it reads without colour.
- **Do** set anything on the field in the on-field tokens and anything on a card in the card tokens.
- **Do** push related-away cards back to stock-back (#E9E2D6) instead of lowering opacity.
- **Do** restyle within the frozen DOM contract; add colours and families as tokens.

### Don't:
- **Don't** add blueprint grids, texture images, glow, or blurred shadows; depth is material and frame.
- **Don't** round corners on any card, button, stamp or plate.
- **Don't** use red for Stale, Confirm or Held, or as decoration.
- **Don't** set body copy in Archivo, or entries in the body face.
- **Don't** read theme 1 tokens (--field, --frame, --rule-cyan, the stamp inks) from an alternate theme.
- **Don't** rename, re-nest or remove an element in the frozen DOM contract.

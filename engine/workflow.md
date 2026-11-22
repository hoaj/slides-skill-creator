# The Engine's workflow

Follow this file from top to bottom for every deck. `<skill>` is the folder that holds the Slides
skill's `SKILL.md`. Every tool runs through one command:

```sh
python3 <skill>/engine/deck.py <command>
```

Generated files (the template, the deck, exports, extracted slides) go in the user's project,
never in the skill folder.

## What must always hold

- **One self-contained HTML file.** Fonts, CSS, JavaScript and images are inlined. It opens
  without a server or a network.
- **The message comes first.** Build nothing until the user has approved the slide outline and
  the key terms. A Playbook cannot change this.
- **On brand.** Use the Brand pack's themes, fonts, logo and icons, and obey its `brand.md`.
- **A fixed 1920x1080 stage** that scales to the window. Size content in px or `--fs-*` tokens,
  never `vw`. Switch slides with `.active` and `.visible`, never `display:none`.
- **Semantic colour tokens.** Use `--text`, `--muted`, `--accent`, `--on-accent` and `--surface`
  so a slide stays readable when its theme changes. Body copy stays on `--text`; the accent is
  for headings, numbers and graphics.
- **One frame per deck.** The `.deck-frame` block appears once in `#deckStage`.

## 1. Identify the task

| The user wants | Do this |
|---|---|
| A new deck | Go to step 2. |
| A `.pptx` turned into a deck | Run `deck.py extract-pptx in.pptx <project folder>`. Use the text as raw material for the Interview, not as a layout to copy. Then go to step 2. |
| To edit a deck built here | Run `deck.py inspect deck.html`. It prints the deck's brand, Deck type and key terms. Keep them, follow that Deck type's content rules from `deck.py interview`, and go to step 6. |

If anything fails to run, `deck.py doctor` says what is missing.

## 2. Select the brand

Run `deck.py brands`.

- With one brand, use it.
- With several, infer the brand from the conversation and the listed aliases. When it is unclear,
  ask. The wrong brand means the wrong deck.

Use that slug as `--brand <slug>` from here on.

## 3. Propose at most one Deck type

Run `deck.py deck-types --brand <slug>`.

If one Deck type matches the request, propose it in one sentence and let the user confirm it or
pick none. A deck has at most one. If none matches, or the pack has none, continue without one
and do not mention Deck types.

## 4. Run the Interview

```sh
python3 <skill>/engine/deck.py interview --brand <slug> [--deck-type <id>]
```

This prints the one final list: the Engine's questions with the brand's Playbook and the Deck type
already applied. Do not apply Playbook files by hand. Then:

- **Facts are yours to find; decisions are the user's.** First read what the user pointed at
  (files, a `.pptx`, links, the conversation) and answer factual questions from it.
- **Ask one question at a time**, with the question tool when the coding agent has one. Otherwise
  number the options so the user can answer "2".
- **Recommend an answer** with each question, worded so "yes" accepts it, and always leave room
  for another answer.
- **Do not ask** a question marked `fixed` (use its answer) or one the material already answers.
  Language and density are each asked once, here and nowhere else.
- If the user's request already answers everything, read it back in one sentence and ask whether
  to go on to the outline.
- Tell the user about any `Warnings` the command prints that affect this deck.

For photos the user supplies: check that they survive a 16:9 crop, round them with `--radius`,
and inline small ones as data URIs. Never insert stock-photo URLs. Without photos, use the pack's
backgrounds, panels and typography.

## 5. Get the outline and key terms approved

These three steps are protected. No Playbook or Deck type can remove them.

**Outline.** Write one line per slide that names its role in the argument, not just its topic. A
Deck type's outline proposal is a starting point the user must still approve.

```text
Slide 1: Cover: set the context
Slide 2: Situation: anchor the audience in what they know
Slide 3: Complication: show the cost of doing nothing
Slide 4: Recommendation: the decision we ask for
```

**Key terms.** Below the outline, list the terms that recur (usually 4 to 10): the options, the
metrics, the roles and the main pieces of work.

```text
Key terms
- Buy the product: the vendor's product as it ships. Avoid: vendor option, off the shelf
- Active customers: customers who logged in during the last 30 days. Avoid: users, subscribers
```

- Use one name per concept, and put the other names you met under `Avoid:`.
- Define what the term is in one sentence, not why it is good.
- When the source uses one word for two things, give each its own term.
- Prefer the name the audience already uses.

**Approval.** End with: "Does this structure serve the message? Are these the names the audience
knows? Any slides to add, remove or reorder before I build?" **Build nothing until the user
approves.**

## 6. Build

Read `<skill>/engine/docs/html-template.md` for the template's skeleton, then write the template
in the user's project. Read `docs/slide-templates.md` for layouts, `docs/widgets.md` before
adding a widget and `docs/roadmaps.md` for roadmaps. The Interview's `Layouts` section lists the
layout ids, with the Deck type's recommended ones first. A pack's own layouts are in
`brands/<slug>/layouts/<id>.html`: copy that `<section>` into the template.

```sh
python3 <skill>/engine/deck.py build --brand <slug> [--deck-type <id>] template.html deck.html --open
```

- `--deck-type` records the Deck type in the deck as `data-deck-type`, so a later edit follows the
  same recipe. Later builds keep it. `--deck-type none` clears it. If the id no longer exists,
  the build warns and keeps the deck as it is.
- `--open` reloads the tab that already shows the deck, on the same slide.
- Write the approved key terms into the template as a comment right after `<body>`:

  ```html
  <!-- key-terms
  - Buy the product: the vendor's product as it ships. Avoid: vendor option, off the shelf
  -->
  ```

- Give every `<section>` a `data-title` and a `data-theme` the pack defines, and `data-layout`
  with its layout id. Mark covers, sections and closings with `data-kind`.
- Set `data-deck-id` (stable) and a fresh `data-deck-rev` on `#deckStage` every time you
  regenerate, plus `data-classification`, `data-header` and `lang` from the Interview.
- Name every concept exactly as the key terms do, on every slide, in titles, cards, labels,
  tables, `data-title` and alt text. A slide reused from another deck keeps that deck's words
  until you change them.
- A headline states the slide's point. Do not count the items below it, and use a kicker only
  when it adds what the headline does not say.

**Fix every line the build prints** before showing the deck: `key terms:`, `headline count:`,
`kicker:`, `number format:` and `markup:`. Keep a flagged number only when it is the point.

## 7. Verify and deliver

Check the deck in a real browser before handing it over:

1. It opens with no console errors and in the brand's font.
2. At 1280x720 nothing overflows, is cropped or overlaps. At phone width the stage scales down.
3. Every slide can be reached with the keyboard, and build steps and at least one widget work.
4. Edit mode opens. The Background picker lists this brand's themes.
5. The frame is on every slide: logo, date in the right language, classification, header if set
   and a page number.
6. The text uses the key terms, and the closing slide names things as the opening slides did.

Overflow is clipped silently, so measure it. Run this in the page, for example through the coding
agent's browser tool. It should report nothing:

```js
window.deck._pdfPrep();
const spread = v => Math.max(...v) - Math.min(...v);
document.querySelectorAll('.slide').forEach((s, i) => {
  const c = s.querySelector('.slide-content');
  if (c && c.scrollHeight > c.clientHeight + 1) console.warn('Slide', i + 1, 'overflows by', c.scrollHeight - c.clientHeight, 'px');
  s.querySelectorAll('.card-row').forEach(row => {
    const cards = [...row.children], tops = cards.map(k => k.getBoundingClientRect());
    if (spread(tops.map(b => b.height)) > 2) console.warn('Slide', i + 1, ': cards in a row differ in height');
    const parts = Math.min(...cards.map(k => k.children.length));
    for (let p = 0; p < parts; p++)
      if (spread(cards.map(k => k.children[p].getBoundingClientRect().top)) > 2) { console.warn('Slide', i + 1, ': card part', p + 1, 'starts at different heights'); break; }
  });
});
window.deck._teardownPDF();
```

Then deliver. **The HTML deck is the deliverable.** Tell the user about its toolbar:

- **Present now**, **Edit presentation** (all text in place, icons by clicking them, then Save).
- **Export to PDF.** In the print dialog: Save as PDF, Margins None, Scale 100%, Background
  graphics on. A wrong setting crops every slide.
- **Export to PPTX**, which needs no tooling. For batch work, or to write installable fonts:

  ```sh
  python3 <skill>/engine/deck.py export-pptx deck.html deck.pptx --brand <slug> --fonts ./ttf
  ```

  Without the brand's font installed, the live text in PowerPoint falls back to a system font.
  The HTML stays the original: re-export after edits rather than editing both.

Remove working files that are not deliverables, such as extracted slides, before you finish.

## For maintainers

`deck.py check` validates the Brand packs, `deck.py sample --brand <slug>` builds the neutral Sample
deck, and `deck.py compare <old-engine> <new-engine> --brand <slug>` compares it on two Engines.
The Brand pack and Playbook formats are in `docs/brand-pack.md`.

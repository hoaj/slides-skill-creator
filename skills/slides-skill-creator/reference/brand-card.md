# The brand card and the Brand pack

The brand card is the one place the maintainer sees everything a Brand pack will hold, with the
source of each value, before anything is written. The Brand pack is written from the approved
card. The format of every pack file is in `<gen>/../../engine/docs/brand-pack.md`.

## Read the material

| Material | How |
|---|---|
| PowerPoint template (`.pptx`, `.potx`) | `gen.py extract-pptx <file> --out <work>/extract`: theme colours, theme fonts, embedded font names, slide size, layout names, the colours used most, and the master and layout images copied to `<work>/extract/media/` |
| Guidelines PDF or website | Read it yourself: colour names and values, typefaces, logo rules, tone, layout rules, what to avoid |
| Logo | Use an SVG. A PNG, JPEG or EMF can only be a reference: ask for the SVG |
| Font files (`.woff2`, `.ttf`, `.otf`, `.woff`) | The `fonts` tool reads family, weight and style from the files in step 4 |
| Icon set (a folder of SVGs) | The `icons` tool bundles it in step 4. Ask for its licence |

Prefer an exact value from a file over one read from a picture. When two sources disagree,
show both on the card and ask.

## What the card holds

Every row has a value and a source: a file and where in it (`template.pptx theme1 accent1`,
`guidelines.pdf p. 4`), **proposed** for your own judgement, or **asked** for the user's answer.

| Section | Values |
|---|---|
| Identity | name, slug (`a-z`, `0-9`, `-`; never `plain`), aliases the user says when they mean this brand |
| Palette | each brand colour with a short lowercase name and its hex value |
| Themes | for each theme: label, `--bg`, `--text`, `--muted`, `--accent`, `--on-accent`, `--surface`, whether it is a hero theme (covers, dividers), and for a gradient theme the gradient and its solid base colour |
| Type | the display and body families, and the font files, or the system stack when there are none |
| Logo | the SVG file, and whether it follows the text colour (`currentColor`) |
| Icons | the icon set and its licence, or none |
| Classification | the labels a deck may carry (`none` for no label) and the default |
| Numbers | thousands and decimal separators, when not `,` and `.` |
| Design rules | what goes into `brand.md`: when to use each theme, colour rules, what to avoid |
| Own layouts | a layout the brand needs that the Engine's base layouts lack, or none |

**Propose the themes yourself.** A good set has a light default for content slides, a quiet
light alternative, and one or two dark or colour hero themes for covers and section dividers.
Every theme needs `--text`, `--muted` and `--on-accent` at 4.5:1 or better; the `guard` tool
measures this in step 4.

**Ask only for what no source gives**, one question at a time: a missing SVG logo, font files for
a font that is only named, the classification labels, the aliases. Name what you will use if the
user has no answer (system fonts, no icons).

Show the card as one Markdown table per section, then ask the user to approve it or name what to
change. On a change, show the new card. The card is approved when the user says so about the
card as it now is.

## Write the Brand pack

From the approved card, in this order. Every tool prints JSON; read it before the next step.

1. **Start the pack:**
   ```sh
   python3 <gen>/tools/gen.py pack-init --out <work>/packs/<slug> --slug <slug> --name "<Name>" --alias "<alias>"
   ```
   It copies the Engine's `plain` pack with the colour prefix renamed to `--<slug>-`. Everything
   in it is a placeholder for you to replace.
2. **`tokens.css`.** In `:root`, one `--<slug>-<name>` per palette colour, the font stacks, the
   series colours for charts (six that read on the light themes), and the `--ui-*` colours of the
   browser toolbar. Keep every other `:root` token the plain pack has: the build stops on a
   missing one. Then one `[data-theme="<value>"]` rule per theme with `--bg`, `--surface`,
   `--text`, `--muted`, `--accent`, `--on-accent` and `--hairline`. The default theme's selector
   also names `.deck-stage:not([data-theme])`.
3. **Gradients.** A gradient theme sets `--bg` to its solid base colour in `tokens.css`, sets
   `"bloom": true` in `brand.json`, and draws the gradient in `assets/gradients.css` on
   `.slide[data-theme="<value>"]::before`, scaled by `--bloom-amount`.
4. **`brand.json`.** The themes with `value`, `label`, `hero` and `bloom`, `defaultTheme`,
   `classifications`, `defaultClassification`, `aliases`, and `numberFormat` when needed.
5. **The logo** goes to `assets/logo.svg`. Set its fills to `currentColor` when it follows the
   theme's text colour.
6. **Fonts**, when there are font files:
   ```sh
   python3 <gen>/tools/gen.py fonts --pack <pack> --src <files>... --display "<family>" --body "<family>"
   ```
   Copy a licence that came with the fonts to `licenses/`.
7. **Icons**, when there is a set:
   ```sh
   python3 <gen>/tools/gen.py icons --pack <pack> --src <folder of SVGs>
   ```
   Copy its licence to `licenses/` and name the source in `licenses/README.md`.
8. **Contrast data:**
   ```sh
   python3 <gen>/tools/gen.py guard --pack <pack>
   ```
   It writes `guard` and prints each theme's ratios for `body`, `muted` and `on-accent`. When it
   asks for `--base`, give the solid colour under that theme's gradient. Check its proposed
   `neutrals` and `vivids` against the card: a neutral is a colour for text and quiet
   backgrounds, a vivid an accent for headings, numbers and graphics. Correct them with
   `--neutral` or `--vivid`. A pair below 4.5:1 goes back to the user: change the colour, or add
   a `contrastExceptions` entry with the reason they give (for example, the pair is used only at
   34px or larger).
9. **`brand.md`**: the brand's design rules for the agent building decks, under `## Look`,
   `## Themes` (a table: theme, use it for), `## Design rules`, `## Classification`, and
   `## Contrast exception` or `## Own layout` when the pack has one.
10. **Own layouts** and the **Playbook**, when the card or the interview has them, in `layouts/`
    and `playbook/` as `engine/docs/brand-pack.md` describes.
11. **Validate:**
    ```sh
    python3 <gen>/tools/gen.py pack-check --pack <pack>
    ```
    Fix every error. A missing `pptxLead` warning is expected until the pack is calibrated.

When the pack is already in a Slides skill, run steps 6 to 8 on `<skill>/brands/<slug>` and
validate with `python3 <skill>/engine/deck.py check --brand <slug>`.

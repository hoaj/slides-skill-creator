# PowerPoint export: how it works, and what bites

`deck.py export-pptx` turns a built deck into a `.pptx` that keeps the design **and** keeps
the text editable. Read this before changing the export or debugging one that looks wrong.

```sh
python3 <skill>/engine/deck.py export-pptx deck.html deck.pptx
python3 <skill>/engine/deck.py export-pptx deck.html deck.pptx --brand <slug> --fonts ./ttf
```

## Two ways to export, one implementation

| | Toolbar **Export to PPTX** | `deck.py export-pptx` |
|---|---|---|
| Runs | in the deck, no tooling | Python + Playwright |
| Background | the slide serialised into an SVG `<foreignObject>` and drawn to a canvas | Chrome's own screenshot |
| Text layer | identical: both call `DeckPPTX.plan()` | identical |
| Needs | nothing (PptxGenJS is inlined) | `playwright python-pptx`, plus `fonttools brotli` for packs with font files |

`engine/runtime/pptx-export.js` is the **single source of truth for the measurement**.
`deck.py export-pptx` calls `DeckPPTX.plan()` in the page rather than carrying its own
copy, and injects the module into decks built before it existed. Change the measurement
in one place or the two exports drift apart.

## The approach

The deck keeps its animations; only the *capture* is frozen. `_pdfPrep()` resolves
build-steps and snaps widgets to their final values, and the rasteriser restates the "no
transitions, no animations" rule inside the `<foreignObject>`, because that rule lives on
`body.deck-pdf-export` and there is no `<body>` in there to carry it.

Each slide becomes two layers:

1. **A full-bleed PNG** of the slide rendered by Chrome **with the editable text made
   invisible** (`color:transparent`, which keeps the boxes, borders and shadows the text
   sits in; `visibility:hidden` would take the element's background with it). Gradients,
   SVG icons, chart widgets and the frame are therefore *exact*, because they are the
   browser's own pixels.
2. **One native PowerPoint text box per styled run**, positioned from the browser's own
   measurements. So the text is still text.

What counts as editable text is not a new rule. It is the controller's
`Deck.editableLeaves` walk over `.slide-content` minus `Deck.EDIT_DENY`. Icons, counter
values, chart labels and `[data-noedit]` stay in the background image, the same things the
inline editor refuses to touch.

The geometry is exact, not fitted: a 1920×1080 stage is PowerPoint's standard 16:9 slide
(960×540pt) at **exactly 2 px per pt**, so positions convert with no rounding.

## The things that bite

Each of these came from exporting a real deck and comparing it back. They are all handled
in the code; this is why it looks the way it does.

| Symptom | Cause |
|---|---|
| A shrink-to-fit pill re-wraps: `Live` becomes `Liv`/`e` | PowerPoint measures the same font wider than Chrome, and such boxes are sized to exactly their text. Carry Chrome's line breaks over as hard breaks and leave PowerPoint's own wrapping **off**. |
| Long headlines drift right, cumulatively | Chrome kerns from the font's GPOS table. PowerPoint does not, and **ignores the DrawingML `kern` attribute** that should ask it to. Correct each run's width back to the browser's with tracking. |
| Uppercase labels ship lowercase **and** stretched | The line text comes from raw DOM text nodes, but the geometry is of the *rendered* text. Replay `text-transform` when building runs. |
| `Q1` renders as `Q 1` | CSS letter-spacing is added after **every** character, the last included, so a measured width holds *n* units of it while only *n−1* gaps are visible. Take those out before spreading the kerning difference. |
| An agenda numeral is the wrong size and colour, and blown apart (`0    1`) | **An element is not a styling unit.** An `<li>` can carry a body label and a large accent `<span>01</span>`. Style per *run*, and correct each run's tracking at its own size. |
| Text is the wrong colour versus the presented deck | `contrast-guard.js` processes only the **active** slide. In an export every slide is laid out at once, so `_pdfPrep()` guards every slide. |
| Large type sits a little high | PowerPoint does not lay text out on the CSS line box, and the error grows with `line-height`. The Brand pack's `pptxLead` corrects it. Without one, the export applies no correction and warns. |
| Everything is offset, more the further down the slide | On screen the stage is CSS-transformed to fit the window, so every rect comes back scaled. Divide by `1920 / slideRect.width`. |
| Text sits high by half the leading correction | The box is centre-anchored, so its **height** must be computed before the top is shifted. |
| A `→` in a heading turns up in a serif face | The brand face has no glyph for it. The browser substitutes silently from the CSS fallback, but a PowerPoint run pinned to the brand font makes PowerPoint choose its own substitute. The build records which characters the pack's faces cannot draw (`pptxMissingGlyphs`, exact, from their cmaps) and those runs get the CSS fallback family. Do **not** detect coverage by comparing advances in the browser: two fonts can share one. |
| Text renders in a default face, and centred runs shift | The run's weight had no entry in the pack's `pptxFonts`, and a CSS stack can name a face the pack does not bundle. Resolve to the **nearest weight the pack ships**, never to the CSS family. |
| A run of several styles stacks vertically instead of flowing | Runs are per-line *and* per-style. Group into lines first, then into contiguous chunks: runs that touch flow as runs in one paragraph, runs with a gap between them (a flex gap) get a box each. |
| A vertical axis label comes out as a column of upright letters, reversed | Compose the element's CSS transforms (plus the quarter turn of a vertical `writing-mode`) into an angle. At 90/270 emit one run in the element's *unrotated* frame, centred where the text sits, and put the angle on the shape. PowerPoint rotates about the centre. |
| A bar chart exports with every bar the same height | Widgets were not at their end state, or a CSS collision defeated the end-state rule. An unscoped `.bar { align-self:center; height:40px }` beats `.chart-bars .bar` unless the widget states those properties. Scope layout CSS that reuses a widget class name. |
| The fallback for a missing glyph is itself a font without it | The next family in the CSS stack can be another of the pack's own faces. Skip the pack's faces alongside the generic keywords when choosing a fallback. |
| A centred line drifts a couple of points | Centre and right alignment are only safe when a line is ONE run. Anchor a multi-run line at its measured left edge. |
| The same deck exports differently from different window sizes | Slide content sized in `vw`. `vw` is the window, not the stage, and the stage already scales itself. Size slide content in px or the `--fs-*` tokens. |

## Do not judge fidelity by pixel-diffing the .pptx

Text is almost entirely glyph edges, so antialiasing dominates a pixel score: a slide of
large type can read *worse* than a dense one at identical accuracy.

Compare the **text layer** instead. PowerPoint's own PDF export carries every span's text,
bbox, baseline `origin`, size and colour, and the browser measurements are in the same
coordinate space. Compare **baselines**, not bounding boxes: a PDF span's bbox top is the
ink top of the glyphs actually in it, so `Th` and `eee` differ at the same position.

Two artefacts of that comparison are not export faults:

- PyMuPDF inserts a space wherever it judges the gap between two glyphs wide, so a small
  tracked run can come back with an extra space. Check the geometry before believing it.
- PowerPoint splits a run at a glyph the font cannot draw, so one run becomes two spans.
  Match on glyphs with whitespace squashed.

## Vertical placement is calibrated per font

PowerPoint does not lay text out on the CSS line box, and the size of the disagreement
depends on the *face's own metrics*. So the correction is calibrated per Brand pack and
stored in `brand.json` as `pptxLead: [fs, lh, c]`:

```text
shift = fs × natural line height × font size − lh × line height − c
```

The natural line height comes from the pack's own font files at build time. `pptxLead` is
optional. A pack without it, or with system fonts only, gets no vertical correction, and
the export warns. Making the calibration is the Generator's job.

Traps when deriving it:

- **Chrome's em box excludes `hhea.lineGap`.** Its text rect is ascent plus descent only.
  Counting the gap puts every line out by a size-dependent amount.
- Chrome rounds `getBoundingClientRect()` **heights** to whole pixels while positions stay
  fractional. Any model leaning on the measured height inherits that quantisation.
- Compare **baselines** (`span["origin"]`), never bbox tops.
- A calibration deck must space its probe boxes generously, and should vary line-height
  independently of font size, or the fit cannot separate the two terms.

Two ideas that were tested and do **not** work:

- Setting the box height to `lines × line-spacing` so the centre anchor has nothing to
  centre. It makes placement much worse.
- The DrawingML `kern` attribute to make PowerPoint kern like the browser. It is ignored.

**Known gap:** glyph coverage is unioned across a pack's faces and frozen at build time. A
character present in Regular and missing from Light would pass, and a character typed in
through inline editing is not covered.

## Driving PowerPoint for verification

Automating PowerPoint over AppleScript is the least reliable step, and its failures say
nothing about the export.

- A modal **"PowerPoint can't read `<file>`"** can be intermittent and not a property of
  the file. Retry from a fully quit PowerPoint before blaming the export.
- **-9074** is its sandbox refusing to write. It will not save into a temp directory
  (`/var/folders/…`) even though it opens from one. A plain folder under `~/Desktop` works.
- **-1712** is the AppleScript interface wedged, usually while a modal dialog is up.
- Prefer a polite `quit`. If you must kill it, match the full name
  (`pkill -f "Microsoft PowerPoint"`) so you do not also kill other Office apps.

## Fonts: the one thing that makes an export look wrong elsewhere

PowerPoint renders the text layer with the **installed** font. `--fonts <dir>` writes
installable TTFs converted from the pack's woff2. Without the font installed, the
background stays perfect and the live text falls back to a system face, which also shifts
centre-aligned runs. Install the font before judging an export.

PowerPoint has only bold and italic flags, so a weight that is neither 400 nor 700 must be
addressed by its **own family name**. The build reads this from the font files rather than
a hand-kept table, because the CSS family name is not necessarily the font's real one.

## Known limits

- **Occlusion is not modelled.** Text hidden behind a later opaque element is removed from
  the background and drawn on top as a text box, so it reappears. In practice this only
  shows up when a deck's markup is already broken.
- **Mixed-style elements split into a box per run**, because only the measured rect can
  reproduce a flex gap or a mid-line size change. Those runs do not reflow together when
  edited. Single-style elements stay one box and reflow normally.
- Tracking is corrected as **uniform** per run, so a run's width lands exactly while
  individual pairs stay off by a fraction of a point.
- `--image-only` skips the text layer entirely (command only; the button always writes it).
- The button inlines PptxGenJS (about 480KB). That buys an export that works offline with
  no tooling.
- The button rasterises through `<foreignObject>`, which cannot draw cross-origin images.
  A deck that references an external image would export with that image missing.

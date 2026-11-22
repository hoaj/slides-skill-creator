# Single-file assembly guide

## How to assemble

A deck inlines the Engine's runtime and **one Brand pack** into one `<style>` block in `<head>` and one `<script>` block at the end of `<body>`. The pack supplies the colour tokens, logo and, when it has them, fonts, gradients and icons. `deck.py build` generates the `window.DeckBrand` config from its `brand.json`, so the same runtime renders any brand.

**Use `deck.py build`. Do not paste by hand.** Author your slides and per-deck `<style>` in a template that holds the marker comments in the skeleton below, then run:

```bash
# <skill> is the folder that holds this Slides skill. The template and the deck live in
# the user's project, never in the skill folder.
python3 <skill>/engine/deck.py build --brand <slug> template.html deck.html --open
```

`--open` reloads the browser tab that already shows the deck (it keeps its slide) and opens a new one only the first time. The `<!-- key-terms -->` comment after `<body>` holds the approved key terms; the build warns about each slide that uses a name listed under `Avoid:`.

`--brand` selects the pack in `<skill>/brands/`. The build replaces each marker with the real file contents and stops with a precise error when a marker, a required pack file or a required field is missing. Optional pack files that are absent (`fonts.css`, `assets/gradients.css`, `icon-library.js`) expand to nothing.

Order inside `<style>`:

1. the pack's `fonts.css`, when it has one
2. the pack's `tokens.css`
3. the pack's `assets/gradients.css`, when it has one
4. `engine/runtime/viewport-base.css`
5. `engine/runtime/widgets.css`
6. `engine/runtime/chrome.css`
7. per-deck slide layout styles, authored for this deck

Order inside `<script>`, at the **end of `<body>`**:

1. the `window.DeckBrand` config; it must come **first**, because the controller and contrast guard read it
2. `engine/runtime/widgets.js`
3. `engine/runtime/deck-controller.js`
4. `engine/runtime/contrast-guard.js`; it must come **after** the controller, because it wraps `deck.go`
5. the pack's `icon-library.js`, when it has one
6. `engine/runtime/edit-icons.js`, after the controller, because it reads `window.deck`
7. `engine/runtime/pptxgen.bundle.js`
8. `engine/runtime/pptx-export.js`

## Skeleton

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>DECK TITLE</title>
<style>
/*__FONTS__*/        /* the pack's fonts.css (@font-face blocks), when present */
/*__TOKENS__*/       /* the pack's tokens.css */
/*__GRADIENTS__*/    /* the pack's assets/gradients.css, when present */
/*__VIEWPORT__*/     /* engine/runtime/viewport-base.css */
/*__WIDGETS_CSS__*/  /* engine/runtime/widgets.css */
/*__CHROME__*/       /* engine/runtime/chrome.css */
/* Per-deck slide layout styles go here (authored by you) */
</style>
</head>
<body>
<!-- key-terms
- TERM: what it is, in one sentence. Avoid: other name, another name
-->
  <div class="deck-viewport">
    <main class="deck-stage" id="deckStage" data-deck-id="UNIQUE-DECK-ID" data-deck-rev="CONTENT-REV"
          data-theme="THEME" data-classification="LABEL" data-header="" lang="en">
      <!-- Persistent frame: one layer, identical on every slide. The controller fills
           the date (today, per lang), classification, header and page number. -->
      <div class="deck-frame">
        <span class="deck-logo"><!--__LOGO__--></span>
        <span class="deck-date"></span>
        <span class="deck-pagenum"></span>
        <span class="deck-classification"></span>
        <span class="deck-header"></span>
      </div>
      <!-- slides from slide-templates.md, authored at 1920×1080 -->
      <section class="slide active" data-theme="THEME" data-kind="cover" data-title="Cover">
        <div class="slide-content"><!-- cover title top-left --></div>
      </section>
      <!-- more slides -->
    </main>
  </div>
<script>
/*__BRAND_CONFIG__*/    /* window.DeckBrand, generated from brand.json; must be first */
/*__WIDGETS_JS__*/      /* engine/runtime/widgets.js */
/*__CONTROLLER_JS__*/   /* engine/runtime/deck-controller.js */
/*__CONTRAST_JS__*/     /* engine/runtime/contrast-guard.js (after the controller) */
/*__ICONS_JS__*/        /* the pack's icon-library.js, when present */
/*__EDIT_ICONS_JS__*/   /* engine/runtime/edit-icons.js (after the controller) */
/*__PPTXGEN_JS__*/      /* engine/runtime/pptxgen.bundle.js, vendored PptxGenJS */
/*__PPTX_EXPORT_JS__*/  /* engine/runtime/pptx-export.js, powers the Export to PPTX button */
</script>
</body>
</html>
```

## Rules

Every deck is **one `.html` file**. The only allowed external files are large user photos in a sibling `assets/` folder; small photos are base64-embedded in the HTML.

The `id="deckStage"` attribute on the stage element is **required** by the controller. Do not rename or omit it.

The `data-theme` attribute on the stage sets the deck-wide colour theme. It must be one of the pack's themes, and the build stops on any other value.

## Deck attributes and the frame

`#deckStage` carries the attributes that drive the persistent frame:

- **`data-deck-id`**: a unique id baked in at generation (a title slug plus a short random suffix, like `intro-a1b9`). It keys this deck's `localStorage` autosave, so two decks with the same title never overwrite each other's edits. Keep it **stable** across regenerations of the same deck. The storage key starts with `<slug>-deck`.
- **Slide position**: the deck writes the current slide to the URL as `#/N` (1-based, like the page number) and to `localStorage` under its own key, so a reload or a rebuild reopens the slide the viewer was on, and a `…/deck.html#/5` link opens slide 5. The position is kept apart from the edit draft, so it survives a new `data-deck-rev`.
- **`data-deck-rev`**: a content stamp that **changes every time the deck is regenerated** (a content hash or timestamp). On load, if it differs from the one a saved draft was based on, the deck discards that stale draft and shows the freshly built file. A coding agent that regenerates a deck must write a fresh value.
- **`data-theme`**: the colour theme. Values come from the pack's `brand.json` and fill the edit panel's Background picker. Set it on `#deckStage` as the deck default and on any `.slide` to mix backgrounds. Themes with `bloom: true` in the manifest show a per-slide **Bloom** slider, which sets `--bloom-amount` on the slide.
- **`data-classification`**: the classification badge in the frame. Valid values are the labels in the pack's `classifications`. The value `none` hides the badge. Without this attribute the deck uses the pack's `defaultClassification`, and the build stops on a label the pack does not define.
- **`data-header`**: an optional header shown at the top of every slide; hidden when empty.
- **`lang`**: drives the auto-formatted date in `.deck-date`. Use `en` (English) or `da` (Danish).

The `.deck-frame` block appears **once** per deck, immediately inside `#deckStage` before the first `<section>`. Keep the `<!--__LOGO__-->` marker inside `.deck-logo`: the build inlines the pack's logo SVG there and strips its XML prolog. A logo that uses `currentColor` inherits `--text` and themes correctly on every background.

The page number shows on every slide (1…N). `data-kind` (`cover`, `section`, `closing`) is an optional semantic hint on a `<section>` and does not change numbering.

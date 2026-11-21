# Roadmaps

Three reusable, **brand-agnostic** roadmap layouts for the Engine. They are built on
semantic tokens and the Brand pack's `--series-*` chart palette, so they theme to **any**
brand automatically.

| Layout | Use it for |
|--------|------------|
| **A · Quarter columns** | Strategic overview — initiatives grouped by quarter (or any phase), with status, plus a "cross-cutting" row for always-on work |
| **B · Dependency map** | Grouping work by dependency type (none / brand / external), with effort ribbons and a legend |
| **C · Gantt timeline** | Week- or month-level delivery plan — labelled rows with category-coloured bars placed on a time grid, milestone markers |

**How to use:** paste the **Roadmap toolkit CSS** below into your per-deck `<style>`,
then drop in the markup for the layout(s) you need. Roadmaps read best on a **light
theme** of the active pack; set it on the `<section>`.

**Conventions baked in:**
- **Category colours** map to `--series-1 … --series-6` (the brand's chart palette), via `--s1 … --s6` modifier classes. Pick a consistent meaning per deck (e.g. s1 = internal/owned, s2 = integration, s3 = brand-dependent, s4 = external) and reuse it across all three layouts + the legend.
- **Pick series that are visually distinct for the active brand.** Check the pack's `brand.md` for what each series means. A series can be a pale neutral, which is fine for a large Gantt fill but weak for a small dot or 4px border. For thin accents prefer the pack's stronger series.
- **Accent** (`--accent`) marks "in progress / now". **Muted** marks "planned / not committed".
- **Bar-label contrast** is handled by the runtime contrast guard — it composites each bar's fill and flips the label to a readable colour, so labels stay legible on any brand's series colours. Author bar text normally.
- **Keep the Gantt bar rules scoped under `.gantt`.** `.bar` is also the Engine's
  bar-chart class; an unscoped `.bar { height:40px }` flattens every bar chart in the
  deck to a uniform height, with no error, in the browser and in every export.
- All cards use a two-level surface hierarchy that works on any light theme: containers on `--surface`, inner cards on `--bg` with a `--hairline` border.

---

## Roadmap toolkit CSS

```css
/* === ROADMAP TOOLKIT (brand-agnostic) — paste into the per-deck <style> ===
   Semantic tokens + --series-* so it themes to any brand. Use on a light theme.

   The Gantt bar rules are scoped under .gantt ON PURPOSE. `.bar` is also the
   Engine's bar-chart class (widgets.css: .chart-bars .bar), and an unscoped
   `.bar { align-self:center; height:40px }` silently flattens every bar chart in
   the deck to 40px — with no error, in the browser and in any export. Keep the
   scope if you edit these. */

/* Page header */
.rm-head { display:flex; flex-direction:column; gap:8px; }
.rm-head .kicker { font:700 22px/1 var(--font-display); color:var(--accent); letter-spacing:.06em; text-transform:uppercase; }
.rm-head h1 { font:700 var(--fs-h1)/1 var(--font-display); color:var(--text); margin:0; }
.rm-stack { display:flex; flex-direction:column; gap:20px; flex:1; min-height:0; }

/* Status / category pill (· = a coloured dot before the label) */
.pill { display:inline-flex; align-items:center; gap:8px; padding:6px 14px; border-radius:999px;
  font:700 15px/1 var(--font-display); letter-spacing:.06em; text-transform:uppercase; white-space:nowrap;
  background:color-mix(in srgb, var(--accent) 14%, transparent); color:var(--text); }
.pill::before { content:''; width:8px; height:8px; border-radius:50%; background:var(--accent); flex:none; }
.pill--muted { background:color-mix(in srgb, var(--text) 7%, transparent); }
.pill--muted::before { background:var(--muted); }
.pill--s1{background:color-mix(in srgb,var(--series-1) 16%,transparent)} .pill--s1::before{background:var(--series-1)}
.pill--s2{background:color-mix(in srgb,var(--series-2) 16%,transparent)} .pill--s2::before{background:var(--series-2)}
.pill--s3{background:color-mix(in srgb,var(--series-3) 16%,transparent)} .pill--s3::before{background:var(--series-3)}
.pill--s4{background:color-mix(in srgb,var(--series-4) 16%,transparent)} .pill--s4::before{background:var(--series-4)}

/* --- Layout A: quarter columns --- */
.rm-cols { display:grid; grid-template-columns:repeat(var(--rm-n,3),1fr); gap:24px; flex:1; min-height:0; }
.q-col { display:flex; flex-direction:column; gap:18px; padding:24px; background:var(--surface); border-radius:var(--radius); min-height:0; }
.q-col__head { display:flex; align-items:center; justify-content:space-between; gap:12px; }
.q-col__title { font:700 28px/1 var(--font-display); color:var(--text); }
.q-col__list { display:flex; flex-direction:column; gap:12px; }
.init { padding:14px 18px; background:var(--bg); border:1px solid var(--hairline); border-left:4px solid var(--accent); border-radius:12px; display:flex; flex-direction:column; gap:4px; }
.init__title { font:700 20px/1.2 var(--font-display); color:var(--text); }
.init__desc  { font:400 16px/1.35 var(--font-body); color:var(--muted); }
.init--muted { border-left-color:var(--muted); }
.init--s1{border-left-color:var(--series-1)} .init--s2{border-left-color:var(--series-2)}
.init--s3{border-left-color:var(--series-3)} .init--s4{border-left-color:var(--series-4)}
.open-slot { padding:10px 16px; border:1.5px dashed var(--hairline); border-radius:12px; display:flex; align-items:center; gap:12px; color:var(--muted); }
.open-slot__plus { width:24px; height:24px; border-radius:50%; display:inline-flex; align-items:center; justify-content:center; background:color-mix(in srgb,var(--accent) 20%,transparent); color:var(--text); font:700 18px/1 var(--font-display); flex:none; }
.open-slot__t { font:700 15px/1.2 var(--font-display); color:var(--text); }
/* cross-cutting strip spanning all columns */
.cross-box { background:var(--surface); border:1px solid var(--hairline); border-radius:18px; padding:16px 18px; display:flex; flex-direction:column; gap:10px; flex:none; }
.cross-box__head { display:flex; align-items:center; justify-content:space-between; gap:12px; }
.cross-box__title { font:700 20px/1 var(--font-display); color:var(--text); }
.cross-rows { display:flex; flex-direction:column; gap:6px; }
.cross-row { display:grid; grid-template-columns:repeat(var(--rm-n,3),1fr); column-gap:24px; }

/* --- Layout B: dependency map --- */
.rm-grid { display:grid; grid-template-columns:repeat(var(--rm-n,3),1fr); gap:22px; flex:1; min-height:0; }
.dep-block { display:flex; flex-direction:column; gap:14px; padding:22px; border-radius:var(--radius); background:var(--surface); }
.dep-block__head { display:flex; flex-direction:column; gap:8px; }
.dep-block__head-row { display:flex; align-items:center; justify-content:space-between; gap:10px; }
.dep-block__title { font:700 24px/1 var(--font-display); color:var(--text); }
.dep-block__sub   { font:400 15px/1.3 var(--font-body); color:var(--muted); }
.dep-cards { display:flex; flex-direction:column; gap:12px; }
.dep-card { background:var(--bg); border:1px solid var(--hairline); border-radius:14px; padding:14px 16px; display:flex; flex-direction:column; gap:6px; }
.dep-card--s2 { border-left:4px solid var(--series-2); }
.dep-card--s3 { border-left:4px solid var(--series-3); }
.dep-card--s4 { border-left:4px solid var(--series-4); }
.dep-card__title { font:700 19px/1.2 var(--font-display); color:var(--text); }
.dep-card__desc  { font:400 15px/1.35 var(--font-body); color:var(--muted); }
.dep-card__note { margin-top:6px; padding:8px 12px; background:color-mix(in srgb,var(--series-4) 14%,transparent); border-radius:8px; font:700 14px/1.25 var(--font-display); color:var(--text); }
/* effort / phase ribbon inside a card */
.ribbon { display:flex; flex-direction:column; gap:8px; margin-top:6px; }
.ribbon__seg { display:flex; flex-direction:column; gap:2px; padding:8px 12px; border-radius:10px; background:color-mix(in srgb,var(--series-1) 16%,transparent); }
.ribbon__seg--heavy { background:color-mix(in srgb,var(--series-3) 18%,transparent); }
.ribbon__weeks { font:700 13px/1 var(--font-display); letter-spacing:.06em; text-transform:uppercase; color:var(--text); }
.ribbon__label { font:400 14px/1.3 var(--font-body); color:var(--text); }

/* shared legend */
.legend { display:flex; gap:18px; padding:12px 18px; background:var(--surface); border-radius:14px; border:1px solid var(--hairline); flex-wrap:wrap; flex:none; }
.legend__item { display:flex; align-items:center; gap:8px; font:400 14px/1 var(--font-body); color:var(--text); }
.legend__sw { width:14px; height:14px; border-radius:4px; flex:none; }
.legend__sw--s1{background:var(--series-1)} .legend__sw--s2{background:var(--series-2)}
.legend__sw--s3{background:var(--series-3)} .legend__sw--s4{background:var(--series-4)}
.legend__sw--muted{background:color-mix(in srgb,var(--text) 18%,transparent)}

/* --- Layout C: Gantt timeline ---
   --rm-cols = number of time columns (weeks/months). --rm-gutter = label width.
   Place period bars, ticks, and bars with inline style="grid-column:<start>/span <n>". */
.gantt { position:relative; background:var(--surface); border:1px solid var(--hairline); border-radius:20px; padding:22px 26px 18px; flex:1; display:flex; flex-direction:column; gap:12px; min-height:0; }
.gantt__axis { display:grid; grid-template-columns:var(--rm-gutter,200px) 1fr; gap:16px; align-items:end; }
.gantt__periods { display:grid; grid-template-columns:repeat(var(--rm-cols,12),1fr); }
.gantt__periods > div { font:700 14px/1 var(--font-display); color:var(--accent); letter-spacing:.08em; text-transform:uppercase; padding:4px 0 6px; border-top:2px solid var(--accent); }
.gantt__ticks { display:grid; grid-template-columns:repeat(var(--rm-cols,12),1fr); border-bottom:1px solid var(--hairline); padding-bottom:5px; }
.gantt__tick { font:700 11px/1 var(--font-display); color:var(--muted); letter-spacing:.04em; }
.gantt__rows { display:flex; flex-direction:column; gap:8px; flex:1; min-height:0; }
.gantt__row { display:grid; grid-template-columns:var(--rm-gutter,200px) 1fr; gap:16px; align-items:center; min-height:56px; }
.gantt__label { display:flex; flex-direction:column; gap:2px; }
.gantt__label-t { font:700 17px/1.15 var(--font-display); color:var(--text); }
.gantt__label-s { font:400 12px/1.25 var(--font-body); color:var(--muted); }
.gantt__track { position:relative; height:48px; background:color-mix(in srgb,var(--text) 5%,transparent); border-radius:8px; display:grid; grid-template-columns:repeat(var(--rm-cols,12),1fr); }
.gantt .bar { align-self:center; height:40px; border-radius:8px; display:flex; flex-direction:column; align-items:center; justify-content:center; padding:4px 10px; font:700 12px/1.15 var(--font-display); text-align:center; color:var(--on-accent); background:var(--series-1); }
.gantt .bar--s2{background:var(--series-2)} .gantt .bar--s3{background:var(--series-3)} .gantt .bar--s4{background:var(--series-4)}
.gantt .bar--milestone { border:2.5px solid var(--text); }   /* go-live / decision point */
.gantt .bar__sub { display:block; font-weight:400; font-size:11px; }
```

---

## Layout A — Quarter columns

`--rm-n` sets the number of columns (default 3). Status: use `pill--accent`-style (the plain `.pill` = accent/now), `.pill--muted` = planned, or `.pill--sN` for a category. Initiative emphasis via `.init--muted` / `.init--sN` (left border).

```html
<section class="slide active" data-theme="white" data-title="Roadmap 2026">
  <div class="slide-content rm-stack">
    <div class="rm-head reveal">
      <span class="kicker">Strategy · 2026</span>
      <h1>Quarterly roadmap</h1>
    </div>
    <div class="rm-cols reveal" style="--rm-n:3">
      <div class="q-col">
        <div class="q-col__head"><div class="q-col__title">Q2</div><span class="pill">In progress</span></div>
        <div class="q-col__list">
          <div class="init"><div class="init__title">Initiative one</div><div class="init__desc">One line on what it delivers.</div></div>
          <div class="init"><div class="init__title">Initiative two</div><div class="init__desc">One line on what it delivers.</div></div>
        </div>
      </div>
      <div class="q-col">
        <div class="q-col__head"><div class="q-col__title">Q3</div><span class="pill pill--muted">Planned</span></div>
        <div class="q-col__list">
          <div class="init init--muted"><div class="init__title">Planned initiative</div><div class="init__desc">Short description.</div></div>
          <div class="open-slot"><span class="open-slot__plus">+</span><span class="open-slot__t">Room for intake</span></div>
        </div>
      </div>
      <div class="q-col">
        <div class="q-col__head"><div class="q-col__title">Q4</div><span class="pill pill--muted">Not committed</span></div>
        <div class="q-col__list">
          <div class="init init--muted"><div class="init__title">Candidate initiative</div><div class="init__desc">Short description.</div></div>
        </div>
      </div>
    </div>
    <!-- optional cross-cutting strip spanning all columns -->
    <div class="cross-box reveal" style="--rm-n:3">
      <div class="cross-box__head"><div class="cross-box__title">Cross-cutting</div><span class="pill pill--s1">Ongoing</span></div>
      <div class="cross-rows">
        <div class="cross-row"><div class="init init--s1" style="grid-column:2 / span 2"><div class="init__title">Always-on workstream</div><div class="init__desc">Spans Q3–Q4.</div></div></div>
      </div>
    </div>
  </div>
</section>
```

---

## Layout B — Dependency map

Group work by dependency type. Tint the block + cards with a category (`--sN`); use `.ribbon` for effort/phase, `.dep-card__note` for blockers. Close with a `.legend`.

```html
<section class="slide" data-theme="white" data-title="Dependencies">
  <div class="slide-content rm-stack">
    <div class="rm-head reveal"><span class="kicker">Strategy · 2026</span><h1>Dependency map</h1></div>
    <div class="rm-grid reveal" style="--rm-n:3">

      <div class="dep-block">
        <div class="dep-block__head">
          <div class="dep-block__head-row"><div class="dep-block__title">No dependencies</div><span class="pill">Owned</span></div>
          <div class="dep-block__sub">Delivered without external input.</div>
        </div>
        <div class="dep-cards">
          <div class="dep-card"><div class="dep-card__title">Item</div><div class="dep-card__desc">What it is.</div></div>
        </div>
      </div>

      <div class="dep-block">
        <div class="dep-block__head">
          <div class="dep-block__head-row"><div class="dep-block__title">Brand-dependent</div><span class="pill pill--s3">Needs brand</span></div>
          <div class="dep-block__sub">Requires time per brand.</div>
        </div>
        <div class="dep-cards">
          <div class="dep-card dep-card--s3">
            <div class="dep-card__title">Item with phases</div><div class="dep-card__desc">Landed brand by brand.</div>
            <div class="ribbon">
              <div class="ribbon__seg"><div class="ribbon__weeks">W33–W35 · Light</div><div class="ribbon__label">1 day — input + validation</div></div>
              <div class="ribbon__seg ribbon__seg--heavy"><div class="ribbon__weeks">W36–W41 · Heavy</div><div class="ribbon__label">1 week — implementation + prod validation</div></div>
            </div>
          </div>
        </div>
      </div>

      <div class="dep-block">
        <div class="dep-block__head">
          <div class="dep-block__head-row"><div class="dep-block__title">External</div><span class="pill pill--s4">External</span></div>
          <div class="dep-block__sub">Needs external prerequisites.</div>
        </div>
        <div class="dep-cards">
          <div class="dep-card dep-card--s4">
            <div class="dep-card__title">Item</div><div class="dep-card__desc">Cross-team platform work.</div>
            <div class="dep-card__note">Requires budget for a separate subscription</div>
          </div>
        </div>
      </div>

    </div>
    <div class="legend reveal">
      <div class="legend__item"><span class="legend__sw legend__sw--muted"></span>No dependencies</div>
      <div class="legend__item"><span class="legend__sw legend__sw--s3"></span>Brand-dependent</div>
      <div class="legend__item"><span class="legend__sw legend__sw--s4"></span>External</div>
    </div>
  </div>
</section>
```

---

## Layout C — Gantt timeline

A CSS-grid Gantt. Set `--rm-cols` (number of time columns) and `--rm-gutter` (label width) on the `.gantt`. Then place period headers, ticks, and bars on the grid with inline `style="grid-column:<start> / span <n>"` (columns are 1-indexed). Use `.bar--sN` for category and `.bar--milestone` for a go-live/decision point. Bar labels stay legible automatically (contrast guard).

```html
<section class="slide" data-theme="white" data-title="Delivery roadmap">
  <div class="slide-content rm-stack">
    <div class="rm-head reveal"><span class="kicker">Strategy · 2026</span><h1>Delivery roadmap</h1></div>
    <!-- 12 columns = 12 months; gutter 200px -->
    <div class="gantt reveal" style="--rm-cols:12; --rm-gutter:200px">

      <div class="gantt__axis">
        <div></div>
        <div>
          <div class="gantt__periods">
            <div style="grid-column:1 / span 3">Q1</div>
            <div style="grid-column:4 / span 3">Q2</div>
            <div style="grid-column:7 / span 3">Q3</div>
            <div style="grid-column:10 / span 3">Q4</div>
          </div>
          <div class="gantt__ticks">
            <div class="gantt__tick" style="grid-column:1">Jan</div>
            <div class="gantt__tick" style="grid-column:4">Apr</div>
            <div class="gantt__tick" style="grid-column:7">Jul</div>
            <div class="gantt__tick" style="grid-column:10">Oct</div>
          </div>
        </div>
      </div>

      <div class="gantt__rows">
        <div class="gantt__row">
          <div class="gantt__label"><span class="gantt__label-t">Workstream one</span><span class="gantt__label-s">Owner · note</span></div>
          <div class="gantt__track">
            <div class="bar" style="grid-column:1 / span 5">Discovery → build</div>
          </div>
        </div>
        <div class="gantt__row">
          <div class="gantt__label"><span class="gantt__label-t">Workstream two</span><span class="gantt__label-s">Owner · note</span></div>
          <div class="gantt__track">
            <div class="bar bar--s2" style="grid-column:4 / span 4">Integration</div>
            <div class="bar bar--milestone" style="grid-column:8 / span 1">Go-live</div>
          </div>
        </div>
        <div class="gantt__row">
          <div class="gantt__label"><span class="gantt__label-t">Workstream three</span><span class="gantt__label-s">Owner · note</span></div>
          <div class="gantt__track">
            <div class="bar bar--s3" style="grid-column:7 / span 6">Rollout<span class="bar__sub">brand by brand</span></div>
          </div>
        </div>
      </div>

      <div class="legend" style="margin-top:auto">
        <div class="legend__item"><span class="legend__sw legend__sw--s1"></span>Internal</div>
        <div class="legend__item"><span class="legend__sw legend__sw--s2"></span>Integration</div>
        <div class="legend__item"><span class="legend__sw legend__sw--s3"></span>Rollout</div>
      </div>

    </div>
  </div>
</section>
```

**Tips**
- Keep ≤ 6–7 Gantt rows per slide; split long programmes across two slides.
- For week-level plans use `--rm-cols:` = number of weeks shown and label every other tick (`grid-column:1`, `3`, `5`, …).
- A bar spanning the full width = an always-on workstream; a 1-column `.bar--milestone` = a dated milestone.
- Don't add `data-keep-color` to bars — the contrast guard needs to adjust their labels per brand.

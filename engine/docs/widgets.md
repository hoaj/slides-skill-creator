# Interactive Widget Usage Guide

Widgets animate automatically when their slide becomes active. Charts and counters **re-animate each time their slide becomes active** — keep to a handful of animated widgets per slide to avoid visual overload.

> **Use the provided widget markup exactly as shown — do not reimplement charts/counters/toggles from scratch.** They rely on non-obvious CSS the Engine already handles. For example, a bar chart's percentage-height fills only work because `.chart-bars` gives each `.bar` a *stretched, definite-height* track (`align-items:stretch`); a hand-rolled flex column with `align-items:flex-end` collapses the fills to zero height and renders **no bars, with no error**. Copy the contract markup below verbatim and only change the data values/labels.
>
> **Never put `.reveal` and `data-step` on the same element.** They conflict: `.reveal` fades the element to full opacity on slide entry, while `data-step` keeps it dimmed until stepped — the two fight and the element behaves oddly. Use `.reveal` for entrance animation **or** `data-step` for click-to-reveal, not both on one node.

---

## 1. Data Viz

Use for results, metrics, and KPIs. All data-viz widgets animate on slide-advance automatically — no extra JS wiring needed.

### Bar Chart

**When to use:** Compare discrete values side by side (e.g. score by segment, monthly volume).

**Markup contract:**

```html
<div class="chart-bars">
  <div class="bar" data-value="N" data-max="N" style="--bar-color:var(--series-1)">
    <span class="value">label</span>
    <div class="fill"></div>
    <span class="label">caption</span>
  </div>
</div>
```

The `.fill` element animates its height to `data-value / data-max × 100 %`. Include one `.bar` child per data point; `--bar-color` accepts any CSS color or token.

**Example — three-bar chart:**

```html
<div class="chart-bars">
  <div class="bar" data-value="72" data-max="100" style="--bar-color:var(--series-1)">
    <span class="value">72</span>
    <div class="fill"></div>
    <span class="label">Q1</span>
  </div>
  <div class="bar" data-value="85" data-max="100" style="--bar-color:var(--series-2)">
    <span class="value">85</span>
    <div class="fill"></div>
    <span class="label">Q2</span>
  </div>
  <div class="bar" data-value="91" data-max="100" style="--bar-color:var(--series-3)">
    <span class="value">91</span>
    <div class="fill"></div>
    <span class="label">Q3</span>
  </div>
</div>
```

---

### Donut Chart

**When to use:** Show a single percentage or part-of-whole figure (e.g. market share, completion rate).

**Markup contract:**

```html
<div class="chart-donut" data-percent="N"><span class="pct">N%</span></div>
```

The donut arc fills to `data-percent` (0–100). Place the matching percentage label inside `.pct`.

**Example — 68% completion:**

```html
<div class="chart-donut" data-percent="68">
  <span class="pct">68%</span>
</div>
```

---

### Counter / Animated Stat

**When to use:** Highlight a single impressive number that should count up on entry (e.g. "4.2M users", "99.8% uptime").

**Markup contract:**

```html
<span class="counter-stat" data-to="N" data-decimals="0" data-suffix="%">0</span>
```

The element counts up from `0` to `data-to` over ~1.1 s. `data-decimals` (optional, default `0`) controls decimal places; `data-suffix` (optional) is appended after the number. Set the initial text content to `0`.

**Example — animated score:**

```html
<span class="counter-stat" data-to="4.8" data-decimals="1" data-suffix=" / 5">0</span>
```

---

## 2. Toggle / Scenario Switcher

**When to use:** Let the audience flip between two or more scenarios live mid-slide without advancing (e.g. "Before / After", "Plan A / Plan B").

**Markup contract:**

```html
<div class="toggle-group" role="tablist">
  <button role="tab" aria-selected="true"  aria-controls="PANEL-A-ID">Label A</button>
  <button role="tab" aria-selected="false" aria-controls="PANEL-B-ID">Label B</button>
</div>

<div class="toggle-panel active" id="PANEL-A-ID">
  <!-- content for scenario A -->
</div>
<div class="toggle-panel" id="PANEL-B-ID">
  <!-- content for scenario B -->
</div>
```

Exactly one button starts with `aria-selected="true"` and its corresponding panel starts with class `active`. Clicking a tab shows its panel and hides all others within the same slide. No additional JS wiring is needed.

**Example — Before / After:**

```html
<div class="toggle-group" role="tablist">
  <button role="tab" aria-selected="true"  aria-controls="before-panel">Before</button>
  <button role="tab" aria-selected="false" aria-controls="after-panel">After</button>
</div>

<div class="toggle-panel active" id="before-panel">
  <p>Old process: <strong>12 steps</strong>, done by hand</p>
</div>
<div class="toggle-panel" id="after-panel">
  <p>New process: <strong>3 steps</strong>, mostly automatic</p>
</div>
```

---

## 3. Click-to-Reveal / Build Steps

**When to use:** Progressively disclose bullet points, diagram layers, or any content one item at a time as you press Arrow/Space — without creating separate slides.

**Markup contract:**

Add the `data-step` attribute to any element(s) that should be revealed one-per-advance:

```html
<p data-step>First point revealed on first advance.</p>
<p data-step>Second point revealed on second advance.</p>
<p data-step>Third point revealed on third advance.</p>
```

Elements with `data-step` start dim (low opacity) and become fully opaque when revealed. The deck controller handles all sequencing — press Arrow or Space to reveal the next step; only after all steps are shown does the next advance move to the next slide. No JS wiring needed.

**Example — three-step argument build:**

```html
<section class="slide" data-title="Why it works">
  <div class="slide-content">
    <h2>Why the change works</h2>
    <p data-step>1. It removes a manual step</p>
    <p data-step>2. It shortens the wait</p>
    <p data-step>3. It makes the result easier to check</p>
  </div>
</section>
```

---

## 4. Embedded Demo / iframe

**When to use:** Show a live web tool, prototype, or dashboard inside the slide without leaving the deck.

**Markup contract:**

```html
<iframe class="embed-frame" data-src="https://example.com"></iframe>
```

Use `data-src` instead of `src`. The deck controller sets `src` lazily when the slide activates, so off-screen iframes do not load early and slow down the initial render.

**Caveats:**
- The embedded site must allow framing. Many sites set `X-Frame-Options: DENY` or a restrictive `Content-Security-Policy` that will block the embed and show a blank frame.
- Cross-origin content cannot be controlled or scripted by the deck.

**Example — embedded prototype:**

```html
<section class="slide" data-title="Live Demo">
  <div class="slide-content" style="height:80%">
    <iframe class="embed-frame" data-src="https://prototype.example.com/demo"></iframe>
  </div>
</section>
```

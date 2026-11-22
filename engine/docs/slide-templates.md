# HTML Slides — Template Library

> **Theme names belong to the Brand pack.** Use a value the active pack defines (see its `brand.json`, `tokens.css` and `brand.md`). The examples use `white`; replace it with one of the pack's themes.

## Conventions

- **Stage size**: all slides are authored at **1920×1080 px**. The `.slide` class applies the pack's `--pad` padding automatically; content must fit within that padded area.
- **Entrance animation**: add class `reveal` to elements that should rise-and-fade in when the slide becomes visible. Keep to **≤ 6 `.reveal` children** per slide — if you need more, group elements.
- **Editable text**: all text inside `.slide-content` is editable in edit mode automatically — you do **not** need `data-edit`. Add `data-noedit` to a node to keep it locked. (Legacy `data-edit` attributes in older decks are harmless and ignored.)
- **Editable icons**: inline `.deck-icon` SVGs are swappable/removable via the in-slide picker in edit mode; keep `fill="currentColor"` so a swapped icon inherits the slide's colour and contrast.
- **Slide identity**: every `<section>` must carry `data-title="..."` — this value appears in the overview grid thumbnail and the editor panel.
- **Build-steps**: add `data-step` to elements that should reveal one-per-advance (arrow key / spacebar). These start dim and become opaque as the presenter steps through. **Do not also put `.reveal` on a `data-step` element** — the two animations conflict (see `widgets.md`).
- **Vertical balance**: by default give content slides `class="slide-content center"` so content is vertically centered (avoids the lopsided "everything in the top third" look). Drop `center` to top-align genuinely dense slides (large grids, long transcripts). Cover/section/closing already center via their own flex.
- **Vertical rhythm (don't hand-space every block)**: `.slide-content.center` applies a built-in `gap:var(--space-lg)` between its **direct children**, so stacked blocks (kicker, heading, body, chart…) never collide even if you forget to space them. Make each major block a direct child of `.slide-content.center` and let the gap do the work — don't pack everything into one wrapper (that defeats the rhythm), and don't re-add `margin-top` on top of it. When a slide has a kicker (see **Headlines**), couple it tightly to its heading by wrapping *just those two* in `<div class="stack-tight">…</div>`; that group then sits one `--space-lg` step from the body. Override the rhythm for a specific slide by setting your own `gap` on its `.slide-content` (inline `style` wins). After adding spacing, re-run the overflow check (see **Density budget**), because generous gaps can push a dense slide past the budget.
- **Spacing**: use the **spacing-scale tokens** from the pack's `tokens.css`: `--space-xs` (tight pairs like kicker→headline), `--space-sm` (intra-block like headline→lead), `--space-md` (list/agenda item gaps and card stacks), `--space-lg` (block separation, usually equal to `--gap`), `--space-xl` (hero separation, grid columns, process rows) and `--pad-card` (card padding). Do **not** free-hand pixel values for margins, gaps or padding: one-off values make the rhythm uneven across slides. The Engine's margin reset is zero-specificity (`:where(...)`), so your class/inline rules win without `style=""` hacks just to defeat the reset.
- **Density budget**: usable content height is **1080 − 2 × `--pad`**. Overflow is clipped silently (`overflow:hidden`), so check `slide-content.scrollHeight ≤ clientHeight` per slide rather than trusting a glance.
- **Headlines**: a content slide is a headline and a body. The headline states the slide's point in the deck's key terms.
  - **Kicker only when it adds something.** A kicker (the small label above a headline) belongs on a cover (the deck or event), a section divider (the section number or name) or a roadmap (the plan and year): it says what the headline doesn't. A kicker that restates the headline ("What the server needs" above "Requirements for the server") is left out.
  - **No counts of the items below.** Write "Requirements for the server", not "Five requirements for the server": the list already shows how many, and the count goes stale on the next edit. Keep a number only when it is the point ("3 of 4 pilots met the target").
  - `deck.py build` warns about both (`kicker:` and `headline count:` lines).
- **Numbers**: when the pack sets the optional `numberFormat` in `brand.json`, write numbers in that format, also when the deck is in another language. With thousands `.` and decimal `,` that is `159.365`, `3,5 %`, `1,5x`. Version numbers, dates, times and code stay as they are ("OAuth 2.1"). The counter widget formats with it on its own; `deck.py build` warns about numbers in the other convention (`number format:` lines).
- **Cards in a row**: build every row of side-by-side cards with `.card-row` > `.card` (see the "Card row" template). Cards in a row share one height and their titles, tags and bodies start at the same y.
- **Pack tokens only**: use only the CSS custom properties and class names defined in the pack's `tokens.css` and `assets/gradients.css`, `engine/runtime/viewport-base.css` (layout helpers such as `.stack-tight` and `.card-row`) and `engine/runtime/widgets.css`. Do not invent new class names or hard-code color hex values.
- **Body text contrast**: body copy must use `--text` (the brand's body/heading text color, which adapts per theme so it stays readable on the slide background). Reserve `--accent` (the signature accent) for headings, large display numerals, marks, icons, and graphic elements — never on small body text (the accent's contrast ratio fails at small sizes on light backgrounds).
- **Backgrounds (per slide):** every slide sets its own `data-theme`, picking a value the active pack defines. Mix freely across slides; the frame (logo, date, page number, classification) recolors automatically. Default to solid colors, and reserve any gradient theme the pack provides for the occasional hero or cover backdrop. On a light theme with a bloom, keep heavy text where the background is close to solid.
- **Frame safe zone:** the persistent frame occupies the top ~70px and bottom ~90px of the stage. The `.slide` padding (`--pad`) must clear it, so do not place content in those bands. The page number shows on every slide; `data-kind="cover"`/`"section"`/`"closing"` is an optional semantic hint only.

---

## Templates

Each layout has a stable id. Put it on the slide as `data-layout="<id>"`. A Deck type names its
recommended layouts by these ids, and a Brand pack's own layouts add ids of their own (see
`brand-pack.md`). A pack's layouts are in `brands/<slug>/layouts/`.

### Cover

**Layout id**: `cover`
**Narrative role**: Opening slide — brand identity, deck title, presenter, date.
**Density note**: Very low; hero typography dominates; title and subtitle only.

```html
<section class="slide active" data-theme="white" data-kind="cover" data-title="Cover">
  <div class="slide-content">
    <h1 class="reveal" data-edit style="font:700 var(--fs-hero)/0.98 var(--font-display);max-width:100%;text-wrap:balance;overflow-wrap:break-word">Deck title goes here</h1>
    <p class="reveal" data-edit style="font-size:var(--fs-h3);color:var(--muted);margin-top:var(--space-sm)">Subtitle · Presenter</p>
  </div>
</section>
```

> **Hero headlines never overflow — and never size them in `vw`.** Use
> `var(--fs-hero)` with `text-wrap:balance;overflow-wrap:break-word;max-width:100%`, and
> let a long title wrap (the overflow check catches one that still does not fit).
>
> `vw` is the **window**, not the stage. The stage is always 1920px internally and is
> already CSS-scaled to fit the window, so a `clamp(…,7vw,…)` hero scales a second time
> and shrinks on a small window — and whatever size the window happened to be is then
> baked into a PDF or PPTX export, which is why the same deck exported twice could differ.
> Size slide content in px (or the `--fs-*` tokens); the stage handles fitting.

---

### Title slide (kicker + headline + subtitle)

**Layout id**: `title`
**Narrative role**: Cover or title slide with a large headline and a one-line subtitle, optionally under a small kicker (eyebrow) that names what the headline doesn't: the deck, the event or the date. Drop the kicker when it would only restate the headline.
**Density note**: Very low. Keep kicker + headline + subtitle in **one flex-column container** so all three share the same left edge.

```html
<section class="slide active" data-theme="white" data-kind="cover" data-title="Title">
  <div class="slide-content" style="display:flex;flex-direction:column;justify-content:center;align-items:flex-start;gap:var(--space-sm)">
    <span class="reveal" data-edit style="font:700 var(--fs-h3)/1 var(--font-display);color:var(--accent)">→ Kicker / eyebrow line</span>
    <h1 class="reveal" data-edit style="font:700 var(--fs-hero)/0.98 var(--font-display);color:var(--text);max-width:100%;text-wrap:balance;overflow-wrap:break-word">One overview of AI across the business.</h1>
    <p class="reveal" data-edit style="font-size:var(--fs-h3);color:var(--muted);max-width:1100px;line-height:1.35;margin-top:var(--space-xs)">A one-line subtitle that frames the deck.</p>
  </div>
</section>
```

> Shown on `data-theme="white"`; for a cover, prefer the active pack's hero theme.

---

### Header + subtitle (content slide)

**Layout id**: `header`
**Narrative role**: Standard content slide whose header carries a sub-heading / deck line beneath it before the body.
**Density note**: Medium. The subtitle is a **sub-heading, not a caption** — keep it at `--fs-h3` so it stays readable when projected; it must never be smaller than the body (`--fs-body`).

```html
<section class="slide" data-theme="white" data-title="Header + subtitle">
  <div class="slide-content center" style="gap:var(--space-sm)">
    <h2 class="reveal" data-edit style="font:700 var(--fs-h1)/1.05 var(--font-display);color:var(--text)">Reuse becomes visible</h2>
    <p class="reveal" data-edit style="font-size:var(--fs-h3);color:var(--muted);max-width:1100px;line-height:1.35">The same overview, filtered by technology.</p>
    <p class="reveal" data-edit style="font-size:var(--fs-body);color:var(--text);max-width:1100px;line-height:1.5;margin-top:var(--space-xs)">Supporting body copy goes here.</p>
  </div>
</section>
```

---

### Section divider

**Layout id**: `section`
**Narrative role**: Marks the start of a new chapter or topic; resets audience attention.
**Density note**: Minimal; a single large numeral plus a short chapter label.

```html
<section class="slide" data-theme="white" data-kind="section" data-title="Section divider">
  <div class="slide-content" style="display:flex;flex-direction:column;justify-content:center;gap:var(--space-sm)">
    <span class="reveal" style="font:700 var(--fs-hero)/1 var(--font-display);color:var(--accent);line-height:0.9" data-edit>01</span>
    <h2 class="reveal" data-edit style="font:700 var(--fs-title)/1.05 var(--font-display);color:var(--text);max-width:900px">Chapter title</h2>
    <p class="reveal" data-edit style="font-size:var(--fs-h3);color:var(--muted);max-width:720px">A brief description of what this section covers.</p>
  </div>
</section>
```

> Shown on `data-theme="white"`; for a section divider, prefer the active pack's hero theme.

---

### Agenda

**Layout id**: `agenda`
**Narrative role**: Presents the run-of-show so the audience knows what to expect.
**Density note**: Low–medium; numbered list of 3–5 agenda items with optional timing.

```html
<section class="slide" data-theme="white" data-title="Agenda">
  <div class="slide-bg bg-glow"></div>
  <div class="slide-content" style="display:flex;flex-direction:column;justify-content:center;gap:var(--gap)">
    <h2 class="reveal" data-edit style="font:700 var(--fs-title)/1 var(--font-display);color:var(--text)">Agenda</h2>
    <ol style="list-style:none;padding:0;margin:0;display:flex;flex-direction:column;gap:var(--space-md);counter-reset:agenda">
      <li class="reveal" data-edit style="font-size:var(--fs-body);color:var(--text);display:flex;align-items:center;gap:var(--space-md);counter-increment:agenda">
        <span style="font:700 var(--fs-h2)/1 var(--font-display);color:var(--accent);min-width:64px">01</span>First agenda item
      </li>
      <li class="reveal" data-edit style="font-size:var(--fs-body);color:var(--text);display:flex;align-items:center;gap:var(--space-md);counter-increment:agenda">
        <span style="font:700 var(--fs-h2)/1 var(--font-display);color:var(--accent);min-width:64px">02</span>Second agenda item
      </li>
      <li class="reveal" data-edit style="font-size:var(--fs-body);color:var(--text);display:flex;align-items:center;gap:var(--space-md);counter-increment:agenda">
        <span style="font:700 var(--fs-h2)/1 var(--font-display);color:var(--accent);min-width:64px">03</span>Third agenda item
      </li>
      <li class="reveal" data-edit style="font-size:var(--fs-body);color:var(--text);display:flex;align-items:center;gap:var(--space-md);counter-increment:agenda">
        <span style="font:700 var(--fs-h2)/1 var(--font-display);color:var(--accent);min-width:64px">04</span>Fourth agenda item
      </li>
    </ol>
  </div>
</section>
```

---

### Big-statement

**Layout id**: `statement`
**Narrative role**: One memorable assertion — the core takeaway the audience should leave with.
**Density note**: Very low; hero-scale text only, no supporting copy.

```html
<section class="slide" data-theme="white" data-title="Big statement">
  <div class="slide-content" style="display:flex;flex-direction:column;justify-content:center;gap:var(--gap)">
    <h2 class="reveal" data-edit style="font:700 var(--fs-hero)/0.95 var(--font-display);color:var(--text);max-width:1500px">The one thing that changes everything.</h2>
  </div>
</section>
```

> A Brand pack can add its own signature graphic above the statement; check its `brand.md` and `assets/`. Shown on `data-theme="white"`; prefer the pack's hero theme for impact.

---

### Title + Content

**Layout id**: `content`
**Narrative role**: Standard content slide with a heading and a bulleted list that builds step-by-step.
**Density note**: Medium; three bullet points revealed one per advance.

```html
<section class="slide" data-title="Title + Content">
  <div class="slide-content">
    <h2 class="reveal" data-edit style="font:700 var(--fs-title)/1 var(--font-display)">Section title</h2>
    <ul style="margin-top:var(--gap);display:flex;flex-direction:column;gap:var(--space-md);font-size:var(--fs-body);list-style:none;padding:0">
      <li class="reveal" data-step data-edit>First point revealed on advance</li>
      <li class="reveal" data-step data-edit>Second point</li>
      <li class="reveal" data-step data-edit>Third point</li>
    </ul>
  </div>
</section>
```

---

### Two-Content

**Layout id**: `two-content`
**Narrative role**: Side-by-side comparison or two parallel themes with equal visual weight.
**Density note**: Medium; two columns, each with a heading and a short paragraph.

```html
<section class="slide" data-title="Two Content">
  <div class="slide-content" style="display:grid;grid-template-columns:1fr 1fr;gap:var(--space-xl);align-content:center">
    <div><h3 class="reveal" data-edit style="font:700 var(--fs-h2)/1 var(--font-display);color:var(--accent)">Left</h3>
      <p class="reveal" data-edit style="font-size:var(--fs-body);margin-top:var(--space-sm)">Left column copy.</p></div>
    <div><h3 class="reveal" data-edit style="font:700 var(--fs-h2)/1 var(--font-display);color:var(--accent)">Right</h3>
      <p class="reveal" data-edit style="font-size:var(--fs-body);margin-top:var(--space-sm)">Right column copy.</p></div>
  </div>
</section>
```

---

### Text + Image

**Layout id**: `text-image`
**Narrative role**: Combines narrative copy with a supporting visual — ideal for product shots, screenshots, or photography.
**Density note**: Medium; copy on the left, full-height image on the right.

```html
<section class="slide" data-theme="white" data-title="Text + Image">
  <div class="slide-content" style="display:grid;grid-template-columns:1fr 1fr;gap:var(--space-xl);align-items:center;height:100%">
    <div style="display:flex;flex-direction:column;gap:var(--gap)">
      <h2 class="reveal" data-edit style="font:700 var(--fs-title)/1.05 var(--font-display);color:var(--text)">Headline here</h2>
      <p class="reveal" data-edit style="font-size:var(--fs-body);color:var(--text);max-width:640px;line-height:1.5">Supporting body copy that adds context to the image on the right. Keep it to three or four lines so it stays legible at presentation scale.</p>
      <p class="reveal" data-edit style="font-size:var(--fs-h3);color:var(--accent);font-weight:700">Key takeaway or call to action</p>
    </div>
    <div class="reveal" style="height:760px;border-radius:var(--radius);overflow:hidden">
      <img src="assets/photo.jpg" alt="Descriptive alt text" style="object-fit:cover;width:100%;height:100%;display:block">
    </div>
  </div>
</section>
```

---

### Metrics / KPI

**Layout id**: `chart`
**Narrative role**: Showcases quantitative results with an animated bar chart.
**Density note**: Medium; heading plus three-bar chart.

```html
<section class="slide" data-theme="white" data-title="Metrics">
  <div class="slide-content">
    <h2 class="reveal" data-edit style="font:700 var(--fs-title)/1 var(--font-display)">Results</h2>
    <div class="chart-bars reveal" style="margin-top:var(--space-xl)">
      <div class="bar" data-value="42" data-max="100" style="--bar-color:var(--series-1)">
        <span class="value">42%</span><div class="fill"></div><span class="label">2023</span></div>
      <div class="bar" data-value="68" data-max="100" style="--bar-color:var(--series-2)">
        <span class="value">68%</span><div class="fill"></div><span class="label">2024</span></div>
      <div class="bar" data-value="91" data-max="100" style="--bar-color:var(--series-1)">
        <span class="value">91%</span><div class="fill"></div><span class="label">2025</span></div>
    </div>
  </div>
</section>
```

---

### Big stat / figure

**Layout id**: `kpi`
**Narrative role**: A single hero number with a unit (e.g. "~30 min", "4.2M") and a short caption — the headline figure of a slide.
**Density note**: Very low; one giant numeral plus a caption (and optionally a supporting list beside it).

```html
<section class="slide" data-theme="white" data-title="Big stat">
  <div class="slide-content center" style="gap:var(--space-md)">
    <div class="reveal" data-keep-color>
      <div style="font:700 var(--fs-hero)/0.9 var(--font-display);color:var(--accent);letter-spacing:-0.03em" data-edit>~30<span style="font-size:0.4em;font-weight:700;letter-spacing:normal;margin-left:0.12em">min</span></div>
      <p data-edit style="font-size:var(--fs-h3);color:var(--text);max-width:520px;margin-top:var(--space-xs)">A short caption that explains the number.</p>
    </div>
  </div>
</section>
```

> **Unit suffixes reset tracking.** The giant number uses tight negative `letter-spacing` for display polish, but the unit (`min`, `M`, `%` words) must set `letter-spacing:normal` on its own `<span>` — otherwise the suffix inherits the tight tracking and its letters cram together. Give the unit a legible relative size (`~0.4em`) and `700` weight.

---

### Comparison / Toggle

**Layout id**: `comparison`
**Narrative role**: Interactive before/after or scenario switcher the presenter can click through.
**Density note**: Low–medium; toggle control plus a text panel per state.

```html
<section class="slide" data-title="Comparison">
  <div class="slide-content">
    <h2 class="reveal" data-edit style="font:700 var(--fs-title)/1 var(--font-display)">Before vs after</h2>
    <div class="toggle-group reveal" role="tablist" style="margin-top:var(--space-lg)">
      <button role="tab" aria-selected="true" aria-controls="p-before">Before</button>
      <button role="tab" aria-selected="false" aria-controls="p-after">After</button>
    </div>
    <div style="margin-top:var(--space-lg);font-size:var(--fs-body)">
      <div class="toggle-panel active" id="p-before" data-edit>The old PowerPoint way.</div>
      <div class="toggle-panel" id="p-after" data-edit>The new interactive deck.</div>
    </div>
  </div>
</section>
```

---

### Process / Build-steps

**Layout id**: `process`
**Narrative role**: Walks through a sequential process or workflow, revealing each stage on advance.
**Density note**: Medium; three to four horizontal stages, each with a numeral, label, and short description.

```html
<section class="slide" data-theme="white" data-title="Process">
  <div class="slide-bg bg-glow"></div>
  <div class="slide-content" style="display:flex;flex-direction:column;justify-content:center;gap:var(--space-xl)">
    <h2 class="reveal" data-edit style="font:700 var(--fs-title)/1 var(--font-display);color:var(--text)">How it works</h2>
    <div class="card-row" style="--cols:3;--card-parts:3">
      <div class="card" data-step>
        <span style="font:700 var(--fs-h2)/1 var(--font-display);color:var(--accent)">01</span>
        <h3 data-edit style="font:700 var(--fs-h3)/1.1 var(--font-display);color:var(--text)">Discover</h3>
        <p data-edit style="font-size:var(--fs-body);color:var(--text);line-height:1.45">Understand user needs and map the current landscape.</p>
      </div>
      <div class="card" data-step>
        <span style="font:700 var(--fs-h2)/1 var(--font-display);color:var(--accent)">02</span>
        <h3 data-edit style="font:700 var(--fs-h3)/1.1 var(--font-display);color:var(--text)">Design</h3>
        <p data-edit style="font-size:var(--fs-body);color:var(--text);line-height:1.45">Prototype and validate solutions with real users.</p>
      </div>
      <div class="card" data-step>
        <span style="font:700 var(--fs-h2)/1 var(--font-display);color:var(--accent)">03</span>
        <h3 data-edit style="font:700 var(--fs-h3)/1.1 var(--font-display);color:var(--text)">Deliver</h3>
        <p data-edit style="font-size:var(--fs-body);color:var(--text);line-height:1.45">Ship, measure, and iterate continuously.</p>
      </div>
    </div>
  </div>
</section>
```

---

### Card row (groups, pillars, options side by side)

**Layout id**: `cards`
**Narrative role**: Puts two to four peers side by side (groups of concepts, pillars, options) so the audience compares them part by part.
**Density note**: Medium; each card has the same parts in the same order: title, tag, body.

Build every row of cards with the Engine's `.card-row` / `.card`. They are a CSS subgrid, so cards in a row share one height **and** line up inside: every title, tag and body starts at the same y, even when one title wraps to two lines. Each direct child of a `.card` is one part (one row). Give every card the same parts in the same order (a card without a tag keeps an empty `<span>` in its place). Set `--cols` (default 3) and `--card-parts` (default 3) on the row when they differ.

```html
<section class="slide" data-theme="white" data-title="Card row">
  <div class="slide-content center">
    <h2 class="reveal" style="font:700 var(--fs-title)/1 var(--font-display);color:var(--text)">Where customers get help</h2>
    <div class="card-row reveal" style="--cols:3;--card-parts:3">
      <div class="card">
        <h3 style="font:700 var(--fs-h3)/1.1 var(--font-display);color:var(--text)">Self-service</h3>
        <span style="font-size:var(--fs-caption);color:var(--muted)">Most customers</span>
        <ul style="display:flex;flex-direction:column;gap:var(--space-xs);list-style:none;padding:0;font-size:var(--fs-body);color:var(--text)">
          <li>Find the answer in the app</li>
          <li>Change the plan yourself</li>
        </ul>
      </div>
      <div class="card">
        <h3 style="font:700 var(--fs-h3)/1.1 var(--font-display);color:var(--text)">Chat with a bot that hands over to a person</h3>
        <span style="font-size:var(--fs-caption);color:var(--muted)">When the app is not enough</span>
        <ul style="display:flex;flex-direction:column;gap:var(--space-xs);list-style:none;padding:0;font-size:var(--fs-body);color:var(--text)">
          <li>Answers around the clock</li>
          <li>Hands over with the context</li>
          <li>Follows up by mail</li>
        </ul>
      </div>
      <div class="card">
        <h3 style="font:700 var(--fs-h3)/1.1 var(--font-display);color:var(--text)">Phone</h3>
        <span style="font-size:var(--fs-caption);color:var(--muted)">Complex cases</span>
        <ul style="display:flex;flex-direction:column;gap:var(--space-xs);list-style:none;padding:0;font-size:var(--fs-body);color:var(--text)">
          <li>A specialist on the line</li>
        </ul>
      </div>
    </div>
  </div>
</section>
```

The whole row carries one `.reveal`, so it rises as one block. To reveal the cards one at a time, put `data-step` on each `.card` instead (never both).

---

### Quote

**Layout id**: `quote`
**Narrative role**: Features a powerful testimonial, insight, or memorable quote from an external voice.
**Density note**: Very low; one large quotation and a short attribution line.

```html
<section class="slide" data-theme="white" data-title="Quote">
  <div class="slide-content" style="display:flex;flex-direction:column;justify-content:center;gap:var(--gap)">
    <span class="reveal" style="font:700 var(--fs-hero)/1 var(--font-display);color:var(--accent);line-height:0.8">"</span>
    <blockquote class="reveal" data-edit style="font:700 var(--fs-title)/1.1 var(--font-display);color:var(--text);margin:0;max-width:1400px">The future belongs to those who build it with intention and speed.</blockquote>
    <p class="reveal" data-edit style="font-size:var(--fs-h3);color:var(--muted)">— Name, Title, Organisation</p>
  </div>
</section>
```

---

### Closing

**Layout id**: `closing`
**Narrative role**: Final slide — thank you, contact details, and a strong brand send-off.
**Density note**: Low; thank-you line and contact/URL.

```html
<section class="slide" data-theme="white" data-kind="closing" data-title="Closing">
  <div class="slide-content" style="display:flex;flex-direction:column;justify-content:center;gap:var(--gap)">
    <h2 class="reveal" data-edit style="font:700 var(--fs-hero)/0.95 var(--font-display);color:var(--text)">Thank you.</h2>
    <p class="reveal" data-edit style="font-size:var(--fs-h3);color:var(--muted)">you@example.com · example.com</p>
  </div>
</section>
```

> A Brand pack can add its own signature graphic above the thank-you line; check its `brand.md` and `assets/`. Shown on `data-theme="white"`; prefer the pack's hero theme for the send-off.

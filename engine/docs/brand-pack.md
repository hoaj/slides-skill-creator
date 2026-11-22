# The Brand pack format

A Brand pack is one folder, `brands/<slug>/`. `deck.py check` validates it, and every command that
uses a pack runs the same validator first.

| Path | Status |
|---|---|
| `brand.json` | Required |
| `tokens.css` | Required. The source for colours and font stacks |
| `brand.md` | Required. The brand's design rules |
| Logo, usually `assets/logo.svg` | Required. Named by `logo` in `brand.json` |
| `assets/gradients.css` | Required when a theme has `bloom` set |
| `fonts/` and `fonts.css` | Optional. Without them the pack uses the system stacks in `tokens.css` |
| `icon-library.js` and `icons.md` | Optional. Without them the icon picker is hidden |
| `layouts/` | Optional. The pack's own layouts |
| `playbook/` | Optional. `interview.md` and `deck-types/<id>.md` |

`fonts.css` can point at the font files with a relative `url("fonts/name.woff2")`. The build inlines
them, so the pack holds each font once and the built deck stays one file.

## `brand.json`

`formatVersion`, `slug`, `name`, `aliases` (use `[]` for none), `logo`, `defaultTheme`, `themes`,
`classifications`, `defaultClassification`, `fonts` and `guard` are required. `pptxLead`,
`numberFormat` (`{ "thousands": ".", "decimal": "," }`) and `contrastExceptions` are optional.

`guard` is contrast data that must match `tokens.css`: each palette colour exists there, and
`themeBg` and `themeText` are each theme's `--bg` and `--text`. A gradient or transparent theme
names its solid base colour in `themeBg`.

Every theme must reach WCAG AA (4.5:1) for `body` (`--text` on `--bg`), `muted` (`--muted` on `--bg`)
and `on-accent` (`--on-accent` on `--accent`). An exception names the theme, the pair and a reason:

```json
"contrastExceptions": [{ "theme": "brand", "pair": "muted", "reason": "Used only at 34px or larger." }]
```

## Own layouts

A layout is one HTML file and an optional stylesheet, named by its id:

```text
layouts/scorecard.html
layouts/scorecard.css
```

- The HTML holds exactly one `<section class="slide layout-<id>" data-title="...">`.
- Every CSS selector starts with `.layout-<id>` or `.layout-<id>__part`, so a pack cannot change a
  base layout. Rules may sit inside `@media`. Other at-rules, such as `@import`, are not allowed.
- A layout holds no script and loads no remote file.
- An id cannot be one of the Engine's base layout ids, listed in `engine/layouts.json`.

The build inlines the pack's layout CSS into every deck. An agent copies the `<section>` into the
deck's template.

## The Playbook

### `playbook/interview.md`

Four actions change the Engine's Interview. Each is a `##` heading naming a question id:

```markdown
## guide: audience
Suggest the board, the volunteers or partners.
- The board
- Volunteers

## after: audience
id: volunteer-role
Ask what role the volunteers have.

## replace: arc
Always use: Finding, Meaning, Recommendation.

## skip: language
answer: da
```

- `guide` adds help text. Lines starting with `-` are answer options, shown first.
- `after` adds a question with its own unique id.
- `replace` and `skip` work only on unprotected questions. `skip` must give the fixed answer.

The question ids are `outcome`, `audience`, `takeaway`, `arc`, `evidence`, `language`, `length`,
`density`, `setting`, `theme`, `classification` and `header`.

`outcome`, `audience` and `takeaway` are protected: they accept `guide` and `after` only. The
steps `outline`, `key-terms` and `approval` accept no rule at all. Trying to change any of them
stops `check` and the build.

### `playbook/deck-types/<id>.md`

```markdown
---
name: Survey report
when: Results from a survey or analysis
layouts: [kpi, chart, quote]
---

## Interview
### replace: arc
Finding, Meaning, Recommendation

## Outline
1. Cover
2. Key finding

## Content rules
- Show n and the data source on every chart.
```

`name` and `when` are required, and everything else is optional. Interview rules use `###` headings.

### Precedence and problems

Rules apply in the order Engine, `interview.md`, Deck type, and the most specific rule wins: a later
`guide`, `replace` or `skip` on a question overrides an earlier one.

- A rule naming an **unknown question id or layout** warns and is ignored, so the build continues.
- A **format error** stops `check` and the build: `skip` without an answer, a duplicate new id, an
  unknown action, or two conflicting rules in one file.

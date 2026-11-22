# Acme

The example Brand pack. Acme is a fictional company, so this pack can show every Brand pack and
Playbook feature in public.

## Look

- **Type:** Public Sans, regular and bold, for headings and body text.
- **Colours:** ink, cobalt and sun, with mist and paper as quiet backgrounds. Coral appears only
  in the Dawn gradient, and teal only in the chart series.
- **Logo:** a rising triangle and a drawn wordmark in `currentColor`, so it follows each theme.

## Themes

| Theme | Use it for |
|---|---|
| Paper | The default for content slides |
| Mist | Content slides that need a quiet break from Paper |
| Ink | Covers, section dividers and closing slides |
| Cobalt | A strong cover or section divider |
| Sun | One highlight slide in a deck, not more |
| Dawn | The gradient for covers and big statements, with the Bloom slider |

## Design rules

- Body copy stays on `--text`. Sun and cobalt are for headings, numbers and graphics.
- Use **Sun** at most once in a deck, so it keeps its effect.
- Keep heavy text away from the bright corner of a Dawn slide.
- Show one idea per slide. Prefer a chart or a number over a paragraph.

## Contrast exception

Muted text on **Cobalt** measures 4.07:1, below the 4.5:1 of WCAG AA for body text. It is allowed
because that theme uses muted text only for subtitles at `--fs-h3` (34px) or larger, where
WCAG AA asks for 3:1. Do not set captions in muted text on Cobalt.

## Classification

`INTERNAL`, `PUBLIC` or none. The default is `INTERNAL`.

## Own layout

`scorecard` shows three measured results with a score bar each. Use it for survey and KPI results.

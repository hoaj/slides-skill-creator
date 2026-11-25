---
name: slides-skill-creator
description: Creates and maintains Slides skills, coding-agent skills that build on-brand HTML slide decks from a shared Engine. Use to make a Slides skill for a brand from its guidelines, logo, fonts or PowerPoint template (new), to add another brand to an existing Slides skill (add-brand), or to change a Brand pack's fonts, icons, colours, themes, layouts, Playbook, Deck types or PowerPoint calibration (edit-brand). Also when asked to upgrade or check a Slides skill. Not for building a deck, which the Slides skill itself does.
---

# slides-skill-creator

This skill is the **Generator**. It makes a **Slides skill**: a skill in a repo the maintainer
owns, holding a copy of the **Engine**, one or more **Brand packs** and `engine.lock`. A Brand pack
is data, CSS, an SVG logo, fonts, icons and instructions, never hand-written code. These terms,
and Playbook, Interview, Deck type, Sample deck and Starter files, mean what `<gen>/../../GLOSSARY.md`
says.

- `<gen>` is the folder of this `SKILL.md`. The Engine is `<gen>/../../engine`.
- `<skill>` is a Slides skill's folder, the one holding its `SKILL.md`: `<repo>/skills/<name>-slides`
  in a repo of its own, `<repo>/plugins/<name>-slides/skills/<name>-slides` in a shared one.
- `<work>` is a working folder outside every repo, for the brand material, extracted facts and
  draft packs. Brand material never goes into a commit, an issue or this repo.

## Prerequisites

| Check | Command | Passes when |
|---|---|---|
| Python 3.8 or newer | `python3 --version` | `>= 3.8` |
| `gh` logged in, for a new repo or a PR | `gh auth status` | exit 0 |
| Font tools, when the brand has font files | `python3 -c "import fontTools, brotli"` | exit 0; else `python3 -m pip install fonttools brotli` |
| Engine checks of the Slides skill | `python3 <skill>/engine/deck.py doctor` | it reports what the machine lacks |

## Modes

| Mode | When | Read first |
|---|---|---|
| `new` | A brand has no Slides skill yet | [reference/new.md](reference/new.md) |
| `add-brand` | Another brand joins an existing Slides skill | [reference/add-brand.md](reference/add-brand.md) |
| `edit-brand` | A Brand pack changes: fonts, icons, colours, themes, layouts, Playbook, Deck types, PowerPoint calibration | [reference/edit-brand.md](reference/edit-brand.md) |

**Upgrade and check are not Generator modes.** Run them in the Slides skill's repo:
`python3 <skill>/engine/deck.py upgrade` moves it to a newer Engine release and opens a PR, and
`python3 <skill>/engine/deck.py check` validates its Brand packs.

## The flow

`new` and `add-brand` take every step; `edit-brand` takes the steps its change touches and always
ends with steps 5 and 6. Each step ends on its gate: the next step starts only once it holds.

1. **Collect material.** The user gives what they have: a PowerPoint template, guidelines as PDF,
   a website, a logo, font files, an icon set. Copy it into `<work>/material/`.
   Gate: every file the user named is in `<work>/material/`, or they said it does not exist.
2. **Show the brand card.** Scripts extract what is unambiguous, you read the rest, and the card
   shows every value with its source and asks only for what is missing:
   [reference/brand-card.md](reference/brand-card.md).
   Gate: the user approved the card. Nothing is written before that.
3. **Run the Playbook interview**, one question at a time:
   [reference/playbook.md](reference/playbook.md). The user may skip it and do it later with
   `edit-brand`.
   Gate: the user approved `interview.md` and each Deck type, or chose to skip.
4. **Write the Brand pack** in `<work>/packs/<slug>/` from the approved card:
   [reference/brand-card.md](reference/brand-card.md#write-the-brand-pack).
   Gate: `gen.py pack-check` reports `"valid": true`.
5. **Build the Sample deck.** Run `deck.py check`, then build and open the Sample deck in `<work>`:
   ```sh
   python3 <skill>/engine/deck.py check
   python3 <skill>/engine/deck.py sample --brand <slug> <work>/<slug>-sample.html --open
   ```
   It shows every theme, the base layouts, the pack's own layouts, widgets, icons and the footer.
   Ask the user to page through it and approve it or name what to change. Make each change in the
   pack, run the tool that owns it (fonts, icons, guard), and build the Sample deck again.
   Gate: the user approved the Sample deck as it now is, and `deck.py check` reports 0 errors.
6. **Commit** after approval: the first push of a new repo, or a PR. The mode's reference says
   which.

## Tools

Every tool prints JSON; a failure is `{"error": {...}}` with exit 1. A `next` field names what to
run next. `--help` on any command lists its flags. Quote every value with a space in it.

```sh
python3 <gen>/tools/gen.py extract-pptx <file.pptx> --out <work>/extract
python3 <gen>/tools/gen.py pack-init --out <work>/packs/<slug> --slug <slug> --name "<Name>" [--alias "<a>"]...
python3 <gen>/tools/gen.py fonts --pack <pack> --src <font file>... [--display "<family>"] [--body "<family>"]
python3 <gen>/tools/gen.py icons --pack <pack> --src <folder of SVGs>
python3 <gen>/tools/gen.py guard --pack <pack> [--base <theme>=<colour>]... [--neutral <c>]... [--vivid <c>]...
python3 <gen>/tools/gen.py pack-check --pack <pack>
python3 <gen>/tools/gen.py new --dir <folder> | --into <repo root> --skill <name>-slides --description "<text>" --repo <owner/name> --author "<name>" --brand <pack>
python3 <gen>/tools/gen.py add-brand --skill-dir <skill> --brand <pack>
python3 <gen>/tools/gen.py describe --skill-dir <skill> --description "<text>"
python3 <gen>/tools/gen.py bump --skill-dir <skill> major|minor|patch
python3 <gen>/tools/gen.py calibrate prepare|fit --skill-dir <skill> --brand <slug> --out <work>/calibration [--powerpoint] [--write]
```

`<pack>` is a Brand pack folder: a draft in `<work>/packs/<slug>` before the skill has it, and
`<skill>/brands/<slug>` after. The Engine's own commands (`check`, `sample`, `build`,
`export-pptx`, `extract-pptx`, `doctor`) run through `python3 <skill>/engine/deck.py`; call them
rather than repeating what they do.

## Rules

- **The maintainer approves three things before they are written:** the brand card, the skill's
  name and trigger description, and the Sample deck. Show each and wait for their answer.
- **A brand difference lives in its Brand pack.** Change the skill's `engine/` only when the
  maintainer decides on a local Engine edit; Upgrade then has to merge it.
- **A new repo is private** unless the maintainer explicitly chooses public. Show the choice
  before anything is created on GitHub.
- **Font files are embedded in every deck.** The Generator does not check font licences: tell the
  maintainer they are responsible for having the right to embed and distribute the fonts, and
  keep a licence file in `licenses/` when the font comes with one.
- **`plain` is the Engine's hidden test pack.** No Brand pack may use that slug.
- A problem with the Generator itself (a tool fails, this guidance misleads, a Starter file is
  wrong): offer `slides-skill-creator-feedback`.

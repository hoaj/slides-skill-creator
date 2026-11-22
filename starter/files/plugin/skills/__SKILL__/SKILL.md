---
name: __SKILL__
description: __DESCRIPTION_JSON__
---

# __SKILL__

Builds on-brand HTML slide decks with this skill's Brand packs.

## Start here

Read `engine/workflow.md` in this skill's folder before doing anything else, and follow it from
top to bottom. It covers a new deck, a `.pptx` to convert and an edit to an existing deck.

## Paths

`<skill>` means the folder that holds this `SKILL.md`, in every coding agent. Run every Engine
tool through one command:

```sh
python3 <skill>/engine/deck.py <command>
```

Generated files (templates, decks, exports and extracted slides) go in the user's project, never
in the skill folder. An installed skill may be replaced on its next update.

## What lives where

- `engine/` is a copy of the shared Engine. Leave it unedited unless a maintainer has decided on
  a local change, because Upgrade has to merge every edit.
- `brands/` holds this skill's Brand packs. A difference between brands belongs there.
- `engine.lock` records the Engine release this copy came from. Only Upgrade changes it.

## Problems

When a tool fails, run `deck.py doctor`. To report a bug or request a feature, use the
`__SKILL__-feedback` skill.

## Local rules

<!-- Rules for all of this skill's Brand packs. Upgrade never changes this section. -->

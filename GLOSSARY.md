# slides-skill-creator

A generator of coding-agent skills that build on-brand slide decks from a shared, versioned engine.

## Language

**Generator**:
The `slides-skill-creator` plugin, the original that creates and maintains Slides skills.
_Avoid_: factory, template, creator skill

**Engine**:
The shared, versioned code and workflow that build, present, edit and export decks for any brand.
_Avoid_: motor, core, framework

**Slides skill**:
A skill made by the Generator that holds a copy of the Engine and one or more Brand packs.
_Avoid_: generated plugin, brand skill, deck skill

**Brand pack**:
Everything that makes a deck belong to one brand: its look, its design rules and its Playbook.
_Avoid_: theme, brand kit

**Starter files**:
The files the Generator gives a new Slides skill that are neither Engine nor Brand pack, and that the Slides skill then owns.
_Avoid_: template, scaffold, boilerplate

**Playbook**:
The part of a Brand pack that adapts how decks are planned, through interview changes and deck types.
_Avoid_: brand instructions, prompt pack

**Upgrade**:
Moving a Slides skill to a newer Engine release.
_Avoid_: sync, update, bump

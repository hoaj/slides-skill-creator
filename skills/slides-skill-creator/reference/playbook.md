# The Playbook interview

A short interview that turns how a brand makes decks into its Playbook: `playbook/interview.md`,
which changes the Engine's Interview, and `playbook/deck-types/<id>.md`, one recipe per kind of
deck the brand makes repeatedly. The file formats, the protected questions and the precedence
rules are in `<gen>/../../engine/docs/brand-pack.md#the-playbook`; read it before writing either
file.

Ask one question at a time and wait for the answer. Offer the user to skip the whole interview:
the pack works without a Playbook, and `edit-brand` can add one later.

## Questions

1. **Which kinds of deck do you make often?** For each answer, ask when it is used, and whether
   it always follows the same outline. Each kind with a stable outline becomes a Deck type.
2. **Are some answers always the same?** Walk the Engine's Interview ids (`outcome`, `audience`,
   `takeaway`, `arc`, `evidence`, `language`, `length`, `density`, `setting`, `theme`,
   `classification`, `header`) and ask which are always answered the same way or always need the
   same help, for this brand or for one Deck type.
3. **Are there content rules?** What every deck of this brand, or of one Deck type, must or must
   not contain: sources on charts, no names of people, a disclaimer slide.

## From answers to rules

| The user says | Rule |
|---|---|
| A question always gets the same answer | `skip: <id>` with `answer:`; allowed only on unprotected questions |
| A question always has the same choices or needs help | `guide: <id>` with its text and `-` options |
| A question is always answered by a fixed rule | `replace: <id>` with the rule; not on `outcome`, `audience`, `takeaway` |
| Something extra must always be asked | `after: <id>` with a new unique `id:` |
| A kind of deck has a stable outline or rules | a Deck type with `name`, `when`, its `## Outline`, `## Content rules` and its own `## Interview` rules under `###` headings |

The outline, the key terms and the user's approval of the outline cannot be changed by any rule.
When the user asks for that, say so and offer a `guide` instead.

## Approve

Show each file in full and ask the user to approve it or name what to change. Write the files
to the pack's `playbook/` only after approval, then check that the merged Interview reads as the
user expects:

```sh
python3 <skill>/engine/deck.py interview --brand <slug> [--deck-type <id>]
```

Before the skill exists, run `gen.py pack-check --pack <pack>` instead. A warning for an unknown
question id or layout means the rule is ignored: correct it.

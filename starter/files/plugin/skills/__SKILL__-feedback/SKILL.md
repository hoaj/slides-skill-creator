---
name: __SKILL__-feedback
description: Files a problem with the __SKILL__ skill as a GitHub issue on __REPO__, after the user approves the text. Use when a deck.py command fails, a deck from __SKILL__ renders or exports wrongly, its guidance turned out wrong, it lacks something the user needs, or the user says "report this" about it. A maintainer also uses it to forward an Engine bug to the public Engine repo. Not for building or editing decks, or for content and design choices in the user's own deck.
---

# __SKILL__ feedback

Something in `__SKILL__` got in the way. Draft one issue for `__REPO__`, show it to the user, and
file it only on a yes.

**You report, and the skill stays as it is.** Change nothing in the Engine, Brand packs or
Starter files here. A fix idea goes in the issue under *Suggestion*.

`<skill>` below is the `__SKILL__` folder next to this skill's folder.

## 1. Search for the same problem

```sh
gh issue list --repo __REPO__ --state all --search "<symptom>" --json number,title,state,url
```

- **Open match:** add a comment with the new facts instead of a new issue, after the user's yes.
- **Closed match:** a user updates the plugin. A maintainer runs
  `python3 <skill>/engine/deck.py upgrade`.
- **No `gh` or no access:** skip the search and go on.

## 2. Decide the kind

- **Bug:** a command fails, or the output or the guidance is wrong.
- **Feature:** the skill cannot do what the user needs.

## 3. Collect the facts

```sh
python3 <skill>/engine/deck.py doctor --report
```

It prints versions, the OS, browsers and which Engine files were edited locally, with the home
directory replaced by `~`. Add what the user was doing, the exact command, what should have
happened and what happened.

## 4. Redact

Leave out deck content, source files, people's names and screenshots with real content. Reproduce
the problem with placeholder text and quote only the error after redaction.

## 5. Show it and ask

Show the title and body, and say who can read issues on `__REPO__`. On a correction, show the new
text and ask again.

## 6. File it after a yes

```sh
gh issue create --repo __REPO__ --title "<title>" --body-file - <<'EOF'
## What happened
## Expected
## Steps with placeholder content
## Environment
## Suggestion
EOF
```

Without `gh` or access, give the user the title and body to paste into a new issue. Then give the
user the issue link and return to their task.

## Forward an Engine bug (maintainers only)

Use this when a filed issue looks like a bug in the shared Engine. The public repo must never
learn about this skill's brand, so the public issue is written from scratch.

1. Read the private issue on `__REPO__`.
2. Reproduce the bug with the Engine's neutral `plain` Brand pack, the Sample deck and neutral
   text, outside the skill folder:

   ```sh
   python3 <skill>/engine/deck.py sample --brand plain <temp folder>/plain-sample.html
   ```

3. Write a new public text from that reproduction. Never copy from the private issue, and do not
   name this skill, its repo, its brand or its people.
4. Show the text and file it on `hoaj/slides-skill-creator` only after a yes:

   ```sh
   gh issue create --repo hoaj/slides-skill-creator --title "<title>" --body-file - <<'EOF'
   <the neutral reproduction>
   EOF
   ```

5. Comment the public link on the private issue. The public issue never links back.

If the bug cannot be reproduced on `plain`, keep it in `__REPO__` as a possible Brand pack or
local issue. Send a redacted description upstream only when the maintainer explicitly chooses to.

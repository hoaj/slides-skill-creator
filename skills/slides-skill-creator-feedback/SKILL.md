---
name: slides-skill-creator-feedback
description: Files a problem with the slides-skill-creator Generator as a public GitHub issue on hoaj/slides-skill-creator, after the user approves the text. Use when a Generator mode (new, add-brand, edit-brand) or tool fails or misleads, rendered Starter files are wrong, the Generator's guidance turned out wrong, it lacks something the maintainer needs, or the user says "report this" about slides-skill-creator. Not for a Slides skill's own problems, which go to its <skill>-feedback skill, or for building decks.
---

# slides-skill-creator feedback

Something in the Generator got in the way. Draft one issue for `hoaj/slides-skill-creator`, show
it to the user, and file it only on a yes.

**You report, and the Generator stays as it is.** A fix idea goes in the issue under *Suggestion*.

A problem in a Slides skill goes to that skill's `<skill>-feedback` skill instead. Its forwarding
step is the way an Engine bug reaches this repo.

## 1. Gather the facts

- **Intent:** what the maintainer was doing, and which mode.
- **Where:** the tool and its exact command line, or the guidance followed.
- **Expected and actual:** what should have happened, and the output after redaction.
- **Environment:** the Generator version, Python version and OS.

## 2. Redact

`hoaj/slides-skill-creator` is public. Before anything leaves the machine:

- Name no real organisation, brand, person or private repo. Write `<brand>` and `<repo>`.
- Include no brand material: guidelines, logos, fonts, colours, templates or deck content.
- Replace the home directory with `~`, and remove tokens and credentials.
- Reproduce with the `acme` or `plain` Brand pack and neutral text whenever possible.

## 3. Search for a duplicate

```sh
gh issue list --repo hoaj/slides-skill-creator --state all --search "<symptom>" --json number,title,state,url
```

An open match gets a comment with the new facts instead of a new issue, after the user's yes.
Without `gh`, skip the search.

## 4. Show it and ask

Title: `<mode or tool>: <symptom>` for a bug, `feature: <capability>` for a feature request.

```md
## Intent
## Where
## Expected
## Actual
## Environment
## Suggestion
```

Show the title and body, say the issue will be public, and ask whether to file it. On a
correction, show the new text and ask again.

## 5. File it after a yes

```sh
gh issue create --repo hoaj/slides-skill-creator --title "<title>" --body-file - <<'EOF'
<body>
EOF
```

Without `gh` or access, give the user the title and body to paste into a new issue. Then give the
user the issue link and return to their work.

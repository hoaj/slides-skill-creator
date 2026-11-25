# Mode: new

Creates a Slides skill with its first Brand pack, either in a repo of its own that is also its
own marketplace (`--dir`), or in `plugins/<name>-slides` of a shared repo that already holds a
marketplace (`--into`). The person running `new` is the skill's maintainer.

Done when the Slides skill is on GitHub with an approved Sample deck: pushed to `main` of its own
repo, or in a PR on the shared repo.

## 1. Material, card, Playbook, pack

Take steps 1 to 4 of the flow in `SKILL.md`. The pack ends in `<work>/packs/<slug>/` with
`gen.py pack-check` valid.

## 2. Name, description and repo

Propose each value and ask one at a time:

| Value | Rule | Example |
|---|---|---|
| skill name | `<name>-slides`, lowercase, usually the brand's slug | `acme-slides` |
| description | the trigger: names the brand and its aliases, says it builds slide decks, presentations and PowerPoint exports for them, and that it is not for other brands; one line, at most 1024 characters | `Builds on-brand slide decks, presentations and PowerPoint exports for Acme ("Acme Corp", "Acme Inc"). Use for any deck, talk or report for Acme, or to turn an Acme .pptx into a web deck. Not for other brands.` |
| repo | `owner/name` on GitHub, or the shared marketplace repo the skill joins | `acme-example/acme-slides` |
| visibility | **private**, unless the maintainer explicitly chooses public. A public repo publishes the Brand pack: its fonts, logo and colours | private |
| author | the maintainer's name, for the manifests | `Acme Maintainers` |
| local folder | where the repo is cloned | `~/code/acme-slides` |

The name and the description are approved like the card: show them, wait for a yes.

## 3. Repo of its own: create and scaffold

Show the repo, its visibility and the folder, and ask before creating anything on GitHub. Then:

```sh
gh repo create <owner/name> --private --clone --description "<one line>"   # --public only when chosen
python3 <gen>/tools/gen.py new --dir <local folder> --skill <name>-slides --description "<text>" \
  --repo <owner/name> --author "<author>" --brand <work>/packs/<slug>
```

When the repo already exists, clone it instead. `new --dir` writes only into a folder that is
missing, empty or holds nothing but `.git`; if the repo has files, ask whether to start from an
empty repo. It validates the pack, renders the Starter files (manifests for Claude Code, Cursor
and Copilot CLI, the marketplace files, CI, the release workflow, the thin `SKILL.md` and the
`<name>-slides-feedback` skill), copies the Engine and the pack, and writes `engine.lock`. Its
JSON names `skillDir`: that is `<skill>` from here on.

## 4. Sample deck

Take step 5 of the flow on `<skill>`. Changes now go into `<skill>/brands/<slug>/`; the draft in
`<work>/packs/` is no longer used. Offer the PowerPoint calibration
([powerpoint.md](powerpoint.md)) when the pack has font files and the maintainer has PowerPoint;
without it, decks still export and the export warns.

## 5. Push

After the Sample deck is approved:

```sh
cd <local folder> && git add -A && git commit -m "new: <name>-slides 0.1.0" && git push -u origin HEAD:main
```

The push runs CI and the release workflow, which publishes `v0.1.0`. Watch it with
`gh run watch --repo <owner/name>` and report the result.

## Into a shared repo

For a repo whose root already holds a marketplace (`.claude-plugin/marketplace.json`,
`.cursor-plugin/marketplace.json` or `.github/plugin/marketplace.json`):

1. Clone it or `git pull` the clone, and branch: `git switch -c new/<name>-slides`.
2. Scaffold with `--into` instead of `--dir`:
   ```sh
   python3 <gen>/tools/gen.py new --into <clone> --skill <name>-slides --description "<text>" \
     --repo <owner/name> --author "<author>" --brand <work>/packs/<slug>
   ```
   It writes the plugin to `plugins/<name>-slides/`, its workflows to `.github/workflows/` (they
   run only when the plugin changes), and adds one entry to every marketplace file at the root.
   It refuses, and writes nothing, when the root has no marketplace, a marketplace file is not
   valid JSON or already lists the skill, or a target file exists.
3. Take step 4 on `<skill>`.
4. Commit, push the branch and open a PR; the maintainer of the shared repo merges it. The merge
   publishes `<name>-slides-v0.1.0`.
   ```sh
   git add -A && git commit -m "new: <name>-slides 0.1.0" && git push -u origin HEAD
   gh pr create --repo <owner/name> --title "new: <name>-slides 0.1.0" --body "<brands, check result>"
   ```

## Hand over

Tell the maintainer:

- how to install the skill from its marketplace, in Claude Code: `/plugin marketplace add <owner/name>`,
  then `/plugin install <name>-slides@<marketplace name>`;
- that users report problems through `<name>-slides-feedback`, which files issues on the repo;
- that `add-brand` and `edit-brand` here change the skill, and `deck.py upgrade` in the skill
  moves it to a newer Engine.

# Mode: add-brand

Adds a Brand pack to an existing Slides skill. Done when a PR holds the new pack, the updated
trigger description and a minor version bump, with an approved Sample deck.

1. **Clone** the Slides skill's repo, or `git pull` the clone, and branch:
   `git switch -c add-brand/<slug>`. `<skill>` is its `skills/<name>-slides` folder
   (`plugins/<name>-slides/skills/<name>-slides` in a shared repo). Run
   `python3 <skill>/engine/deck.py brands` to see the brands it has.
2. **Material, card, Playbook, pack:** steps 1 to 4 of the flow in `SKILL.md`. The new slug must
   differ from every brand the skill has.
3. **Add the pack:**
   ```sh
   python3 <gen>/tools/gen.py add-brand --skill-dir <skill> --brand <work>/packs/<slug>
   ```
   It refuses a pack whose format the skill's Engine does not support; then run
   `python3 <skill>/engine/deck.py upgrade` first.
4. **Propose the new trigger description:** the old one with the new brand and its aliases
   added, still excluding every other brand. When the skill holds several brands, it says so and
   lets the Slides skill infer the brand from aliases. Show it and wait for a yes, then:
   ```sh
   python3 <gen>/tools/gen.py describe --skill-dir <skill> --description "<text>"
   ```
   It changes the description in `SKILL.md`, the manifests, the marketplace entries and
   `engine.lock`.
5. **Sample deck:** step 5 of the flow for the new brand. Build the Sample deck of every other
   brand too, and confirm with the user that they are unchanged.
6. **Bump and PR:**
   ```sh
   python3 <gen>/tools/gen.py bump --skill-dir <skill> minor
   git add -A && git commit -m "add-brand: <slug>" && git push -u origin HEAD
   gh pr create --title "add-brand: <slug>" --body "<the brand, the description change, check result>"
   ```
   The maintainer merges; the merge publishes the new version. Keep brand material out of the PR
   text.

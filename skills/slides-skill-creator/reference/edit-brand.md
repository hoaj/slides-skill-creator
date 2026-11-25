# Mode: edit-brand

Changes one Brand pack of a Slides skill. Done when a PR holds the change and a version bump,
with `deck.py check` at 0 errors and an approved Sample deck.

1. **Clone** the Slides skill's repo, or `git pull` the clone, and branch:
   `git switch -c edit-brand/<slug>-<change>`. `<pack>` is `<skill>/brands/<slug>`.
2. **Agree the change.** Ask what should change and collect any new material into
   `<work>/material/`. For a change of look, show the affected rows of the brand card
   ([brand-card.md](brand-card.md)), old and new, and wait for a yes.
3. **Make it** with the step that owns it:

   | Change | Do |
   |---|---|
   | Fonts | `gen.py fonts --pack <pack> --src <new files>... --display "<family>" --body "<family>"`. It replaces the pack's font set and deletes the old files. Update the licence in `licenses/`, then calibrate again ([powerpoint.md](powerpoint.md)), since the calibration belongs to the old face |
   | Colours or themes | Edit `tokens.css` and the themes in `brand.json` (and `assets/gradients.css` for a gradient), then `gen.py guard --pack <pack>`, keeping or giving `--base` for gradient themes. A theme removed here may still be named by decks already built; they keep working, because each deck carries its own copy |
   | Icons | `gen.py icons --pack <pack> --src <folder of SVGs>` with the whole new set |
   | Logo | Replace the SVG named by `logo` in `brand.json` |
   | Layouts | Edit `layouts/<id>.html` and `.css` as `engine/docs/brand-pack.md` describes |
   | Playbook or Deck types | The Playbook interview for the part that changes ([playbook.md](playbook.md)) |
   | PowerPoint calibration | [powerpoint.md](powerpoint.md) |
   | Design rules | Edit `brand.md`, and show the new text for approval |

   A name or alias change also needs a new trigger description, approved and set with
   `gen.py describe`.
4. **Check and Sample deck:** step 5 of the flow in `SKILL.md`.
5. **Bump and PR:** `patch` for a correction (a colour value, a rule, a calibration), `minor`
   for something new (a theme, a layout, a Deck type, new fonts).
   ```sh
   python3 <gen>/tools/gen.py bump --skill-dir <skill> patch|minor
   git add -A && git commit -m "edit-brand: <slug>: <change>" && git push -u origin HEAD
   gh pr create --title "edit-brand: <slug>: <change>" --body "<what changed, check result>"
   ```
   The maintainer merges. Keep brand material out of the PR text.

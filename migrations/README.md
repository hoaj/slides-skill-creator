# Brand pack format migrations

Each change to the Brand pack format ships one script here, `format_N.py`, that moves a Brand
pack from format N-1 to format N. Upgrade runs them in order for every Brand pack in the skill.

A script defines one function:

```python
def migrate(pack):
    """pack is the Brand pack's folder (a pathlib.Path). Returns a list of what it could not decide."""
```

It makes every change that has one right answer, including setting `formatVersion` in
`brand.json` to N, and returns a short line for each thing it leaves to the coding agent, such as
free text in a Playbook. The agent decides those, and its choices go into the upgrade's PR.

Every script has a test. There are none yet: format 1 is the first.

"""The Engine's workflow file and layout ids, read as the contract they are."""
import json
import re
import unittest

from tests.helpers import ENGINE

WORKFLOW = (ENGINE / "workflow.md").read_text(encoding="utf-8")


class WorkflowTest(unittest.TestCase):
    def test_every_shell_command_goes_through_deck_py(self):
        blocks = re.findall(r"```sh\n(.*?)```", WORKFLOW, re.S)
        self.assertGreater(len(blocks), 2)
        for block in blocks:
            for line in block.strip().splitlines():
                self.assertTrue(line.strip().startswith("python3 <skill>/engine/deck.py "), line)

    def test_every_named_command_exists(self):
        sys_path = str(ENGINE)
        import sys
        sys.path.insert(0, sys_path)
        from deck import parser
        known = parser()._subparsers._group_actions[0].choices
        for name in re.findall(r"deck\.py ([a-z-]+)", WORKFLOW):
            if name != "command":
                self.assertIn(name, known)

    def test_the_phases_are_in_order(self):
        headings = re.findall(r"^## (\d)\. (.+)$", WORKFLOW, re.M)
        self.assertEqual([n for n, _ in headings], list("1234567"))
        for word, (_, title) in zip(("task", "brand", "Deck type", "Interview", "outline", "Build", "Verify"), headings):
            self.assertIn(word, title)

    def test_it_states_the_rules_the_decisions_require(self):
        for text in ("at most one", "one question at a time", "Build nothing until the user",
                     "data-deck-type", "deck.py inspect", "deck.py interview", "deck.py deck-types",
                     "deck.py brands", "Language and density are each asked once"):
            self.assertIn(text.lower(), " ".join(WORKFLOW.lower().split()), text)


class LayoutIdTest(unittest.TestCase):
    def test_every_base_layout_is_documented_under_its_id(self):
        layouts = json.loads((ENGINE / "layouts.json").read_text(encoding="utf-8"))["layouts"]
        self.assertEqual(len({item["id"] for item in layouts}), len(layouts))
        for item in layouts:
            doc = (ENGINE / item["doc"]).read_text(encoding="utf-8")
            self.assertIn(f"**Layout id**: `{item['id']}`", doc)


if __name__ == "__main__":
    unittest.main()

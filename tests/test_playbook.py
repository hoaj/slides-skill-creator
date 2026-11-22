import json
import shutil
import sys
import unittest

from tests.helpers import ENGINE, Workspace

sys.path.insert(0, str(ENGINE))

IDS = ["outcome", "audience", "takeaway", "arc", "evidence", "language", "length", "density",
       "setting", "theme", "classification", "header"]
SURVEY = """---
name: Survey report
when: Results from a survey
layouts: [kpi, chart]
---

## Interview
{rules}

## Outline
1. Cover
2. Key finding

## Content rules
- Show n on every chart.
"""


class PlaybookCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ws = Workspace()

    @classmethod
    def tearDownClass(cls):
        cls.ws.close()

    def setUp(self):
        self.pack = self.ws.add_pack("played")

    def tearDown(self):
        for pack in (self.ws.skill / "brands").iterdir():
            shutil.rmtree(str(pack))

    def brand_rules(self, text):
        self.ws.write(self.pack / "playbook" / "interview.md", text)

    def deck_type(self, rules="", type_id="survey", text=None):
        self.ws.write(self.pack / "playbook" / "deck-types" / f"{type_id}.md",
                      SURVEY.format(rules=rules) if text is None else text)

    def interview(self, deck_type=None, brand="played"):
        args = ["interview", "--brand", brand, "--json"]
        if deck_type:
            args += ["--deck-type", deck_type]
        result = self.ws.stdlib(*args)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(result.stdout)

    @staticmethod
    def question(merged, question_id):
        return next(q for q in merged["questions"] if q["id"] == question_id)

    def assert_stops(self, *expected):
        for command in (["check", "--brand", "played"],
                        ["build", "--brand", "played", str(self.ws.project / "nope.html"),
                         str(self.ws.project / "out.html")]):
            result = self.ws.stdlib(*command)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            output = result.stdout + result.stderr
            self.assertNotIn("Traceback", output)
            for text in expected:
                self.assertIn(text, output)


class InterviewTest(PlaybookCase):
    def test_the_engine_has_the_twelve_stable_ids_in_order(self):
        merged = self.interview()
        self.assertEqual([q["id"] for q in merged["questions"]], IDS)

    def test_groups(self):
        merged = self.interview()
        groups = {}
        for q in merged["questions"]:
            groups.setdefault(q["group"], []).append(q["id"])
        self.assertEqual(groups, {"Message": IDS[:5], "Framing": IDS[5:9], "Look": IDS[9:]})

    def test_language_and_density_are_asked_once(self):
        ids = [q["id"] for q in self.interview()["questions"]]
        self.assertEqual(ids.count("language"), 1)
        self.assertEqual(ids.count("density"), 1)
        for q in self.interview()["questions"]:
            if q["id"] not in ("language", "density"):
                self.assertNotIn("language", q["ask"].lower())

    def test_protected_markers(self):
        merged = self.interview()
        self.assertEqual([q["id"] for q in merged["questions"] if q["protected"]],
                         ["outcome", "audience", "takeaway"])
        self.assertEqual([s["id"] for s in merged["protectedSteps"]], ["outline", "key-terms", "approval"])
        self.assertTrue(all(s["protected"] for s in merged["protectedSteps"]))

    def test_theme_and_classification_options_come_from_the_pack(self):
        merged = self.interview()
        self.assertEqual(self.question(merged, "theme")["options"], ["White", "Silver", "Graphite"])
        self.assertIn("PRIVATE (default)", self.question(merged, "classification")["options"])

    def test_text_output_shows_markers_and_sections(self):
        result = self.ws.stdlib("interview", "--brand", "played")
        self.assertEqual(result.returncode, 0)
        for text in ("outcome  [protected]", "Fixed answers", "Protected steps", "approval  [protected]",
                     "Outline proposal", "Content rules", "Warnings"):
            self.assertIn(text, result.stdout)

    def test_unknown_brand_and_deck_type_stop(self):
        result = self.ws.stdlib("interview", "--brand", "nosuch")
        self.assertEqual(result.returncode, 1)
        self.deck_type()
        result = self.ws.stdlib("interview", "--brand", "played", "--deck-type", "nosuch")
        self.assertEqual(result.returncode, 1)
        self.assertIn("survey", result.stderr)

    def test_interview_validates_the_pack_first(self):
        self.ws.edit_manifest(self.pack, lambda m: m.pop("name"))
        result = self.ws.stdlib("interview", "--brand", "played")
        self.assertEqual(result.returncode, 1)
        self.assertIn("field 'name'", result.stderr)


class ActionTest(PlaybookCase):
    def test_guide_adds_help_and_options_first(self):
        self.brand_rules("## guide: audience\nSuggest the board.\n- The board\n- Partners\n")
        q = self.question(self.interview(), "audience")
        self.assertEqual(q["guide"], "Suggest the board.")
        self.assertEqual(q["options"][:2], ["The board", "Partners"])
        self.assertGreater(len(q["options"]), 2)

    def test_guide_works_on_a_protected_question(self):
        self.brand_rules("## guide: outcome\nFocus on the decision.\n")
        self.assertEqual(self.question(self.interview(), "outcome")["guide"], "Focus on the decision.")
        self.assertEqual(self.ws.check("played").returncode, 0)

    def test_after_adds_a_question_in_place(self):
        self.brand_rules("## after: audience\nid: volunteer-role\nAsk what role the volunteers have.\n")
        merged = self.interview()
        ids = [q["id"] for q in merged["questions"]]
        self.assertEqual(ids[ids.index("audience") + 1], "volunteer-role")
        q = self.question(merged, "volunteer-role")
        self.assertEqual((q["ask"], q["source"], q["group"]),
                         ("Ask what role the volunteers have.", "brand", "Message"))

    def test_several_after_rules_keep_their_order(self):
        self.brand_rules("## after: arc\nid: first\nFirst?\n\n## after: arc\nid: second\nSecond?\n")
        ids = [q["id"] for q in self.interview()["questions"]]
        self.assertEqual(ids[ids.index("arc"):ids.index("arc") + 3], ["arc", "first", "second"])

    def test_after_can_anchor_on_a_new_question_in_the_same_file(self):
        self.brand_rules("## after: first\nid: second\nSecond?\n\n## after: arc\nid: first\nFirst?\n")
        ids = [q["id"] for q in self.interview()["questions"]]
        self.assertEqual(ids[ids.index("arc"):ids.index("arc") + 3], ["arc", "first", "second"])

    def test_other_rules_can_name_a_question_the_file_adds(self):
        self.brand_rules("## guide: role\nHelp.\n\n## after: arc\nid: role\nWhich role?\n")
        self.assertEqual(self.question(self.interview(), "role")["guide"], "Help.")

    def test_replace_changes_the_question(self):
        self.brand_rules("## replace: arc\nAlways use: Finding, Meaning, Recommendation.\n")
        q = self.question(self.interview(), "arc")
        self.assertEqual(q["ask"], "Always use: Finding, Meaning, Recommendation.")
        self.assertEqual(q["options"], [])

    def test_replace_can_bring_its_own_options(self):
        self.brand_rules("## replace: density\nHow dense?\n- Sparse\n- Full\n")
        self.assertEqual(self.question(self.interview(), "density")["options"], ["Sparse", "Full"])

    def test_skip_fixes_the_answer(self):
        self.brand_rules("## skip: language\nanswer: da\n")
        merged = self.interview()
        q = self.question(merged, "language")
        self.assertTrue(q["fixed"])
        self.assertEqual(q["answer"], "da")
        self.assertEqual(merged["fixedAnswers"], {"language": "da"})
        text = self.ws.stdlib("interview", "--brand", "played").stdout
        self.assertIn("language  [fixed: da]", text)
        self.assertIn("language = da", text)


class ProtectionTest(PlaybookCase):
    def test_protected_questions_cannot_be_replaced_or_skipped(self):
        for question in ("outcome", "audience", "takeaway"):
            for rule in (f"## replace: {question}\nOther text.\n", f"## skip: {question}\nanswer: x\n"):
                with self.subTest(rule=rule):
                    self.brand_rules(rule)
                    self.assert_stops("playbook/interview.md", f"protected question '{question}'", "Fix:")

    def test_protected_steps_accept_no_rule_at_all(self):
        for step in ("outline", "key-terms", "approval"):
            for rule in (f"## guide: {step}\nText.\n", f"## after: {step}\nid: extra\nText.\n",
                         f"## replace: {step}\nText.\n", f"## skip: {step}\nanswer: x\n"):
                with self.subTest(rule=rule):
                    self.brand_rules(rule)
                    self.assert_stops(f"protected step '{step}'")

    def test_a_deck_type_cannot_remove_them_either(self):
        self.deck_type("### skip: takeaway\nanswer: x\n")
        self.assert_stops("playbook/deck-types/survey.md", "protected question 'takeaway'")
        self.deck_type("### replace: approval\nNo approval.\n")
        self.assert_stops("protected step 'approval'")

    def test_the_protected_steps_stay_in_every_merge(self):
        self.brand_rules("## skip: arc\nanswer: x\n")
        self.deck_type("### skip: evidence\nanswer: y\n")
        merged = self.interview("survey")
        self.assertEqual([s["id"] for s in merged["protectedSteps"]], ["outline", "key-terms", "approval"])
        for question in ("outcome", "audience", "takeaway"):
            self.assertFalse(self.question(merged, question)["fixed"])


class UnknownIdTest(PlaybookCase):
    def test_unknown_question_id_warns_and_is_ignored(self):
        for rule in ("## guide: nosuch\nHelp.\n", "## after: nosuch\nid: extra\nText.\n",
                     "## replace: nosuch\nText.\n", "## skip: nosuch\nanswer: x\n"):
            with self.subTest(rule=rule):
                self.brand_rules(rule)
                merged = self.interview()
                self.assertEqual([q["id"] for q in merged["questions"]], IDS)
                self.assertEqual(merged["fixedAnswers"], {})
                self.assertTrue(any("nosuch" in w for w in merged["warnings"]))
                result = self.ws.check("played")
                self.assertEqual(result.returncode, 0, result.stdout)
                self.assertIn("unknown question id 'nosuch'", result.stdout)

    def test_unknown_id_does_not_stop_the_build(self):
        self.brand_rules("## guide: nosuch\nHelp.\n")
        result = self.ws.build("played", out="played.html")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("nosuch", result.stderr)

    def test_unknown_layout_warns_and_is_ignored(self):
        self.deck_type(text=SURVEY.format(rules="").replace("[kpi, chart]", "[kpi, nosuch]"))
        merged = self.interview("survey")
        self.assertEqual(merged["layouts"]["recommended"], ["kpi"])
        self.assertTrue(any("unknown layout 'nosuch'" in w for w in merged["warnings"]))
        self.assertEqual(self.ws.check("played").returncode, 0)

    def test_a_deck_type_can_recommend_the_packs_own_layout(self):
        self.ws.write(self.pack / "layouts" / "band.html",
                      '<section class="slide layout-band" data-title="Band"></section>')
        self.deck_type(text=SURVEY.format(rules="").replace("[kpi, chart]", "[band, kpi]"))
        merged = self.interview("survey")
        self.assertEqual(merged["layouts"]["recommended"], ["band", "kpi"])
        self.assertEqual(merged["layouts"]["own"], ["band"])
        self.assertEqual(merged["warnings"], [])

    def test_unknown_deck_type_section_warns(self):
        self.deck_type(text=SURVEY.format(rules="") + "\n## Extra\nText\n")
        result = self.ws.check("played")
        self.assertEqual(result.returncode, 0)
        self.assertIn("section '## Extra'", result.stdout)


class FormatErrorTest(PlaybookCase):
    def test_skip_without_an_answer_stops(self):
        for rule in ("## skip: language\n", "## skip: language\nanswer:\n", "## skip: language\nThe text.\n"):
            with self.subTest(rule=rule):
                self.brand_rules(rule)
                self.assert_stops("playbook/interview.md", "rule 'skip: language'", "no answer")

    def test_duplicate_new_id_stops(self):
        self.brand_rules("## after: arc\nid: extra\nOne?\n\n## after: length\nid: extra\nTwo?\n")
        self.assert_stops("repeats the new id 'extra'")

    def test_new_id_equal_to_an_engine_question_stops(self):
        self.brand_rules("## after: arc\nid: language\nAgain?\n")
        self.assert_stops("adds the id 'language', which already exists")

    def test_new_id_equal_to_a_protected_step_stops(self):
        self.brand_rules("## after: arc\nid: approval\nAgain?\n")
        self.assert_stops("adds the id 'approval'")

    def test_a_deck_type_cannot_reuse_a_brand_question_id(self):
        self.brand_rules("## after: arc\nid: extra\nOne?\n")
        self.deck_type("### after: length\nid: extra\nTwo?\n")
        self.assert_stops("playbook/deck-types/survey.md", "adds the id 'extra'")

    def test_after_needs_an_id(self):
        self.brand_rules("## after: arc\nJust a question?\n")
        self.assert_stops("has no 'id:' line")

    def test_after_with_a_bad_id_stops(self):
        self.brand_rules("## after: arc\nid: Not Valid\nText?\n")
        self.assert_stops("invalid id 'Not Valid'")

    def test_rules_need_text(self):
        for rule in ("## guide: arc\n", "## replace: arc\n", "## after: arc\nid: extra\n"):
            with self.subTest(rule=rule):
                self.brand_rules(rule)
                self.assert_stops("has no text")

    def test_unknown_action_stops(self):
        for heading in ("## remove: arc", "## Notes", "## guide arc"):
            with self.subTest(heading=heading):
                self.brand_rules(heading + "\nText.\n")
                self.assert_stops("is not a Playbook action")

    def test_action_without_a_target_stops(self):
        self.brand_rules("## guide:\nText.\n")
        self.assert_stops("names no question id")

    def test_conflicting_rules_in_one_file_stop(self):
        for rules in ("## replace: arc\nOne.\n\n## skip: arc\nanswer: x\n",
                      "## guide: arc\nOne.\n\n## guide: arc\nTwo.\n"):
            with self.subTest(rules=rules):
                self.brand_rules(rules)
                self.assert_stops("conflicts with")

    def test_deck_type_needs_name_and_when(self):
        for missing, text in (("name", "---\nwhen: x\n---\n"), ("when", "---\nname: x\n---\n")):
            with self.subTest(missing=missing):
                self.deck_type(text=text)
                self.assert_stops(f"front matter '{missing}'")

    def test_deck_type_needs_front_matter(self):
        self.deck_type(text="## Outline\n1. Cover\n")
        self.assert_stops("front matter")

    def test_deck_type_id_format(self):
        self.deck_type(type_id="Bad_Id")
        self.assert_stops("Deck type id")

    def test_deck_type_with_a_repeated_section_stops(self):
        self.deck_type(text=SURVEY.format(rules="") + "\n## Outline\n1. Again\n")
        self.assert_stops("appears twice")

    def test_deck_type_rules_use_level_three_headings(self):
        self.deck_type("### remove: arc\nText.\n")
        self.assert_stops("playbook/deck-types/survey.md", "is not a Playbook action")


class PrecedenceTest(PlaybookCase):
    def test_deck_type_replace_beats_brand_replace(self):
        self.brand_rules("## replace: arc\nBrand arc.\n")
        self.deck_type("### replace: arc\nDeck type arc.\n")
        self.assertEqual(self.question(self.interview(), "arc")["ask"], "Brand arc.")
        self.assertEqual(self.question(self.interview("survey"), "arc")["ask"], "Deck type arc.")

    def test_deck_type_guide_beats_brand_guide(self):
        self.brand_rules("## guide: audience\nBrand help.\n- Brand option\n")
        self.deck_type("### guide: audience\nDeck type help.\n- Deck type option\n")
        q = self.question(self.interview("survey"), "audience")
        self.assertEqual(q["guide"], "Deck type help.")
        self.assertIn("Deck type option", q["options"])
        self.assertNotIn("Brand option", q["options"])

    def test_deck_type_skip_beats_brand_replace(self):
        self.brand_rules("## replace: arc\nBrand arc.\n")
        self.deck_type("### skip: arc\nanswer: Fixed arc\n")
        q = self.question(self.interview("survey"), "arc")
        self.assertTrue(q["fixed"])
        self.assertEqual(q["answer"], "Fixed arc")

    def test_deck_type_replace_beats_brand_skip(self):
        self.brand_rules("## skip: language\nanswer: da\n")
        self.deck_type("### replace: language\nAsk for the language again.\n")
        merged = self.interview("survey")
        q = self.question(merged, "language")
        self.assertFalse(q["fixed"])
        self.assertEqual(q["ask"], "Ask for the language again.")
        self.assertEqual(merged["fixedAnswers"], {})

    def test_deck_type_skip_changes_a_brand_skip_answer(self):
        self.brand_rules("## skip: language\nanswer: da\n")
        self.deck_type("### skip: language\nanswer: en\n")
        self.assertEqual(self.interview("survey")["fixedAnswers"], {"language": "en"})

    def test_deck_type_can_change_a_question_the_brand_added(self):
        self.brand_rules("## after: arc\nid: extra\nBrand question?\n")
        self.deck_type("### replace: extra\nDeck type question?\n")
        self.assertEqual(self.question(self.interview("survey"), "extra")["ask"], "Deck type question?")

    def test_without_a_deck_type_only_the_brand_applies(self):
        self.brand_rules("## replace: arc\nBrand arc.\n")
        self.deck_type("### replace: arc\nDeck type arc.\n")
        merged = self.interview()
        self.assertIsNone(merged["deckType"])
        self.assertEqual(merged["outlineProposal"], [])
        self.assertEqual(merged["contentRules"], [])


class DeckTypesTest(PlaybookCase):
    def test_lists_the_packs_deck_types(self):
        self.deck_type(type_id="survey")
        self.deck_type(type_id="review")
        result = self.ws.stdlib("deck-types", "--brand", "played", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([t["id"] for t in json.loads(result.stdout)], ["review", "survey"])
        text = self.ws.stdlib("deck-types", "--brand", "played").stdout
        self.assertIn("survey: Survey report. Use for: Results from a survey", text)

    def test_says_when_there_are_none(self):
        self.assertIn("no Deck types", self.ws.stdlib("deck-types", "--brand", "played").stdout)

    def test_outline_and_content_rules_reach_the_interview(self):
        self.deck_type()
        merged = self.interview("survey")
        self.assertEqual(merged["deckType"]["id"], "survey")
        self.assertEqual(merged["outlineProposal"], ["Cover", "Key finding"])
        self.assertEqual(merged["contentRules"], ["Show n on every chart."])
        self.assertEqual(merged["layouts"]["recommended"], ["kpi", "chart"])


class AcmeTest(PlaybookCase):
    def test_interview_merges_playbook_and_survey(self):
        self.ws.add_acme()
        merged = self.interview("survey", brand="acme")
        ids = [q["id"] for q in merged["questions"]]
        self.assertEqual(ids[ids.index("audience") + 1], "decision-owner")
        self.assertEqual(ids[ids.index("evidence") + 1], "sample-size")
        self.assertEqual(self.question(merged, "arc")["ask"], "Always use: Finding, Meaning, Recommendation.")
        self.assertEqual(self.question(merged, "decision-owner")["guide"], "Name the person who acts on the recommendations.")
        self.assertIn("The leadership team", self.question(merged, "audience")["options"])
        self.assertEqual(merged["fixedAnswers"], {"language": "en"})
        self.assertEqual(len(merged["outlineProposal"]), 5)
        self.assertEqual(len(merged["contentRules"]), 3)
        self.assertEqual(merged["layouts"]["recommended"], ["kpi", "chart", "quote", "scorecard"])
        self.assertEqual(merged["warnings"], [])

    def test_the_brand_alone_uses_its_own_arc(self):
        self.ws.add_acme()
        merged = self.interview(brand="acme")
        self.assertIn("Context, Choice, Consequence", self.question(merged, "arc")["ask"])
        self.assertNotIn("sample-size", [q["id"] for q in merged["questions"]])


if __name__ == "__main__":
    unittest.main()

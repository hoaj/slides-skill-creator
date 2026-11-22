"""Read a Brand pack's Playbook and merge it with the Engine's Interview.

Precedence is Engine, then `playbook/interview.md`, then one Deck type. The most specific rule
wins. Four actions exist: `guide`, `after`, `replace` and `skip`.

    * A rule that names an unknown question id or layout warns and is ignored.
    * A format error (`skip` without an answer, a duplicate new id) stops the build and `check`,
      and so does a rule that would remove a protected question or step.

Within one layer, `after` rules are applied first, so a rule can name a question the same file
adds. Across layers, a later `guide`, `replace` or `skip` overrides an earlier one on that id.
"""
import copy
import json
import re

from . import layouts
from .common import ENGINE, DeckError, display

ACTIONS = ("guide", "after", "replace", "skip")
QUESTION_ID = re.compile(r"^[a-z][a-z0-9-]*$")
DECK_TYPE_ID = re.compile(r"^[a-z0-9][a-z0-9-]*$")
FRONT_MATTER = re.compile(r"^---[ \t]*\n(.*?)\n---[ \t]*(?:\n|$)", re.S)
FIELD = re.compile(r"^([A-Za-z-]+)\s*:\s*(.*)$")
NUMBERED = re.compile(r"^\d+[.)]\s+(.*)$")
BULLET = re.compile(r"^[-*]\s+(.*)$")
DECK_TYPE_SECTIONS = ("interview", "outline", "content rules")
FORMAT_DOC = "See engine/docs/brand-pack.md."


def engine_interview():
    return json.loads((ENGINE / "interview.json").read_text(encoding="utf-8"))


def protected_question_ids():
    return [q["id"] for q in engine_interview()["questions"] if q["protected"]]


def protected_step_ids():
    return [s["id"] for s in engine_interview()["steps"]]


class Problems:
    """Errors and warnings as (file, where, problem, fix)."""

    def __init__(self):
        self.errors, self.warnings = [], []

    def error(self, path, where, problem, fix):
        self.errors.append((display(path), where, problem, fix))

    def warn(self, path, where, problem, fix):
        item = (display(path), where, problem, fix)
        if item not in self.warnings:
            self.warnings.append(item)


class Rule:
    def __init__(self, action, target, line):
        self.action, self.target, self.line = action, target, line
        self.new_id, self.answer = None, None
        self.text, self.options = "", []

    @property
    def where(self):
        return f"rule '{self.action}: {self.target}' (line {self.line})"


def _parse_body(rule, lines, path, problems):
    body = [(n, s.strip()) for n, s in lines if s.strip()]
    if rule.action == "after":
        hit = FIELD.match(body[0][1]) if body else None
        if not (hit and hit.group(1) == "id" and hit.group(2).strip()):
            problems.error(path, rule.where, "has no 'id:' line.",
                           "Start the rule's text with a line such as: id: my-question")
            return
        rule.new_id = hit.group(2).strip()
        if not QUESTION_ID.match(rule.new_id):
            problems.error(path, rule.where, f"has the invalid id '{rule.new_id}'.",
                           "Use lowercase letters, digits and hyphens.")
        body = body[1:]
    if rule.action == "skip":
        answers = [FIELD.match(s) for _, s in body]
        answers = [a.group(2).strip() for a in answers if a and a.group(1) == "answer"]
        if not (answers and answers[0]):
            problems.error(path, rule.where, "has no answer, so later steps would not know the value.",
                           "Add a line such as: answer: en")
            return
        rule.answer = answers[0]
        return
    text = []
    for _, s in body:
        bullet = BULLET.match(s)
        if bullet:
            rule.options.append(bullet.group(1).strip())
        else:
            text.append(s)
    rule.text = " ".join(text)
    if not rule.text and not rule.options:
        problems.error(path, rule.where, "has no text.", "Add the text the rule should use.")


def parse_rules(numbered_lines, level, path, problems):
    """The rules in `## action: id` (level 2) or `### action: id` (level 3) headings."""
    marker = "#" * level
    heading = re.compile(r"^" + marker + r"(?!#)\s*(.*)$")
    rules, current, body = [], None, []

    def flush():
        if current is not None:
            _parse_body(current, body, path, problems)
            rules.append(current)

    for n, line in numbered_lines:
        hit = heading.match(line)
        if not hit:
            if current is not None:
                body.append((n, line))
            continue
        flush()
        current, body = None, []
        title = hit.group(1).strip()
        action, sep, target = title.partition(":")
        action, target = action.strip().lower(), target.strip()
        if not sep or action not in ACTIONS:
            problems.error(path, f"heading '{marker} {title}' (line {n})",
                           f"is not a Playbook action. The actions are {', '.join(ACTIONS)}.",
                           f"Write it as: {marker} guide: <question id>. {FORMAT_DOC}")
            continue
        if not target:
            problems.error(path, f"heading '{marker} {title}' (line {n})", "names no question id.",
                           f"Write it as: {marker} {action}: <question id>")
            continue
        current = Rule(action, target, n)
    flush()
    return rules


def _check_conflicts(rules, path, problems):
    seen = {}
    for rule in rules:
        if rule.action == "after":
            continue
        for earlier in seen.get(rule.target, []):
            if earlier.action == rule.action or {earlier.action, rule.action} == {"replace", "skip"}:
                problems.error(path, rule.where,
                               f"conflicts with '{earlier.action}: {earlier.target}' on line {earlier.line}.",
                               "Keep one of the two rules.")
        seen.setdefault(rule.target, []).append(rule)


def _parse_front_matter(text, path, problems):
    meta = {}
    hit = FRONT_MATTER.match(text)
    if not hit:
        problems.error(path, "front matter", "is missing.",
                       "Start the file with --- then name: and when: lines and another ---.")
        return meta, 1
    for line in hit.group(1).splitlines():
        field = FIELD.match(line.strip())
        if field:
            meta[field.group(1)] = field.group(2).strip().strip("\"'")
    for key in ("name", "when"):
        if not meta.get(key):
            problems.error(path, f"front matter '{key}'", "is missing.",
                           f"Add a line such as: {key}: ...")
    return meta, text[:hit.end()].count("\n") + 1


def _layouts_list(value):
    value = (value or "").strip()
    if value.startswith("[") and value.endswith("]"):
        value = value[1:-1]
    return [v.strip().strip("\"'") for v in value.split(",") if v.strip()]


class DeckType:
    def __init__(self, type_id, path):
        self.id, self.path = type_id, path
        self.name, self.when = "", ""
        self.layouts, self.rules, self.outline, self.content_rules = [], [], [], []


def parse_deck_type(path, problems):
    type_id = path.stem
    deck_type = DeckType(type_id, path)
    if not DECK_TYPE_ID.match(type_id):
        problems.error(path, "Deck type id", f"'{type_id}' is not a valid id.",
                       "Name the file with lowercase letters, digits and hyphens.")
    text = path.read_text(encoding="utf-8")
    meta, first_line = _parse_front_matter(text, path, problems)
    deck_type.name, deck_type.when = meta.get("name", ""), meta.get("when", "")
    deck_type.layouts = _layouts_list(meta.get("layouts"))

    lines = list(enumerate(text.splitlines(), 1))[first_line - 1:]
    sections, name = {}, None
    for n, line in lines:
        hit = re.match(r"^##(?!#)\s*(.*)$", line)
        if hit:
            name = hit.group(1).strip().lower()
            if name not in DECK_TYPE_SECTIONS:
                problems.warn(path, f"section '## {hit.group(1).strip()}' (line {n})", "is unknown and ignored.",
                              f"Use one of: {', '.join(s.capitalize() for s in DECK_TYPE_SECTIONS)}.")
                name = None
            elif name in sections:
                problems.error(path, f"section '## {hit.group(1).strip()}' (line {n})", "appears twice.",
                               "Keep one section with this name.")
            else:
                sections[name] = []
            continue
        if name:
            sections[name].append((n, line))

    deck_type.rules = parse_rules(sections.get("interview", []), 3, path, problems)
    _check_conflicts(deck_type.rules, path, problems)
    for _, line in sections.get("outline", []):
        hit = NUMBERED.match(line.strip()) or BULLET.match(line.strip())
        if hit:
            deck_type.outline.append(hit.group(1).strip())
    for _, line in sections.get("content rules", []):
        hit = BULLET.match(line.strip()) or NUMBERED.match(line.strip())
        if hit:
            deck_type.content_rules.append(hit.group(1).strip())
    return deck_type


def deck_type_paths(pack):
    folder = pack.path("playbook", "deck-types")
    return sorted(folder.glob("*.md")) if folder.is_dir() else []


def load_rules(pack, problems):
    """(brand rules, {Deck type id: DeckType}), recording format problems."""
    brand = []
    path = pack.path("playbook", "interview.md")
    if path.is_file():
        lines = list(enumerate(path.read_text(encoding="utf-8").splitlines(), 1))
        brand = parse_rules(lines, 2, path, problems)
        _check_conflicts(brand, path, problems)
    types = {}
    for deck_path in deck_type_paths(pack):
        types[deck_path.stem] = parse_deck_type(deck_path, problems)
    return brand, types


def _apply_after(questions, rules, path, problems, source):
    """Insert `after` questions, repeating so one new question can anchor another."""
    pending = [r for r in rules if r.action == "after" and r.new_id]
    protected = protected_step_ids()
    last = {}
    for rule in pending:
        if rule.new_id in protected or any(q["id"] == rule.new_id for q in questions):
            problems.error(path, rule.where, f"adds the id '{rule.new_id}', which already exists.",
                           "Give the new question an id of its own.")
    pending = [r for r in pending
               if r.new_id not in protected and not any(q["id"] == r.new_id for q in questions)]
    ids = [r.new_id for r in pending]
    for rule in pending:
        if ids.count(rule.new_id) > 1:
            problems.error(path, rule.where, f"repeats the new id '{rule.new_id}'.",
                           "Give each new question an id of its own.")
    pending = [r for i, r in enumerate(pending) if r.new_id not in ids[:i]]
    while pending:
        placed = []
        for rule in pending:
            if rule.target in protected:
                problems.error(path, rule.where, f"targets the protected step '{rule.target}'.",
                               "A Playbook cannot change the outline, the key terms or the approval.")
                placed.append(rule)
                continue
            anchor = last.get(rule.target, rule.target)
            index = next((i for i, q in enumerate(questions) if q["id"] == anchor), None)
            if index is None:
                continue
            anchor_q = next(q for q in questions if q["id"] == rule.target)
            questions.insert(index + 1, {
                "id": rule.new_id, "group": anchor_q["group"], "protected": False, "ask": rule.text,
                "options": list(rule.options), "guide": "", "fixed": False, "answer": None,
                "source": source})
            last[rule.target] = rule.new_id
            placed.append(rule)
        if not placed:
            break
        pending = [r for r in pending if r not in placed]
    for rule in pending:
        problems.warn(path, rule.where, f"names the unknown question id '{rule.target}' and is ignored.",
                      f"Use one of the ids in `deck.py interview`. {FORMAT_DOC}")


def _apply_other(questions, rules, path, problems, source):
    protected_steps = protected_step_ids()
    for rule in rules:
        if rule.action == "after":
            continue
        if rule.target in protected_steps:
            problems.error(path, rule.where, f"targets the protected step '{rule.target}'.",
                           "A Playbook cannot change the outline, the key terms or the approval.")
            continue
        question = next((q for q in questions if q["id"] == rule.target), None)
        if question is None:
            problems.warn(path, rule.where, f"names the unknown question id '{rule.target}' and is ignored.",
                          f"Use one of the ids in `deck.py interview`. {FORMAT_DOC}")
            continue
        if rule.action in ("replace", "skip") and question["protected"]:
            verb = "replaced" if rule.action == "replace" else "skipped"
            problems.error(path, rule.where, f"would remove the protected question '{rule.target}', "
                           f"which cannot be {verb}.",
                           "Use guide or after on this question instead.")
            continue
        if rule.action == "guide":
            question["guide"] = rule.text
            question["guideOptions"] = list(rule.options)
        elif rule.action == "replace":
            question.update(ask=rule.text, options=list(rule.options), fixed=False, answer=None,
                            guide="", guideOptions=[], replacedBy=source)
        else:
            question.update(fixed=True, answer=rule.answer, skippedBy=source)


def _base_questions(pack):
    questions = copy.deepcopy(engine_interview()["questions"])
    for q in questions:
        q.update(guide="", fixed=False, answer=None, source="engine")
        if q["id"] == "theme":
            themes = pack.manifest.get("themes")
            q["options"] = [t["label"] for t in themes if isinstance(t, dict) and isinstance(t.get("label"), str)
                            ] if isinstance(themes, list) else []
        elif q["id"] == "classification":
            default = pack.manifest.get("defaultClassification")
            labels = pack.manifest.get("classifications")
            q["options"] = [f"{c} (default)" if c == default else c
                            for c in labels if isinstance(c, str)] if isinstance(labels, list) else []
    return questions


def _finish(question):
    extra = question.pop("guideOptions", [])
    question["options"] = extra + [o for o in question["options"] if o not in extra]
    if question["fixed"]:
        question["options"] = []
    return question


def merge(pack, type_id=None):
    """(the merged Interview as plain data, Problems). Unknown `type_id` is a DeckError."""
    problems = Problems()
    brand, types = load_rules(pack, problems)
    deck_type = None
    if type_id:
        deck_type = types.get(type_id)
        if deck_type is None:
            available = ", ".join(sorted(types)) or "(none)"
            raise DeckError(f"unknown Deck type '{type_id}' for Brand pack '{pack.slug}'. "
                            f"Available: {available}")
    questions = _base_questions(pack)
    interview_path = pack.path("playbook", "interview.md")
    _apply_after(questions, brand, interview_path, problems, "brand")
    _apply_other(questions, brand, interview_path, problems, "brand")
    layers_for_layouts = []
    if deck_type:
        _apply_after(questions, deck_type.rules, deck_type.path, problems, "deck-type")
        _apply_other(questions, deck_type.rules, deck_type.path, problems, "deck-type")
        known = set(layouts.known_ids(pack))
        for layout in deck_type.layouts:
            if layout in known:
                layers_for_layouts.append(layout)
            else:
                problems.warn(deck_type.path, f"layouts: {layout}",
                              f"names the unknown layout '{layout}' and is ignored.",
                              f"Use one of: {', '.join(layouts.known_ids(pack))}.")
    questions = [_finish(q) for q in questions]
    steps = copy.deepcopy(engine_interview()["steps"])
    for step in steps:
        step["protected"] = True
    result = {
        "brand": {"slug": pack.slug, "name": pack.manifest.get("name", pack.slug)},
        "deckType": {"id": deck_type.id, "name": deck_type.name, "when": deck_type.when} if deck_type else None,
        "questions": questions,
        "fixedAnswers": {q["id"]: q["answer"] for q in questions if q["fixed"]},
        "protectedSteps": steps,
        "outlineProposal": deck_type.outline if deck_type else [],
        "contentRules": deck_type.content_rules if deck_type else [],
        "layouts": {"recommended": layers_for_layouts, "base": layouts.base_ids(), "own": layouts.own_ids(pack)},
        "warnings": [_as_text(w) for w in problems.warnings],
    }
    return result, problems


def _as_text(item):
    file, where, problem, fix = item
    return f"{file}: {where} {problem} Fix: {fix}"


def check(pack):
    """Every Playbook problem: the brand rules alone, and with each Deck type."""
    combined = Problems()
    _record(combined, merge(pack)[1])
    for type_id in sorted(p.stem for p in deck_type_paths(pack)):
        _record(combined, merge(pack, type_id)[1])
    return combined


def _record(combined, problems):
    for item in problems.errors:
        if item not in combined.errors:
            combined.errors.append(item)
    for item in problems.warnings:
        if item not in combined.warnings:
            combined.warnings.append(item)


def list_deck_types(pack):
    """[{id, name, when}] for the pack's Deck types, sorted by id."""
    problems = Problems()
    out = []
    for path in deck_type_paths(pack):
        deck_type = parse_deck_type(path, problems)
        out.append({"id": deck_type.id, "name": deck_type.name, "when": deck_type.when})
    return out


def render(result):
    """The merged Interview as the text an agent reads."""
    brand = result["brand"]
    deck_type = result["deckType"]
    lines = [f"Interview for {brand['name']} ({brand['slug']})",
             f"Deck type: {deck_type['id']} ({deck_type['name']})" if deck_type else "Deck type: none",
             "", "Ask one question at a time, with a recommended answer. Do not ask what the "
             "material already answers, and do not ask a question marked fixed.", ""]
    group, number = None, 0
    for q in result["questions"]:
        if q["group"] != group:
            group = q["group"]
            lines.append(group)
        number += 1
        marks = []
        if q["protected"]:
            marks.append("protected")
        if q["fixed"]:
            marks.append(f"fixed: {q['answer']}")
        if q["source"] != "engine":
            marks.append(f"added by {q['source']}")
        mark = f"  [{'; '.join(marks)}]" if marks else ""
        lines.append(f"  {number}. {q['id']}{mark}")
        if q["fixed"]:
            continue
        lines.append(f"     {q['ask']}")
        if q["guide"]:
            lines.append(f"     Guide: {q['guide']}")
        if q["options"]:
            lines.append(f"     Options: {'; '.join(q['options'])}")
    lines.extend(["", "Fixed answers"])
    lines.extend(f"  {k} = {v}" for k, v in result["fixedAnswers"].items())
    if not result["fixedAnswers"]:
        lines.append("  (none)")
    lines.extend(["", "Protected steps (a Playbook cannot change these)"])
    for step in result["protectedSteps"]:
        lines.append(f"  {step['id']}  [protected]: {step['what']}")
    lines.extend(["", "Outline proposal (the user must still approve the outline)"])
    lines.extend(f"  {i}. {item}" for i, item in enumerate(result["outlineProposal"], 1))
    if not result["outlineProposal"]:
        lines.append("  (none: write the outline from the answers)")
    lines.extend(["", "Content rules"])
    lines.extend(f"  - {rule}" for rule in result["contentRules"])
    if not result["contentRules"]:
        lines.append("  (none)")
    found = result["layouts"]
    lines.extend(["", "Layouts"])
    if found["recommended"]:
        lines.append(f"  recommended: {', '.join(found['recommended'])}")
    lines.append(f"  base: {', '.join(found['base'])}")
    lines.append(f"  own: {', '.join(found['own']) if found['own'] else '(none)'}")
    lines.extend(["", "Warnings"])
    lines.extend(f"  - {w}" for w in result["warnings"])
    if not result["warnings"]:
        lines.append("  (none)")
    return "\n".join(lines)

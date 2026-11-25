"""Paths, errors and JSON helpers shared by the Generator's tools.

The Generator is this repo: the skill lives in `skills/slides-skill-creator/`, and the Engine and
the Starter files sit at the repo root, two folders up from the skill.
"""
import json
import pathlib
import sys

TOOLS = pathlib.Path(__file__).resolve().parent.parent
GEN = TOOLS.parent
ROOT = GEN.parent.parent
ENGINE = ROOT / "engine"
STARTER = ROOT / "starter"

if not (ENGINE / "deck.py").is_file() or not (STARTER / "render.py").is_file():
    sys.exit(f"error: the Generator is incomplete: {ENGINE} and {STARTER} must exist next to "
             "skills/. Reinstall slides-skill-creator.")

# The Engine's `lib` package and the Starter renderer. The Generator's own package is `genlib`,
# so the two never collide.
for path in (str(ENGINE), str(STARTER)):
    if path not in sys.path:
        sys.path.insert(0, path)

SLUG = r"[a-z0-9]+(?:-[a-z0-9]+)*"
HIDDEN_PACK = "plain"


class GenError(Exception):
    """A problem the maintainer or the agent can fix. gen.py prints it as JSON and exits 1."""

    def __init__(self, message, **details):
        super().__init__(message)
        self.details = details


def read_json(path):
    path = pathlib.Path(path)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise GenError(f"file not found: {path}")
    except ValueError as e:
        raise GenError(f"{path}: not valid JSON ({e})")


def dump_json(data):
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def write_json(path, data):
    pathlib.Path(path).write_bytes(dump_json(data).encode("utf-8"))


def write_text(path, text):
    """Write UTF-8 with LF line endings on every OS."""
    pathlib.Path(path).write_bytes(text.encode("utf-8"))


def need(module, install):
    """Import an optional dependency, or stop with the command that installs it."""
    import importlib
    try:
        return importlib.import_module(module)
    except ImportError:
        raise GenError(f"this tool needs {module}. Install it with: python3 -m pip install {install}")

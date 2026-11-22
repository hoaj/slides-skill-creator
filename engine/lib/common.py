"""Paths and errors shared by the Engine's commands."""
import pathlib

ENGINE = pathlib.Path(__file__).resolve().parent.parent
SKILL = ENGINE.parent
RUNTIME = ENGINE / "runtime"
BRANDS = SKILL / "brands"
FIXTURES = ENGINE / "fixtures"


class DeckError(Exception):
    """A problem the user can fix. deck.py prints it and exits with status 1."""


def display(path):
    """A path relative to the skill folder when it is inside it, for error messages."""
    path = pathlib.Path(path)
    try:
        return path.resolve().relative_to(SKILL).as_posix()
    except ValueError:
        return str(path)


def ensure_outside_skill(path, what="output"):
    """Stop when generated output would land inside the skill folder."""
    resolved = pathlib.Path(path).resolve()
    if resolved == SKILL or SKILL in resolved.parents:
        raise DeckError(f"{what} must not go into the skill folder: {resolved}. "
                        "Write it to the user's project instead.")
    return resolved

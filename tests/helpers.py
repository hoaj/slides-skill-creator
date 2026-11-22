"""A throwaway Slides skill holding a copy of the Engine, so tests never touch the repo."""
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile

REPO = pathlib.Path(__file__).resolve().parent.parent
ENGINE = REPO / "engine"
TEMPLATE = REPO / "tests" / "fixtures" / "smoke.template.html"


class Workspace:
    """<root>/skill/engine, <root>/skill/brands and a separate <root>/project."""

    def __init__(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self._tmp.name).resolve()
        self.skill = self.root / "skill"
        self.engine = self.skill / "engine"
        self.project = self.root / "project"
        self.project.mkdir()
        shutil.copytree(ENGINE, self.engine, ignore=shutil.ignore_patterns("__pycache__"))
        (self.skill / "brands").mkdir()

    def close(self):
        self._tmp.cleanup()

    def deck(self, *args, python_flags=(), cwd=None):
        """Run deck.py from the project folder, by default on the bare standard library."""
        cmd = [sys.executable, *python_flags, str(self.engine / "deck.py"), *args]
        return subprocess.run(cmd, cwd=str(cwd or self.project), capture_output=True, text=True)

    def stdlib(self, *args, cwd=None):
        """-I -S: no site-packages, so only the standard library can be imported."""
        return self.deck(*args, python_flags=("-I", "-S"), cwd=cwd)

    def add_pack(self, slug, edit=None):
        """Copy the plain pack to brands/<slug>, optionally editing its manifest."""
        pack = self.skill / "brands" / slug
        if pack.exists():
            shutil.rmtree(str(pack))
        shutil.copytree(self.engine / "fixtures" / "plain", pack)
        manifest = json.loads((pack / "brand.json").read_text(encoding="utf-8"))
        manifest["slug"] = slug
        manifest["name"] = slug.title()
        if edit:
            edit(manifest)
        (pack / "brand.json").write_text(json.dumps(manifest), encoding="utf-8")
        return pack

    def build(self, brand="plain", template=TEMPLATE, out="deck.html"):
        return self.stdlib("build", "--brand", brand, str(template), str(self.project / out))

    def built(self, out="deck.html"):
        return (self.project / out).read_text(encoding="utf-8")

    def deck_brand(self, out="deck.html"):
        """The window.DeckBrand object of a built deck."""
        html = self.built(out)
        start = html.index("window.DeckBrand = ") + len("window.DeckBrand = ")
        end = html.index(";\n", start)
        return json.loads(html[start:end])

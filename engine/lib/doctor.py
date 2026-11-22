"""Check this machine and the Brand packs, or print a redacted environment report.

`doctor` exits 0 when everything required is present. `doctor --report` prints only
versions, OS, browser availability and dependency status for a bug report: no deck content,
no Brand pack names and no paths from the home directory.
"""
import importlib.util
import os
import pathlib
import platform
import shutil
import sys

from . import packs
from .common import BRANDS, ENGINE, RUNTIME, DeckError

try:
    from importlib.metadata import PackageNotFoundError, version as package_version
except ImportError:  # pragma: no cover - Python 3.8+ has it; deck.py enforces that
    package_version = None
    PackageNotFoundError = Exception

ENGINE_FILES = ("viewport-base.css", "widgets.css", "chrome.css", "widgets.js",
                "deck-controller.js", "contrast-guard.js", "edit-icons.js",
                "pptx-export.js", "pptxgen.bundle.js")
# (import name, package name, what it is for)
OPTIONAL = (("pptx", "python-pptx", "export-pptx and extract-pptx"),
            ("playwright", "playwright", "export-pptx"),
            ("fontTools", "fonttools", "PowerPoint font mapping for packs with font files"),
            ("brotli", "brotli", "reading woff2 font files"),
            ("numpy", "numpy", "compare"),
            ("fitz", "pymupdf", "compare"),
            ("PIL", "pillow", "compare"))
BROWSERS = (("Google Chrome", "Google Chrome.app", r"Google\Chrome\Application\chrome.exe",
             ("google-chrome", "google-chrome-stable")),
            ("Microsoft Edge", "Microsoft Edge.app", r"Microsoft\Edge\Application\msedge.exe",
             ("microsoft-edge", "microsoft-edge-stable")),
            ("Brave", "Brave Browser.app", r"BraveSoftware\Brave-Browser\Application\brave.exe",
             ("brave-browser",)),
            ("Chromium", "Chromium.app", r"Chromium\Application\chrome.exe",
             ("chromium", "chromium-browser")))


def os_name():
    if sys.platform.startswith("darwin"):
        return f"macOS {platform.mac_ver()[0]} ({platform.machine()})"
    if sys.platform.startswith("win"):
        return f"Windows {platform.release()} ({platform.machine()})"
    return f"{platform.system()} {platform.release()} ({platform.machine()})"


def redact_home(text):
    home = str(pathlib.Path.home())
    return text.replace(home, "~") if home and home != os.sep else text


def engine_version():
    try:
        return (ENGINE / "VERSION").read_text(encoding="utf-8").strip()
    except OSError:
        return "unknown"


def browsers():
    """Names of the Chromium-family browsers found on this machine."""
    found = []
    for name, mac_app, win_exe, linux_cmds in BROWSERS:
        if sys.platform.startswith("darwin"):
            there = any((root / mac_app).is_dir() for root in
                        (pathlib.Path("/Applications"), pathlib.Path.home() / "Applications"))
        elif sys.platform.startswith("win"):
            roots = [os.environ.get(k) for k in ("ProgramFiles", "ProgramFiles(x86)", "LocalAppData")]
            there = any(root and (pathlib.Path(root) / win_exe).is_file() for root in roots)
        else:
            there = any(shutil.which(cmd) for cmd in linux_cmds)
        if there:
            found.append(name)
    return found


def dependency(module, package):
    """The installed version, "installed" when unknown, or None."""
    if importlib.util.find_spec(module) is None:
        return None
    try:
        return package_version(package) if package_version else "installed"
    except PackageNotFoundError:
        return "installed"


def missing_engine_files():
    return [f for f in ENGINE_FILES if not (RUNTIME / f).is_file()]


def pack_status():
    """{slug: error or None} for every pack in <skill>/brands, plus the hidden pack."""
    slugs = [packs.HIDDEN_PACK]
    if BRANDS.is_dir():
        slugs += sorted(p.name for p in BRANDS.iterdir()
                        if (p / "brand.json").is_file() and p.name != packs.HIDDEN_PACK)
    status = {}
    for slug in slugs:
        try:
            packs.load(slug)
            status[slug] = None
        except DeckError as e:
            status[slug] = str(e)
    return status


def report():
    status = pack_status()
    deps = "\n".join(f"- {package}: {dependency(module, package) or 'not installed'}"
                     for module, package, _ in OPTIONAL)
    found = browsers()
    missing = missing_engine_files()
    valid = sum(1 for error in status.values() if error is None)
    text = (
        "## Environment\n"
        f"- Engine: {engine_version()}\n"
        f"- Python: {platform.python_version()} ({platform.python_implementation()})\n"
        f"- OS: {os_name()}\n"
        f"- Browsers: {', '.join(found) if found else 'none found'}\n"
        f"- Engine files: {len(ENGINE_FILES) - len(missing)}/{len(ENGINE_FILES)} present\n"
        "- Engine files edited locally: unknown (no engine.lock)\n"
        f"- Brand packs: {len(status) - 1} plus the hidden test pack, {valid} of {len(status)} valid\n"
        "\n## Optional dependencies\n"
        f"{deps}\n"
    )
    print(redact_home(text), end="")
    return 0


def tag(ok):
    return "[ OK ]" if ok is True else ("[WARN]" if ok == "warn" else "[MISS]")


def run(report_only=False):
    if report_only:
        return report()
    problems = 0
    print("Engine doctor")
    print(f"Engine: {engine_version()}")
    print(f"OS:     {os_name()}")
    print(f"Python: {platform.python_version()}\n")

    print("Required")
    ok = sys.version_info >= (3, 8)
    print(f"  {tag(ok)} Python 3.8 or newer")
    problems += 0 if ok else 1
    missing = missing_engine_files()
    print(f"  {tag(not missing)} Engine files ({len(ENGINE_FILES) - len(missing)}/{len(ENGINE_FILES)})")
    for name in missing:
        problems += 1
        print(f"         missing: engine/runtime/{name}")

    print("\nOptional")
    for module, package, purpose in OPTIONAL:
        v = dependency(module, package)
        print(f"  {tag(True if v else 'warn')} {package}{' ' + v if v else ''}: {purpose}")
        if not v:
            print(f"         install: {sys.executable or 'python3'} -m pip install {package}")
    found = browsers()
    print(f"  {tag(True if found else 'warn')} browser: {', '.join(found) if found else 'none found'}")
    if not found:
        print("         install Google Chrome, or run: python3 -m playwright install chromium")

    print("\nBrand packs")
    for slug, error in pack_status().items():
        shown = f"{slug} (hidden test pack)" if slug == packs.HIDDEN_PACK else slug
        print(f"  {tag(error is None)} {shown}")
        if error:
            problems += 1
            for line in error.splitlines():
                print(f"         {line.strip()}")

    print()
    print("Summary: ready to build decks." if not problems
          else f"Summary: {problems} required item(s) need attention.")
    return 1 if problems else 0

"""Show a built deck in the browser, reusing the tab that already shows it.

Opening the file again would put a second tab next to the first on every rebuild. This
looks for a tab that already shows the deck and reloads it in place (the deck keeps its
slide), and opens a new tab only when no browser shows the deck yet.

Tab reuse works on macOS with Google Chrome, Microsoft Edge, Brave and Safari, through
AppleScript. The first run asks once for permission to control the browser (System
Settings > Privacy & Security > Automation). If that is declined, a new tab opens and the
message says so. On other systems the deck opens once; reload that tab after a rebuild.
"""
import pathlib
import platform
import subprocess
import webbrowser

# Browsers with an AppleScript tab model, in the order they are searched.
CHROMIUM = ("Google Chrome", "Microsoft Edge", "Brave Browser")
SAFARI = "Safari"


def _osascript(script):
    """Run AppleScript; return (ok, stdout)."""
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    return r.returncode == 0, (r.stdout.strip() or r.stderr.strip())


def _running(app):
    ok, out = _osascript(f'application "{app}" is running')
    return ok and out == "true"


def _as_str(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _match(var, base):
    """AppleScript condition: the tab shows this file, with or without #/N or ?query."""
    b = _as_str(base)
    return (f'({var} is {b} or {var} starts with ({b} & "#") '
            f'or {var} starts with ({b} & "?"))')


def _reload_script(app, base, target):
    """AppleScript that reloads the first tab showing `base`; prints reloaded/none."""
    t = _as_str(target) if target else None
    if app == SAFARI:
        nav = f"set URL of t to {t}" if t else "set URL of t to (URL of t)"
        return f'''
tell application "{app}"
  repeat with w in windows
    repeat with t in tabs of w
      set u to URL of t
      if u is not missing value and {_match("u", base)} then
        {nav}
        set current tab of w to t
        return "reloaded"
      end if
    end repeat
  end repeat
  return "none"
end tell'''
    nav = f"set URL of t to {t}\n        " if t else ""
    return f'''
tell application "{app}"
  repeat with w in windows
    set i to 0
    repeat with t in tabs of w
      set i to i + 1
      set u to URL of t
      if {_match("u", base)} then
        {nav}tell t to reload
        set active tab index of w to i
        return "reloaded"
      end if
    end repeat
  end repeat
  return "none"
end tell'''


def reload_existing_tab(base, target=None):
    """macOS only: reload a browser tab showing `base`. Returns (app or None, note)."""
    note = ""
    for app in CHROMIUM + (SAFARI,):
        if not _running(app):
            continue
        ok, out = _osascript(_reload_script(app, base, target))
        if ok and out == "reloaded":
            return app, ""
        if not ok and ("-1743" in out or "not allowed" in out.lower()):
            note = (f"note: not allowed to control {app}; allow it under System Settings > "
                    "Privacy & Security > Automation to reuse the tab next time.")
    return None, note


def open_deck(path, slide=None):
    """Reload the tab showing the deck, or open it. Returns a one-line message."""
    path = pathlib.Path(path).resolve()
    base = path.as_uri()
    target = f"{base}#/{slide}" if slide else None
    if platform.system() == "Darwin":
        app, note = reload_existing_tab(base, target)
        if app:
            return f"Reloaded {path.name} in its {app} tab."
        subprocess.run(["open", target or base] if target else ["open", str(path)], check=False)
        return f"Opened {path.name} in a new tab." + (f"\n{note}" if note else "")
    webbrowser.open(target or base)
    return (f"Opened {path.name}. After the next rebuild, reload that tab "
            "(the deck keeps its slide); tab reuse is macOS-only.")

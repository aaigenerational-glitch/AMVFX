"""AMVFX in-app updater.

Checks the public GitHub repo for a newer VERSION and, on request,
updates the installed app **in place** - no reinstall. Only the app
payload is overwritten; the private ``.venv`` and any user outputs are
never touched, so models and settings survive an update.

Stdlib only (urllib + zipfile), so it works in the app, the CLI and the
installer alike:

    python -m amvfx.updater --check
    python -m amvfx.updater --apply
"""
import io
import json
import os
import shutil
import sys
import tempfile
import urllib.request
import zipfile

REPO = "aaigenerational-glitch/AMVFX"
BRANCH = "main"
VERSION_URL = (f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/VERSION")
ZIPBALL_URL = f"https://codeload.github.com/{REPO}/zip/refs/heads/{BRANCH}"
COMMITS_URL = (f"https://api.github.com/repos/{REPO}/commits"
               f"?sha={BRANCH}&per_page=")

# Files/dirs an update is allowed to overwrite (mirrors the installer).
UPDATE_ITEMS = ["app.py", "launch_amvfx.py", "amvfx", "requirements.txt",
                "requirements-lite.txt", "LICENSE", "README.md", "MODELS.md",
                "VERSION", "AE", "Blender Export", "blender", "docs",
                "examples", "tests", "installer"]
IGNORE = shutil.ignore_patterns(".git", ".venv", "__pycache__", "*.pyc",
                                "*.zip", ".DS_Store")
TIMEOUT = 30


def _fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "AMVFX-Updater"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return resp.read()


def parse_version(text):
    parts = []
    for chunk in str(text).strip().split("."):
        digits = "".join(c for c in chunk if c.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts) or (0,)


def is_newer(remote, local):
    return parse_version(remote) > parse_version(local)


def local_version(app_dir):
    vf = os.path.join(app_dir, "VERSION")
    if os.path.isfile(vf):
        with open(vf) as f:
            v = f.read().strip()
            if v:
                return v
    try:
        from amvfx import __version__
        return __version__
    except Exception:
        return "0.0.0"


def remote_version():
    return _fetch(VERSION_URL).decode("utf-8", "replace").strip()


def recent_commits(limit=5):
    """Return the latest commits on main as [{sha, message, date}].

    Uses the public GitHub REST commits endpoint (unauthenticated:
    60 requests/hour, and "Check for updates" makes one call, so this
    is well inside the budget). Any failure — offline, rate-limited,
    unexpected payload — returns [] instead of raising: the update
    check must never fail because the changelog could not be fetched.
    """
    try:
        n = max(1, min(int(limit), 20))
    except (TypeError, ValueError):
        n = 5
    try:
        raw = _fetch(COMMITS_URL + str(n))
        data = json.loads(raw.decode("utf-8", "replace"))
    except Exception:
        return []
    commits = []
    if isinstance(data, list):
        for c in data:
            if not isinstance(c, dict):
                continue
            inner = c.get("commit") or {}
            msg = inner.get("message") or ""
            commits.append({
                "sha": (c.get("sha") or "")[:7],
                "message": msg.splitlines()[0].strip() if msg else "",
                "date": (inner.get("committer") or {}).get("date", ""),
            })
    return commits


def check_for_update(app_dir):
    """Return {current, latest, update_available} or {error: ...}."""
    current = local_version(app_dir)
    try:
        latest = remote_version()
    except Exception as exc:
        return {"current": current, "latest": None,
                "update_available": False, "error": str(exc)}
    available = is_newer(latest, current)
    return {"current": current, "latest": latest,
            "update_available": available, "error": None,
            "recent_commits": recent_commits() if available else []}


def apply_update(app_dir, source=None, log=print):
    """Download the latest repo ZIP and overwrite the payload in place.

    `source` may be a local .zip path (used by the tests); default is the
    GitHub zipball of the main branch. Returns the new version string.
    """
    app_dir = os.path.abspath(app_dir)
    if source and os.path.isfile(source):
        with open(source, "rb") as f:
            data = f.read()
    else:
        log("Downloading the latest AMVFX from GitHub...")
        data = _fetch(source or ZIPBALL_URL)
    work = tempfile.mkdtemp(prefix="amvfx_update_")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            z.extractall(work)
        roots = [d for d in os.listdir(work)
                 if os.path.isdir(os.path.join(work, d))]
        if len(roots) != 1:
            raise RuntimeError("Unexpected update archive layout.")
        src_root = os.path.join(work, roots[0])
        new_version = local_version(src_root)
        for item in UPDATE_ITEMS:
            src = os.path.join(src_root, item)
            dst = os.path.join(app_dir, item)
            if os.path.isdir(src):
                if os.path.exists(dst):
                    shutil.rmtree(dst)
                shutil.copytree(src, dst, ignore=IGNORE)
            elif os.path.isfile(src):
                shutil.copy2(src, dst)
        log(f"Updated AMVFX in place -> v{new_version}. "
            "Restart the app to use it.")
        return new_version
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if "--app-dir" in argv:
        i = argv.index("--app-dir")
        app_dir = argv[i + 1]
    if "--apply" in argv:
        info = check_for_update(app_dir)
        if info.get("error"):
            print(f"Update check failed: {info['error']}")
            return 1
        if not info["update_available"]:
            print(f"Already up to date (v{info['current']}).")
            return 0
        print(f"Updating v{info['current']} -> v{info['latest']} ...")
        apply_update(app_dir)
        return 0
    info = check_for_update(app_dir)
    if info.get("error"):
        print(f"Could not check for updates: {info['error']}")
        return 1
    if info["update_available"]:
        print(f"Update available: v{info['current']} -> v{info['latest']} "
              "(run with --apply to install it)")
        for c in info.get("recent_commits") or []:
            print(f"  {c['sha']} {c['message']}")
    else:
        print(f"AMVFX v{info['current']} is up to date.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

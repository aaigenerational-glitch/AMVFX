"""Job history: remember recent generation jobs and list them under the
generator, so a user can see what they ran, with which profile and
passes, and where the output went.

Stored as JSON at ~/.amvfx/history.json (user home, so app updates never
wipe it). Pure stdlib, no model dependency. History must never break a
generation job: every write is best-effort and swallows OSError.
"""
import json
import os
from datetime import datetime

MAX_ENTRIES = 20
HISTORY_DIRNAME = ".amvfx"
HISTORY_FILENAME = "history.json"


def default_history_path():
    return os.path.join(os.path.expanduser("~"),
                        HISTORY_DIRNAME, HISTORY_FILENAME)


def load_history(path=None):
    """Return the recorded jobs, newest first; [] when none or unreadable."""
    path = path or default_history_path()
    try:
        with open(path, "r") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return []
    if not isinstance(data, list):
        return []
    entries = [e for e in data if isinstance(e, dict)]
    entries.reverse()
    return entries


def record_job(input_name, profile, passes, output_dir, frames,
               resolution, zip_path=None, path=None, when=None):
    """Append one job to the history file (newest kept, capped at
    MAX_ENTRIES). Returns the entry dict, or None if it could not be
    written."""
    entry = {
        "time": (when or datetime.now().astimezone()).isoformat(
            timespec="seconds"),
        "input": os.path.basename(input_name) if input_name else "",
        "profile": profile,
        "passes": list(passes),
        "frames": int(frames),
        "resolution": f"{resolution[0]}x{resolution[1]}",
        "output": output_dir,
        "zip": zip_path or "",
    }
    path = path or default_history_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        entries = []
        try:
            with open(path, "r") as f:
                data = json.load(f)
            if isinstance(data, list):
                entries = [e for e in data if isinstance(e, dict)]
        except (OSError, ValueError):
            entries = []
        entries.append(entry)
        entries = entries[-MAX_ENTRIES:]
        tmp = path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(entries, f, indent=2)
        os.replace(tmp, path)
    except OSError:
        return None
    return entry


def clear_history(path=None):
    """Delete the history file. Returns True if a file was removed."""
    path = path or default_history_path()
    try:
        os.remove(path)
    except OSError:
        return False
    return True


def format_history(entries):
    """Render recorded jobs as Markdown for the app UI."""
    if not entries:
        return ("No jobs yet. Generate some passes and they will be "
                "listed here with their profile, passes and output folder.")
    lines = ["| When | Input | Profile | Passes | Frames | Output folder |",
             "|---|---|---|---|---|---|"]
    for e in entries:
        when = e.get("time", "")[:16].replace("T", " ")
        lines.append("| {when} | {inp} | {prof} | {passes} | {frames} | `{out}` |".format(
            when=when,
            inp=e.get("input", ""),
            prof=e.get("profile", ""),
            passes=", ".join(e.get("passes", [])),
            frames=e.get("frames", ""),
            out=e.get("output", "")))
    return "\n".join(lines)

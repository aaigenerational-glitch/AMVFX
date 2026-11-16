#!/usr/bin/env python3
"""AMVFX launcher - what the desktop shortcut points at.

Starts the Gradio app with the install folder's private venv Python and
opens the browser once the server is on its way. If the venv is missing
(fresh copy of the repo), falls back to the current interpreter.
"""
import os
import subprocess
import sys
import threading
import time
import webbrowser

HERE = os.path.dirname(os.path.abspath(__file__))
URL = "http://127.0.0.1:7860"


def venv_python():
    cand = os.path.join(HERE, ".venv",
                        "Scripts" if os.name == "nt" else "bin",
                        "python.exe" if os.name == "nt" else "python")
    return cand if os.path.exists(cand) else sys.executable


def _open_browser():
    time.sleep(5)
    webbrowser.open(URL)


if __name__ == "__main__":
    threading.Thread(target=_open_browser, daemon=True).start()
    raise SystemExit(subprocess.call(
        [venv_python(), os.path.join(HERE, "app.py")], cwd=HERE))

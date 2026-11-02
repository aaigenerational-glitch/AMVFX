#!/usr/bin/env python3
"""Build the standalone AMVFX installer executable for THIS platform.

PyInstaller cannot cross-compile: run this on Windows to get the .exe,
on macOS to get the Mac binary, on Linux for a Linux binary. The GitHub
Actions workflow in .github/workflows/release.yml does exactly that on
all three runners and attaches the results to a GitHub Release.

    pip install pyinstaller
    python installer/build.py            # -> dist/AMVFX-Installer[.exe]

The whole AMVFX payload (app, add-ons, docs) is bundled inside the
executable as data files; install.py finds it via sys._MEIPASS.
"""
import os
import platform
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from install import PAYLOAD_ITEMS  # noqa: E402


def main():
    try:
        import PyInstaller.__main__
    except ImportError:
        print("PyInstaller is required: pip install pyinstaller")
        return 1
    sep = ";" if platform.system() == "Windows" else ":"
    args = [
        os.path.join(HERE, "install.py"),
        "--onefile",
        "--name", "AMVFX-Installer",
        "--distpath", os.path.join(ROOT, "dist"),
        "--workpath", os.path.join(ROOT, "build"),
        "--specpath", os.path.join(ROOT, "build"),
        "--noconfirm",
    ]
    if platform.system() in ("Windows", "Darwin"):
        args.append("--windowed")  # GUI-first; no console window
    for item in PAYLOAD_ITEMS:
        src = os.path.join(ROOT, item)
        if os.path.exists(src):
            args.append(f"--add-data={src}{sep}{item}")
    print("PyInstaller args:", " ".join(args))
    PyInstaller.__main__.run(args)
    out = os.path.join(ROOT, "dist",
                       "AMVFX-Installer.exe" if platform.system() == "Windows"
                       else "AMVFX-Installer")
    print("Built:", out, os.path.getsize(out), "bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

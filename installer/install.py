#!/usr/bin/env python3
"""AMVFX installer.

One installer for the whole local workflow:

  * the AMVFX app itself (copied to the install folder + a private venv),
  * the local models (pre-downloaded into the Hugging Face cache so the
    first run is instant and works offline afterwards),
  * the Blender add-on   -- checkbox, installed into every detected
                            Blender version's user addons folder (and
                            auto-enabled when a Blender binary is found),
  * the After Effects panel (.jsx) -- checkbox, copied into every
                            detected AE ScriptUI Panels folder,
  * the After Effects CEP extension -- separate checkbox, copied into the
                            per-user CEP extensions folder (no admin).

Usage:
  python install.py                 # interactive checkboxes (GUI if a
                                    # display is available, else terminal)
  python install.py --gui           # force the checkbox window
  python install.py --yes           # non-interactive, everything on
  python install.py --with-blender --no-ae-panel --no-models
  python install.py --dry-run       # print the plan, change nothing

Stdlib only. Detection paths can be overridden for testing with
AMVFX_BLENDER_ADDONS_DIRS / AMVFX_AE_PANEL_DIRS / AMVFX_CEP_DIR
(os.pathsep-separated lists).
"""

import argparse
import glob
import os
import platform
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if getattr(sys, "frozen", False):
    # PyInstaller build: the payload travels inside the executable and is
    # unpacked to a temp dir (sys._MEIPASS) at runtime.
    PAYLOAD = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
else:
    PAYLOAD = os.path.dirname(HERE)  # the AMVFX repo root
IS_WIN = platform.system() == "Windows"
IS_MAC = platform.system() == "Darwin"

LITE_MODELS = [
    "onnx-community/depth-anything-v2-small",
    "onnx-community/BiRefNet_512x512-ONNX",
]
FULL_MODELS = LITE_MODELS + [
    "onnx-community/BiRefNet-ONNX",
    "prs-eth/marigold-iid-appearance-v1-1",
    "prs-eth/marigold-normals-v1-1",
]
PAYLOAD_ITEMS = ["app.py", "amvfx", "requirements.txt", "requirements-lite.txt",
                 "LICENSE", "README.md", "MODELS.md", "AE", "Blender Export",
                 "blender", "docs", "examples", "tests", "installer"]
IGNORE = shutil.ignore_patterns(".git", ".venv", "__pycache__", "*.pyc",
                                "*.zip", ".DS_Store")


def log(msg):
    print(f"[AMVFX] {msg}", flush=True)


def default_target():
    if IS_WIN:
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        return os.path.join(base, "AMVFX")
    return os.path.join(os.path.expanduser("~"), "AMVFX")


# --------------------------------------------------------------------------
# detection
# --------------------------------------------------------------------------

def _versioned_dirs(base, leaf):
    out = []
    if os.path.isdir(base):
        for ver in sorted(os.listdir(base)):
            d = os.path.join(base, ver, *leaf)
            if os.path.isdir(os.path.join(base, ver)):
                out.append(d)
    return out


def detect_blender_addons_dirs():
    override = os.environ.get("AMVFX_BLENDER_ADDONS_DIRS")
    if override:
        return [p for p in override.split(os.pathsep) if p]
    home = os.path.expanduser("~")
    if IS_WIN:
        base = os.path.join(os.environ.get("APPDATA", ""),
                            "Blender Foundation", "Blender")
        return _versioned_dirs(base, ["scripts", "addons"])
    if IS_MAC:
        base = os.path.join(home, "Library", "Application Support", "Blender")
        return _versioned_dirs(base, ["scripts", "addons"])
    base = os.path.join(home, ".config", "blender")
    return _versioned_dirs(base, ["scripts", "addons"])


def detect_blender_binary():
    cand = shutil.which("blender")
    if cand:
        return cand
    pats = []
    if IS_WIN:
        pats = [r"C:\Program Files\Blender Foundation\Blender *\blender.exe"]
    elif IS_MAC:
        pats = ["/Applications/Blender.app/Contents/MacOS/Blender"]
    for pat in pats:
        hits = sorted(glob.glob(pat))
        if hits:
            return hits[-1]
    return None


def detect_ae_panel_dirs():
    override = os.environ.get("AMVFX_AE_PANEL_DIRS")
    if override:
        return [p for p in override.split(os.pathsep) if p]
    if IS_WIN:
        hits = glob.glob(r"C:\Program Files\Adobe\Adobe After Effects *"
                         r"\Support Files\Scripts\ScriptUI Panels")
        return sorted(hits)
    if IS_MAC:
        return sorted(glob.glob("/Applications/Adobe After Effects */"
                                "Scripts/ScriptUI Panels"))
    return []


def detect_cep_dir():
    override = os.environ.get("AMVFX_CEP_DIR")
    if override:
        return override
    home = os.path.expanduser("~")
    if IS_WIN:
        return os.path.join(os.environ.get("APPDATA", ""), "Adobe", "CEP",
                            "extensions")
    if IS_MAC:
        return os.path.join(home, "Library", "Application Support", "Adobe",
                            "CEP", "extensions")
    return os.path.join(home, ".config", "Adobe", "CEP", "extensions")


# --------------------------------------------------------------------------
# install steps
# --------------------------------------------------------------------------

def install_app(target, dry):
    log(f"App -> {target}")
    if dry:
        return
    os.makedirs(target, exist_ok=True)
    for item in PAYLOAD_ITEMS:
        src = os.path.join(PAYLOAD, item)
        dst = os.path.join(target, item)
        if os.path.isdir(src):
            if os.path.exists(dst):
                shutil.rmtree(dst)
            shutil.copytree(src, dst, ignore=IGNORE)
        elif os.path.isfile(src):
            shutil.copy2(src, dst)


def _python_exe():
    """A real Python interpreter for venv creation. When this installer is
    a frozen PyInstaller binary, sys.executable is the installer itself -
    so find the user's Python instead."""
    if not getattr(sys, "frozen", False):
        return sys.executable
    for name in ("py", "python", "python3"):
        found = shutil.which(name)
        if found:
            return found
    raise RuntimeError(
        "Python 3.10+ is required to install AMVFX but was not found on "
        "PATH. Install it from python.org (tick 'Add to PATH' on Windows) "
        "and re-run this installer.")


def install_venv(target, full, dry):
    req = "requirements.txt" if full else "requirements-lite.txt"
    log(f"Python environment -> {target}/.venv (from {req})")
    if dry:
        return
    venv = os.path.join(target, ".venv")
    if not os.path.exists(venv):
        subprocess.run([_python_exe(), "-m", "venv", venv], check=True)
    py = os.path.join(venv, "Scripts" if IS_WIN else "bin",
                      "python.exe" if IS_WIN else "python")
    subprocess.run([py, "-m", "pip", "install", "--upgrade", "pip"],
                   check=False, capture_output=True)
    subprocess.run([py, "-m", "pip", "install", "-r",
                    os.path.join(target, req)], check=True)


def install_models(target, full, dry):
    models = FULL_MODELS if full else LITE_MODELS
    log("Local models -> Hugging Face cache: " + ", ".join(models))
    if dry:
        return
    py = os.path.join(target, ".venv", "Scripts" if IS_WIN else "bin",
                      "python.exe" if IS_WIN else "python")
    if not os.path.exists(py):
        py = _python_exe()
    code = ("from huggingface_hub import snapshot_download\n"
            "import sys\n"
            "for m in sys.argv[1:]:\n"
            "    print('downloading', m)\n"
            "    snapshot_download(m)\n")
    subprocess.run([py, "-c", code] + models, check=True)


def install_blender_addon(target, dry):
    dirs = detect_blender_addons_dirs()
    src = os.path.join(PAYLOAD, "Blender Export", "amvfx_blender_export")
    if not dirs:
        log("Blender add-on: no Blender user folders detected - skipped. "
            "Install later by copying 'Blender Export/amvfx_blender_export' "
            "into Blender's scripts/addons folder.")
        return
    for d in dirs:
        dst = os.path.join(d, "amvfx_blender_export")
        log(f"Blender add-on -> {dst}")
        if dry:
            continue
        os.makedirs(d, exist_ok=True)
        if os.path.exists(dst):
            shutil.rmtree(dst)
        shutil.copytree(src, dst, ignore=IGNORE)
    binary = detect_blender_binary()
    if binary and not dry:
        log("Blender add-on: enabling in Blender preferences...")
        expr = ("import bpy; "
                "bpy.ops.preferences.addon_enable("
                "module='amvfx_blender_export'); "
                "bpy.ops.wm.save_userpref()")
        try:
            subprocess.run([binary, "-b", "--factory-startup",
                            "--python-expr", expr],
                           capture_output=True, timeout=300)
            log("Blender add-on: enabled (restart Blender if it is open).")
        except Exception as exc:
            log(f"Blender add-on: auto-enable failed ({exc}); enable it in "
                "Edit > Preferences > Add-ons.")
    elif binary:
        log("Blender add-on: (dry-run) would auto-enable via " + binary)


def install_ae_panel(target, dry):
    dirs = detect_ae_panel_dirs()
    src = os.path.join(PAYLOAD, "AE", "AMVFX_Panel.jsx")
    if not dirs:
        log("AE panel: no After Effects install detected - skipped. Copy "
            "AE/AMVFX_Panel.jsx into AE's Scripts/ScriptUI Panels folder "
            "manually (see AE/README.md).")
        return
    for d in dirs:
        dst = os.path.join(d, "AMVFX_Panel.jsx")
        log(f"AE panel -> {dst}")
        if dry:
            continue
        try:
            shutil.copy2(src, dst)
        except PermissionError:
            log("AE panel: permission denied (the Adobe Program Files folder "
                "needs admin). Copy AE/AMVFX_Panel.jsx there manually, or "
                "re-run this installer as administrator.")


def install_cep(target, dry):
    base = detect_cep_dir()
    dst = os.path.join(base, "com.amvfx.panel")
    src = os.path.join(PAYLOAD, "AE", "cep-extension")
    log(f"AE CEP extension -> {dst}")
    if dry:
        return
    os.makedirs(base, exist_ok=True)
    if os.path.exists(dst):
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=IGNORE)
    # unsigned extensions need PlayerDebugMode=1 (per-user, no admin)
    try:
        if IS_MAC:
            for v in ("9", "10", "11", "12"):
                subprocess.run(["defaults", "write", f"com.adobe.CSXS.{v}",
                                "PlayerDebugMode", "1"], capture_output=True)
        elif IS_WIN:
            import winreg
            for v in ("9", "10", "11", "12"):
                key = winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                                       rf"Software\Adobe\CSXS.{v}")
                winreg.SetValueEx(key, "PlayerDebugMode", 0, winreg.REG_SZ, "1")
                winreg.CloseKey(key)
    except Exception as exc:
        log(f"CEP: could not set PlayerDebugMode automatically ({exc}); "
            "see AE/README.md.")


# --------------------------------------------------------------------------
# UI: GUI checkboxes, terminal prompts, or flags
# --------------------------------------------------------------------------

DEFAULTS = dict(app=True, models=True, full=False, blender=True,
                ae_panel=True, cep=False)


def gui_choices():
    import tkinter as tk
    from tkinter import filedialog, scrolledtext
    state = dict(DEFAULTS)
    root = tk.Tk()
    root.title("AMVFX Installer")
    tk.Label(root, text="AMVFX — VFX Passes Generator",
             font=("TkDefaultFont", 13, "bold")).pack(anchor="w", padx=12, pady=(10, 2))
    tk.Label(root, text="Choose what to install. Add-ons are placed into the "
                        "detected Blender / After Effects folders automatically.",
             wraplength=430, justify="left").pack(anchor="w", padx=12)
    target_var = tk.StringVar(value=default_target())
    row = tk.Frame(root); row.pack(anchor="w", padx=12, pady=6)
    tk.Label(row, text="Install folder:").pack(side="left")
    tk.Entry(row, textvariable=target_var, width=38).pack(side="left", padx=4)
    tk.Button(row, text="Browse...", command=lambda: target_var.set(
        filedialog.askdirectory() or target_var.get())).pack(side="left")
    vars_ = {}
    boxes = [
        ("app", "AMVFX app (required)", True),
        ("models", "Local models (Depth Anything V2 + BiRefNet, ~400 MB)", False),
        ("full", "Full model set (adds Marigold IID + Normals, GPU profile)", False),
        ("blender", "Blender add-on (AMVFX_PBR + Z-Depth displacement)", False),
        ("ae_panel", "After Effects panel (ScriptUI .jsx)", False),
        ("cep", "After Effects CEP extension (.zxp source, unsigned mode)", False),
    ]
    for key, label, locked in boxes:
        v = tk.BooleanVar(value=DEFAULTS[key])
        vars_[key] = v
        cb = tk.Checkbutton(root, text=label, variable=v)
        if locked:
            cb.configure(state="disabled")
        cb.pack(anchor="w", padx=16)
    out = scrolledtext.ScrolledText(root, width=64, height=10)
    out.pack(padx=12, pady=8)

    def run_install():
        for k, v in vars_.items():
            state[k] = bool(v.get())
        state["target"] = target_var.get()
        out.insert("end", "Installing...\n")
        root.update_idletasks()
        do_install(state, dry=False, gui_log=lambda m: (
            out.insert("end", m + "\n"), out.see("end"), root.update_idletasks()))
        out.insert("end", "Done.\n")

    tk.Button(root, text="Install", command=run_install,
              width=18).pack(pady=(0, 10))
    root.mainloop()
    return None  # install already ran inside the GUI


def prompt_choices():
    state = dict(DEFAULTS)
    state["target"] = default_target()
    print("AMVFX installer — press Enter to accept the default.")
    t = input(f"Install folder [{state['target']}]: ").strip()
    if t:
        state["target"] = t
    questions = [
        ("models", "Download the local models now?"),
        ("full", "Include the full GPU model set (Marigold)?"),
        ("blender", "Install the Blender add-on into detected Blender folders?"),
        ("ae_panel", "Install the After Effects panel (.jsx) into detected AE folders?"),
        ("cep", "Install the After Effects CEP extension (unsigned mode)?"),
    ]
    for key, q in questions:
        d = "Y" if DEFAULTS[key] else "n"
        ans = input(f"{q} [{'Y/n' if d == 'Y' else 'y/N'}]: ").strip().lower()
        state[key] = (ans not in ("n", "no")) if d == "Y" else (ans in ("y", "yes"))
    return state


def do_install(state, dry=False, gui_log=None):
    global log
    if gui_log:
        log = gui_log
    target = state["target"]
    install_app(target, dry)
    if not state.get("skip_venv"):
        install_venv(target, state.get("full", False), dry)
    if state.get("models"):
        install_models(target, state.get("full", False), dry)
    if state.get("blender"):
        install_blender_addon(target, dry)
    if state.get("ae_panel"):
        install_ae_panel(target, dry)
    if state.get("cep"):
        install_cep(target, dry)
    log(f"Finished. App: {target}")
    log("Run the app:  " + os.path.join(target, ".venv",
                                        "Scripts" if IS_WIN else "bin",
                                        "python") + " " +
        os.path.join(target, "app.py"))


def main():
    ap = argparse.ArgumentParser(description="AMVFX installer")
    ap.add_argument("--target", default=None)
    ap.add_argument("--gui", action="store_true")
    ap.add_argument("--yes", action="store_true",
                    help="non-interactive: app + models + Blender + AE panel")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--skip-venv", action="store_true",
                    help="copy files only; do not create the Python venv")
    for name in ("models", "full", "blender", "ae-panel", "cep"):
        ap.add_argument(f"--with-{name}", dest=name.replace("-", "_"),
                        action="store_true", default=None)
        ap.add_argument(f"--no-{name}", dest=name.replace("-", "_"),
                        action="store_false", default=None)
    args = ap.parse_args()

    flags = {k: v for k, v in vars(args).items()
             if k in ("models", "full", "blender", "ae_panel", "cep")
             and v is not None}
    if args.gui:
        gui_choices()
        return 0
    if args.yes or flags or args.target or args.dry_run or args.skip_venv:
        state = dict(DEFAULTS)
        state["target"] = args.target or default_target()
        state["skip_venv"] = args.skip_venv
        state.update(flags)
        if args.yes:
            state.update(models=True, blender=True, ae_panel=True)
        do_install(state, dry=args.dry_run)
        return 0
    # interactive: GUI when a display exists, else terminal prompts
    if os.environ.get("DISPLAY") or IS_WIN or IS_MAC:
        try:
            gui_choices()
            return 0
        except Exception:
            pass
    state = prompt_choices()
    do_install(state, dry=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

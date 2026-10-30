# AMVFX Installer

One installer for the whole local AMVFX workflow — the app, its Python
environment, the local models, and the host-application add-ons, each
add-on behind its **own checkbox**:

- ☑ **AMVFX app** (always) — copied to the install folder with a private
  `.venv`.
- ☑ **Local models** — Depth Anything V2 Small + BiRefNet pre-downloaded
  into the Hugging Face cache, so the first run is instant and later runs
  work offline.
- ☐ **Full model set** — adds Marigold IID + Marigold Normals (GPU
  profile) to the download.
- ☑ **Blender add-on** — `amvfx_blender_export` is copied into **every
  detected Blender version's** user addons folder
  (`.../Blender/<version>/scripts/addons`), and auto-enabled when a
  Blender binary is found (headless `addon_enable` + save userpref).
- ☑ **After Effects panel** — `AMVFX_Panel.jsx` is copied into every
  detected **ScriptUI Panels** folder. That folder lives under Program
  Files on Windows, so a permission denial is reported with the manual
  fallback (copy it yourself, or re-run as administrator).
- ☐ **After Effects CEP extension** — copied into the per-user CEP
  extensions folder (no admin needed) and `PlayerDebugMode` is set for
  the unsigned build.

## Run it

```sh
# Windows
installer\install.bat
# macOS / Linux
./installer/install.sh
```

With a display you get a **checkbox window** (Tkinter); in a terminal you
get the same choices as prompts. Power users can script it:

```sh
python installer/install.py --yes                       # everything, unattended
python installer/install.py --with-blender --no-ae-panel
python installer/install.py --target D:\Apps\AMVFX --full
python installer/install.py --dry-run                   # print the plan only
```

Detection covers the standard per-user Blender folders on Windows /
macOS / Linux and the standard Adobe install locations on Windows /
macOS. Nothing is installed into a host app you didn't check off, and
re-running the installer upgrades in place (folders are replaced, never
merged). After installing, restart Blender / After Effects if they were
open.

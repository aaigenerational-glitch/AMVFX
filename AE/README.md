# AMVFX for After Effects

Two ways to run AMVFX from inside After Effects. Both drive your **local**
AMVFX install (`python -m amvfx ...`) and then import the generated passes
into your project as a stacked comp — source plate at the bottom, one layer
per pass above it, plus the multi-layer EXR sequence when present.

## Option 1 — ScriptUI panel (recommended, no installer)

`AMVFX_Panel.jsx` is a dockable After Effects panel — the standard
"script plugin" form for AE.

1. Copy `AMVFX_Panel.jsx` into:
   - Windows: `C:\Program Files\Adobe\Adobe After Effects <version>\Support Files\Scripts\ScriptUI Panels\`
   - macOS: `/Applications/Adobe After Effects <version>/Scripts/ScriptUI Panels/`
2. Restart After Effects, open **Window > AMVFX_Panel.jsx**.
3. Set the AMVFX install folder + Python command, choose the source
   (below), choose profile/passes, then **Generate**, then
   **Import + Build Comp**.

In **Preferences > Scripting & Expressions**, enable
"Allow Scripts to Write Files and Access Network" (needed for the panel to
launch the local AMVFX process). AE pauses while passes generate.

## Choosing the source: file, or the selected timeline clip

Both panels offer two source modes:

- **Pick a file** — any image/video on disk (the original workflow).
- **Use Selected Clip** — the layer selected in the active comp's
  timeline becomes the source:
  - a **footage layer** resolves to its file on disk;
  - a **composition / precomp layer** is first rendered to a temp
    movie through the render queue (H.264 template when available,
    otherwise Lossless; the whole render queue renders), and that
    movie becomes the source;
  - anything else (solid, text, shape, camera, footage with no file)
    reports a plain-language error instead of guessing.

Notes: generation runs on the **whole source file** — a layer's
in/out trim is not applied yet (roadmap item). Passes are imported and
stacked into a new comp as before, so the generated layers line up
with the plate you selected.

## Option 2 — CEP extension (`.zxp` source)

`cep-extension/` is a complete CEP panel (manifest for host `AEFT`,
Adobe's `CSInterface.js`, HTML/JS client, ExtendScript host in
`host/AMVFX_Host.jsx`).

**Developer-mode install (unsigned):** copy `cep-extension/` to
`%APPDATA%\Adobe\CEP\extensions\com.amvfx.panel\` (Windows) or
`~/Library/Application Support/Adobe/CEP/extensions/com.amvfx.panel/`
(macOS), set `PlayerDebugMode` to `1` for CSXS.9/CSXS.10/CSXS.11, restart
AE, open **Window > Extensions > AMVFX**.

**Producing an installable signed `.zxp`:** Adobe only ships its signer
(`ZXPSignCmd`) for macOS and Windows — there is no Linux signer, which is
why this repo ships the extension source rather than a pre-signed `.zxp`.
On a Mac/Windows machine with the CEP Resources toolkit:

```sh
ZXPSignCmd -selfSignedCert US CA "AMVFX" "AMVFX Dev" cert.p12 password
ZXPSignCmd -sign cep-extension AMVFX_CEP.zxp cert.p12 password http://timestamp.digicert.com
```

The resulting `AMVFX_CEP.zxp` installs through Adobe's Extension Manager /
Exchange or the `UnifiedPluginInstallerAgent`.

## About `.aex`

A `.aex` is a **compiled native C++ plug-in** built with Adobe's After
Effects SDK — per-OS binaries that have to be compiled with a C++
toolchain against the SDK; they are not scripts and cannot be generated
from this codebase. AMVFX's compute lives in Python (open models), so the
panel routes above are the practical integration: they put AMVFX inside
AE's UI and comp workflow without a native rewrite. (UXP is Adobe's newer
plugin system; for After Effects the CEP/ScriptUI routes above are the
broadly supported ones.)

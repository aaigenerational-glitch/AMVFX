# AMVFX Roadmap

Two lists. **Approved backlog** is what the daily update job works
through, one bounded item per day: implement, test, bump the patch
version, push to GitHub - installed apps then pick the change up from
their **Updates** panel, no reinstall.

**Under consideration** is John's parking lot for bigger tools. Those
items are *ideas to evaluate only* - **nobody implements them without
John's explicit approval**, and the daily job must never pick from
that list.

## Approved backlog (daily updates work from here)

1. **UI: job history** - the app remembers recent jobs (input, profile,
   passes, output folder) and lists them under the generator.
2. **UI: per-pass preview zoom** - click a preview to see it full-size
   before downloading the ZIP.
3. **Installer: repair mode** - re-running the installer over an
   existing install refreshes files but keeps the venv and models
   (verify + document the behaviour, add a test).
4. **Blender add-on: camera-from-plate** - optional camera whose
   background is the source plate, matched to the plate aspect.
5. **AE panel: comp naming** - name the built comp after the source
   file instead of a fixed string.
6. **Performance: model session cache** - reuse ONNX sessions across
   frames in a video job instead of re-creating them per frame
   (measure before/after on the 12-frame test clip).
7. **Bug-fix sweep: paths with spaces** - audit installer, updater,
   launcher and both add-ons for unquoted paths; fix and add tests.
8. **Docs: quickstart GIF/screenshots** for the README and Pages site.
9. **Updater: show what changed** - fetch the repo's recent commit
   titles during "Check for updates" and list them before applying.
10. **Tests: pipeline smoke test** - a 2-frame synthetic video through
    the lite profile in CI-style local runs.

## Under consideration (NOT approved - evaluation only)

| Tool | What it would do | Candidate open tech | Notes |
|---|---|---|---|
| Rotobrush-style propagation | Paint a mask on one frame, propagate it through the shot | SAM 2 / SAM 3 video segmentation | GPU-heavy; needs an interactive UI, not just a pass |
| Video matte refinement | Cleaner, temporally stable alpha for hair/edges | MatAnyone 2 | License check first (research licenses in this family); Beeble publicly licenses it, we may not be able to |
| Per-object passes | Cryptomatte-style object ID pass + per-object normals | SAM 2 masks + existing passes | Was offered 2026-10-30 as a separate build; still unchosen |
| Chroma keyer | Green/blue-screen keying pass as an alpha alternative | Classic keying math (no model) | Cheap to build; quality bar vs BiRefNet unclear |
| Object removal / inpainting | Erase a masked object across frames | ProPainter, LaMa | GPU-heavy; big quality variance |
| Upscaling | 2x/4x pass upscaling for delivery | Real-ESRGAN, SeedVR2 | License + VRAM check needed |
| Temporal depth smoothing | Flicker-free depth on video | Video Depth Anything | Replaces per-frame depth; evaluate vs current |
| In-app relight preview | Drag-a-light preview using the passes | Three.js / custom shader on the passes | The "3D Relight" story Beeble leads with; UI-sized job |
| Motion vectors pass | Optical-flow MVs for post motion blur | RAFT flow | Useful in Nuke/AE; niche audience |
| Frame interpolation | Slow-motion / fps conversion of passes | RIFE | Must interpolate all passes consistently |
| Denoise pass set | Clean plates for VFX work | Restormer / NAFNet | Extra pass type, moderate cost |
| Face / body tracking | Landmarks + segmentation for characters | MediaPipe | Different audience (VTuber/mocap); scope risk |

Evaluation rule for this list: license first (weights must allow the
use), then VRAM/CPU reality on a normal creator machine, then whether
it fits the passes workflow - in that order.

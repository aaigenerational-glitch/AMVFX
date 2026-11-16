# AMVFX Roadmap

How updates flow: the daily update job ships **one bounded item per
day** - implement, test, bump the patch version, push to GitHub -
and installed apps pick the change up from their **Updates** panel,
no reinstall.

Two pools to pick from:

- **Approved backlog** - the priority queue, worked top-down.
- **Ideas pool** - bigger tools and directions kept in mind as
  references. Since 2026-11-16 the daily job **may also choose from
  this pool at its own discretion**; nothing here needs John's
  explicit say-so anymore. An item that takes longer than a day is
  fine too - it just ships as **WIP** until finished (protocol
  below).

## WIP protocol (multi-day items)

When the daily job takes on something that cannot finish in one
run, it is welcome to - under these rules:

1. The item is marked **WIP (started <date>)** here in the roadmap
   and stays the job's active item until it is done or abandoned;
   each daily run continues it before picking anything new.
2. User-facing surfaces carry the notice with them: a "WIP -
   experimental, may not work yet" label in the app/panel, WIP
   comments in the code, and WIP stated plainly in the day's report
   and commit message.
3. A WIP feature must never break the existing app: if it cannot
   run yet, it ships disabled by default or clearly gated, and the
   full test suite still passes.
4. When it is finished and verified, the WIP labels come off and
   the item moves to **Done**.

## Approved backlog (daily updates work from here first)

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
6. **AE selected clip: respect layer in/out** - when the source comes
   from a timeline selection, trim generation to the layer's in/out
   points instead of the whole file.
7. **Integrations polish (standing)** - regularly review the Blender
   add-on and the AE panels for visual and UI improvements: layout,
   labels, icons, grouping, sensible defaults. Small, shippable steps.
8. **Performance: model session cache** - reuse ONNX sessions across
   frames in a video job instead of re-creating them per frame
   (measure before/after on the 12-frame test clip).
9. **Bug-fix sweep: paths with spaces** - audit installer, updater,
   launcher and both add-ons for unquoted paths; fix and add tests.
10. **Docs: quickstart GIF/screenshots** for the README and Pages site.
11. **Updater: show what changed** - fetch the repo's recent commit
    titles during "Check for updates" and list them before applying.
12. **Tests: pipeline smoke test** - a 2-frame synthetic video through
    the lite profile in CI-style local runs.

## Ideas pool (references the daily job may draw from)

| Tool / direction | What it would do | Candidate open tech | Notes |
|---|---|---|---|
| Rotobrush-style propagation | Paint a mask on one frame, propagate it through the shot | SAM 2 / SAM 3 video segmentation | GPU-heavy; needs an interactive UI, not just a pass |
| Video matte refinement | Cleaner, temporally stable alpha for hair/edges | MatAnyone 2 | License check first (research licenses in this family) |
| Per-object passes | Cryptomatte-style object ID pass + per-object normals | SAM 2 masks + existing passes | Offered 2026-10-30 as a separate build |
| Chroma keyer | Green/blue-screen keying pass as an alpha alternative | Classic keying math (no model) | Cheap to build; quality bar vs BiRefNet unclear |
| Object removal / inpainting | Erase a masked object across frames | ProPainter, LaMa | GPU-heavy; big quality variance |
| Upscaling | 2x/4x pass upscaling for delivery | Real-ESRGAN, SeedVR2 | License + VRAM check needed |
| Sharpening | Detail enhancement pass/tool for soft plates | OpenCV unsharp / Real-ESRGAN-lite | Pairs with upscaling; keep it a tool, not a default |
| Denoising | Clean plates for VFX work | Restormer / NAFNet | Extra pass type, moderate cost |
| Temporal depth smoothing | Flicker-free depth on video | Video Depth Anything | Replaces per-frame depth; evaluate vs current |
| In-app relight preview | Drag-a-light preview using the passes | Three.js / custom shader on the passes | The "3D Relight" story Beeble leads with; UI-sized job |
| AE graph tooling | In-depth graph/easing editor inside the AE integration (Flow-style: curve presets, easing library applied to keyframes) | ExtendScript keyframe APIs + CEP UI | Lives in the AE panel, not the pass pipeline; Flow is the reference UX |
| Motion vectors pass | Optical-flow MVs for post motion blur | RAFT flow | Useful in Nuke/AE; niche audience |
| Frame interpolation | Slow-motion / fps conversion of passes | RIFE | Must interpolate all passes consistently |
| Face / body tracking | Landmarks + segmentation for characters | MediaPipe | Different audience (VTuber/mocap); scope risk |

### Vision / long-term reference (not a build item)

**Video-interactive environment simulation (Blender).** John's
concept, recorded 2026-11-16 as a reference to keep in mind, *not* an
implementation: hidden 3D proxy geometry for body parts (feet first)
is replicated from the video clip and tracked so the proxies move
**1:1 with the person in the footage**; the plate then *interacts*
with a 3D environment as if it were a 3D model - feet pressing into
interactive snow, parting grass, and similar ground/environment
effects - with panel options to hide or unhide each simulated part.
Research-scale (needs reliable body/foot tracking from monocular
video + a simulation step); small stepping stones (e.g. a tracked
ground-contact shadow/deformation plane) may be prototyped from the
ideas pool, but the full vision stays parked until it is feasible in
bounded steps.

Evaluation rule for the pool: license first (weights must allow the
use), then VRAM/CPU reality on a normal creator machine, then whether
it fits the passes workflow - in that order.

## Done

- **2026-11-16 (v0.2.1)** - AE integration: **selected timeline clip
  as the source**. Both the ScriptUI panel and the CEP extension can
  now take the layer selected in the active comp: footage resolves to
  its file on disk; a composition/precomp is rendered to a temp movie
  via the render queue first; anything else errors in plain language.
  (Whole-file generation for now; layer in/out trim is backlog #6.)
- **2026-11-15 (v0.2.0)** - in-app updater, desktop-shortcut
  installer option, this roadmap, daily update job created.

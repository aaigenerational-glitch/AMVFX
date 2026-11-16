# AMVFX Roadmap

How updates flow: since 2026-11-16 (John's direction) the daily
update job ships a **bundle, not a single item** - one anchor item
plus several smaller improvements in the same run, together with a
research pass and extra checks (see "Daily bundle rule" below).
Each bundle is implemented in reviewable increments, tested, given
a version bump, and pushed to GitHub; installed apps pick the
change up from their **Updates** panel, no reinstall.

The north star: AMVFX should become an **essential tool for AMV
editors** - fast, trustworthy VFX passes, a smooth AE/Blender
round-trip, and scene-planning help (camera, lighting, motion)
around the edit, not just a pass generator.

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
   and stays the job's **anchor item** until it is done or
   abandoned; each daily run continues it first - but the rest of
   that day's bundle (smaller finished items, research, checks)
   still ships around it, so a long WIP never freezes all other
   progress.
2. User-facing surfaces carry the notice with them: a "WIP -
   experimental, may not work yet" label in the app/panel, WIP
   comments in the code, and WIP stated plainly in the day's report
   and commit message.
3. A WIP feature must never break the existing app: if it cannot
   run yet, it ships disabled by default or clearly gated, and the
   full test suite still passes.
4. When it is finished and verified, the WIP labels come off and
   the item moves to **Done**.

## Daily bundle rule (John, 2026-11-16)

Each daily run aims for a **release bundle**, in this shape:

1. **Anchor item** - the top backlog item, the continuing WIP, or
   one ideas-pool pick (the day's main feature or fix).
2. **Supporting items** - several smaller finished improvements in
   the same run, spread across the app on purpose: a bug fix, a
   UI/UX polish, an AE or Blender integration improvement, a
   performance tweak, a test or docs improvement. Aim for roughly
   **3-6 shipped pieces total** when the work supports it; quality
   and passing tests beat hitting a count.
3. **Research pass** - check official docs/release notes (Blender,
   After Effects/CEP, Gradio, the models in MODELS.md), license
   pages for any candidate model, and how AMV editors actually
   work (camera moves, lighting setups, popular AE/Blender
   workflows). Cross-check claims against at least two sources and
   flag anything unsupported. Findings land here in the roadmap
   (new backlog/ideas entries with a one-line verdict) - research
   that changes nothing is still reported in one line.
4. **Checks** - the full test suite plus the import check, and
   targeted verification for whatever was touched (node --check
   for ExtendScript, the headless Blender test for the add-on,
   installer dry-run for installer changes). Each bundle piece is
   its own increment: if one piece fails its checks and cannot be
   fixed in the run, drop or revert **that piece** and ship the
   rest - never ship a failing piece to make the bundle look
   bigger, and never let one bad piece sink the whole day.
5. **Report** - grouped: shipped pieces, research findings,
   checks run, WIP state, next bundle's likely anchor.

## Approved backlog (daily updates work from here first)

1. **UI: per-pass preview zoom** - click a preview to see it full-size
   before downloading the ZIP.
2. **Installer: repair mode** - re-running the installer over an
   existing install refreshes files but keeps the venv and models
   (verify + document the behaviour, add a test).
3. **Blender add-on: camera-from-plate** - optional camera whose
   background is the source plate, matched to the plate aspect.
4. **AE panel: comp naming** - name the built comp after the source
   file instead of a fixed string.
5. **AE selected clip: respect layer in/out** - when the source comes
   from a timeline selection, trim generation to the layer's in/out
   points instead of the whole file.
6. **Integrations polish (standing)** - regularly review the Blender
   add-on and the AE panels for visual and UI improvements: layout,
   labels, icons, grouping, sensible defaults. Small, shippable steps.
7. **Performance: model session cache** - reuse ONNX sessions across
   frames in a video job instead of re-creating them per frame
   (measure before/after on the 12-frame test clip).
8. **Bug-fix sweep: paths with spaces** - audit installer, updater,
   launcher and both add-ons for unquoted paths; fix and add tests.
9. **Docs: quickstart GIF/screenshots** for the README and Pages site.
10. **Updater: show what changed** - fetch the repo's recent commit
    titles during "Check for updates" and list them before applying.
11. **Tests: pipeline smoke test** - a 2-frame synthetic video through
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
| Camera rig + scene blocking | A camera matched to the plate (aspect, focal feel, horizon, ground plane) with position/rotation controls, so editors can plan moves against the shot | Depth + plate metadata; Blender camera tools | Stepping stone toward the diorama vision below; bounded pieces only |
| 3D diorama / parallax stage | Plate split into depth layers on a mini 3D stage to preview camera moves, parallax and light direction before committing | Existing depth/alpha passes; Blender planes or an in-app 3D preview | Part of the conceptual camera/diorama track (2026-11-16); research + small prototypes first |
| Lighting + motion-path planner | Overlays showing key-light direction, shadow side, and subject/camera motion paths over the plate or stage | Normal/depth passes; vector overlays | Planning aid for AMV editors; starts as research/overlays, not a renderer |

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

**AMV scene-planning stage (camera rig + 3D diorama).** John's
concept, recorded 2026-11-16 as a *concept to keep in mind, not an
implementation directive*: AMVFX grows toward overall 3D
landscapes presented like a **diorama** of the shot, where an
editor can see where their **camera** and **lighting** actually
sit, the **directions** things face, and the **motion paths** of
camera and subject - camera rigging for planning an edit, not
just passes after the fact. Allowed today: research notes,
paper/data-model sketches, and small bounded stepping stones from
the ideas pool (camera-from-plate, ground plane, depth-layer
stage, light-direction arrows, motion-path overlays). The full
landscape/camera-rig suite stays long-term until it can be broken
into bounded, testable steps - and anything partially built ships
under the WIP protocol.

Evaluation rule for the pool: license first (weights must allow the
use), then VRAM/CPU reality on a normal creator machine, then whether
it fits the passes workflow - in that order.

## Done

- **2026-11-16 (v0.2.2)** - UI: **job history**. The app remembers
  recent generation jobs (input, profile, passes, frames, resolution,
  output folder) in `~/.amvfx/history.json` and lists them in a
  "Recent jobs" accordion under the generator, with Refresh and Clear
  buttons. New `amvfx/history.py` module + `tests/test_history.py`
  (record/load, 20-entry cap, corrupt-file recovery, best-effort
  writes that never break a job).
- **2026-11-16 (v0.2.1)** - AE integration: **selected timeline clip
  as the source**. Both the ScriptUI panel and the CEP extension can
  now take the layer selected in the active comp: footage resolves to
  its file on disk; a composition/precomp is rendered to a temp movie
  via the render queue first; anything else errors in plain language.
  (Whole-file generation for now; layer in/out trim is backlog #6.)
- **2026-11-15 (v0.2.0)** - in-app updater, desktop-shortcut
  installer option, this roadmap, daily update job created.

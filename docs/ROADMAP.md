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

1. **Integrations polish (standing)** - regularly review the Blender
   add-on and the AE panels for visual and UI improvements: layout,
   labels, icons, grouping, sensible defaults. Small, shippable steps.
2. **Bug-fix sweep: paths with spaces** - audit installer, updater,
   launcher and both add-ons for unquoted paths; fix and add tests.
   (Partial 2026-11-18, v0.4.0: audit found all subprocess calls are
   already list-form; fixed the two real gaps - PowerShell single-quote
   escaping in the installer shortcut, quote-stripping in both JSX
   generate commands - plus a unit test. Re-audit 2026-11-19, v0.5.0:
   clean - every subprocess call is still list-form (ffmpeg encode,
   NormalCrafter shell-out, launcher, installer pip/venv/Blender/
   defaults/PowerShell), both JSX panels still use q() quoting, and
   updater.py / blender/amvfx_loader.py make no subprocess calls at
   all. Item DONE.)
3. **Docs: quickstart GIF/screenshots** for the README and Pages site.
   (DONE 2026-11-20, v0.6.0: a real lite run on
   `examples/test_portrait.jpg` — 5 passes at 640x640 — produced a
   labelled animated GIF cycling source/alpha/depth/normal/AO plus a
   contact-sheet PNG, both in `docs/images/`, and a "Quick start" visual
   section in the README with a chroma-key CLI example. The example
   image is a concert shot, not a portrait — the passes still read
   cleanly, so it stays.)
4. **Tests: pipeline smoke test** - a 2-frame synthetic video through
   the lite profile in CI-style local runs. (DONE 2026-11-19, v0.5.0:
   tests/test_smoke.py runs pipeline.run end-to-end on real cached
   ONNX models and asserts the manifest, PNGs, per-pass MP4s and
   sane pass values. Note: it needs ~3.3 GB free - BiRefNet 512 peaks
   there - and was OOM-killed twice on a busy shared VM before
   passing; single-threaded ORT via OMP_NUM_THREADS=1 in the test.
   A dead end on the way: ORT_ENABLE_BASIC graph optimisation
   measured no better than the default level on the 512 model, so
   backends.py is unchanged.)

## Ideas pool (references the daily job may draw from)

| Tool / direction | What it would do | Candidate open tech | Notes |
|---|---|---|---|
| Rotobrush-style propagation | Paint a mask on one frame, propagate it through the shot | SAM 2 / SAM 3 video segmentation | License VERIFIED 2026-11-18: SAM 2.1 code + checkpoints are Apache-2.0 (Meta paper, PyPI LICENSE) — license-clear. SAM 3 is a separate gated Meta licence — do NOT use. GPU-heavy; needs an interactive UI, not just a pass |
| Video matte refinement | Cleaner, temporally stable alpha for hair/edges | MatAnyone 2 | License VERIFIED 2026-11-18: NTU S-Lab License 1.0 — non-commercial free, commercial use needs author permission (Beeble licenses it directly). NOT a default/commercial-safe backend; research-only, opt-in non-commercial experiment at most |
| Per-object passes | Cryptomatte-style object ID pass + per-object normals | SAM 2 masks + existing passes | Offered 2026-10-30 as a separate build |
| Chroma keyer | Green/blue-screen keying pass as an alpha alternative | Classic keying math (no model) | DONE 2026-11-20 (v0.6.0): `amvfx/keying.py` — RGB-distance key + smoothstep feather ramp + despill (G' = min(G, max(R,B)), weighted by 1-alpha so opaque pixels keep their colour), wired as `--alpha-backend chroma` (+ `--key-color/--key-similarity/--key-smoothness`), Gradio alpha-source radio, `tests/test_keying.py`; verified end-to-end on a synthetic green-screen frame (bg alpha 0, subject 255). Method cross-checked 2026-11-20 against two independent write-ups (nrtechstudio, vectree) — they agree on the distance, ramp and despill formulas |
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
| Camera rig + scene blocking | A camera matched to the plate (aspect, focal feel, horizon, ground plane) with position/rotation controls, so editors can plan moves against the shot | Depth + plate metadata; Blender camera tools | Stepping stone toward the diorama vision below; bounded pieces only. First stone SHIPPED 2026-11-18 (v0.4.0): camera-from-plate in the Blender add-on (background image + render res + framing). Second stone SHIPPED 2026-11-19 (v0.5.0): ground plane (AMVFX_Ground, plate-width, depth prop, dark rough material, "Scene Planning" panel box). Third stone SHIPPED 2026-11-20 (v0.6.0): depth-layer stage (AMVFX_Layer_00..N, source masked per depth band with soft Map Range ramps, Z-spaced, distance-ratio rescale to hold framing). Next stone: light-direction overlay |
| 3D diorama / parallax stage | Plate split into depth layers on a mini 3D stage to preview camera moves, parallax and light direction before committing | Existing depth/alpha passes; Blender planes or an in-app 3D preview | Part of the conceptual camera/diorama track (2026-11-16); research + small prototypes first. First stone SHIPPED 2026-11-20 (v0.6.0): Blender depth-layer stage (see camera-rig row). Research 2026-11-20 (mouzeclick, olaf-motion, actionvfx — agree): the standard 2.5D workflow is 3–5 layers spaced on Z, pushed layers rescaled by the distance ratio (twice as far = 200%), camera animated, layers still; depth-map + Displacement Map is the faster alternative but stretches edges when pushed |
| Lighting + motion-path planner | Overlays showing key-light direction, shadow side, and subject/camera motion paths over the plate or stage | Normal/depth passes; vector overlays | Planning aid for AMV editors; starts as research/overlays, not a renderer |
| Depth-map 3D lighting guide | Show editors how to turn the depth pass into real 3D geometry (AE displacement / Blender displacement, both already in AMVFX) and throw a point light at it, so a flat clip can be relit in 3D | Existing depth pass + Blender add-on displacement | Research 2026-11-17: AMV tutorials already teach this exact move with generated depth maps ("3D Lighting with Depth Maps in After Effects", amvtutorial.com) and AE 2025+ native 3D camera/spotlight setups; a worked guide + preset fits the scene-planning track — docs-sized, not a new model. DONE 2026-11-19 (v0.5.0): docs/depth-3d-lighting-guide.md (AE Displacement Map + 3D layer + Point light; Blender Z-Depth + light + ground plane; normal-pass light-direction tip). Sources re-verified 2026-11-19: amvtutorial listing + two Adobe helpx pages. |

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

- **2026-11-20 (v0.6.0)** - **Chroma keyer** (ideas pool, anchor):
  `amvfx/keying.py` — classic green/blue-screen alpha without a model
  (normalised RGB distance to the key colour, smoothstep feather ramp,
  despill clamped to the larger other channel, weighted by 1-alpha);
  `--alpha-backend chroma` + `--key-color/--key-similarity/--key-smoothness`
  in the CLI and pipeline, alpha-source radio + key-colour dropdown in
  the Gradio app, provenance + `alpha_backend` in the manifest,
  `tests/test_keying.py` (6 tests), verified end-to-end on a synthetic
  green-screen frame. **Blender add-on: depth-layer stage** (camera-rig
  track, third stone): new `amvfx.add_depth_layers` operator + "Scene
  Planning" panel button and props (`depth_layers` 2–6, `depth_spread`):
  the plate split into depth bands on separate planes, each masked by
  soft Map Range ramps on the depth pass, Z-spaced, rescaled by the
  distance ratio to hold the plate framing; add-on version (0, 5, 0);
  headless test extended in `tests/test_blender_addon.py` — not runnable
  on the dev VM, which has no Blender binary. **UI: gallery Download All**
  (`buttons=["download", "download_all"]` on the pass gallery — Gradio
  6.20+ feature, installed 6.31.0; `tests/test_app.py`). **Docs:
  quickstart GIF/screenshots** (backlog #3 DONE): real lite run on
  `examples/test_portrait.jpg` → labelled animated GIF + contact sheet
  in `docs/images/`, README quickstart section. Research 2026-11-20:
  Blender 5.0 released 18 Nov 2025 (5.2 LTS 14 Jul 2026; adaptive
  subdivision no longer experimental — relevant to our Subdiv levels);
  Gradio 6.32.0 latest; 2.5D parallax workflow cross-checked across
  three tutorials; chroma-key math cross-checked across two write-ups.
- **2026-11-19 (v0.5.0)** - **Tests: pipeline smoke test** (backlog #4
  DONE): `tests/test_smoke.py` — a 2-frame synthetic video through
  the lite profile end-to-end on the real cached ONNX models; asserts
  the manifest (frames/profile/passes/provenance), PNGs for every
  pass, per-pass MP4s when ffmpeg exists, and sane pass values
  (alpha/depth means strictly inside 0..255). Single-threaded ORT
  (`OMP_NUM_THREADS=1` in the test); measured peak ~3.3 GB (BiRefNet
  512) and OOM-killed twice on the busy shared VM before passing.
  **Blender add-on: ground plane** (camera-rig track, second stone):
  new `amvfx.add_ground_plane` operator + "Scene Planning" panel box
  (camera + ground plane + depth prop): an `AMVFX_Ground` plane at
  the plate's bottom edge, plate-width, extending toward the camera,
  dark fully-rough Principled material, reused on re-run; add-on
  version (0, 4, 0); headless test extended in
  `tests/test_blender_addon.py` — not runnable on the dev VM, which
  has no Blender binary. **Bug-fix sweep (paths with spaces, DONE)**:
  full re-audit found no gaps — all subprocess calls list-form, both
  JSX panels use q() quoting. **Docs: depth-map 3D lighting guide**
  (`docs/depth-3d-lighting-guide.md`): AE native route (Displacement
  Map + 3D layer + Point light) and Blender route (Z-Depth + light +
  ground plane), normal-pass light-direction tip. **UI: job summary
  shows the output folder** (`app.format_job_note` + `tests/test_app.py`;
  test_app sanitizes no_proxy first, same httpx trap as the app
  import check). Research 2026-11-19: Blender
  `primitive_plane_add` confirmed in official API docs; amvtutorial
  depth-lighting article + two Adobe helpx pages re-verified;
  low-quality search hits claiming Blender 5.1/5.2 were flagged
  unverified and not used.
- **2026-11-18 (v0.4.0)** - **Installer: repair mode** (`--repair`
  flag + GUI checkbox): refreshes app files and add-ons, keeps the
  existing venv (no recreate, no pip reinstall) and local models;
  errors clearly on a fresh target, and a plain re-run over an
  existing install now hints at `--repair` (`installer/install.py` +
  `tests/test_installer.py`). **Blender add-on: camera-from-plate**
  (new `amvfx.add_camera` operator + panel button): creates/reuses
  `AMVFX_Camera`, sets it as scene camera, render resolution from the
  plate pixels, source plate as camera background image (FIT, behind
  the scene), camera framed on the plate from its vertical FOV
  (headless test extended in `tests/test_blender_addon.py` — not
  runnable on the dev VM, which has no Blender binary). **AE selected
  clip: respect layer in/out**: CLI `--start-frame/--end-frame`
  (end exclusive), `pipeline.run` + `extract_frames` support,
  `frame_range` in the manifest; both AE panels map the selected
  layer's in/out points (comp time -> source frames via startTime and
  stretch; reversed layers fall back to whole file) — `tests/test_trim.py`
  plus a real 12-frame lite run trimmed 3..8 verified by hand.
  **Performance: model session cache** — ONNX sessions cached
  process-wide in `backends.py` (`clear_session_cache()` for tests);
  measured on this VM: repeat-job construction 1.86s -> 0.20s (Depth)
  and 9.43s -> 0.71s (BiRefNet), ~10.4s saved per repeat lite job.
  **Bug-fix sweep (partial)**: PowerShell single-quote escaping in the
  installer shortcut + quote-stripping `q()` in both JSX generate
  commands; audit found all subprocess calls already list-form.
  Research 2026-11-18: SAM 2.1 Apache-2.0 verified (SAM 3 gated, avoid);
  MatAnyone 2 S-Lab 1.0 non-commercial-only verified; Blender camera
  background images and AE `inPoint`/`outPoint` confirmed in official
  docs.
- **2026-11-17 (v0.3.0)** - UI: **per-pass preview zoom**. Clicking a
  gallery thumbnail now shows that pass full-size in a persistent
  "Selected pass" viewer under the gallery (new `amvfx/preview.py` +
  `tests/test_preview.py`); the gallery also keeps its built-in
  lightbox (`allow_preview`, on by default in Gradio 6.31 — verified
  against the installed version's docs and signature, so this item
  was really about the persistent viewer, not the lightbox). Same
  bundle: **updater shows what changed** (latest commit subjects
  from the GitHub commits API, unauthenticated 60/hr, degrades to
  silence offline — `updater.recent_commits()` + tests) and **AE
  comp naming** (both panels now build `AMVFX_<source-stem>` instead
  of `AMVFX_AMVFX_source`; JSX syntax-checked only, never run in AE).
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

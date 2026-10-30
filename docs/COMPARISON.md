# Beeble VFX Pass Generator vs AMVFX — honest comparison

Researched 2026-10-30 from Beeble's official docs (docs.beeble.ai) and the
open-source projects listed in MODELS.md. AMVFX is an independent
open-source alternative, not a copy: no Beeble code, weights or assets.

## What Beeble does (SwitchLight 3.0)

- Input: image, video, image sequence (EXR/PNG/JPG; MP4/MOV ProRes/H.264/H.265), up to 4K, up to 1 h (desktop)
- Passes: Alpha, Depth, Normal (object-space/OpenGL), Base Color, Roughness, Specular, Metallic
- Output: 16-bit multi-layer EXR (all passes in one file per frame), PNG sequences, per-pass MP4
- Extras: 3D Relight editor (HDRI/point/area/sun/video lights), Blender/Unreal/Nuke loaders, batch render queue, cloud credits or paid desktop app

## AMVFX parity today (v0.1)

| Capability | Beeble | AMVFX |
|---|---|---|
| Alpha pass | ✅ MatAnyone-2 class matting | ✅ BiRefNet (per-frame + light temporal smoothing) |
| Depth pass | ✅ | ✅ Depth Anything V2 Small, clip-wide normalization |
| Normal pass | ✅ model, object-space/OpenGL per spec | ✅ derived from depth (lite) / Marigold Normals (gpu) / NormalCrafter (video, GPU, temporally consistent). Export format selectable OpenGL (Beeble-matching) or DirectX. Space: AMVFX declares the plate/object frame — for a 2.5D plate the unrotated plate frame is the object frame; true per-object space would need object poses a monocular plate doesn't contain |
| Base color | ✅ | ✅ gpu profile (Marigold IID) |
| Roughness | ✅ | ✅ gpu profile (Marigold IID) |
| Metallic | ✅ | ✅ gpu profile (Marigold IID) |
| Specular | ✅ | ✅ derived PBR F0 from base color + metallic |
| AO pass | (older SwitchLight listed AO) | ✅ derived bonus pass |
| Multi-layer EXR, Beeble layer names | ✅ | ✅ 16-bit float, same layer naming |
| PNG sequences / per-pass MP4 | ✅ | ✅ |
| Input image / video | ✅ | ✅ |
| 4K / 1-hour renders | ✅ | ⚠️ no hard cap in code, but lite profile is CPU-slow; practical short clips |
| Temporal consistency | ✅ video-native model | ⚠️ partial: shared depth scale + alpha smoothing; video-native models are roadmap |
| 3D Relight editor | ✅ | ❌ roadmap (passes are built for Blender/Unreal/Nuke use) |
| Price | paid / credits | free, open source (MIT code) |

## Known gaps to close next

1. Video-native temporal models (Video Depth Anything, NormalCrafter, MatAnyone 2 subject to license).
2. Unified G-buffer backend via NVIDIA Cosmos DiffusionRenderer for GPU servers (27–48 GB VRAM).
3. A simple relight preview (Blender loader script ships in `blender/`; in-app HDRI relight is next).
4. Object-space normals (current normals are view/camera-space, like most estimators).

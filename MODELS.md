# AMVFX model stack & licenses

AMVFX is an original, clean-room composition of published open-source
models. It contains **no Beeble code, weights or assets** — Beeble's
SwitchLight is proprietary. AMVFX reproduces the *workflow* (footage →
VFX passes) using the models below. Every job writes a `manifest.json`
recording exactly which model (or derivation) produced each pass.

| Pass | AMVFX source | Repo | License | Commercial use |
|---|---|---|---|---|
| Depth | Depth Anything V2 **Small** | `depth-anything/Depth-Anything-V2-Small` via `onnx-community/depth-anything-v2-small` | Apache-2.0 | ✅ (only the Small checkpoint is Apache-2.0 — Base/Large/Giant are CC-BY-NC, so AMVFX does not use them) |
| Alpha | BiRefNet (512 default / 1024 quality) | `ZhengPeng7/BiRefNet` via `onnx-community/BiRefNet_512x512-ONNX` / `BiRefNet-ONNX` | MIT | ✅ |
| Base color, Roughness, Metallic | Marigold IID Appearance v1.1 | `prs-eth/marigold-iid-appearance-v1-1` | CreativeML Open RAIL++-M | ⚠️ allowed with RAIL use restrictions — read the license before commercial deployment |
| Normal (gpu profile) | Marigold Normals v1.1 | `prs-eth/marigold-normals-v1-1` | CreativeML Open RAIL++-M | ⚠️ same as above |
| Normal (video, GPU) | NormalCrafter (ICCV 2025) | `Binyr/NormalCrafter` (GitHub), weights `Yanrui95/NormalCrafter` | Code MIT; weights tagged Apache-2.0 | ⚠️ fine-tuned from Stable Video Diffusion — check Stability AI terms for commercial use. Temporally consistent video normals; needs ~6 GB VRAM at 512px, ~20 GB at 1024×576. Wired as `--normal-backend normalcrafter` (shells to a local clone; GPU-only, not run on the CPU dev box). Note: Beeble does **not** disclose using NormalCrafter — its normals come from its own SwitchLight models. NormalCrafter is the closest free equivalent, and it out-scores Marigold normals in its paper's benchmarks |
| Normal (lite profile) | Derived from the depth pass | — (AMVFX code, MIT) | MIT | ✅ deterministic screen-space gradient |
| Specular | Derived (PBR F0) | — (AMVFX code, MIT) | MIT | ✅ `F0 = mix(0.04, basecolor, metallic)` |
| AO | Derived from the depth pass | — (AMVFX code, MIT) | MIT | ✅ local depth-occlusion approximation |

## Optional / roadmap models (researched, not bundled)

| Model | What it would add | License notes |
|---|---|---|
| MoGe-2 (`Ruicheng/moge-2-vitl-normal`, microsoft/MoGe) | Metric depth + model normals in one fast ViT pass; backend stub included (`MoGeBackend`) | MIT ✅ |
| NVIDIA Cosmos DiffusionRenderer (`nv-tlabs/cosmos-transfer1-diffusion-renderer`) | Single unified video G-buffer model (basecolor, normal, depth, roughness, metallic) + forward relighting — the closest open analogue to SwitchLight | Code Apache-2.0; weights NVIDIA Open Model License; needs ~27–48 GB VRAM for video |
| Video Depth Anything / DepthCrafter | Temporally consistent video depth (replaces per-frame depth + clip-wide normalization) | Check per-checkpoint license |
| NormalCrafter | Temporally consistent video normals | Check license |
| MatAnyone 2 | Memory-propagated video matting (Beeble itself licenses this model for its Background Remover) | S-Lab license — verify terms before any commercial use |
| RGB↔X (`zheng95z/rgb-to-x`) | Alternative albedo/roughness/metallic/normals estimator, interior scenes | Check repo license |
| BRIA RMBG-2.0 | Strong alpha model | ❌ CC-BY-NC for open weights — **not used** |

## Why two profiles?

- **lite** — ONNX models only, runs on a CPU (including free Hugging Face
  Spaces). Passes: source, alpha, depth, normal (derived), AO.
- **gpu** — adds the Marigold diffusion models for base color, roughness,
  metallic and model normals, plus the derived specular pass. This is the
  full 7-pass Beeble-equivalent set.

"""AMVFX pipeline: image/video -> Beeble-style VFX passes.

Pass set (mirrors Beeble's VFX Pass Generator):
  source, alpha, depth, normal, basecolor, roughness, metallic, specular
  (+ ao as a bonus derived pass)

Provenance is tracked per pass in manifest.json: which open model produced
it, or that it was deterministically derived from other passes.
"""
import json
import os

import numpy as np

from . import geometry, io_utils

ALL_PASSES = ["source", "alpha", "depth", "normal", "basecolor",
              "roughness", "metallic", "specular", "ao"]

# Which profile can produce which pass (before derivation rules apply)
LITE_PASSES = ["source", "alpha", "depth", "normal", "ao"]
GPU_PASSES = ALL_PASSES


def _smooth_alpha(alphas, weight_prev: float = 0.35):
    """Light exponential temporal smoothing for video mattes."""
    out = []
    prev = None
    for a in alphas:
        if prev is not None and prev.shape == a.shape:
            a = (1 - weight_prev) * a + weight_prev * prev
        out.append(a)
        prev = a
    return out


def generate(frames, profile: str = "lite", passes=None,
            alpha_quality: bool = False, marigold_steps: int = 4,
            normal_format: str = "opengl", progress=None):
    """Generate passes for a list of RGB float frames.

    Returns (per_frame_passes, provenance) where per_frame_passes is a list
    of dicts pass_name -> float array.
    """
    passes = passes or (LITE_PASSES if profile == "lite" else GPU_PASSES)
    provenance = {}
    n = len(frames)

    def say(msg):
        if progress:
            progress(msg)

    # ---- AI passes, frame by frame -------------------------------------
    from .backends import DepthAnythingOnnx, BiRefNetOnnx
    raw_depths = None
    if "depth" in passes or "normal" in passes or "ao" in passes:
        say("Depth: Depth Anything V2 Small (ONNX)")
        depth_model = DepthAnythingOnnx()
        raw_depths = [depth_model.raw_depth(f) for f in frames]
        provenance["depth"] = "model: depth-anything/Depth-Anything-V2-Small (Apache-2.0), normalized clip-wide"
        del depth_model

    alphas = None
    if "alpha" in passes:
        say("Alpha: BiRefNet (ONNX)")
        alpha_model = BiRefNetOnnx(quality=alpha_quality)
        alphas = [alpha_model.alpha(f) for f in frames]
        if n > 1:
            alphas = _smooth_alpha(alphas)
        provenance["alpha"] = ("model: ZhengPeng7/BiRefNet (MIT)"
                               + (", light temporal smoothing" if n > 1 else ""))
        del alpha_model

    marigold = None
    intrinsics = normals_model = None
    if profile == "gpu":
        need_iid = any(p in passes for p in ("basecolor", "roughness", "metallic", "specular"))
        need_normals = "normal" in passes
        if need_iid or need_normals:
            from .backends import MarigoldBackend
            marigold = MarigoldBackend()
        if need_iid:
            say("Intrinsics: Marigold IID Appearance (albedo/roughness/metallic)")
            intrinsics = [marigold.intrinsics(f, steps=marigold_steps) for f in frames]
            marigold.free_iid()
            provenance["basecolor"] = "model: prs-eth/marigold-iid-appearance-v1-1 (RAIL++-M)"
            provenance["roughness"] = "model: prs-eth/marigold-iid-appearance-v1-1 (RAIL++-M)"
            provenance["metallic"] = "model: prs-eth/marigold-iid-appearance-v1-1 (RAIL++-M)"
        if need_normals:
            say("Normals: Marigold Normals")
            normals_model = [marigold.normals(f, steps=marigold_steps) for f in frames]
            marigold.free_normals()
            provenance["normal"] = "model: prs-eth/marigold-normals-v1-1 (RAIL++-M)"

    # ---- Assemble per-frame pass dicts ---------------------------------
    lo = hi = None
    if raw_depths is not None:
        lo, hi = geometry.percentile_range(raw_depths)
    results = []
    for i, frame in enumerate(frames):
        d = {}
        if "source" in passes:
            d["source"] = frame
        if alphas is not None:
            d["alpha"] = alphas[i]
        depth_n = None
        if raw_depths is not None:
            depth_n = geometry.normalize_depth(raw_depths[i], lo, hi)
            if "depth" in passes:
                d["depth"] = depth_n
        if intrinsics is not None:
            if "basecolor" in passes:
                d["basecolor"] = intrinsics[i]["albedo"]
            if "roughness" in passes:
                d["roughness"] = intrinsics[i]["roughness"]
            if "metallic" in passes:
                d["metallic"] = intrinsics[i]["metallic"]
            if "specular" in passes:
                d["specular"] = geometry.specular_f0(intrinsics[i]["albedo"],
                                                      intrinsics[i]["metallic"])
                provenance["specular"] = "derived: PBR F0 = mix(0.04, basecolor, metallic)"
        if "normal" in passes:
            if normals_model is not None:
                d["normal"] = normals_model[i]
            elif depth_n is not None:
                d["normal"] = geometry.depth_to_normal(depth_n)
                provenance["normal"] = "derived: screen-space gradient of the depth pass"
            if "normal" in d and normal_format != "opengl":
                d["normal"] = geometry.convert_normal_format(d["normal"], normal_format)
                provenance["normal"] += f"; converted to {normal_format} convention"
        if "ao" in passes and depth_n is not None:
            d["ao"] = geometry.ao_from_depth(depth_n)
            provenance["ao"] = "derived: local depth-occlusion approximation"
        results.append(d)
    provenance["source"] = "input frame"
    return results, provenance


def run(input_path: str, out_dir: str, profile: str = "lite", passes=None,
        alpha_quality: bool = False, marigold_steps: int = 4,
        normal_format: str = "opengl", normal_backend: str = "auto",
        max_frames: int = 0, max_width: int = 0,
        export_png: bool = True, export_mp4: bool = True,
        export_exr: bool = True, progress=None):
    """Full job: load input, generate passes, export Beeble-style outputs.

    Returns the manifest dict (also written to out_dir/manifest.json).
    """
    ext = os.path.splitext(input_path)[1].lower()
    is_video = ext in (".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v")
    if is_video:
        frames, fps = io_utils.extract_frames(input_path, max_frames, max_width)
    else:
        frames, fps = [io_utils.load_image(input_path, max_width)], 24.0
    if not frames:
        raise RuntimeError("No frames decoded from input")
    per_frame, provenance = generate(frames, profile=profile, passes=passes,
                                     alpha_quality=alpha_quality,
                                     marigold_steps=marigold_steps,
                                     normal_format=normal_format,
                                     progress=progress)
    # Optional: replace normals with NormalCrafter's temporally consistent
    # video normals (GPU machines only; upstream repo clone required).
    if normal_backend == "normalcrafter":
        if not is_video:
            raise RuntimeError("NormalCrafter backend works on video input")
        from .backends import NormalCrafterBackend
        backend = NormalCrafterBackend()
        if progress:
            progress("Normals: NormalCrafter (video diffusion, GPU)")
        pngs = backend.normals_for_video(input_path, out_dir)
        import cv2
        replaced = 0
        for i, d in enumerate(per_frame):
            if i < len(pngs):
                img = cv2.imread(pngs[i], cv2.IMREAD_COLOR)
                if img is not None:
                    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
                    if img.shape[:2] != frames[i].shape[:2]:
                        img = cv2.resize(img, (frames[i].shape[1], frames[i].shape[0]))
                    if normal_format != "opengl":
                        img = geometry.convert_normal_format(img, normal_format)
                    d["normal"] = img
                    replaced += 1
        if replaced:
            provenance["normal"] = ("model: NormalCrafter (ICCV 2025, MIT code / "
                                    "Apache-2.0-tagged weights), temporally consistent "
                                    "video normals")
    os.makedirs(out_dir, exist_ok=True)
    produced = [p for p in per_frame[0].keys()]
    if export_png:
        for pname in produced:
            pdir = os.path.join(out_dir, pname)
            for i, d in enumerate(per_frame):
                io_utils.save_png(os.path.join(pdir, f"frame_{i:04d}.png"), d[pname])
    if export_mp4 and is_video:
        for pname in produced:
            pdir = os.path.join(out_dir, pname)
            if os.path.isdir(pdir):
                io_utils.encode_mp4(pdir, os.path.join(out_dir, f"{pname}.mp4"), fps)
    exr_written = False
    if export_exr and io_utils.has_exr():
        exr_dir = os.path.join(out_dir, "exr")
        for i, d in enumerate(per_frame):
            io_utils.write_multilayer_exr(
                os.path.join(exr_dir, f"frame_{i:04d}.exr"), d)
        exr_written = True
    manifest = {
        "app": "AMVFX",
        "input": os.path.basename(input_path),
        "kind": "video" if is_video else "image",
        "frames": len(frames),
        "fps": fps,
        "resolution": [int(frames[0].shape[1]), int(frames[0].shape[0])],
        "profile": profile,
        "normal_format": normal_format,
        "normal_space": "object (plate frame; see amvfx/geometry.py note)",
        "passes": produced,
        "provenance": {k: provenance.get(k, "") for k in produced},
        "exports": {"png_sequences": export_png,
                    "mp4_per_pass": bool(export_mp4 and is_video),
                    "multilayer_exr": exr_written},
    }
    with open(os.path.join(out_dir, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)
    return manifest

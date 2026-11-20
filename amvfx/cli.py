"""AMVFX command line: python -m amvfx INPUT -o OUT [--profile lite|gpu]"""
import argparse
import json

from .pipeline import ALL_PASSES, run


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="amvfx",
        description="Open-source VFX passes generator (Beeble-style): "
                    "turn an image or video into alpha, depth, normal, "
                    "base color, roughness, metallic and specular passes.")
    ap.add_argument("input", help="image or video file")
    ap.add_argument("-o", "--out", required=True, help="output directory")
    ap.add_argument("--profile", choices=["lite", "gpu"], default="lite",
                    help="lite = ONNX/CPU models; gpu = adds Marigold "
                         "intrinsics + normals (torch, GPU recommended)")
    ap.add_argument("--passes", default="",
                    help="comma list from: " + ",".join(ALL_PASSES))
    ap.add_argument("--alpha-quality", action="store_true",
                    help="use full BiRefNet instead of BiRefNet-lite for alpha")
    ap.add_argument("--alpha-backend", choices=["birefnet", "chroma"],
                    default="birefnet",
                    help="birefnet = AI matte (default); chroma = classic "
                         "green/blue-screen key, no model")
    ap.add_argument("--key-color", choices=["green", "blue"], default="green",
                    help="screen colour for --alpha-backend chroma")
    ap.add_argument("--key-similarity", type=float, default=0.25,
                    help="chroma key: normalised distance below which a "
                         "pixel is fully transparent (0-1)")
    ap.add_argument("--key-smoothness", type=float, default=0.15,
                    help="chroma key: width of the feathered ramp above "
                         "similarity (0-1)")
    ap.add_argument("--normal-format", choices=["opengl", "directx"],
                    default="opengl",
                    help="normal map green-channel convention (Beeble exports OpenGL)")
    ap.add_argument("--normal-backend", choices=["auto", "normalcrafter"],
                    default="auto",
                    help="normalcrafter = temporally consistent video normals "
                         "(needs a NormalCrafter clone + CUDA GPU)")
    ap.add_argument("--marigold-steps", type=int, default=4)
    ap.add_argument("--max-frames", type=int, default=0)
    ap.add_argument("--max-width", type=int, default=0)
    ap.add_argument("--start-frame", type=int, default=0,
                    help="trim a video: first frame to process (0 = start)")
    ap.add_argument("--end-frame", type=int, default=0,
                    help="trim a video: frame to stop before (0 = to the end)")
    ap.add_argument("--no-mp4", action="store_true")
    ap.add_argument("--no-exr", action="store_true")
    args = ap.parse_args(argv)
    if args.end_frame and args.end_frame <= args.start_frame:
        ap.error("--end-frame must be greater than --start-frame")
    passes = [p.strip() for p in args.passes.split(",") if p.strip()] or None
    manifest = run(args.input, args.out, profile=args.profile, passes=passes,
                   alpha_quality=args.alpha_quality,
                   marigold_steps=args.marigold_steps,
                   normal_format=args.normal_format,
                   normal_backend=args.normal_backend,
                   alpha_backend=args.alpha_backend,
                   key_color=args.key_color,
                   key_similarity=args.key_similarity,
                   key_smoothness=args.key_smoothness,
                   max_frames=args.max_frames, max_width=args.max_width,
                   start_frame=args.start_frame, end_frame=args.end_frame,
                   export_mp4=not args.no_mp4, export_exr=not args.no_exr,
                   progress=lambda m: print(f"[amvfx] {m}", flush=True))
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

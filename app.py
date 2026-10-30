"""AMVFX - Gradio app (Hugging Face Spaces entry point).

Upload an image or short video, pick a profile, get Beeble-style VFX
passes back as preview images plus a ZIP with PNG sequences, per-pass
MP4s and multi-layer EXRs.
"""
import os
import shutil
import sys
import tempfile
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import gradio as gr

from amvfx.pipeline import LITE_PASSES, run

GPU_AVAILABLE = False
try:
    import torch
    GPU_AVAILABLE = torch.cuda.is_available()
except Exception:
    pass

PROFILES = ["lite"] + (["gpu"] if GPU_AVAILABLE else [])


def process(file_obj, profile, passes, progress=gr.Progress()):
    if file_obj is None:
        raise gr.Error("Upload an image or video first.")
    src = file_obj if isinstance(file_obj, str) else file_obj.name
    workdir = tempfile.mkdtemp(prefix="amvfx_")
    out_dir = os.path.join(workdir, "out")
    chosen = passes or LITE_PASSES
    manifest = run(src, out_dir, profile=profile, passes=chosen,
                   max_frames=48, max_width=1024,
                   progress=lambda m: progress(0.1, desc=m))
    # previews: first frame of each pass
    previews = []
    for pname in manifest["passes"]:
        p = os.path.join(out_dir, pname, "frame_0000.png")
        if os.path.exists(p):
            previews.append((p, pname))
    zip_path = os.path.join(workdir, "amvfx_passes.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for root, _dirs, files in os.walk(out_dir):
            for fn in files:
                full = os.path.join(root, fn)
                z.write(full, os.path.relpath(full, out_dir))
    note = (f"Profile: {manifest['profile']} - {manifest['frames']} frame(s) "
            f"at {manifest['resolution'][0]}x{manifest['resolution'][1]}. "
            f"Passes: {', '.join(manifest['passes'])}. "
            "ZIP contains PNG sequences"
            + (", per-pass MP4s" if manifest["exports"]["mp4_per_pass"] else "")
            + (" and multi-layer EXRs (Beeble-style layer names)."
               if manifest["exports"]["multilayer_exr"] else "."))
    return previews, zip_path, note


with gr.Blocks(title="AMVFX - Open-Source VFX Passes") as demo:
    gr.Markdown(
        "# AMVFX - Open-Source VFX Passes Generator\n"
        "Turn footage into **relightable VFX passes** - alpha, depth, normal, "
        "base color, roughness, metallic, specular - using only open-source "
        "models. An open alternative to Beeble's VFX Pass Generator "
        "(SwitchLight), built from Depth Anything V2, BiRefNet and Marigold.\n\n"
        "**lite** profile runs on CPU (depth, alpha, depth-derived normal, AO). "
        "**gpu** profile adds Marigold albedo / roughness / metallic / model "
        "normals and the derived specular F0 pass.")
    with gr.Row():
        inp = gr.File(label="Image or video", file_types=["image", "video"])
        with gr.Column():
            profile = gr.Radio(PROFILES, value="lite", label="Profile")
            passes = gr.CheckboxGroup(
                choices=["source", "alpha", "depth", "normal", "basecolor",
                         "roughness", "metallic", "specular", "ao"],
                value=["source", "alpha", "depth", "normal"],
                label="Passes (gpu profile needed for basecolor/roughness/metallic/specular)")
            btn = gr.Button("Generate passes", variant="primary")
    gallery = gr.Gallery(label="Pass previews (frame 1)", columns=4)
    zip_out = gr.File(label="All passes (ZIP)")
    note_out = gr.Textbox(label="Job summary", interactive=False)
    btn.click(process, [inp, profile, passes], [gallery, zip_out, note_out])

if __name__ == "__main__":
    demo.launch()

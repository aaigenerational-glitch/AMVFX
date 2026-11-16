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

    # ---------------- Updates: check + install in place ----------------
    APP_DIR = os.path.dirname(os.path.abspath(__file__))
    ON_SPACE = bool(os.environ.get("SPACE_ID"))

    def _check_updates():
        from amvfx import updater
        info = updater.check_for_update(APP_DIR)
        if info.get("error"):
            return (f"You are on v{info['current']}. Could not reach "
                    f"GitHub to check for updates.")
        if info["update_available"]:
            return (f"Update available: v{info['current']} -> "
                    f"v{info['latest']}. 'Update now' installs it in "
                    "place - models, venv and settings are kept - then "
                    "restart the app.")
        return f"You are up to date (v{info['current']})."

    def _apply_update():
        from amvfx import updater
        try:
            new = updater.apply_update(APP_DIR, log=lambda m: None)
        except Exception as exc:
            return f"Update failed: {exc}"
        return (f"Updated to v{new}. Close this app window/process and "
                "reopen AMVFX (desktop shortcut) to use the new version.")

    with gr.Accordion("Updates - get new features without reinstalling",
                      open=False):
        if ON_SPACE:
            gr.Markdown("This hosted copy updates itself when the "
                        "project publishes a new version. To update a "
                        "*local* install, use this panel in the app on "
                        "your own machine.")
        else:
            from amvfx import __version__ as _v
            gr.Markdown(f"Installed version: **v{_v}**. Updates come "
                        "from the AMVFX GitHub repo and install over "
                        "this folder - no reinstall, no re-download of "
                        "models.")
            with gr.Row():
                check_btn = gr.Button("Check for updates")
                update_btn = gr.Button("Update now", variant="primary")
            update_out = gr.Textbox(label="Update status",
                                    interactive=False)
            check_btn.click(_check_updates, None, update_out)
            update_btn.click(_apply_update, None, update_out)

if __name__ == "__main__":
    demo.launch()

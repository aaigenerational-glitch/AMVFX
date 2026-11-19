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

from amvfx import history, preview
from amvfx.pipeline import LITE_PASSES, run

GPU_AVAILABLE = False
try:
    import torch
    GPU_AVAILABLE = torch.cuda.is_available()
except Exception:
    pass

PROFILES = ["lite"] + (["gpu"] if GPU_AVAILABLE else [])


def format_job_note(manifest, out_dir):
    """One-line job summary for the UI: profile, frames, resolution, passes,
    exports - and the output folder, so a user can find the files on disk
    without digging through temp dirs."""
    note = (f"Profile: {manifest['profile']} - {manifest['frames']} frame(s) "
            f"at {manifest['resolution'][0]}x{manifest['resolution'][1]}. "
            f"Passes: {', '.join(manifest['passes'])}. "
            "ZIP contains PNG sequences"
            + (", per-pass MP4s" if manifest["exports"]["mp4_per_pass"] else "")
            + (" and multi-layer EXRs (Beeble-style layer names)."
               if manifest["exports"]["multilayer_exr"] else "."))
    return note + f" Output folder: {out_dir}"


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
    note = format_job_note(manifest, out_dir)
    # Remember this job for the "Recent jobs" list (best-effort: a
    # history failure must never break a finished job).
    history.record_job(src, profile, manifest["passes"], out_dir,
                       manifest["frames"], manifest["resolution"],
                       zip_path=zip_path)
    history_md = history.format_history(history.load_history())
    # Full-size viewer defaults to the first pass; clicking a thumbnail
    # below swaps it (see gallery.select handler).
    zoom_path, zoom_label = preview.select_preview(previews, 0)
    return previews, zoom_path, zoom_label, zip_path, note, history_md


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
    gallery = gr.Gallery(
        label="Pass previews (frame 1) — click a thumbnail to zoom",
        columns=4, allow_preview=True)
    # Persistent full-size viewer: clicking a thumbnail above swaps
    # this to that pass at full resolution (the gallery's own lightbox
    # is transient). The full ZIP download is below; the gallery
    # lightbox also offers a per-image download button.
    zoom = gr.Image(label="Selected pass (full size)")
    zoom_name = gr.Textbox(label="Zoomed pass", interactive=False,
                           value="No preview selected")

    def _on_preview_select(previews, evt: gr.SelectData):
        return preview.select_preview(previews, evt.index)

    gallery.select(_on_preview_select, [gallery], [zoom, zoom_name])

    zip_out = gr.File(label="All passes (ZIP)")
    note_out = gr.Textbox(label="Job summary", interactive=False)

    # ---------------- Recent jobs: remember what was run ----------------
    def _refresh_history():
        return history.format_history(history.load_history())

    def _clear_history():
        history.clear_history()
        return history.format_history([])

    with gr.Accordion("Recent jobs", open=False):
        gr.Markdown("Recent generation jobs on this machine - input, "
                    "profile, passes and output folder. Stored in "
                    "~/.amvfx/history.json; app updates never wipe it.")
        history_md = gr.Markdown(_refresh_history())
        with gr.Row():
            refresh_btn = gr.Button("Refresh")
            clear_btn = gr.Button("Clear history")
        refresh_btn.click(_refresh_history, None, history_md)
        clear_btn.click(_clear_history, None, history_md)

    btn.click(process, [inp, profile, passes],
              [gallery, zoom, zoom_name, zip_out, note_out, history_md])

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
            msg = (f"Update available: v{info['current']} -> "
                   f"v{info['latest']}. 'Update now' installs it in "
                   "place - models, venv and settings are kept - then "
                   "restart the app.")
            commits = info.get("recent_commits") or []
            if commits:
                msg += "\n\nWhat changed:\n" + "\n".join(
                    f"- {c['sha']} {c['message']}" for c in commits)
            return msg
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

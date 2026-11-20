"""App helper tests: the job-summary note shown after a generation.

Pure function, no Gradio launch and no model weights needed.
Run: python tests/test_app.py
"""
import os
import sys

# This VM's no_proxy contains bracketed IPv6 entries that crash httpx
# (used by gradio) at import - sanitize before importing app, same as
# the app.py import check in the daily job.
os.environ["no_proxy"] = "localhost,127.0.0.1"
os.environ["NO_PROXY"] = "localhost,127.0.0.1"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as app_module


def _manifest(**overrides):
    m = {"profile": "lite", "frames": 2, "resolution": [64, 48],
         "passes": ["source", "alpha", "depth", "normal", "ao"],
         "exports": {"mp4_per_pass": True, "multilayer_exr": False}}
    m.update(overrides)
    return m


def test_note_shows_output_folder():
    note = app_module.format_job_note(_manifest(), "/tmp/amvfx job/out")
    assert "Output folder: /tmp/amvfx job/out" in note, note
    assert "Profile: lite - 2 frame(s) at 64x48." in note, note
    assert "Passes: source, alpha, depth, normal, ao." in note, note
    assert "per-pass MP4s" in note, note
    assert "multi-layer EXRs" not in note, note
    print("PASS test_note_shows_output_folder")


def test_note_exr_and_no_mp4():
    m = _manifest(exports={"mp4_per_pass": False, "multilayer_exr": True})
    note = app_module.format_job_note(m, "/tmp/out")
    assert "per-pass MP4s" not in note, note
    assert "multi-layer EXRs" in note, note
    assert note.endswith("Output folder: /tmp/out"), note
    print("PASS test_note_exr_and_no_mp4")


def test_gallery_has_download_buttons():
    # The pass gallery must offer per-image download and download-all
    # (Gradio 6.20+ Gallery buttons), so editors can grab the previews
    # without waiting for the ZIP.
    import gradio as gr
    galleries = [b for b in app_module.demo.blocks.values()
                 if isinstance(b, gr.Gallery)]
    assert galleries, "no Gallery in the app"
    buttons = galleries[0].buttons or []
    assert "download" in buttons, buttons
    assert "download_all" in buttons, buttons
    print("PASS test_gallery_has_download_buttons")


def test_alpha_source_controls_exist():
    # Chroma key must be reachable from the UI: an alpha-source radio
    # and a key-colour dropdown.
    import gradio as gr
    radios = [b for b in app_module.demo.blocks.values()
              if isinstance(b, gr.Radio) and b.label == "Alpha source"]
    assert radios, "no 'Alpha source' radio"
    # Gradio 6 stores choices as (value, label) tuples.
    choice_values = [c[0] if isinstance(c, tuple) else c
                     for c in radios[0].choices]
    assert "Chroma key (green/blue screen)" in choice_values, \
        radios[0].choices
    dropdowns = [b for b in app_module.demo.blocks.values()
                 if isinstance(b, gr.Dropdown)
                 and b.label == "Key colour (chroma key only)"]
    assert dropdowns, "no key-colour dropdown"
    dd_values = [c[0] if isinstance(c, tuple) else c
                 for c in dropdowns[0].choices]
    assert set(dd_values) == {"green", "blue"}, dropdowns[0].choices
    print("PASS test_alpha_source_controls_exist")


if __name__ == "__main__":
    test_note_shows_output_folder()
    test_note_exr_and_no_mp4()
    test_gallery_has_download_buttons()
    test_alpha_source_controls_exist()
    print("all app tests passed")

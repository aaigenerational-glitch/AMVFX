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


if __name__ == "__main__":
    test_note_shows_output_folder()
    test_note_exr_and_no_mp4()
    print("all app tests passed")

"""Pipeline smoke test: a 2-frame synthetic video through the lite profile.

End-to-end check of pipeline.run with the real cached ONNX models
(Depth Anything V2 Small + BiRefNet lite): manifest, PNG sequences and
per-pass MP4s all land where the app and the Blender add-on expect them.
Needs the model weights in the local HF cache (they are, on the dev VM);
ffmpeg is required for the MP4 assertions and is skipped gracefully when
absent. Slow-ish on CPU (a few seconds per model) - keep it to 2 tiny
frames. Run: python tests/test_smoke.py
"""
import json
import os
import shutil
import sys
import tempfile

# Keep ONNX Runtime single-threaded: on this small shared VM the default
# thread pool plus two resident sessions (depth + BiRefNet, held by the
# session cache) can push RSS past the cgroup limit and get OOM-killed.
# Must be set before onnxruntime is first imported (backends import it
# lazily, so setting it here is early enough).
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OMP_WAIT_POLICY", "PASSIVE")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

from amvfx import pipeline

N_FRAMES = 2


def _make_video(path):
    import cv2
    w = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), 24.0,
                        (64, 48))
    assert w.isOpened(), "VideoWriter failed to open"
    # frame 0: a bright circle on dark ground (something to segment);
    # frame 1: the same circle shifted a few pixels (motion + smoothing)
    for i in range(N_FRAMES):
        frame = np.zeros((48, 64, 3), dtype=np.uint8)
        cx = 24 + 8 * i
        cv2.circle(frame, (cx, 24), 12, (220, 200, 180), -1)
        cv2.rectangle(frame, (0, 40), (64, 48), (60, 60, 60), -1)
        w.write(frame)
    w.release()


def test_lite_video_smoke():
    from amvfx import backends
    with tempfile.TemporaryDirectory() as tmp:
        clip = os.path.join(tmp, "clip.mp4")
        _make_video(clip)
        out_dir = os.path.join(tmp, "out")
        manifest = pipeline.run(clip, out_dir, profile="lite")
        backends.clear_session_cache()
        assert manifest["kind"] == "video", manifest
        assert manifest["frames"] == N_FRAMES, manifest
        assert manifest["fps"] == 24.0, manifest
        assert manifest["profile"] == "lite", manifest
        assert manifest["resolution"] == [64, 48], manifest
        assert manifest["passes"] == pipeline.LITE_PASSES, manifest
        for pname in pipeline.LITE_PASSES:
            assert manifest["provenance"][pname], pname
        # PNG sequence for every pass, one file per frame
        for pname in pipeline.LITE_PASSES:
            pdir = os.path.join(out_dir, pname)
            for i in range(N_FRAMES):
                png = os.path.join(pdir, f"frame_{i:04d}.png")
                assert os.path.isfile(png), png
                assert os.path.getsize(png) > 0, png
        # per-pass MP4s when ffmpeg is available
        if shutil.which("ffmpeg"):
            assert manifest["exports"]["mp4_per_pass"] is True, manifest
            for pname in pipeline.LITE_PASSES:
                mp4 = os.path.join(out_dir, f"{pname}.mp4")
                assert os.path.isfile(mp4), mp4
        # value sanity: the passes are real model output, not blank files
        import cv2
        alpha = cv2.imread(os.path.join(out_dir, "alpha", "frame_0000.png"),
                           cv2.IMREAD_UNCHANGED)
        assert alpha is not None and alpha.size > 0
        assert alpha.min() >= 0 and alpha.max() <= 255
        assert 0 < float(alpha.mean()) < 255, float(alpha.mean())
        depth = cv2.imread(os.path.join(out_dir, "depth", "frame_0000.png"),
                           cv2.IMREAD_UNCHANGED)
        assert depth is not None and depth.size > 0
        assert 0 < float(depth.mean()) < 255, float(depth.mean())
        # manifest round-trips as JSON (the Blender add-on reads it)
        with open(os.path.join(out_dir, "manifest.json")) as f:
            assert json.load(f)["frames"] == N_FRAMES
    print("PASS test_lite_video_smoke")


if __name__ == "__main__":
    test_lite_video_smoke()
    print("all smoke tests passed")

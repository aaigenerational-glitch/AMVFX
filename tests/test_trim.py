"""Frame-trim tests: --start-frame/--end-frame (AE layer in/out).

Builds a small synthetic MP4 (12 frames, each a flat grey level that
encodes its index) and checks that extract_frames trims by frame index
and that the CLI passes the range through to pipeline.run.
No model weights needed - the pipeline itself is stubbed for the CLI test.
Run: python tests/test_trim.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

from amvfx import io_utils

N_FRAMES = 12


def _make_video(path):
    import cv2
    w = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), 24.0,
                        (64, 48))
    assert w.isOpened(), "VideoWriter failed to open"
    for i in range(N_FRAMES):
        grey = np.full((48, 64, 3), i * 20, dtype=np.uint8)
        w.write(grey)
    w.release()


def test_extract_frames_trims_by_index():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "clip.mp4")
        _make_video(path)
        frames, fps = io_utils.extract_frames(path)
        assert len(frames) == N_FRAMES, len(frames)
        assert fps == 24.0, fps
        # trim 3..8 (end exclusive): 5 frames, first is index 3, last is 7
        frames, _ = io_utils.extract_frames(path, start_frame=3, end_frame=8)
        assert len(frames) == 5, len(frames)
        assert abs(float(frames[0].mean()) * 255 - 60) < 10, frames[0].mean()
        assert abs(float(frames[-1].mean()) * 255 - 140) < 10, frames[-1].mean()
        # start-only trim: frames 9, 10, 11
        frames, _ = io_utils.extract_frames(path, start_frame=9)
        assert len(frames) == 3, len(frames)
        assert abs(float(frames[0].mean()) * 255 - 180) < 10
        # end-only trim: frames 0..3
        frames, _ = io_utils.extract_frames(path, end_frame=4)
        assert len(frames) == 4, len(frames)
        # start past the end: nothing decoded (pipeline raises on this)
        frames, _ = io_utils.extract_frames(path, start_frame=50)
        assert frames == []
        # max_frames still caps the trimmed result
        frames, _ = io_utils.extract_frames(path, start_frame=2,
                                            max_frames=2)
        assert len(frames) == 2, len(frames)
    print("PASS test_extract_frames_trims_by_index")


def test_cli_passes_frame_range_through():
    import amvfx.cli as cli

    seen = {}

    def fake_run(input_path, out_dir, **kwargs):
        seen.update(kwargs)
        return {"frames": 1}

    real_run = cli.run
    cli.run = fake_run
    try:
        with tempfile.TemporaryDirectory() as tmp:
            rc = cli.main([os.path.join(tmp, "clip.mp4"), "-o",
                           os.path.join(tmp, "out"), "--start-frame", "3",
                           "--end-frame", "8"])
        assert rc == 0
        assert seen.get("start_frame") == 3, seen
        assert seen.get("end_frame") == 8, seen
    finally:
        cli.run = real_run
    print("PASS test_cli_passes_frame_range_through")


def test_cli_rejects_empty_range():
    import amvfx.cli as cli

    try:
        cli.main(["in.mp4", "-o", "out", "--start-frame", "8",
                  "--end-frame", "8"])
    except SystemExit as exc:
        assert exc.code != 0, exc.code
    else:
        raise AssertionError("expected --end-frame <= --start-frame to fail")
    print("PASS test_cli_rejects_empty_range")


if __name__ == "__main__":
    test_extract_frames_trims_by_index()
    test_cli_passes_frame_range_through()
    test_cli_rejects_empty_range()
    print("all trim tests passed")

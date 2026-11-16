"""Job-history tests: record/load/cap/format/clear, all on a temp file
(no network, no models).
Run: python tests/test_history.py
"""
import os
import sys
import tempfile
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from amvfx import history  # noqa: E402


def test_record_and_load():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "history.json")
        assert history.load_history(path) == []
        e = history.record_job("clip.mp4", "lite",
                               ["source", "alpha", "depth"],
                               os.path.join(tmp, "out"), 12, (640, 360),
                               zip_path=os.path.join(tmp, "passes.zip"),
                               path=path,
                               when=datetime(2026, 11, 16, 11, 0, 0,
                                             tzinfo=timezone.utc))
        assert e is not None
        assert e["input"] == "clip.mp4"
        assert e["resolution"] == "640x360"
        assert e["frames"] == 12
        loaded = history.load_history(path)
        assert len(loaded) == 1 and loaded[0]["input"] == "clip.mp4"
        # newest first
        history.record_job("still.png", "lite", ["source"],
                           os.path.join(tmp, "out2"), 1, (512, 512),
                           path=path)
        loaded = history.load_history(path)
        assert [x["input"] for x in loaded] == ["still.png", "clip.mp4"]
    print("PASS test_record_and_load")


def test_cap_and_corrupt():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "history.json")
        for i in range(history.MAX_ENTRIES + 5):
            history.record_job(f"job{i}.png", "lite", ["source"],
                               os.path.join(tmp, f"out{i}"), 1, (64, 64),
                               path=path)
        loaded = history.load_history(path)
        assert len(loaded) == history.MAX_ENTRIES, len(loaded)
        assert loaded[0]["input"] == f"job{history.MAX_ENTRIES + 4}.png"
        # corrupt file -> empty history, and recording still recovers
        with open(path, "w") as f:
            f.write("{not json")
        assert history.load_history(path) == []
        history.record_job("recovered.png", "lite", ["source"],
                           os.path.join(tmp, "out"), 1, (64, 64), path=path)
        assert len(history.load_history(path)) == 1
        # non-list JSON -> empty
        with open(path, "w") as f:
            f.write('{"a": 1}')
        assert history.load_history(path) == []
    print("PASS test_cap_and_corrupt")


def test_format_and_clear():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "history.json")
        assert "No jobs yet" in history.format_history([])
        history.record_job("clip.mp4", "lite", ["alpha", "depth"],
                           os.path.join(tmp, "out"), 3, (640, 360),
                           path=path)
        md = history.format_history(history.load_history(path))
        assert "clip.mp4" in md and "lite" in md and "alpha, depth" in md
        assert history.clear_history(path) is True
        assert history.load_history(path) == []
        assert history.clear_history(path) is False
    print("PASS test_format_and_clear")


def test_record_never_raises():
    # unwritable location must not raise - history is best-effort
    bad = os.path.join("/proc", "nope", "history.json")
    assert history.record_job("x.png", "lite", ["source"], "/tmp", 1,
                              (1, 1), path=bad) is None
    print("PASS test_record_never_raises")


if __name__ == "__main__":
    test_record_and_load()
    test_cap_and_corrupt()
    test_format_and_clear()
    test_record_never_raises()
    print("all history tests passed")

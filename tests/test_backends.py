"""Backend tests: ONNX session cache (roadmap backlog #5).

Checks that repeated backend construction in one process reuses the
same ORT session instead of rebuilding it, and that clearing the cache
forces a rebuild. Uses the real cached models (HF cache, no network).
Run: python tests/test_backends.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from amvfx.backends import (BiRefNetOnnx, DepthAnythingOnnx,
                            clear_session_cache)


def test_session_cache_reuses_sessions():
    clear_session_cache()
    a = DepthAnythingOnnx()
    b = DepthAnythingOnnx()
    assert a.sess is b.sess, "depth sessions must be the same object"
    c = BiRefNetOnnx()
    d = BiRefNetOnnx()
    assert c.sess is d.sess, "alpha sessions must be the same object"
    assert a.sess is not c.sess, "different models must not share a session"
    clear_session_cache()
    e = DepthAnythingOnnx()
    assert e.sess is not a.sess, "clear must force a rebuild"
    clear_session_cache()
    print("PASS test_session_cache_reuses_sessions")


if __name__ == "__main__":
    test_session_cache_reuses_sessions()
    print("all backend tests passed")

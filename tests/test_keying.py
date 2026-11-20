"""Chroma keyer tests (pure numpy, no models).

Run: python -m pytest tests/test_keying.py  or  python tests/test_keying.py
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from amvfx import keying  # noqa: E402


def _frame(bg, fg, fg_box=(slice(4, 12), slice(4, 12))):
    """16x16 frame: uniform background colour, solid subject square."""
    f = np.zeros((16, 16, 3), dtype=np.float32)
    f[:, :] = bg
    f[fg_box] = fg
    return f


def test_pure_green_screen_keys_to_zero():
    f = _frame((0.0, 1.0, 0.0), (0.8, 0.2, 0.2))
    alpha, _ = keying.chroma_key(f, key="green")
    assert alpha[0, 0] == 0.0, alpha[0, 0]
    assert alpha[8, 8] == 1.0, alpha[8, 8]
    print("PASS test_pure_green_screen_keys_to_zero")


def test_blue_screen_and_custom_key_colour():
    f = _frame((0.0, 0.0, 1.0), (0.9, 0.8, 0.1))
    alpha, _ = keying.chroma_key(f, key="blue")
    assert alpha[0, 0] == 0.0 and alpha[8, 8] == 1.0
    alpha2, _ = keying.chroma_key(f, key=(0.0, 0.0, 1.0))
    assert np.allclose(alpha, alpha2)
    print("PASS test_blue_screen_and_custom_key_colour")


def test_feather_ramp_is_monotonic():
    # A horizontal green gradient: distance grows left -> right, so
    # alpha must rise monotonically across the ramp.
    row = np.linspace(0.0, 1.0, 32, dtype=np.float32)
    f = np.zeros((1, 32, 3), dtype=np.float32)
    f[0, :, 1] = 1.0 - row  # green fades out left -> right
    f[0, :, 0] = row
    alpha, _ = keying.chroma_key(f, key="green", similarity=0.1,
                                 smoothness=0.4)
    a = alpha[0]
    assert a[0] == 0.0 and a[-1] == 1.0
    assert np.all(np.diff(a) >= -1e-6), a
    assert np.any((a > 0.0) & (a < 1.0)), "ramp has no feathered middle"
    print("PASS test_feather_ramp_is_monotonic")


def test_no_screen_colour_means_opaque():
    f = np.full((8, 8, 3), (0.7, 0.3, 0.2), dtype=np.float32)
    alpha, despilled = keying.chroma_key(f, key="green")
    assert np.all(alpha == 1.0)
    assert np.allclose(despilled, f), "opaque pixels must not be despilled"
    print("PASS test_no_screen_colour_means_opaque")


def test_despill_clamps_green_cast_on_edges():
    # Edge pixel: half screen, half skin — green channel above both
    # others, so despill must pull it down to the larger other channel.
    f = np.zeros((1, 1, 3), dtype=np.float32)
    f[0, 0] = (0.4, 0.9, 0.3)
    alpha = np.array([[0.5]], dtype=np.float32)
    out = keying.despill(f, key="green", alpha=alpha, strength=1.0)
    # weight (1 - 0.5) = 0.5: G moves halfway from 0.9 to cap 0.4
    assert abs(out[0, 0, 1] - 0.65) < 1e-6, out
    assert out[0, 0, 0] == 0.4 and out[0, 0, 2] == 0.3
    # Opaque pixel: despill must not touch it at all.
    out2 = keying.despill(f, key="green", alpha=np.ones((1, 1)), strength=1.0)
    assert np.allclose(out2, f)
    print("PASS test_despill_clamps_green_cast_on_edges")


def test_bad_inputs_raise():
    f = np.zeros((4, 4, 3), dtype=np.float32)
    for bad in (dict(key="magenta"), dict(similarity=1.5),
                dict(smoothness=-0.1), dict(despill_strength=2.0)):
        try:
            keying.chroma_key(f, **bad)
        except ValueError:
            pass
        else:
            raise AssertionError(f"no ValueError for {bad}")
    try:
        keying.chroma_key(np.zeros((4, 4), dtype=np.float32))
    except ValueError:
        pass
    else:
        raise AssertionError("no ValueError for 2-D frame")
    print("PASS test_bad_inputs_raise")


if __name__ == "__main__":
    test_pure_green_screen_keys_to_zero()
    test_blue_screen_and_custom_key_colour()
    test_feather_ramp_is_monotonic()
    test_no_screen_colour_means_opaque()
    test_despill_clamps_green_cast_on_edges()
    test_bad_inputs_raise()
    print("all keying tests passed")

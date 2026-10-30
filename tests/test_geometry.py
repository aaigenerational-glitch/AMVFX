"""Geometry + EXR tests (no model downloads needed).

Run: python -m pytest tests/  or  python tests/test_geometry.py
"""
import os
import sys
import tempfile

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from amvfx import geometry, io_utils  # noqa: E402


def test_flat_depth_gives_up_normals():
    d = np.full((32, 32), 0.5, dtype=np.float32)
    n = geometry.depth_to_normal(d)
    assert n.shape == (32, 32, 3)
    # flat surface -> normal ~ (0,0,1) -> stored ~(0.5, 0.5, 1.0)
    assert np.allclose(n[..., 0], 0.5, atol=1e-5)
    assert np.allclose(n[..., 1], 0.5, atol=1e-5)
    assert np.allclose(n[..., 2], 1.0, atol=1e-5)


def test_sloped_depth_tilts_normals():
    d = np.tile(np.linspace(0, 1, 32, dtype=np.float32), (32, 1))
    n = geometry.depth_to_normal(d, strength=2.0)
    assert (n[..., 0] < 0.5).all()  # tilts away from +x slope


def test_specular_f0():
    albedo = np.full((4, 4, 3), 0.8, dtype=np.float32)
    dielectric = geometry.specular_f0(albedo, np.zeros((4, 4), np.float32))
    assert np.allclose(dielectric, 0.04)
    metal = geometry.specular_f0(albedo, np.ones((4, 4), np.float32))
    assert np.allclose(metal, 0.8)


def test_ao_flat_is_unoccluded():
    d = np.full((32, 32), 0.5, dtype=np.float32)
    ao = geometry.ao_from_depth(d)
    assert np.allclose(ao, 1.0)


def test_normalize_depth_range():
    raw = np.array([[0.0, 5.0], [10.0, 2.5]], dtype=np.float32)
    n = geometry.normalize_depth(raw, 0.0, 10.0)
    assert n.min() == 0.0 and n.max() == 1.0


def test_normal_format_conversion():
    n = np.zeros((2, 2, 3), dtype=np.float32)
    n[..., 0] = 0.5
    n[..., 1] = 0.75
    n[..., 2] = 1.0
    same = geometry.convert_normal_format(n, "opengl")
    assert np.allclose(same, n)
    dx = geometry.convert_normal_format(n, "directx")
    assert np.allclose(dx[..., 1], 0.25)  # green flipped
    assert np.allclose(dx[..., 0], 0.5) and np.allclose(dx[..., 2], 1.0)
    back = geometry.convert_normal_format(dx, "directx")
    assert np.allclose(back, n)  # flip is its own inverse


def test_exr_roundtrip():
    if not io_utils.has_exr():
        print("skip: OpenEXR unavailable")
        return
    passes = {
        "source": np.random.rand(16, 16, 3).astype(np.float32),
        "alpha": np.random.rand(16, 16).astype(np.float32),
        "depth": np.random.rand(16, 16).astype(np.float32),
        "normal": np.random.rand(16, 16, 3).astype(np.float32),
        "basecolor": np.random.rand(16, 16, 3).astype(np.float32),
    }
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "frame_0000.exr")
        io_utils.write_multilayer_exr(p, passes)
        layers, data = io_utils.read_exr_layers(p)
        for want in ("Source.red", "Alpha.red", "Depth.red",
                     "Normal.green", "Basecolor.blue"):
            assert want in layers, f"missing {want} in {layers}"
        assert data["Depth.red"].shape == (16, 16)
        assert np.allclose(data["Alpha.red"], passes["alpha"], atol=1e-3)


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"{len(fns)} tests passed")

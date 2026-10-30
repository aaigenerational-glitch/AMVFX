"""Pure-numpy geometry / PBR derivations for AMVFX.

These are deterministic, physically-grounded derivations used to complete
the Beeble-style pass set from the AI-estimated passes:

- normal from depth      (screen-space gradient of the depth field)
- AO from depth          (local depth-occlusion approximation, SSAO-lite)
- specular F0            (standard PBR dielectric F0 = 0.04 blended to the
                          base colour by metallic: F0 = mix(0.04, albedo, metallic))
"""
import numpy as np


def depth_to_normal(depth: np.ndarray, strength: float = 1.0) -> np.ndarray:
    """Convert a [0,1] depth map (H,W) float to an OpenGL-style normal map.

    Returns float array (H,W,3) in [0,1], where the stored vector is
    n*0.5+0.5 and +Y is up (OpenGL convention, matching Beeble's spec).
    """
    d = depth.astype(np.float32)
    gy, gx = np.gradient(d)  # one-sided at borders, central inside
    nx = -gx * strength
    ny = gy * strength  # image Y is down; OpenGL normal green is up
    nz = np.ones_like(d)
    norm = np.sqrt(nx * nx + ny * ny + nz * nz) + 1e-8
    n = np.stack([nx / norm, ny / norm, nz / norm], axis=-1)
    return (n * 0.5 + 0.5).astype(np.float32)


def ao_from_depth(depth: np.ndarray, radius: int = 9, power: float = 1.0) -> np.ndarray:
    """Approximate ambient occlusion from a [0,1] depth map.

    A pixel that sits in a local depth 'valley' (closer surroundings on
    average after blur, i.e. recessed areas) is darkened. This is an
    approximation for preview/comp use, not a ray-traced AO.
    Returns (H,W) float in [0,1] where 1 = unoccluded.
    """
    d = depth.astype(np.float32)
    k = max(3, radius if radius % 2 == 1 else radius + 1)
    # box blur via cumulative sums (fast, no scipy dependency)
    padded = np.pad(d, ((k // 2, k // 2), (k // 2, k // 2)), mode="edge")
    cs = padded.cumsum(axis=0).cumsum(axis=1)
    cs = np.pad(cs, ((1, 0), (1, 0)), mode="constant")
    h, w = d.shape
    total = (cs[k:k + h, k:k + w] - cs[0:h, k:k + w] - cs[k:k + h, 0:w] + cs[0:h, 0:w])
    local_mean = total / float(k * k)
    # depth here is disparity-like (1 = near). Recessed = local mean nearer than pixel.
    occ = np.clip((local_mean - d) * 4.0, 0.0, 1.0)
    ao = 1.0 - occ * power
    return ao.astype(np.float32)


def specular_f0(basecolor: np.ndarray, metallic: np.ndarray) -> np.ndarray:
    """Specular reflectance at normal incidence (F0), per PBR convention.

    basecolor: (H,W,3) float [0,1] sRGB-ish albedo
    metallic:  (H,W) float [0,1]
    Returns (H,W,3) float [0,1]: 0.04 grey for dielectrics, tinted by the
    base colour for metals.
    """
    m = metallic.astype(np.float32)[..., None]
    dielectric = np.full_like(basecolor, 0.04, dtype=np.float32)
    return (dielectric * (1.0 - m) + basecolor.astype(np.float32) * m).astype(np.float32)


def convert_normal_format(normal: np.ndarray, fmt: str = "opengl") -> np.ndarray:
    """Convert a stored [0,1] normal map between tangent conventions.

    AMVFX generates OpenGL convention (green = +Y up), matching Beeble's
    export spec. Unreal and some tools expect DirectX (green = -Y down):
    that conversion is exactly a flip of the green channel's direction.
    """
    if fmt == "opengl":
        return normal
    if fmt == "directx":
        out = normal.astype(np.float32).copy()
        out[..., 1] = 1.0 - out[..., 1]
        return out
    raise ValueError(f"unknown normal format: {fmt}")


# About normal *spaces*: estimators (Depth Anything, MoGe, Marigold,
# NormalCrafter) all output camera-space normals. Beeble's spec labels its
# normals "object space". For a 2.5D plate the plate itself is the object:
# with the plate unrotated at the origin, plate/object space and camera
# space coincide up to the axis convention, which is why AMVFX declares
# the plate frame in the manifest ("normal_space": "object (plate frame)")
# when the object export is chosen. True per-object space for *segmented
# scene objects* would require each object's pose, which a monocular
# plate does not contain; AMVFX does not fake it.


def normalize_depth(raw: np.ndarray, lo: float, hi: float) -> np.ndarray:
    """Normalize a raw depth/disparity field to [0,1] with fixed lo/hi so a
    whole clip shares one scale (temporal stability)."""
    if hi - lo < 1e-8:
        return np.zeros_like(raw, dtype=np.float32)
    return np.clip((raw.astype(np.float32) - lo) / (hi - lo), 0.0, 1.0).astype(np.float32)


def percentile_range(frames_raw, lo_pct: float = 2.0, hi_pct: float = 98.0):
    """Global percentile range across a list of raw depth frames."""
    allv = np.concatenate([f.astype(np.float32).ravel()[::17] for f in frames_raw])
    lo, hi = np.percentile(allv, [lo_pct, hi_pct])
    return float(lo), float(hi)

"""Chroma keying: a green/blue-screen alpha pass with classic math.

No model, no weights — the technique studios have used since the
Vlahos difference keyer: measure how far each pixel sits from the
screen colour, turn that distance into a feathered alpha ramp, and
strip the coloured spill off the edges.

Method (cross-checked against two independent write-ups, see
docs/ROADMAP.md research 2026-11-20):
- distance: Euclidean distance in RGB space from the key colour,
  normalised by the largest possible distance (black to white,
  sqrt(3) in unit RGB), so it lands in [0, 1].
- alpha: 0 below the `similarity` threshold (definitely screen),
  1 above `similarity + smoothness` (definitely subject), with a
  smoothstep ramp between — the feathered edge, not a hard cut.
- despill: the key channel is clamped toward the larger of the
  other two channels (G' = min(G, max(R, B)) for green), blended
  by (1 - alpha) so fully opaque interior pixels are untouched and
  only edge / semi-transparent pixels lose the cast.
"""
import numpy as np

KEY_COLORS = {
    "green": (0.0, 1.0, 0.0),
    "blue": (0.0, 0.0, 1.0),
}


def resolve_key_color(key):
    """Accept 'green'/'blue' or an (R, G, B) tuple in [0, 1]."""
    if isinstance(key, str):
        try:
            return np.array(KEY_COLORS[key.lower()], dtype=np.float32)
        except KeyError:
            raise ValueError(
                f"unknown key colour {key!r}; use 'green', 'blue' or an "
                "(R, G, B) tuple in [0, 1]") from None
    rgb = np.asarray(key, dtype=np.float32)
    if rgb.shape != (3,) or np.any(rgb < 0.0) or np.any(rgb > 1.0):
        raise ValueError("key colour must be 'green', 'blue' or an "
                         "(R, G, B) tuple in [0, 1]")
    return rgb


def chroma_key(frame, key="green", similarity=0.25, smoothness=0.15,
               despill_strength=1.0):
    """Key a frame against a green/blue screen.

    frame: (H, W, 3) float RGB in [0, 1].
    similarity: normalised distance below which a pixel is fully
        transparent (definitely screen). Raise it when parts of the
        screen survive; lower it when subject colours start to vanish.
    smoothness: width of the feathered ramp above `similarity`.
    despill_strength: 0 = no spill removal, 1 = full clamp of the
        key channel on edge pixels.

    Returns (alpha, despilled_frame): alpha is (H, W) float in
    [0, 1] (0 = screen, 1 = subject); despilled_frame is the input
    with the screen cast removed from edge pixels.
    """
    if frame.ndim != 3 or frame.shape[2] != 3:
        raise ValueError("frame must be (H, W, 3) RGB")
    if not 0.0 <= similarity <= 1.0:
        raise ValueError("similarity must be in [0, 1]")
    if not 0.0 <= smoothness <= 1.0:
        raise ValueError("smoothness must be in [0, 1]")
    if not 0.0 <= despill_strength <= 1.0:
        raise ValueError("despill_strength must be in [0, 1]")
    key_rgb = resolve_key_color(key)
    f = frame.astype(np.float32)
    # Normalised RGB distance to the key colour: 0 = exact screen colour.
    dist = np.sqrt(np.sum((f - key_rgb) ** 2, axis=-1)) / np.sqrt(3.0)
    if smoothness <= 0.0:
        alpha = (dist > similarity).astype(np.float32)
    else:
        t = np.clip((dist - similarity) / smoothness, 0.0, 1.0)
        alpha = (t * t * (3.0 - 2.0 * t)).astype(np.float32)
    despilled = despill(f, key_rgb, alpha, despill_strength)
    return alpha, despilled


def despill(frame, key="green", alpha=None, strength=1.0):
    """Remove the screen colour's cast from edge pixels.

    The key channel is clamped to the larger of the other two
    channels — the standard spill-suppression bound — blended by
    (1 - alpha) * strength, so opaque subject pixels keep their
    colour. With alpha=None the clamp applies to the whole frame.
    """
    key_rgb = resolve_key_color(key)
    f = np.asarray(frame, dtype=np.float32)
    # The key channel is whichever channel the key colour is pure in.
    ch = int(np.argmax(key_rgb))
    others = [i for i in range(3) if i != ch]
    cap = np.maximum(f[..., others[0]], f[..., others[1]])
    clamped = np.minimum(f[..., ch], cap)
    if alpha is None:
        weight = float(strength)
    else:
        weight = (1.0 - np.asarray(alpha, dtype=np.float32)) * float(strength)
    out = f.copy()
    out[..., ch] = f[..., ch] + weight * (clamped - f[..., ch])
    return np.clip(out, 0.0, 1.0).astype(np.float32)

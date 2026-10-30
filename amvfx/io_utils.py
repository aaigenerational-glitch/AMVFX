"""I/O for AMVFX: frames, PNG sequences, per-pass MP4s and multi-layer EXR.

EXR layout follows Beeble Studio's published spec: 16-bit float, one file
per frame, layers named ``<Layer>.red/.green/.blue`` with layers
Source, Alpha, Normal, Basecolor, Depth, Roughness, Metallic, Specular.
"""
import os
import subprocess

import numpy as np

try:
    import OpenEXR
    import Imath
    _HAS_EXR = True
except Exception:  # pragma: no cover
    _HAS_EXR = False


def has_exr() -> bool:
    return _HAS_EXR


def to_uint8(arr: np.ndarray) -> np.ndarray:
    a = np.clip(arr, 0.0, 1.0)
    return (a * 255.0 + 0.5).astype(np.uint8)


def save_png(path: str, arr: np.ndarray) -> None:
    """Save float [0,1] array (H,W) or (H,W,3) as 8-bit PNG (RGB order)."""
    import cv2
    u8 = to_uint8(arr)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if u8.ndim == 3:
        cv2.imwrite(path, cv2.cvtColor(u8, cv2.COLOR_RGB2BGR))
    else:
        cv2.imwrite(path, u8)


def write_multilayer_exr(path: str, passes: dict) -> None:
    """Write one multi-layer half-float EXR.

    passes: name -> float array (H,W) or (H,W,3), values in [0,1]
            (depth may exceed if raw metric; stored as-is).
    Layer names mirror Beeble: Source, Alpha, Normal, Basecolor, Depth,
    Roughness, Metallic, Specular, AO.
    """
    if not _HAS_EXR:
        raise RuntimeError("OpenEXR python package not available")
    layer_names = {
        "source": "Source", "alpha": "Alpha", "normal": "Normal",
        "basecolor": "Basecolor", "depth": "Depth", "roughness": "Roughness",
        "metallic": "Metallic", "specular": "Specular", "ao": "AO",
    }
    channels = {}
    data = {}
    height = width = None
    for key, arr in passes.items():
        layer = layer_names.get(key, key.capitalize())
        a = np.asarray(arr, dtype=np.float32)
        if a.ndim == 2:
            a = a[..., None]
        height, width = a.shape[0], a.shape[1]
        chan_names = ["red", "green", "blue"][: a.shape[2]]
        for i, cn in enumerate(chan_names):
            name = f"{layer}.{cn}"
            channels[name] = Imath.Channel(Imath.PixelType(Imath.PixelType.HALF))
            data[name] = a[:, :, i].astype(np.float16).tobytes()
    header = OpenEXR.Header(width, height)
    header["channels"] = channels
    header["compression"] = Imath.Compression(Imath.Compression.ZIP_COMPRESSION)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    out = OpenEXR.OutputFile(path, header)
    out.writePixels(data)
    out.close()


def read_exr_layers(path: str):
    """Return (layer_names, {channel: (H,W) float32}) for verification."""
    if not _HAS_EXR:
        raise RuntimeError("OpenEXR python package not available")
    f = OpenEXR.InputFile(path)
    hdr = f.header()
    dw = hdr["dataWindow"]
    w = dw.max.x - dw.min.x + 1
    h = dw.max.y - dw.min.y + 1
    out = {}
    for name in hdr["channels"]:
        raw = f.channel(name, Imath.PixelType(Imath.PixelType.FLOAT))
        out[name] = np.frombuffer(raw, dtype=np.float32).reshape(h, w)
    f.close()
    return sorted(out.keys()), out


def extract_frames(video_path: str, max_frames: int = 0, max_width: int = 0):
    """Decode a video to a list of RGB float frames [0,1] + fps.

    Uses OpenCV (already a hard dependency). Image inputs should be
    handled by load_image instead.
    """
    import cv2
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video: {video_path}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
    frames = []
    while True:
        ok, bgr = cap.read()
        if not ok:
            break
        if max_width and bgr.shape[1] > max_width:
            scale = max_width / bgr.shape[1]
            bgr = cv2.resize(bgr, (max_width, int(bgr.shape[0] * scale)),
                             interpolation=cv2.INTER_AREA)
        frames.append(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0)
        if max_frames and len(frames) >= max_frames:
            break
    cap.release()
    return frames, float(fps)


def load_image(path: str, max_width: int = 0) -> np.ndarray:
    import cv2
    bgr = cv2.imread(path, cv2.IMREAD_COLOR)
    if bgr is None:
        raise RuntimeError(f"Could not read image: {path}")
    if max_width and bgr.shape[1] > max_width:
        scale = max_width / bgr.shape[1]
        bgr = cv2.resize(bgr, (max_width, int(bgr.shape[0] * scale)),
                         interpolation=cv2.INTER_AREA)
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0


def encode_mp4(png_dir: str, out_path: str, fps: float) -> bool:
    """Encode a frame_%04d.png sequence to an H.264 MP4 via ffmpeg."""
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    cmd = ["ffmpeg", "-y", "-framerate", str(fps), "-i",
           os.path.join(png_dir, "frame_%04d.png"),
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", out_path]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode == 0 and os.path.exists(out_path)

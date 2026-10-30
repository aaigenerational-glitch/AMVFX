"""Model backends for AMVFX. Every backend wraps one open-source model
hosted on Hugging Face; see MODELS.md for licenses.

Lite profile (ONNX, CPU-friendly, no torch):
  - Depth  : depth-anything/Depth-Anything-V2-Small (Apache-2.0)
             via onnx-community/depth-anything-v2-small
  - Alpha  : ZhengPeng7/BiRefNet (MIT) via onnx-community/BiRefNet_lite-ONNX
             (full-quality option: onnx-community/BiRefNet-ONNX)

GPU profile (torch + diffusers, also runs slowly on CPU):
  - Albedo/Roughness/Metallic : prs-eth/marigold-iid-appearance-v1-1
  - Normal (model)            : prs-eth/marigold-normals-v1-1
  - Geometry alt (depth+normal, metric): Ruicheng/moge-2-vitl-normal (MIT),
             requires the optional `moge` package from microsoft/MoGe.
"""
import numpy as np

IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


def _onnx_session(repo_id: str, filename: str = None):
    import onnxruntime as ort
    from huggingface_hub import hf_hub_download
    if filename is None:
        # onnx-community exports keep the graph under onnx/
        for cand in ("onnx/model.onnx", "model.onnx"):
            try:
                filename = cand
                path = hf_hub_download(repo_id, cand)
                break
            except Exception:
                filename = None
        if filename is None:
            raise RuntimeError(f"No ONNX graph found in {repo_id}")
    else:
        path = hf_hub_download(repo_id, filename)
    # Memory-frugal session: the default ORT arena can balloon RSS and get
    # the process OOM-killed on small machines (verified on a 7 GB VM with
    # the 1024px BiRefNet export).
    opts = ort.SessionOptions()
    opts.enable_cpu_mem_arena = False
    opts.enable_mem_pattern = False
    opts.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    sess = ort.InferenceSession(path, sess_options=opts,
                                providers=["CPUExecutionProvider"])
    return sess


def _prep(sess, frame: np.ndarray, size_hw):
    """Resize + ImageNet-normalize a float RGB frame for an ONNX session."""
    import cv2
    h, w = size_hw
    img = cv2.resize(frame, (w, h), interpolation=cv2.INTER_AREA)
    img = (img - IMAGENET_MEAN) / IMAGENET_STD
    return np.ascontiguousarray(img.transpose(2, 0, 1)[None], dtype=np.float32)


class DepthAnythingOnnx:
    """Relative depth (disparity-like: larger = nearer). Apache-2.0 weights."""

    repo = "onnx-community/depth-anything-v2-small"

    def __init__(self):
        self.sess = _onnx_session(self.repo)
        inp = self.sess.get_inputs()[0]
        shape = inp.shape  # [1,3,H,W], may contain dynamic dims
        self.size = (int(shape[2]) if isinstance(shape[2], int) else 518,
                     int(shape[3]) if isinstance(shape[3], int) else 518)
        self.in_name = inp.name

    def raw_depth(self, frame: np.ndarray) -> np.ndarray:
        import cv2
        x = _prep(self.sess, frame, self.size)
        out = self.sess.run(None, {self.in_name: x})[0]
        d = np.asarray(out)[0]
        if d.ndim == 3:
            d = d[0]
        d = cv2.resize(d.astype(np.float32), (frame.shape[1], frame.shape[0]),
                       interpolation=cv2.INTER_LINEAR)
        return d.astype(np.float32)


class BiRefNetOnnx:
    """Foreground alpha matte in [0,1]. MIT weights (BiRefNet family)."""

    def __init__(self, quality: bool = False):
        # Default is the 512x512 export: same MIT weights family, far lower
        # activation memory than the 1024px exports. quality=True uses the
        # full 1024px BiRefNet for machines with RAM/GPU headroom.
        self.repo = ("onnx-community/BiRefNet-ONNX" if quality
                     else "onnx-community/BiRefNet_512x512-ONNX")
        self.sess = _onnx_session(self.repo)
        inp = self.sess.get_inputs()[0]
        shape = inp.shape
        self.size = (int(shape[2]) if isinstance(shape[2], int) else 1024,
                     int(shape[3]) if isinstance(shape[3], int) else 1024)
        self.in_name = inp.name

    def alpha(self, frame: np.ndarray) -> np.ndarray:
        import cv2
        x = _prep(self.sess, frame, self.size)
        out = self.sess.run(None, {self.in_name: x})[0]
        a = np.asarray(out, dtype=np.float32)
        while a.ndim > 2:
            a = a[0]
        # BiRefNet ONNX exports already emit probabilities; clip defensively
        if a.min() < 0.0 or a.max() > 1.0:
            a = 1.0 / (1.0 + np.exp(-a))
        a = cv2.resize(a, (frame.shape[1], frame.shape[0]),
                       interpolation=cv2.INTER_LINEAR)
        return np.clip(a, 0.0, 1.0).astype(np.float32)


class MarigoldBackend:
    """GPU profile: intrinsic decomposition + model normals (diffusers).

    Weights: CreativeML Open RAIL++-M (see MODELS.md). Runs on CUDA when
    available; CPU works but is slow (minutes per frame at full size).
    """

    IID = "prs-eth/marigold-iid-appearance-v1-1"
    NORMALS = "prs-eth/marigold-normals-v1-1"

    def __init__(self, device: str = None):
        import torch
        self.torch = torch
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.dtype = torch.float16 if self.device == "cuda" else torch.float32
        self._iid = None
        self._normals = None

    def _load_iid(self):
        if self._iid is None:
            import diffusers
            self._iid = diffusers.MarigoldIntrinsicsPipeline.from_pretrained(
                self.IID, torch_dtype=self.dtype).to(self.device)
        return self._iid

    def _load_normals(self):
        if self._normals is None:
            import diffusers
            self._normals = diffusers.MarigoldNormalsPipeline.from_pretrained(
                self.NORMALS, torch_dtype=self.dtype).to(self.device)
        return self._normals

    def intrinsics(self, frame: np.ndarray, steps: int = 4):
        """Return dict with albedo (H,W,3), roughness (H,W), metallic (H,W)."""
        from PIL import Image
        pipe = self._load_iid()
        img = Image.fromarray((np.clip(frame, 0, 1) * 255).astype(np.uint8))
        res = 768 if self.device == "cuda" else 512
        out = pipe(img, num_inference_steps=steps, ensemble_size=1,
                   processing_resolution=res)
        vis = pipe.image_processor.visualize_intrinsics(
            out.prediction, pipe.target_properties)[0]
        res = {}
        for key in ("albedo", "roughness", "metallicity"):
            pil = vis[key]
            arr = np.asarray(pil).astype(np.float32) / 255.0
            if arr.ndim == 3:
                arr = arr[..., 0]
            res["metallic" if key == "metallicity" else key] = arr
        albedo = np.asarray(vis["albedo"]).astype(np.float32) / 255.0
        if albedo.shape[:2] != frame.shape[:2]:
            import cv2
            albedo = cv2.resize(albedo, (frame.shape[1], frame.shape[0]))
            for k in ("roughness", "metallic"):
                res[k] = cv2.resize(res[k], (frame.shape[1], frame.shape[0]))
        res["albedo"] = albedo
        return res

    def normals(self, frame: np.ndarray, steps: int = 4):
        """Return model normal map (H,W,3) float [0,1], OpenGL convention."""
        from PIL import Image
        pipe = self._load_normals()
        img = Image.fromarray((np.clip(frame, 0, 1) * 255).astype(np.uint8))
        res = 768 if self.device == "cuda" else 512
        out = pipe(img, num_inference_steps=steps, ensemble_size=1,
                   processing_resolution=res)
        vis = pipe.image_processor.visualize_normals(out.prediction)
        arr = np.asarray(vis[0]).astype(np.float32) / 255.0
        if arr.shape[:2] != frame.shape[:2]:
            import cv2
            arr = cv2.resize(arr, (frame.shape[1], frame.shape[0]))
        return arr.astype(np.float32)

    def free_iid(self):
        self._iid = None

    def free_normals(self):
        self._normals = None


class NormalCrafterBackend:
    """Video normals via NormalCrafter (ICCV 2025, Binyr/NormalCrafter).

    Temporally consistent video normal sequences from Stable Video
    Diffusion priors - the closest free analogue to the detailed,
    flicker-free normals Beeble advertises. Code: MIT. HF weights
    (Yanrui95/NormalCrafter) tagged Apache-2.0; note it is fine-tuned
    from Stable Video Diffusion, so commercial users should also check
    Stability AI's terms.

    GPU-only in practice (~6 GB VRAM at 512px, ~20 GB at 1024x576).
    This backend shells out to a local clone of the upstream repo:
    set NORMALCRAFTER_HOME or clone into third_party/NormalCrafter.
    It cannot run on a CPU-only box (including this dev VM), so it is
    wired and documented but verified only on GPU machines / Spaces.
    """

    def __init__(self, home: str = None):
        import os
        home = home or os.environ.get("NORMALCRAFTER_HOME") or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "third_party", "NormalCrafter")
        self.home = home
        self.run_py = os.path.join(home, "run.py")

    def is_available(self) -> bool:
        import os
        try:
            import torch
            cuda = torch.cuda.is_available()
        except Exception:
            cuda = False
        return os.path.isfile(self.run_py) and cuda

    def normals_for_video(self, video_path: str, work_dir: str,
                          max_res: int = 512):
        """Run upstream inference; return sorted list of normal PNG paths."""
        import os
        import subprocess
        import sys
        if not self.is_available():
            raise RuntimeError(
                "NormalCrafter needs a local clone (NORMALCRAFTER_HOME) and "
                "a CUDA GPU (~6 GB VRAM at 512px, ~20 GB at 1024x576). "
                "Clone https://github.com/Binyr/NormalCrafter to enable it.")
        out_dir = os.path.join(work_dir, "normalcrafter_out")
        os.makedirs(out_dir, exist_ok=True)
        cmd = [sys.executable, self.run_py, "--video-path", video_path,
               "--save-path", out_dir, "--max-res", str(max_res)]
        r = subprocess.run(cmd, cwd=self.home, capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(f"NormalCrafter failed: {r.stderr[-800:]}")
        pngs = []
        for root, _dirs, files in os.walk(out_dir):
            for fn in sorted(files):
                if fn.lower().endswith(".png"):
                    pngs.append(os.path.join(root, fn))
        return sorted(pngs)


class MoGeBackend:
    """Optional geometry backend: metric depth + normals from MoGe-2 (MIT).

    Requires `pip install git+https://github.com/microsoft/MoGe.git`.
    """

    def __init__(self, model_id: str = "Ruicheng/moge-2-vitl-normal"):
        import torch
        from moge.model.v2 import MoGeModel
        self.torch = torch
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = MoGeModel.from_pretrained(model_id).to(self.device).eval()

    def geometry(self, frame: np.ndarray):
        """Return (metric_depth (H,W) float, normal (H,W,3) float [0,1])."""
        torch = self.torch
        x = torch.tensor(frame.transpose(2, 0, 1), dtype=torch.float32,
                         device=self.device)
        with torch.no_grad():
            out = self.model.infer(x)
        depth = out["depth"].detach().cpu().numpy().astype(np.float32)
        depth = np.where(np.isfinite(depth), depth, 0.0)
        normal = out["normal"].detach().cpu().numpy().astype(np.float32)
        # MoGe normals are OpenCV camera-space unit vectors (y down);
        # convert to OpenGL image convention (y up) for VFX passes.
        normal[..., 1] *= -1.0
        normal = normal * 0.5 + 0.5
        return depth, np.clip(normal, 0, 1).astype(np.float32)

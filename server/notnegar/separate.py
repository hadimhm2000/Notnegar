"""Source separation into layers with Demucs (htdemucs_6s: vocals, drums, bass, guitar, piano, other).

Falls back to a stereo-centre / side split when Demucs is not installed, so the rest of the
pipeline still runs (with lower quality) on a machine without PyTorch.
"""
from __future__ import annotations

import logging
import os

import numpy as np

log = logging.getLogger(__name__)

STEM_INFO = {
    "vocals": {"fa": "آواز", "en": "Vocals"},
    "other":  {"fa": "سازهای دیگر", "en": "Other instruments"},
    "guitar": {"fa": "گیتار", "en": "Guitar"},
    "piano":  {"fa": "پیانو و کیبورد", "en": "Piano / keys"},
    "bass":   {"fa": "بیس", "en": "Bass"},
    "drums":  {"fa": "ضرب و درامز", "en": "Drums & percussion"},
    "centre": {"fa": "صدای وسط (تقریبی)", "en": "Centre (approx.)"},
    "sides":  {"fa": "صدای کناری (تقریبی)", "en": "Sides (approx.)"},
}

_MODEL_CACHE: dict = {}


def demucs_available() -> bool:
    try:
        import torch  # noqa: F401
        import demucs.pretrained  # noqa: F401
        return True
    except Exception:
        return False


def _device() -> str:
    pref = os.environ.get("NOTNEGAR_DEVICE", "auto")
    if pref != "auto":
        return pref
    try:
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"


def separate(x: np.ndarray, sr: int, model_name: str | None = None, progress=None) -> tuple[dict, dict]:
    """Return ({stem: (2, N) float32}, info). ``x`` is stereo (2, N) at ``sr``."""
    model_name = model_name or os.environ.get("NOTNEGAR_DEMUCS_MODEL", "htdemucs_6s")
    if demucs_available() and os.environ.get("NOTNEGAR_DISABLE_DEMUCS") != "1":
        try:
            return _demucs(x, sr, model_name, progress)
        except Exception as e:  # pragma: no cover - depends on the VPS install
            log.exception("Demucs failed, using the stereo fallback: %s", e)
    return _fallback(x), {"method": "stereo-fallback", "model": None, "separated": False}


def _demucs(x: np.ndarray, sr: int, model_name: str, progress=None):
    import torch
    from demucs.pretrained import get_model
    from demucs.apply import apply_model

    dev = _device()
    if model_name not in _MODEL_CACHE:
        m = get_model(model_name)
        m.eval()
        _MODEL_CACHE[model_name] = m
    model = _MODEL_CACHE[model_name]
    if sr != model.samplerate:
        from .dsp import resample_poly
        x = np.stack([resample_poly(c, sr, model.samplerate)[0] for c in x])
    wav = torch.from_numpy(np.ascontiguousarray(x)).float()
    if wav.shape[0] == 1:
        wav = wav.repeat(2, 1)
    ref = wav.mean(0)
    mean, std = ref.mean(), ref.std() + 1e-8
    wav = (wav - mean) / std
    threads = int(os.environ.get("NOTNEGAR_TORCH_THREADS", "0"))
    if threads > 0:
        torch.set_num_threads(threads)
    with torch.no_grad():
        out = apply_model(model, wav[None], device=dev, shifts=int(os.environ.get("NOTNEGAR_DEMUCS_SHIFTS", "1")),
                          split=True, overlap=0.25, progress=False)[0]
    out = out * std + mean
    stems = {name: out[i].cpu().numpy().astype(np.float32) for i, name in enumerate(model.sources)}
    if model.samplerate != sr:
        from .dsp import resample_poly
        stems = {k: np.stack([resample_poly(c, model.samplerate, sr)[0] for c in v]) for k, v in stems.items()}
    return stems, {"method": "demucs", "model": model_name, "device": dev, "separated": True}


def _fallback(x: np.ndarray) -> dict:
    """Centre (mid minus side spectrum) and sides — a rough two-way split."""
    mid = (x[0] + x[1]) / 2
    side = (x[0] - x[1]) / 2
    n_fft, hop = 2048, 512
    win = np.hanning(n_fft)
    n = 1 + max(0, len(mid) - n_fft) // hop
    out_c = np.zeros(len(mid) + n_fft)
    norm = np.zeros(len(mid) + n_fft)
    for t in range(n):
        a = t * hop
        M = np.fft.rfft(mid[a:a + n_fft] * win, n_fft)
        S = np.fft.rfft(side[a:a + n_fft] * win, n_fft)
        g = np.maximum(0, np.abs(M) - 0.8 * np.abs(S)) / (np.abs(M) + 1e-9)
        out_c[a:a + n_fft] += np.fft.irfft(M * g, n_fft) * win
        norm[a:a + n_fft] += win ** 2
    centre = (out_c / np.maximum(norm, 1e-6))[: len(mid)].astype(np.float32)
    sides = x - centre[None, :]
    return {"centre": np.stack([centre, centre]), "sides": sides.astype(np.float32)}

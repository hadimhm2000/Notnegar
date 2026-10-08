"""Turn each separated layer into notes.

* melodic layers (vocals, bass, or a solo instrument): pitch contour → notes
  (CREPE when installed, otherwise the numpy salience tracker)
* polyphonic layers (piano, guitar, other): Basic Pitch when installed, otherwise a numpy fallback;
  each note's exact pitch is re-measured so quarter-tones survive
* drums: onsets for a one-line rhythm part
"""
from __future__ import annotations

import logging
import os
import tempfile

import numpy as np

from . import dsp
from .analysis import Note, segment_notes, quantize_pitch, simplify_ornaments
from .audio import write_wav

log = logging.getLogger(__name__)


def crepe_available() -> bool:
    try:
        import torch  # noqa: F401
        import torchcrepe  # noqa: F401
        return True
    except Exception:
        return False


def basic_pitch_available() -> bool:
    try:
        import basic_pitch.inference  # noqa: F401
        return True
    except Exception:
        return False


def contour(x: np.ndarray, sr: int, fmin: float, fmax: float, use_side: bool = False, progress=None):
    """Pitch contour of a melodic layer: (times, cents rel. C4 or NaN, confidence, method)."""
    mono = dsp.to_mono(x)
    if crepe_available() and os.environ.get("NOTNEGAR_DISABLE_CREPE") != "1":
        try:
            return (*_crepe(mono, sr, fmin, fmax), "crepe")
        except Exception as e:  # pragma: no cover
            log.exception("CREPE failed, using the salience tracker: %s", e)
    side = (x[0] - x[1]) / 2 if (use_side and x.ndim == 2) else None
    t, c, conf = dsp.melody_salience(mono, sr, side=side, fmin=max(30.0, fmin), fmax=fmax, progress=progress)
    return t, c, conf, "salience"


def _crepe(mono: np.ndarray, sr: int, fmin: float, fmax: float):  # pragma: no cover - needs torch
    import torch
    import torchcrepe
    y, _ = dsp.resample_poly(mono, sr, 16000)
    audio = torch.from_numpy(y.astype(np.float32))[None]
    hop = 160
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    model = os.environ.get("NOTNEGAR_CREPE_MODEL", "full")
    with torch.no_grad():
        pitch, per = torchcrepe.predict(audio, 16000, hop, fmin, fmax, model=model, batch_size=1024,
                                        device=dev, return_periodicity=True, decoder=torchcrepe.decode.viterbi)
    per = torchcrepe.filter.median(per, 3)
    per = torchcrepe.threshold.Silence(-60.)(per, audio, 16000, hop)
    pitch = torchcrepe.threshold.At(0.21)(pitch, per)
    pitch = torchcrepe.filter.mean(pitch, 3)
    f = pitch[0].cpu().numpy().astype(np.float64)
    conf = per[0].cpu().numpy().astype(np.float64)
    cents = np.where(np.isfinite(f) & (f > 0), 1200 * np.log2(np.maximum(f, 1e-6) / dsp.C4_HZ), np.nan)
    times = np.arange(len(f)) * hop / 16000
    return times, cents, np.nan_to_num(conf)


def melodic_layer(x: np.ndarray, sr: int, kind: str, offset: float | None = None, progress=None) -> dict:
    """Notes of a single-line layer. Returns dict with notes (before pitch quantisation) and contour."""
    rng = {"vocals": (65, 1100), "bass": (30, 400), "centre": (80, 1300)}.get(kind, (80, 1600))
    t, c, conf, method = contour(x, sr, *rng, use_side=(kind == "centre"), progress=progress)
    return {"times": t, "cents": c, "conf": conf, "method": method}


def notes_from_contour(layer: dict, offset: float, quarter: bool, min_note: float) -> list[Note]:
    raw = segment_notes(layer["times"], layer["cents"], offset)
    notes = quantize_pitch(raw, quarter)
    return simplify_ornaments(notes, min_note)


def poly_layer(x: np.ndarray, sr: int, kind: str, offset: float, quarter: bool) -> tuple[list[Note], str]:
    mono = dsp.to_mono(x)
    events, method = None, "fallback"
    if basic_pitch_available() and os.environ.get("NOTNEGAR_DISABLE_BASIC_PITCH") != "1":
        try:
            events = _basic_pitch(mono, sr)
            method = "basic-pitch"
        except Exception as e:  # pragma: no cover
            log.exception("Basic Pitch failed, using the fallback: %s", e)
    if events is None:
        lo = 35.0 if kind == "piano" else 70.0
        events = dsp.multipitch(mono, sr, max_poly=4 if kind != "other" else 3, fmin=lo)
    notes = []
    for on, off, midi, amp in events:
        qt = int(round(midi)) * 2
        cents = (midi - 60) * 100
        if quarter:
            c = dsp.refine_pitch_cents(mono, sr, on, off, midi)
            if c is not None and np.isfinite(c):
                c -= offset
                s100 = round(c / 100) * 100
                if abs(c - s100) >= 28:
                    qt = int(round(c / 50)) + 120
                cents = c
        notes.append(Note(float(on), float(off), qt, float(cents), float(np.clip(amp, 0.2, 1.0))))
    notes.sort(key=lambda n: (n.onset, n.qt))
    return notes, method


def _basic_pitch(mono: np.ndarray, sr: int):  # pragma: no cover - needs basic-pitch
    from basic_pitch.inference import predict
    from basic_pitch import ICASSP_2022_MODEL_PATH
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "stem.wav")
        write_wav(p, mono / (np.abs(mono).max() + 1e-9) * 0.9, sr)
        _, _, note_events = predict(p, ICASSP_2022_MODEL_PATH, onset_threshold=0.5, frame_threshold=0.3,
                                    minimum_note_length=80, melodia_trick=True)
    return [(float(e[0]), float(e[1]), float(e[2]), float(e[3])) for e in note_events]


def drum_hits(x: np.ndarray, sr: int) -> list[Note]:
    hits = dsp.onsets(dsp.to_mono(x), sr)
    # one-line percussion: pitch is just a placeholder (C4); velocity carries the accent
    return [Note(t, t + 0.1, 120, 0.0, s) for t, s in hits]

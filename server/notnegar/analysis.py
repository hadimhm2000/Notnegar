"""From a pitch contour to notes, and from notes to tuning, quarter-tones and dastgah/scale."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict

import numpy as np

from .theory import SCALES, Scale


@dataclass
class Note:
    onset: float           # seconds
    offset: float          # seconds
    qt: int                # quarter-tone index (2*midi), C4 = 120
    cents: float = 0.0     # measured, relative to C4, tuning offset removed
    velocity: float = 0.8

    @property
    def dur(self) -> float:
        return self.offset - self.onset

    @property
    def midi(self) -> float:
        return self.qt / 2


def tuning_offset(cents: np.ndarray, weights: np.ndarray | None = None) -> float:
    """Global deviation from A=440 in cents, circular mean on the semitone grid.

    Quarter-tone notes sit at the opposite phase and so do not bias the estimate.
    """
    m = np.isfinite(cents)
    if not m.any():
        return 0.0
    w = np.ones(m.sum()) if weights is None else weights[m]
    ang = 2 * np.pi * cents[m] / 100
    return float(np.angle(np.sum(w * np.exp(1j * ang))) / (2 * np.pi) * 100)


def segment_notes(times: np.ndarray, cents: np.ndarray, offset: float, *, split_cents: float = 65,
                  min_frames: int = 4, max_gap_frames: int = 2) -> list[dict]:
    """Split a contour into steady notes; returns dicts with onset, offset and median cents."""
    dt = float(times[1] - times[0]) if len(times) > 1 else 0.01
    raw, cur, gap = [], None, 0

    def close():
        nonlocal cur
        if cur and len(cur["v"]) >= min_frames:
            raw.append({"onset": cur["s"] * dt + times[0], "offset": (cur["e"] + 1) * dt + times[0],
                        "med": float(np.median(cur["v"]))})
        cur = None

    for t, c0 in enumerate(cents):
        if not np.isfinite(c0):
            if cur is not None:
                gap += 1
                if gap > max_gap_frames:
                    close()
            continue
        c = c0 - offset
        gap = 0
        if cur is not None:
            ref = cur["sum"] / len(cur["v"])
            if abs(c - ref) < split_cents:
                cur["v"].append(c); cur["sum"] += c; cur["e"] = t
                continue
            close()
        cur = {"s": t, "e": t, "v": [c], "sum": c}
    close()

    merged = []
    for nt in raw:
        pv = merged[-1] if merged else None
        if pv and nt["onset"] - pv["offset"] < 0.03 and abs(nt["med"] - pv["med"]) < 35:
            d1, d2 = pv["offset"] - pv["onset"], nt["offset"] - nt["onset"]
            pv["med"] = (pv["med"] * d1 + nt["med"] * d2) / (d1 + d2)
            pv["offset"] = nt["offset"]
        else:
            merged.append(dict(nt))
    # octave errors: fold a note that sits an octave away from its neighbours
    meds = [n["med"] for n in merged]
    for i, nt in enumerate(merged):
        nb = meds[max(0, i - 4):i] + meds[i + 1:i + 5]
        if len(nb) < 3:
            continue
        m = float(np.median(nb))
        while nt["med"] - m > 850:
            nt["med"] -= 1200
        while m - nt["med"] > 850:
            nt["med"] += 1200
    return merged


def has_quarter_tones(raw_notes: list[dict]) -> tuple[bool, float]:
    """Decide on whole notes (not frames) whether the music uses quarter-tones."""
    qd = td = 0.0
    qpc = np.zeros(24)
    for nt in raw_notes:
        d = nt["offset"] - nt["onset"]
        dev = nt["med"] - round(nt["med"] / 100) * 100
        td += d
        if abs(dev) >= 30:
            qd += d
            qpc[int(round(nt["med"] / 50)) % 24] += d
    frac = qd / td if td else 0.0
    top = qpc.max() / qd if qd else 0.0
    return bool(frac > 0.10 and top > 0.30), float(frac)


def quantize_pitch(raw_notes: list[dict], quarter: bool, velocity: float = 0.8) -> list[Note]:
    out = []
    for nt in raw_notes:
        s100 = round(nt["med"] / 100) * 100
        dev = nt["med"] - s100
        q = round(nt["med"] / 50) if (quarter and abs(dev) >= 28) else s100 // 50
        out.append(Note(nt["onset"], nt["offset"], int(q) + 120, nt["med"], velocity))
    return out


def simplify_ornaments(notes: list[Note], min_dur: float) -> list[Note]:
    """Fold very short notes (melisma, slides) into the neighbouring held note."""
    if not notes:
        return notes
    out: list[Note] = []
    for n in notes:
        if n.dur < min_dur and out and n.onset - out[-1].offset < 0.05:
            out[-1].offset = n.offset
            continue
        if out and out[-1].dur < min_dur and n.onset - out[-1].offset < 0.05:
            n.onset = out[-1].onset
            out[-1] = n
            continue
        out.append(n)
    return [n for n in out if n.dur >= min_dur * 0.6]


def pitch_profile(notes: list[Note]) -> tuple[np.ndarray, np.ndarray, int]:
    """Duration-weighted pitch-class histogram, phrase-final weights (24 bins each) and phrase count."""
    hist, fin = np.zeros(24), np.zeros(24)
    n_fin = 0
    for i, n in enumerate(notes):
        k = n.qt % 24
        hist[k] += n.dur
        nx = notes[i + 1] if i + 1 < len(notes) else None
        if nx is None or nx.onset - n.offset > 0.3:
            fin[k] += n.dur + (0 if nx else 0.5)
            n_fin += 1
    hist /= hist.sum() or 1
    fin /= fin.sum() or 1
    return hist, fin, n_fin


@dataclass
class ScaleScore:
    scale: Scale
    tonic: int
    score: float
    p: float = 0.0


def rank_scales(hist: np.ndarray, fin: np.ndarray, quarter: bool, n_fin: int = 12) -> list[ScaleScore]:
    """Every template at every tonic; without quarter-tones only 12-tone scales qualify.

    The note set decides the family; the tonic terms (most frequent note, phrase endings) only
    break ties, and phrase endings count less when there are few of them.
    """
    fin_w = 0.4 * min(1.0, n_fin / 12)
    res = []
    for sc in SCALES:
        mask = np.zeros(24, bool)
        mask[list(sc.deg)] = True
        best = None
        for t in range(24):
            if not quarter and (sc.needs_quarter or t % 2):
                continue
            m = np.roll(mask, t)
            s = float(np.sum(hist * np.where(m, 1.0, -1.3))) + 0.35 * hist[t] + fin_w * fin[t]
            if best is None or s > best.score:
                best = ScaleScore(sc, t, s)
        if best:
            res.append(best)
    res.sort(key=lambda r: -r.score)
    ex = np.exp(np.array([r.score for r in res]) / 0.035 - max(r.score for r in res) / 0.035)
    for r, e in zip(res, ex / ex.sum()):
        r.p = float(e)
    return res


def notes_to_dicts(notes: list[Note]) -> list[dict]:
    return [asdict(n) for n in notes]

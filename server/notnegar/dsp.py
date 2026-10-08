"""Signal processing in plain numpy: spectra, predominant-melody tracking, beat and onsets.

These are the dependency-free fallbacks; the pipeline prefers CREPE / Basic Pitch when installed.
"""
from __future__ import annotations

import numpy as np

C4_HZ = 261.6256


def to_mono(x: np.ndarray) -> np.ndarray:
    return x if x.ndim == 1 else x.mean(axis=0)


def resample_poly(x: np.ndarray, sr: int, target: int) -> tuple[np.ndarray, int]:
    """Integer-factor decimation with a simple anti-alias filter (enough for analysis)."""
    if sr == target:
        return x.astype(np.float32), sr
    from scipy.signal import resample_poly as rp
    from math import gcd
    g = gcd(int(sr), int(target))
    return rp(x, target // g, sr // g).astype(np.float32), target


def stft_mag(x: np.ndarray, n_fft: int, hop: int) -> np.ndarray:
    """Magnitude spectrogram, frames x bins (Hann window)."""
    if len(x) < n_fft:
        x = np.pad(x, (0, n_fft - len(x)))
    n = 1 + (len(x) - n_fft) // hop
    idx = np.arange(n_fft)[None, :] + hop * np.arange(n)[:, None]
    win = np.hanning(n_fft).astype(np.float32)
    frames = x[idx] * win
    return np.abs(np.fft.rfft(frames, axis=1)).astype(np.float32)


def _peaks(mag_row: np.ndarray, k_lo: int, k_hi: int, bin_hz: float, rel: float = 0.02, max_peaks: int = 60):
    seg = mag_row[k_lo - 1:k_hi + 2]
    c = seg[1:-1]
    is_pk = (c > seg[:-2]) & (c >= seg[2:]) & (c > rel * (c.max() if c.size else 0))
    ks = np.nonzero(is_pk)[0]
    if ks.size == 0:
        return np.empty(0), np.empty(0)
    if ks.size > max_peaks:
        ks = ks[np.argsort(c[ks])[-max_peaks:]]
    a = np.log(seg[ks] + 1e-12)
    b = np.log(seg[ks + 1] + 1e-12)
    g = np.log(seg[ks + 2] + 1e-12)
    den = a - 2 * b + g
    dlt = np.where(den < 0, 0.5 * (a - g) / np.where(den < 0, den, -1), 0.0)
    freqs = (ks + k_lo + dlt) * bin_hz
    amps = np.exp(b - 0.25 * (a - g) * dlt)
    return freqs, amps


def melody_salience(x: np.ndarray, sr: int, side: np.ndarray | None = None, fmin: float = 110.0,
                    fmax: float = 1300.0, hop_s: float = 0.0213, progress=None):
    """Predominant melody by harmonic summation + Viterbi tracking.

    Returns times (s), cents relative to C4 (NaN when unvoiced) and a 0..1 confidence.
    ``side`` (L-R) suppresses instruments panned away from the centre.
    """
    target = 12000
    x, sr = resample_poly(x, sr, target)
    if side is not None:
        side, _ = resample_poly(side, sr if sr == target else target, target)
    n_fft, hop = 2048, max(64, int(round(hop_s * sr)))
    M = stft_mag(x, n_fft, hop)
    if side is not None:
        S = stft_mag(side[:len(x)], n_fft, hop)[: len(M)]
        C = np.maximum(0, M - 0.8 * S)
    else:
        C = M
    bin_hz = sr / n_fft
    k_lo, k_hi = max(2, int(np.ceil(60 / bin_hz))), min(n_fft // 2 - 2, int(5000 / bin_hz))
    band = (np.arange(C.shape[1]) * bin_hz > max(fmin, 60)) & (np.arange(C.shape[1]) * bin_hz < 1600)
    energy = (C[:, band] ** 2).sum(axis=1)

    B = int(np.ceil(120 * np.log2(fmax / fmin))) + 1          # 10-cent bins
    f_bins = fmin * 2 ** (np.arange(B) / 120)
    prior = np.where(f_bins < fmin * 1.45, (f_bins / (fmin * 1.45)) ** 2, 1.0)
    prior *= np.where(f_bins > 1000, (1000 / f_bins) ** 1.5, 1.0)
    H = np.arange(1, 9)
    hw = 0.8 ** (H - 1)
    offs = np.arange(-5, 6)
    K = 5
    nF = len(C)
    cand_c = np.full((nF, K), np.nan)
    cand_s = np.zeros((nF, K))
    base_cents = 1200 * np.log2(fmin / C4_HZ)
    for t in range(nF):
        fp, ap = _peaks(C[t], k_lo, k_hi, bin_hz)
        if fp.size == 0:
            continue
        fc = fp[:, None] / H[None, :]                        # (P, 8)
        w = np.sqrt(ap)[:, None] * hw[None, :]
        ok = (fc >= fmin * 0.97) & (fc <= fmax)
        cb = 120 * np.log2(np.where(ok, fc, fmin) / fmin)
        b = np.floor(cb)[..., None] + offs                     # (P, 8, 11)
        d = (b - cb[..., None]) / 4.5
        wt = np.where((np.abs(d) < 1) & ok[..., None], np.cos(np.pi * d / 2) ** 2, 0) * w[..., None]
        b = b.astype(int)
        valid = (b >= 0) & (b < B) & (wt > 0)
        sal = np.zeros(B)
        np.add.at(sal, b[valid], wt[valid])
        v = sal * prior
        is_max = np.zeros(B, bool)
        is_max[1:-1] = (v[1:-1] > 0) & (v[1:-1] >= v[:-2]) & (v[1:-1] > v[2:])
        tops = np.nonzero(is_max)[0]
        if tops.size == 0:
            continue
        tops = tops[np.argsort(v[tops])[::-1][:K]]
        a, m, g = v[tops - 1], v[tops], v[tops + 1]
        den = a - 2 * m + g
        off = np.where(den < 0, 0.5 * (a - g) / np.where(den < 0, den, -1), 0)
        cand_c[t, :len(tops)] = base_cents + (tops + off) * 10
        cand_s[t, :len(tops)] = m
        if progress and t % 400 == 0:
            progress(t / nF)

    # Viterbi over candidates; jumps cost lam per semitone
    lam = 0.45
    logS = np.where(np.isnan(cand_c), -np.inf, np.log(cand_s + 1e-9))
    dp = np.full((nF, K), -np.inf)
    bp = np.full((nF, K), -1, int)
    prev_best = 0.0
    for t in range(nF):
        if t > 0 and np.isfinite(dp[t - 1]).any():
            jump = np.abs(cand_c[t][:, None] - cand_c[t - 1][None, :]) / 100
            sc = dp[t - 1][None, :] - lam * jump
            sc = np.where(np.isnan(sc), -np.inf, sc)
            bi = np.argmax(sc, axis=1)
            best = sc[np.arange(K), bi]
            dp[t] = logS[t] + np.where(np.isfinite(best), best, prev_best)
            bp[t] = np.where(np.isfinite(best), bi, -1)
        else:
            dp[t] = logS[t] + prev_best
        if np.isfinite(dp[t]).any():
            prev_best = np.nanmax(np.where(np.isfinite(dp[t]), dp[t], np.nan))
    pick = np.full(nF, -1, int)
    j = -1
    for t in range(nF - 1, -1, -1):
        if j < 0 and np.isfinite(dp[t]).any():
            j = int(np.argmax(dp[t]))
        pick[t] = j
        j = bp[t, j] if j >= 0 else -1

    chosen_s = np.where(pick >= 0, cand_s[np.arange(nF), np.maximum(pick, 0)], 0)
    e_gate = 0.04 * np.percentile(energy, 90) if nF else 0
    gated = chosen_s[energy > e_gate]
    s_ref = np.percentile(gated, 75) if gated.size else 1.0
    voiced = (pick >= 0) & (energy > e_gate) & (chosen_s > 0.22 * s_ref)
    cents = np.where(voiced, cand_c[np.arange(nF), np.maximum(pick, 0)], np.nan)
    conf = np.where(voiced, np.minimum(1, chosen_s / (s_ref + 1e-12)), 0)
    times = np.arange(nF) * hop / sr
    return times, cents.astype(np.float64), conf.astype(np.float64)


def spectral_flux(x: np.ndarray, sr: int, hop_s: float = 0.0116):
    """Onset novelty curve (log-magnitude flux with local mean removed)."""
    x, sr = resample_poly(x, sr, 22050)
    hop = int(round(hop_s * sr))
    M = stft_mag(x, 1024, hop)
    L = np.log1p(1000 * M)
    flux = np.maximum(0, np.diff(L, axis=0)).sum(axis=1)
    flux = np.concatenate([[0], flux])
    k = 17
    local = np.convolve(flux, np.ones(k) / k, mode="same")
    return np.maximum(0, flux - local), hop / sr


def tempo_and_beat(x: np.ndarray, sr: int) -> dict:
    """Tempo (BPM), beat phase, confidence and a 3/4 vs 4/4 guess."""
    nov, dt = spectral_flux(x, sr)
    n = len(nov)

    def ac(L):
        L = int(round(L))
        return float(np.dot(nov[: n - L], nov[L:])) if 0 <= L < n else 0.0

    ac0 = ac(0) or 1.0
    best_L, best_v = 0, -1.0
    for L in range(int(0.3 / dt), int(1.5 / dt) + 1):
        bpm = 60 / (L * dt)
        w = np.exp(-0.5 * (np.log2(bpm / 110) / 0.9) ** 2)
        v = ac(L) * w
        if v > best_v:
            best_v, best_L = v, L
    a1, a2, a3 = ac(best_L - 1), ac(best_L), ac(best_L + 1)
    den = a1 - 2 * a2 + a3
    Lf = best_L + (0.5 * (a1 - a3) / den if den < 0 else 0)
    conf = a2 / ac0
    bpm = 60 / (Lf * dt)
    phase, bv = 0.0, -1.0
    for ph in range(max(1, best_L)):
        idx = np.round(np.arange(ph, n, Lf)).astype(int)
        idx = idx[idx < n]
        s = float(nov[idx].sum())
        if s > bv:
            bv, phase = s, ph * dt
    r2, r3, r4 = ac(2 * Lf), ac(3 * Lf), ac(4 * Lf)
    meter = 3 if (r3 > r4 * 1.15 and r3 > r2 * 0.95) else 4
    return {"bpm": float(bpm), "phase": float(phase), "confidence": float(conf), "meter": meter}


def onsets(x: np.ndarray, sr: int, threshold: float = 3.0) -> list[tuple[float, float]]:
    """Peak-picked onsets (time, strength) — used for the percussion part."""
    nov, dt = spectral_flux(x, sr)
    if not nov.size:
        return []
    med = np.median(nov[nov > 0]) if (nov > 0).any() else 0
    thr = threshold * (med + 1e-9)
    out, last = [], -1.0
    peak_ref = np.percentile(nov, 99) + 1e-9
    thr = max(thr, 0.12 * peak_ref)
    for i in range(1, len(nov) - 1):
        if nov[i] > thr and nov[i] >= nov[i - 1] and nov[i] > nov[i + 1]:
            t = i * dt
            if t - last > 0.09:
                out.append((t, float(min(1, nov[i] / peak_ref))))
                last = t
    return out


def refine_pitch_cents(x: np.ndarray, sr: int, t0: float, t1: float, midi: float) -> float | None:
    """Median spectral-peak frequency of a note's fundamental, in cents relative to C4."""
    a, b = int(t0 * sr), int(min(len(x), t1 * sr))
    if b - a < int(0.05 * sr):
        return None
    seg = x[a:b]
    n_fft = 8192 if sr > 30000 else 4096
    hop = n_fft // 4
    M = stft_mag(seg, n_fft, hop)
    f_exp = 440 * 2 ** ((midi - 69) / 12)
    bin_hz = sr / n_fft
    lo = int(f_exp * 2 ** (-0.6 / 12) / bin_hz)
    hi = int(f_exp * 2 ** (0.6 / 12) / bin_hz) + 1
    if hi >= M.shape[1] - 1 or lo < 2 or hi - lo < 1:
        return None
    est = []
    floor = M[:, lo:hi + 1].max() * 0.05 if M.size else 0
    for row in M:
        k = lo + int(np.argmax(row[lo:hi + 1]))
        if row[k] <= floor:
            continue
        a_, b_, g_ = np.log(row[k - 1:k + 2] + 1e-12)
        den = a_ - 2 * b_ + g_
        d = float(np.clip(0.5 * (a_ - g_) / den, -0.5, 0.5)) if den < 0 else 0.0
        f = (k + d) * bin_hz
        if f > 0:
            est.append(1200 * np.log2(f / C4_HZ))
    est = [e for e in est if np.isfinite(e)]
    return float(np.median(est)) if est else None


def multipitch(x: np.ndarray, sr: int, max_poly: int = 4, fmin: float = 55.0, fmax: float = 2000.0):
    """Rough polyphonic fallback: harmonic-salience peaks per frame, tracked into notes.

    Returns note events (onset, offset, midi_float, amplitude).
    """
    x, sr = resample_poly(x, sr, 16000)
    n_fft, hop = 4096, 256
    M = stft_mag(x, n_fft, hop)
    bin_hz = sr / n_fft
    k_lo, k_hi = max(2, int(fmin / bin_hz)), min(n_fft // 2 - 2, int(5000 / bin_hz))
    dt = hop / sr
    lo_m, hi_m = int(np.ceil(12 * np.log2(fmin / 440) + 69)), int(12 * np.log2(fmax / 440) + 69)
    midis = np.arange(lo_m, hi_m + 1)
    frame_notes = []
    glob = np.percentile(M.max(axis=1), 90) + 1e-9
    for t in range(len(M)):
        fp, ap = _peaks(M[t], k_lo, k_hi, bin_hz, rel=0.05, max_peaks=40)
        if fp.size == 0 or M[t].max() < 0.05 * glob:
            frame_notes.append({})
            continue
        pm = 12 * np.log2(fp / 440) + 69
        sal = {}
        for m in midis:
            s = 0.0
            for h in range(1, 7):
                hm = m + 12 * np.log2(h)
                close = np.abs(pm - hm) < 0.4
                if close.any():
                    s += (0.8 ** (h - 1)) * ap[close].max()
            if s > 0:
                sal[m] = s
        chosen = {}
        used = []
        for m, s in sorted(sal.items(), key=lambda kv: -kv[1]):
            if len(chosen) >= max_poly or s < 0.25 * max(sal.values()):
                break
            if any(abs(m - u) in (12, 19, 24) for u in used):   # likely a harmonic of a chosen note
                continue
            chosen[m] = s
            used.append(m)
        frame_notes.append(chosen)
    # track
    active, events = {}, []
    for t, fn in enumerate(frame_notes + [{}]):
        for m in list(active):
            if m not in fn:
                st, amp = active.pop(m)
                if (t - st) * dt >= 0.08:
                    events.append((st * dt, t * dt, float(m), amp))
        for m, s in fn.items():
            if m not in active:
                active[m] = (t, s)
    peak = max((e[3] for e in events), default=1)
    return [(a, b, m, min(1.0, amp / peak)) for a, b, m, amp in sorted(events)]

"""Synthetic test songs with known answers: separate stems plus their stereo mix."""
from __future__ import annotations

import numpy as np

SR = 44100


def _tone(f, d, amp, harm=6, vib=0.0, decay=0.0, roll=0.7):
    t = np.arange(int(d * SR)) / SR
    ph = 2 * np.pi * np.cumsum(f * (1 + vib * np.sin(2 * np.pi * 5.5 * t))) / SR
    y = sum((roll ** (h - 1)) * np.sin(h * ph) for h in range(1, harm + 1))
    env = np.minimum(1, t / 0.02) * np.minimum(1, np.maximum(0, d - t) / 0.05)
    if decay:
        env = env * np.exp(-t * decay)
    return amp * y * env


def song(kind: str = "segah", seconds_repeat: int = 2):
    """Returns (stems {name: (2, N)}, mix (2, N), expected dict)."""
    if kind == "segah":
        tonic = 329.63 * 2 ** (-50 / 1200)          # E koron
        mel = [(0, 1), (3, .5), (7, .5), (3, 1), (0, 1), (None, .5), (3, .5), (7, 1), (11, .5), (7, .5), (3, 1), (0, 2), (None, 1),
               (7, 1), (11, 1), (14, .5), (11, .5), (7, 1), (3, .5), (0, .5), (3, 1), (0, 2), (None, 1)] * seconds_repeat
        chords = [[0, 14], [-10, 7], [0, 14], [-3, 11]]
        bpm, cents_off = 96, 8
        expected = {"scale": "segah", "tonic": 7, "quarter": True, "bpm": 96}
    else:
        tonic = 440.0                                  # A minor
        mel = [(0, 1), (4, .5), (6, .5), (10, 1), (14, 1), (10, .5), (6, .5), (4, 1), (0, 2), (None, 1),
               (6, 1), (10, 1), (14, .5), (16, .5), (14, 1), (10, 1), (6, .5), (4, .5), (0, 2), (None, 1)] * seconds_repeat
        chords = [[0, 6, 14], [-8, 6, 10], [-4, 4, 10], [-6, 4, 14]]
        bpm, cents_off = 100, 0
        expected = {"scale": "minor", "tonic": 18, "quarter": False, "bpm": 100}
    beat = 60 / bpm
    total = sum(b for _, b in mel) * beat + 1.5
    n = int(total * SR) + SR
    stems = {k: np.zeros((2, n)) for k in ("vocals", "piano", "bass", "drums")}
    t = 0.3
    for q, b in mel:
        d = b * beat
        if q is not None:
            y = _tone(tonic * 2 ** ((q * 50 + cents_off) / 1200), d * 0.95, 0.30, vib=0.006)
            i = int(t * SR)
            stems["vocals"][:, i:i + len(y)] += y
        t += d
    t, k = 0.3, 0
    while t < total - 1.2:
        ch = chords[k % len(chords)]
        for j, q in enumerate(ch):
            y = _tone(tonic / 2 * 2 ** ((q * 50 + cents_off) / 1200), 2 * beat, 0.12, decay=2.5)
            i = int(t * SR)
            stems["piano"][j % 2, i:i + len(y)] += y
            stems["piano"][1 - j % 2, i:i + len(y)] += 0.25 * y
        yb = _tone(tonic / 4 * 2 ** ((ch[0] * 50 + cents_off) / 1200), 2 * beat, 0.18, harm=3, decay=2.5)
        i = int(t * SR)
        stems["bass"][:, i:i + len(yb)] += yb
        for bb in range(2):
            kt = np.arange(int(0.12 * SR)) / SR
            kk = 0.5 * np.sin(2 * np.pi * 55 * kt) * np.exp(-kt * 30)
            i = int((t + bb * beat) * SR)
            stems["drums"][:, i:i + len(kk)] += kk
        t += 2 * beat
        k += 1
    mix = sum(stems.values())
    peak = np.abs(mix).max() * 1.1
    stems = {k: (v / peak).astype(np.float32) for k, v in stems.items()}
    return stems, (mix / peak).astype(np.float32), expected

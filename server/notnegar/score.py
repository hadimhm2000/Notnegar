"""Score model: notes placed on the beat grid, one sequence of events per part.

Writers (LilyPond, MusicXML, MIDI) all read this model, so they agree with each other.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .analysis import Note
from .theory import Scale, Speller

GRID = 0.25                     # beats (a sixteenth note in x/4)
DUR_BEATS = [4, 3, 2, 1.5, 1, 0.75, 0.5, 0.25]


@dataclass
class Event:
    start: float                # beats from the score's time zero
    dur: float                  # beats
    qts: list = field(default_factory=list)     # empty → rest
    velocity: float = 0.8
    name: str = ""              # Persian note name for lyrics-style labels (melodic parts)
    marks: list = field(default_factory=list)   # "left" (left-hand mezrab), "riz" (tremolo)
    label: str = ""             # section name shown above the first note (مقدمه، شعر، ...)

    @property
    def is_rest(self) -> bool:
        return not self.qts


@dataclass
class Part:
    id: str
    name_fa: str
    name_en: str
    kind: str                   # melody | poly | drums
    clef: str                   # treble, treble_8, bass, bass_8, percussion
    events: list = field(default_factory=list)
    group: str = ""             # parts sharing a group are braced (piano)
    midi_program: int = 0


@dataclass
class Score:
    title: str
    subtitle: str
    bpm: float
    meter: float                # bar length in quarter notes; 0 = free rhythm (no bar lines)
    scale: Scale
    tonic: int
    speller: Speller
    parts: list
    beat_s: float
    t0: float
    analysis: dict = field(default_factory=dict)
    time_sig: tuple = (4, 4)    # displayed time signature, e.g. (6, 8)
    tempo_unit: str = "4"       # LilyPond tempo unit: "4" or "4." (compound time)
    tempo_value: float = 0.0    # metronome number for tempo_unit
    composer: str = ""
    instrument_fa: str = ""
    repeats: list = field(default_factory=list)   # [(first bar, length in bars)], written once with |: :|

    @property
    def total_beats(self) -> float:
        return max((e.start + e.dur for p in self.parts for e in p.events), default=0)


def _q(v: float, grid: float = GRID) -> float:
    return round(v / grid) * grid


def _fill(events: list[Event], end: float) -> list[Event]:
    """Sort, remove overlaps, insert rests so the part covers 0..end continuously."""
    out, cur = [], 0.0
    for e in sorted(events, key=lambda e: e.start):
        if e.start < cur - 1e-6:
            continue
        if e.start > cur + 1e-6:
            out.append(Event(cur, e.start - cur))
        out.append(e)
        cur = e.start + e.dur
    if end > cur + 1e-6:
        out.append(Event(cur, end - cur))
    return out


def melody_events(notes: list[Note], t0: float, beat: float, speller: Speller, grid: float = GRID) -> list[Event]:
    ev = []
    for i, n in enumerate(notes):
        s = _q((n.onset - t0) / beat, grid)
        e = _q((n.offset - t0) / beat, grid)
        if i + 1 < len(notes):
            e = min(e, _q((notes[i + 1].onset - t0) / beat, grid))
        if e - s < grid:
            e = s + grid
        if s < 0:
            continue
        # a short gap before the next note is articulation, not a rest
        if i + 1 < len(notes):
            nxt = _q((notes[i + 1].onset - t0) / beat, grid)
            if 0 < nxt - e <= max(0.25, grid) * 1.01 and nxt - s <= 4:
                e = nxt
        ev.append(Event(s, e - s, [n.qt], n.velocity, speller.short(n.qt)))
    # drop overlaps created by rounding
    clean, last_end = [], -1.0
    for x in ev:
        if x.start >= last_end - 1e-6:
            clean.append(x)
            last_end = x.start + x.dur
    return clean


def poly_events(notes: list[Note], t0: float, beat: float) -> list[Event]:
    by_start: dict[float, list[Note]] = {}
    for n in notes:
        s = _q((n.onset - t0) / beat)
        if s >= 0:
            by_start.setdefault(s, []).append(n)
    starts = sorted(by_start)
    ev = []
    for i, s in enumerate(starts):
        group = by_start[s]
        e = max(_q((n.offset - t0) / beat) for n in group)
        if i + 1 < len(starts):
            e = min(e, starts[i + 1])
        if e - s < GRID:
            e = s + GRID
        qts = sorted({n.qt for n in group})
        ev.append(Event(s, e - s, qts, float(np.mean([n.velocity for n in group]))))
    return ev


def drum_events(hits: list[Note], t0: float, beat: float) -> list[Event]:
    starts = sorted({_q((h.onset - t0) / beat) for h in hits if h.onset >= t0})
    ev = []
    for i, s in enumerate(starts):
        e = starts[i + 1] if i + 1 < len(starts) else s + 1
        ev.append(Event(s, min(e - s, 1.0), [120], 0.8))
    return ev


def santur_marks(events: list[Event], beat_q: float, riz_min: float) -> None:
    """Suggested mezrab hands: a note on the beat is struck with the right hand, the notes between
    beats alternate (left = "v" in Persian santur notation); long notes are played as riz (tremolo)."""
    prev = None
    for e in events:
        if e.is_rest:
            prev = None
            continue
        if e.dur >= riz_min - 1e-6:
            e.marks.append("riz")
            prev = "R"
            continue
        on_beat = abs(e.start / beat_q - round(e.start / beat_q)) < 1e-6
        hand = "R" if (on_beat or prev != "R") else "L"
        if hand == "L":
            e.marks.append("left")
        prev = hand


def place_in_range(notes: list[Note], lo_qt: int, hi_qt: int, target_qt: int) -> int:
    """Octave shift (in quarter-tones) that centres a melody on target and keeps most of it in range."""
    if not notes:
        return 0
    med = float(np.median([n.qt for n in notes]))
    best, best_cost = 0, None
    for k in range(-4, 5):
        sh = 24 * k
        out = sum(1 for n in notes if not lo_qt <= n.qt + sh <= hi_qt)
        cost = out * 10 + abs(med + sh - target_qt) / 24
        if best_cost is None or cost < best_cost:
            best, best_cost = sh, cost
    return best


def split_piano(notes: list[Note], split_qt: int = 120) -> tuple[list[Note], list[Note]]:
    return [n for n in notes if n.qt >= split_qt], [n for n in notes if n.qt < split_qt]


def choose_clef(notes: list[Note], kind: str) -> str:
    if kind == "drums":
        return "percussion"
    if not notes:
        return "treble"
    med = float(np.median([n.midi for n in notes]))
    if med >= 57:
        return "treble"
    if med >= 47:
        return "treble_8"
    if med >= 36:
        return "bass"
    return "bass_8"


def finalize(parts: list[Part], meter: float = 0) -> None:
    end = max((e.start + e.dur for p in parts for e in p.events), default=0)
    if meter:
        end = float(np.ceil(end / meter - 1e-9) * meter)
    for p in parts:
        p.events = _fill(p.events, end)


def decompose(dur: float) -> list[float]:
    """Split a duration (beats) into notatable values, longest first."""
    out, rest = [], round(dur / GRID) * GRID
    for d in DUR_BEATS:
        while rest >= d - 1e-6:
            out.append(d)
            rest -= d
    return out


def split_at_bars(start: float, dur: float, meter: int) -> list[tuple[float, float]]:
    """Pieces of an event that each stay inside one bar (for writers that do not split themselves)."""
    if not meter:
        return [(start, dur)]
    out, s, end = [], start, start + dur
    while end - s > 1e-6:
        bar_end = (np.floor(s / meter + 1e-9) + 1) * meter
        e = min(end, bar_end)
        out.append((s, e - s))
        s = e
    return out


# ---------------------------------------------------------------- bars and repeats
@dataclass
class BarItem:
    start: float          # quarter notes from the bar line
    dur: float
    event: Event
    first: bool           # first piece of its event (marks and labels go here)
    tie: bool             # tied into the next bar


def split_bars(events: list[Event], meter: float) -> list[list[BarItem]]:
    """Cut a part's events at the bar lines."""
    total = max((e.start + e.dur for e in events), default=0)
    nbars = max(1, int(np.ceil(total / meter - 1e-9)))
    bars: list[list[BarItem]] = [[] for _ in range(nbars)]
    for e in events:
        pieces = split_at_bars(e.start, e.dur, meter)
        for i, (s, d) in enumerate(pieces):
            b = min(nbars - 1, int(np.floor(s / meter + 1e-9)))
            bars[b].append(BarItem(s - b * meter, d, e, i == 0, (not e.is_rest) and i < len(pieces) - 1))
    return bars


def _bar_notes(bar: list[BarItem]) -> list[tuple]:
    return [(round(it.start, 3), tuple(it.event.qts)) for it in bar if not it.event.is_rest]


def bar_similarity(a: list[BarItem], b: list[BarItem]) -> float:
    na, nb = _bar_notes(a), _bar_notes(b)
    if not na and not nb:
        return 1.0
    if not na or not nb:
        return 0.0
    sb = list(nb)
    hit = 0
    for x in na:
        if x in sb:
            sb.remove(x)
            hit += 1
    return hit / max(len(na), len(nb))


def _passage_seq(bars: list[list[BarItem]]) -> list[tuple]:
    seq = []
    for k, bar in enumerate(bars):
        for it in bar:
            if not it.event.is_rest and it.first:
                seq.append((k, round(it.start * 2) / 2, it.event.qts[0] % 24))
    return seq


def _seq_similarity(a: list[tuple], b: list[tuple]) -> float:
    """1 - edit distance between two note sequences (pitch class, beat position within a quarter)."""
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    ta = [(x[0], x[2]) for x in a]
    tb = [(x[0], x[2]) for x in b]
    n, m = len(ta), len(tb)
    prev = list(range(m + 1))
    for i in range(1, n + 1):
        cur = [i] + [0] * m
        for j in range(1, m + 1):
            same = ta[i - 1][1] == tb[j - 1][1] and abs(ta[i - 1][0] - tb[j - 1][0]) <= 0
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (0 if same else 1))
        prev = cur
    return 1.0 - prev[m] / max(n, m)


def find_repeats(bars: list[list[BarItem]], max_len: int = 8, min_sim: float = 0.62,
                 min_notes: int = 5) -> list[tuple[int, int]]:
    """Passages played twice in a row, as (first bar, length in bars).

    Greedy from the start, longest passage first. A transcription of a real recording never
    repeats note for note, so two passages count as one repeated passage when their note
    sequences (pitch, bar within the passage) mostly agree; the first playing is the one written.
    """
    out, i, n = [], 0, len(bars)
    while i < n:
        found = 0
        for L in range(min(max_len, (n - i) // 2), 0, -1):
            a = _passage_seq(bars[i:i + L])
            b = _passage_seq(bars[i + L:i + 2 * L])
            if len(a) < max(min_notes, 2 * L):
                continue
            if len(b) < 0.6 * len(a) or len(b) > 1.6 * len(a):
                continue
            need = min_sim if L > 1 else 0.85
            if _seq_similarity(a, b) >= need:
                found = L
                break
        if found:
            out.append((i, found))
            i += 2 * found
        else:
            i += 1
    return out

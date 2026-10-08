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
    meter: int                  # beats per bar; 0 = free rhythm (no bar lines)
    scale: Scale
    tonic: int
    speller: Speller
    parts: list
    beat_s: float
    t0: float
    analysis: dict = field(default_factory=dict)

    @property
    def total_beats(self) -> float:
        return max((e.start + e.dur for p in self.parts for e in p.events), default=0)


def _q(v: float) -> float:
    return round(v / GRID) * GRID


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


def melody_events(notes: list[Note], t0: float, beat: float, speller: Speller) -> list[Event]:
    ev = []
    for i, n in enumerate(notes):
        s = _q((n.onset - t0) / beat)
        e = _q((n.offset - t0) / beat)
        if i + 1 < len(notes):
            e = min(e, _q((notes[i + 1].onset - t0) / beat))
        if e - s < GRID:
            e = s + GRID
        if s < 0:
            continue
        # a short gap before the next note is articulation, not a rest
        if i + 1 < len(notes):
            nxt = _q((notes[i + 1].onset - t0) / beat)
            if 0 < nxt - e <= 0.25 and nxt - s <= 4:
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


def finalize(parts: list[Part], meter: int = 0) -> None:
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

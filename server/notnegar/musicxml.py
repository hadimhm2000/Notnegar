"""MusicXML 3.1 export (opens in MuseScore, Sibelius, Finale, Dorico) with koron/sori accidentals."""
from __future__ import annotations

from xml.sax.saxutils import escape

from .score import Score, Part, decompose, split_at_bars

DIV = 4                                   # divisions per quarter note (sixteenth = 1)
TYPE = {4: ("whole", 0), 3: ("half", 1), 2: ("half", 0), 1.5: ("quarter", 1), 1: ("quarter", 0),
        0.75: ("eighth", 1), 0.5: ("eighth", 0), 0.25: ("16th", 0)}
ALTER = {"": None, "b": "-1", "#": "1", "k": "-0.5", "s": "0.5"}
ACCID = {"b": "flat", "#": "sharp", "k": "koron", "s": "sori"}
CLEF = {"treble": ("G", 2, 0), "treble_8": ("G", 2, -1), "bass": ("F", 4, 0), "bass_8": ("F", 4, -1),
        "percussion": ("percussion", None, 0)}


def _note_xml(sc: Score, part: Part, qt: int | None, d: float, chord: bool, tie_start: bool, tie_stop: bool) -> str:
    typ, dots = TYPE[d]
    x = ["<note>"]
    if chord:
        x.append("<chord/>")
    if qt is None:
        x.append("<rest/>")
    elif part.kind == "drums":
        x.append("<unpitched><display-step>C</display-step><display-octave>5</display-octave></unpitched>")
    else:
        letter, acc, octave = sc.speller.spell(qt)
        alt = ALTER[acc]
        x.append(f"<pitch><step>{letter}</step>" + (f"<alter>{alt}</alter>" if alt else "") + f"<octave>{octave}</octave></pitch>")
    x.append(f"<duration>{int(round(d * DIV))}</duration>")
    if tie_stop:
        x.append('<tie type="stop"/>')
    if tie_start:
        x.append('<tie type="start"/>')
    x.append("<voice>1</voice>")
    x.append(f"<type>{typ}</type>" + "<dot/>" * dots)
    if qt is not None and part.kind != "drums":
        _, acc, _ = sc.speller.spell(qt)
        if acc:
            x.append(f"<accidental>{ACCID[acc]}</accidental>")
    if tie_start or tie_stop:
        x.append("<notations>" + ('<tied type="stop"/>' if tie_stop else "") + ('<tied type="start"/>' if tie_start else "") + "</notations>")
    x.append("</note>")
    return "".join(x)


def _measures(sc: Score, part: Part) -> list[list[str]]:
    meter = sc.meter or 4
    nbars = max(1, int(-(-sc.total_beats // meter)))
    bars: list[list[str]] = [[] for _ in range(nbars)]
    for e in part.events:
        pieces = []
        for s, d in split_at_bars(e.start, e.dur, meter):
            for dd in decompose(d):
                pieces.append((s, dd))
                s += dd
        for i, (s, dd) in enumerate(pieces):
            bar = min(nbars - 1, int(s // meter + 1e-9))
            tie_start = (not e.is_rest) and i < len(pieces) - 1
            tie_stop = (not e.is_rest) and i > 0
            if e.is_rest:
                bars[bar].append(_note_xml(sc, part, None, dd, False, False, False))
            else:
                for j, qt in enumerate(e.qts):
                    bars[bar].append(_note_xml(sc, part, qt, dd, j > 0, tie_start, tie_stop))
    return bars


def build(sc: Score) -> str:
    meter = sc.meter or 4
    out = ['<?xml version="1.0" encoding="UTF-8" standalone="no"?>',
           '<!DOCTYPE score-partwise PUBLIC "-//Recordare//DTD MusicXML 3.1 Partwise//EN" "http://www.musicxml.org/dtds/partwise.dtd">',
           '<score-partwise version="3.1">',
           f"<work><work-title>{escape(sc.title)}</work-title></work>",
           "<identification><encoding><software>Notnegar</software></encoding></identification>",
           "<part-list>"]
    for i, p in enumerate(sc.parts):
        out.append(f'<score-part id="P{i+1}"><part-name>{escape(p.name_fa)}</part-name>'
                   f'<part-abbreviation>{escape(p.name_en)}</part-abbreviation></score-part>')
    out.append("</part-list>")
    for i, p in enumerate(sc.parts):
        out.append(f'<part id="P{i+1}">')
        for b, notes in enumerate(_measures(sc, p)):
            out.append(f'<measure number="{b+1}">')
            if b == 0:
                sign, line, octch = CLEF.get(p.clef, ("G", 2, 0))
                clef = f"<clef><sign>{sign}</sign>" + (f"<line>{line}</line>" if line else "") + \
                       (f"<clef-octave-change>{octch}</clef-octave-change>" if octch else "") + "</clef>"
                time = (f"<time><beats>{meter}</beats><beat-type>4</beat-type></time>" if sc.meter
                        else f'<time print-object="no"><beats>{meter}</beats><beat-type>4</beat-type></time>')
                out.append(f"<attributes><divisions>{DIV}</divisions><key><fifths>0</fifths></key>{time}{clef}</attributes>")
                if i == 0:
                    out.append(f'<direction placement="above"><direction-type><metronome><beat-unit>quarter</beat-unit>'
                               f'<per-minute>{int(round(sc.bpm))}</per-minute></metronome></direction-type>'
                               f'<sound tempo="{int(round(sc.bpm))}"/></direction>')
            if not notes:
                notes = [f"<note><rest measure=\"yes\"/><duration>{meter * DIV}</duration><voice>1</voice></note>"]
            out.extend(notes)
            out.append("</measure>")
        out.append("</part>")
    out.append("</score-partwise>")
    return "\n".join(out)

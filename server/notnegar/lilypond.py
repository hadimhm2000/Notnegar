"""LilyPond engraving: a Persian analysis page plus a multi-part score with koron and sori."""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from .score import Score, Part, Event, decompose
from .theory import FA_LETTER, SHORT_ACC

FONT = os.environ.get("NOTNEGAR_FONT", "Vazirmatn, Noto Naskh Arabic, Noto Sans Arabic, DejaVu Sans")
LY_DUR = {4: "1", 3: "2.", 2: "2", 1.5: "4.", 1: "4", 0.75: "8.", 0.5: "8", 0.25: "16"}
ACC_SUFFIX = {"": "", "b": "f", "#": "s", "k": "k", "s": "o"}           # LilyPond persian.ly note names
ACC_ALTER = {"b": ",FLAT", "#": ",SHARP", "k": ",KORON", "s": ",SORI"}  # constants defined by persian.ly
STEP = {"C": 0, "D": 1, "E": 2, "F": 3, "G": 4, "A": 5, "B": 6}
SHORT_NAME = {"vocals": "آواز", "other": "سازها", "guitar": "گیتار", "piano": "پیانو", "bass": "بیس",
              "drums": "ضرب", "centre": "وسط", "sides": "کناری"}
CLEF = {"treble": "treble", "treble_8": "treble_8", "bass": "bass", "bass_8": "bass_8", "percussion": "percussion"}



def lily_available() -> bool:
    return shutil.which(os.environ.get("NOTNEGAR_LILYPOND", "lilypond")) is not None


def q(s: str) -> str:
    """Quote a string for LilyPond."""
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'


def pitch(sc: Score, qt: int) -> str:
    letter, acc, octave = sc.speller.spell(qt)
    name = letter.lower() + ACC_SUFFIX[acc]
    marks = octave - 3
    return name + ("'" * marks if marks > 0 else "," * (-marks))


def _event_music(sc: Score, part: Part, e: Event) -> list[str]:
    pieces = decompose(e.dur)
    if not pieces:
        return []
    if e.is_rest:
        return [f"r{LY_DUR[d]}" for d in pieces]
    if part.kind == "drums":
        head = "c"
    elif len(e.qts) == 1:
        head = pitch(sc, e.qts[0])
    else:
        head = "<" + " ".join(pitch(sc, x) for x in e.qts) + ">"
    toks = []
    for i, d in enumerate(pieces):
        toks.append(head + LY_DUR[d] + ("~" if i < len(pieces) - 1 else ""))
    return toks


def _rest_music(sc: Score, e: Event) -> list[str]:
    """Rests, with whole empty bars written as multi-bar rests."""
    m = sc.meter
    if not m:
        return [f"r{LY_DUR[d]}" for d in decompose(e.dur)]
    out, s, end = [], e.start, e.start + e.dur
    bar_start = -(-s // m) * m                      # next bar line at or after s
    if bar_start > s:
        lead = min(bar_start, end) - s
        out += [f"r{LY_DUR[d]}" for d in decompose(lead)]
        s += lead
    full = int((end - s + 1e-6) // m)
    if full > 0:
        out.append(("R1" if m == 4 else "R2." if m == 3 else "R2") + (f"*{full}" if full > 1 else ""))
        s += full * m
    if end - s > 1e-6:
        out += [f"r{LY_DUR[d]}" for d in decompose(end - s)]
    return out


def part_music(sc: Score, part: Part) -> str:
    toks = []
    for e in part.events:
        toks += _rest_music(sc, e) if e.is_rest else _event_music(sc, part, e)
        if not sc.meter:
            toks.append('\\bar ""')                # allow line breaks in free rhythm
    lines, line = [], []
    for t in toks:
        line.append(t)
        if len(line) >= 16:
            lines.append(" ".join(line)); line = []
    if line:
        lines.append(" ".join(line))
    return "\n      ".join(lines)


def lyrics_for(part: Part) -> str:
    syl = [q(e.name or " ") for e in part.events if not e.is_rest]
    return " ".join(syl)


def _key_alterations(sc: Score) -> str:
    sig = sc.speller.key_signature()
    items = [f"({STEP[l]} . {ACC_ALTER[a]})" for l, a in sig.items() if a in ACC_ALTER]
    return "#`(" + " ".join(items) + ")"


def _fa(s) -> str:
    return f"\\override #'(font-name . {q(FONT)}) {q(s)}"


def analysis_markup(sc: Score, opts: dict) -> str:
    a = sc.analysis
    rows = [
        ("دستگاه یا گام", f"{sc.scale.name}  ({a.get('confidence_fa', '')})"),
        ("نت پایه", a.get("tonic_fa", "")),
        ("گزینه‌ی بعدی", a.get("second_fa", "—")),
        ("کوک مرجع", a.get("tuning_fa", "")),
        ("ربع‌پرده", "دارد" if a.get("quarter") else "ندارد"),
        ("تمپو و وزن", a.get("tempo_fa", "")),
        ("لایه‌ها", a.get("layers_fa", "")),
    ]
    out = ["\\markup \\override #'(font-name . " + q(FONT) + ") \\column {"]
    out.append("  \\fill-line { \"\" \\fontsize #6 \\bold " + q(sc.title) + " }")
    if sc.subtitle:
        out.append("  \\vspace #0.4 \\fill-line { \"\" \\fontsize #1 " + q(sc.subtitle) + " }")
    out.append("  \\vspace #1 \\draw-hline \\vspace #0.6")
    for k, v in rows:
        out.append("  \\fill-line { \"\" \\line { " + q(v) + " \\hspace #1 \\bold " + q(k + ":") + " } }")
    if sc.scale.note:
        out.append("  \\vspace #0.5 \\fill-line { \"\" \\italic \\fontsize #-1 " + q(sc.scale.note) + " }")
    if opts.get("tuning", True) and a.get("tuning_table"):
        out.append("  \\vspace #1.2 \\fill-line { \"\" \\fontsize #2 \\bold " + q("کوک " + a.get("instrument_fa", "ساز")) + " }")
        out.append("  \\vspace #0.5")
        hdr = ["اختلاف با پیانو (سنت)", "فاصله از درجه‌ی قبل", "فرکانس (هرتز)", "نت", "درجه"]
        widths = [26, 24, 18, 16, 8]
        out.append("  \\fill-line { \\line { " + " ".join(f"\\hcenter-in #{w} \\bold {q(h)}" for w, h in zip(widths, hdr)) + " } }")
        for r in a["tuning_table"]:
            cells = [r["dev_fa"], r["step"], r["hz_fa"], r["name"], r["degree_fa"]]
            out.append("  \\vspace #0.2 \\fill-line { \\line { " + " ".join(f"\\hcenter-in #{w} {q(c)}" for w, c in zip(widths, cells)) + " } }")
    if a.get("method_fa"):
        out.append("  \\vspace #1 \\fill-line { \"\" \\fontsize #-2 " + q(a["method_fa"]) + " }")
    out.append("}")
    return "\n".join(out)


def build(sc: Score, opts: dict | None = None) -> str:
    opts = opts or {}
    names = opts.get("names", True)
    meter = sc.meter
    global_lines = ['\\include "persian.ly"']
    g = []
    if meter:
        g.append(f"\\time {meter}/4")
        g.append(f"\\tempo 4 = {int(round(sc.bpm))}")
    else:
        g.append("\\cadenzaOn")
        g.append("\\omit Staff.TimeSignature")
    g.append(f"\\set Staff.keyAlterations = {_key_alterations(sc)}")
    staves = []
    lyric_done = False
    groups: dict[str, list[str]] = {}
    for p in sc.parts:
        vname = "v" + p.id.replace("_", "")
        inst = f"\\markup \\override #'(font-name . {q(FONT)}) {q(p.name_fa)}"
        short = f"\\markup \\override #'(font-name . {q(FONT)}) {q(SHORT_NAME.get(p.id.split('_')[0], p.name_fa))}"
        with_names = "" if p.group else f"instrumentName = {inst} shortInstrumentName = {short} "
        staff_type = "RhythmicStaff" if p.kind == "drums" else "Staff"
        body = part_music(sc, p)
        st = (f"\\new {staff_type} = {q(p.id)} \\with {{ {with_names}}}\n"
              f"    \\new Voice = {q(vname)} {{ \\global "
              + ("" if p.kind == "drums" else f"\\clef {q(CLEF.get(p.clef, 'treble'))} ")
              + f"\\compressMMRests {{\n      {body}\n    }} }}")
        if names and p.kind == "melody" and not lyric_done and any(not e.is_rest for e in p.events):
            st += (f"\n    \\new Lyrics \\with {{ \\override LyricText.font-name = {q(FONT)} "
                   f"\\override LyricText.font-size = #-2 }} \\lyricsto {q(vname)} {{ {lyrics_for(p)} }}")
            lyric_done = True
        if p.group:
            groups.setdefault(p.group, []).append(st)
            if len(groups[p.group]) == 2:
                staves.append(f"\\new PianoStaff \\with {{ instrumentName = {inst} shortInstrumentName = {short} }} <<\n    "
                              + "\n    ".join(groups[p.group]) + "\n  >>")
        else:
            staves.append(st)
    for gname, sts in groups.items():
        if len(sts) == 1:
            staves.append(sts[0])

    header_sub = sc.subtitle
    src = f"""\\version "2.24.0"
{chr(10).join(global_lines)}
#(set-global-staff-size 18)
\\paper {{
  #(set-paper-size "a4")
  top-margin = 12\\mm bottom-margin = 12\\mm left-margin = 14\\mm right-margin = 14\\mm
  ragged-last-bottom = ##t
  print-page-number = ##t
  oddFooterMarkup = \\markup \\fill-line {{ \\override #'(font-name . {q(FONT)}) \\fontsize #-3 {q(sc.title + "  ·  نت‌نگار")} \\fontsize #-3 \\fromproperty #'page:page-number-string }}
  evenFooterMarkup = \\oddFooterMarkup
}}
\\header {{ tagline = ##f }}

global = {{ {" ".join(g)} }}

{analysis_markup(sc, opts)}

\\pageBreak

\\score {{
  \\header {{
    piece = \\markup {_fa(sc.title + ("  ·  " + header_sub if header_sub else ""))}
  }}
  <<
  {chr(10).join("  " + s for s in staves)}
  >>
  \\layout {{
    \\context {{ \\Score \\override BarNumber.font-size = #-2 }}
    \\context {{ \\Voice
      \\remove Note_heads_engraver \\consists Completion_heads_engraver
      \\remove Rest_engraver \\consists Completion_rest_engraver
    }}
  }}
}}
"""
    return src


def render(src: str, out_dir: str | Path, base: str = "score", timeout: int = 600) -> tuple[Path | None, str]:
    """Write the .ly file and run LilyPond; returns (pdf path or None, log)."""
    out_dir = Path(out_dir)
    ly = out_dir / f"{base}.ly"
    ly.write_text(src, encoding="utf-8")
    if not lily_available():
        return None, "lilypond not installed"
    exe = os.environ.get("NOTNEGAR_LILYPOND", "lilypond")
    r = subprocess.run([exe, "-dno-point-and-click", "-o", str(out_dir / base), str(ly)],
                       capture_output=True, text=True, timeout=timeout, cwd=str(out_dir))
    pdf = out_dir / f"{base}.pdf"
    return (pdf if pdf.exists() else None), (r.stdout + r.stderr)[-6000:]

"""End-to-end job: decode → separate layers → transcribe each → analyse → engrave → files."""
from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path

import numpy as np

from . import audio, dsp, lilypond, midi, musicxml
from .analysis import (Note, has_quarter_tones, offset_candidates, pitch_profile, quantize_pitch,
                       rank_scales, segment_notes, simplify_ornaments)
from .score import (Part, Score, choose_clef, drum_events, finalize, melody_events, place_in_range,
                    poly_events, santur_marks, split_piano)
from .separate import STEM_INFO, separate
from .theory import SCALE_BY_ID, Speller, tuning_table
from .transcribe import drum_hits, melodic_layer, poly_layer

log = logging.getLogger(__name__)

FA_DIGITS = str.maketrans("0123456789.-+", "۰۱۲۳۴۵۶۷۸۹٫−+")
INSTRUMENTS = {"santur": "سنتور", "tar": "تار و سه‌تار", "kamancheh": "کمانچه", "ney": "نی",
               "piano": "پیانو یا ساز غربی", "voice": "آواز"}
# written range for the instrument sheet: (lowest, highest, centre) as quarter-tone indices (C4 = 120)
INSTRUMENT_RANGE = {"santur": (128, 178, 148), "tar": (120, 170, 140), "kamancheh": (110, 178, 142),
                    "ney": (120, 172, 144), "piano": (110, 180, 140), "voice": (110, 160, 134)}
MIDI_PROGRAM_INSTR = {"santur": 15, "tar": 105, "kamancheh": 110, "ney": 73, "piano": 0, "voice": 53}
MIDI_PROGRAM = {"vocals": 53, "piano": 0, "guitar": 25, "bass": 33, "other": 48, "centre": 0, "sides": 48}
LAYER_ORDER = ["vocals", "centre", "other", "guitar", "piano", "sides", "bass", "drums"]
MELODIC = {"vocals", "bass", "centre"}
POLY = {"other", "guitar", "piano", "sides"}


def fa(x) -> str:
    return str(x).translate(FA_DIGITS)


class Progress:
    def __init__(self, cb=None):
        self.cb = cb

    def __call__(self, frac: float, stage: str):
        log.info("%3d%% %s", int(frac * 100), stage)
        if self.cb:
            self.cb(float(frac), stage)


def _ser_notes(notes: list[Note]) -> list[list]:
    return [[round(n.onset, 4), round(n.offset, 4), n.qt, round(n.cents, 1), round(n.velocity, 3)] for n in notes]


def _de_notes(rows) -> list[Note]:
    return [Note(r[0], r[1], int(r[2]), r[3], r[4]) for r in rows]


def _choose_reading(times, cents, conf, min_note):
    """Tuning reading, quarter-tone decision, lead notes and scale ranking for one contour."""
    best = None
    for off in offset_candidates(cents, conf):
        raw = segment_notes(times, cents, off)
        q, qf = has_quarter_tones(raw)
        allq = quantize_pitch(raw, q)
        # the scale is judged on every note (simplifying ornaments for the sheet would bias it)
        h, f, nf = pitch_profile(allq)
        rk = rank_scales(h, f, q, nf)
        nts = simplify_ornaments(allq, min_note)
        # a quarter-tone shift keeps every interval, so the scale fit cannot separate the readings:
        # prefer the one without quarter-tones, then fewer notes between semitones, then closer to A=440
        cost = (1.0 if q else 0.0) + qf + 0.3 * abs(off) / 50
        if rk and (best is None or cost < best[0]):
            best = (cost, off, q, qf, nts, h, rk)
    _, off, q, qf, nts, h, rk = best
    return off, q, qf, nts, h, rk


def _vocal_activity(voiced: np.ndarray, dt: float, win_s: float = 1.5) -> np.ndarray:
    k = max(1, int(win_s / dt))
    act = np.convolve(voiced.astype(float), np.ones(k) / k, mode="same")
    return act > 0.2


def _sections(times: np.ndarray, vocal_on: np.ndarray, first_note: float) -> list:
    """Intro / verse / instrumental labels from where the voice sings."""
    if not len(times) or not vocal_on.any():
        return []
    dt = float(times[1] - times[0]) if len(times) > 1 else 0.02
    out, cur, start = [], None, 0
    runs = []
    for i, v in enumerate(list(vocal_on) + [None]):
        if v != cur:
            if cur is not None:
                runs.append((bool(cur), times[start], (i - start) * dt))
            cur, start = v, i
    for i, (voc, t0, dur) in enumerate(runs):
        if voc and dur >= 3:
            out.append([float(t0), "شعر"])
        elif not voc and dur >= 6:
            if t0 + dur <= first_note + 0.5:
                continue
            out.append([float(max(t0, first_note)), "مقدمه" if not out and t0 <= first_note + 1 else "موزیک"])
    clean = []
    for t, lab in out:
        if not clean or clean[-1][1] != lab:
            clean.append([t, lab])
    return clean


def run(input_path: str | Path, job_dir: str | Path, opts: dict | None = None, progress_cb=None,
        stems_dir: str | Path | None = None) -> dict:
    """Process one song. ``stems_dir`` (optional) supplies already separated WAV stems (tests, re-runs).

    opts["mode"]: "sheet" (one melody line for the chosen instrument, default) or "full" (every layer).
    opts["quality"]: "accurate" (separate layers with Demucs, default) or "fast" (no separation).
    """
    opts = dict(opts or {})
    mode = opts.get("mode") if opts.get("mode") in ("sheet", "full") else "sheet"
    quality = opts.get("quality") if opts.get("quality") in ("accurate", "fast") else "accurate"
    opts["mode"], opts["quality"] = mode, quality
    P = Progress(progress_cb)
    job = Path(job_dir)
    (job / "stems").mkdir(parents=True, exist_ok=True)
    t_start = time.time()
    max_s = float(os.environ.get("NOTNEGAR_MAX_SECONDS", "600"))

    P(0.02, "خواندن فایل")
    x, sr = audio.decode(input_path, audio.SR, max_seconds=max_s)
    mix = x.mean(axis=0)

    # 1. layers
    if stems_dir:
        stems = {p.stem: audio.decode(p, sr)[0] for p in sorted(Path(stems_dir).glob("*.wav"))}
        sep_info = {"method": "provided", "model": None, "separated": True}
    elif quality == "fast":
        stems, sep_info = {}, {"method": "none", "model": None, "separated": False}
    else:
        model = (os.environ.get("NOTNEGAR_DEMUCS_MODEL_MELODY", "htdemucs") if mode == "sheet"
                 else os.environ.get("NOTNEGAR_DEMUCS_MODEL", "htdemucs_6s"))
        P(0.05, "جداسازی لایه‌ها (طولانی‌ترین مرحله)")
        stems, sep_info = separate(x, sr, model)
    t_sep = time.time() - t_start
    levels = {k: audio.rms_db(v) for k, v in stems.items()}
    loudest = max(levels.values()) if levels else -120
    audible = {k for k, v in levels.items() if v > loudest - 28}
    stem_files = {}
    if stems:
        P(0.45, "ذخیره‌ی لایه‌ها")
        for k, v in stems.items():
            w = job / "stems" / f"{k}.wav"
            audio.write_wav(w, v / max(1.0, float(np.abs(v).max())), sr)
            mp3 = job / "stems" / f"{k}.mp3"
            if audio.write_mp3(w, mp3):
                w.unlink()
                stem_files[k] = f"stems/{k}.mp3"
            else:
                stem_files[k] = f"stems/{k}.wav"

    # 2. beat: drums layer when present, otherwise the whole mix
    P(0.5, "تشخیص تمپو و وزن")
    beat_src = stems["drums"].mean(0) if ("drums" in stems and "drums" in audible) else mix
    tb = dsp.tempo_and_beat(beat_src, sr)
    if tb["confidence"] < 0.25 and beat_src is not mix:
        tb = dsp.tempo_and_beat(mix, sr)
    beat_s = 60 / tb["bpm"]
    min_note = _min_note(opts.get("detail", "simple" if mode == "sheet" else "normal"), beat_s)

    # 3. lead melody: the voice where it sings, the lead instrument in intros and interludes
    sections = []
    has_vocals = "vocals" in stems and "vocals" in audible
    if has_vocals:
        P(0.55, "دنبال کردن ملودی آواز")
        voc = melodic_layer(stems["vocals"], sr, "vocals", progress=lambda f: P(0.55 + 0.1 * f, "دنبال کردن ملودی آواز"))
        lead = dict(voc)
        dt = float(voc["times"][1] - voc["times"][0]) if len(voc["times"]) > 1 else 0.02
        vocal_on = _vocal_activity(np.isfinite(voc["cents"]), dt)
        inst_key = next((k for k in ("other", "guitar", "piano") if k in stems and k in audible), None)
        if inst_key and mode == "sheet":
            P(0.66, "دنبال کردن ملودی سازها")
            ins = melodic_layer(stems[inst_key], sr, "other")
            n = min(len(voc["cents"]), len(ins["cents"]))
            c_v, c_i = voc["cents"][:n], ins["cents"][:n]
            fill = ~vocal_on[:n] & np.isfinite(c_i)
            # bring the instrument line into the singer's octave
            vm = np.nanmedian(c_v) if np.isfinite(c_v).any() else 0
            if fill.any():
                # instrument parts are written around (or a little below) the singer's register
                im = float(np.median(c_i[fill]))
                c_i = c_i + 1200 * round((vm - 100 - im) / 1200)
            lead = {"times": voc["times"][:n], "cents": np.where(fill, c_i, c_v),
                    "conf": np.where(fill, ins["conf"][:n], voc["conf"][:n]), "method": f"{voc['method']}+{ins['method']}"}
            vocal_on = vocal_on[:n]
        lead_key = "melody" if mode == "sheet" else "vocals"
    else:
        cands = [k for k in ("other", "guitar", "piano") if k in stems and k in audible]
        src_key = max(cands, key=lambda k: levels[k]) if cands else None
        P(0.55, "دنبال کردن ملودی اصلی")
        src = stems[src_key] if src_key else x
        lead = melodic_layer(src, sr, "other" if src_key else "centre",
                             progress=lambda f: P(0.55 + 0.15 * f, "دنبال کردن ملودی اصلی"))
        vocal_on = None
        lead_key = "melody" if mode == "sheet" else (src_key or "centre")

    offset, quarter, qfrac, lead_notes, hist, ranking = _choose_reading(lead["times"], lead["cents"], lead["conf"], min_note)
    if vocal_on is not None and lead_notes:
        sections = _sections(lead["times"], vocal_on, lead_notes[0].onset)

    layers = {lead_key: {"kind": "melody", "notes": lead_notes, "method": lead["method"]}}

    # 4. the other layers (full score only)
    if mode == "full":
        todo = [k for k in LAYER_ORDER if k in stems and k != lead_key and k in audible]
        for i, k in enumerate(todo):
            P(0.7 + 0.18 * i / max(1, len(todo)), f"نت‌نویسی {STEM_INFO.get(k, {}).get('fa', k)}")
            if k == "drums":
                layers[k] = {"kind": "drums", "notes": drum_hits(stems[k], sr), "method": "onsets"}
            elif k in MELODIC:
                lay = melodic_layer(stems[k], sr, k)
                r = segment_notes(lay["times"], lay["cents"], offset)
                layers[k] = {"kind": "melody", "notes": simplify_ornaments(quantize_pitch(r, quarter), min_note),
                             "method": lay["method"]}
            else:
                notes, method = poly_layer(stems[k], sr, k, offset, quarter)
                layers[k] = {"kind": "poly", "notes": simplify_ornaments(notes, min_note * 0.8), "method": method}

    contour = _contour_preview(lead, offset)
    base = {
        "version": 2,
        "mode": mode,
        "quality": quality,
        "duration": round(x.shape[1] / sr, 2),
        "truncated": audio.duration(input_path) > max_s + 1,
        "separation": sep_info,
        "levels_db": {k: round(v, 1) for k, v in levels.items()},
        "audible": sorted(audible, key=lambda k: LAYER_ORDER.index(k) if k in LAYER_ORDER else 99),
        "stems": stem_files,
        "lead": lead_key,
        "offset": offset,
        "quarter": quarter,
        "quarter_fraction": qfrac,
        "tempo": tb,
        "sections": sections,
        "hist": hist.tolist(),
        "ranking": [{"id": r.scale.id, "tonic": r.tonic, "p": r.p} for r in ranking],
        "contour": contour,
        "layers": {k: {"kind": v["kind"], "method": v["method"], "notes": _ser_notes(v["notes"])} for k, v in layers.items()},
        "timing": {"separation": round(t_sep, 1), "analysis": round(time.time() - t_start - t_sep, 1)},
    }
    (job / "notes.json").write_text(json.dumps(base), encoding="utf-8")
    P(0.9, "ساخت نت")
    result = render(job, opts)
    P(1.0, "تمام شد")
    return result


def _even_phrase_octaves(notes: list[Note], window_s: float = 4.0) -> list[Note]:
    """Move passages that sit far above or below the rest of the piece by an octave.

    The voice and the lead instrument often play the same tune an octave apart; on one staff for
    one instrument they belong in the same register. A note moves when the passage around it
    (±window_s) lies more than a fifth away from the whole piece.
    """
    if len(notes) < 8:
        return notes
    on = np.array([n.onset for n in notes])
    qt = np.array([n.qt for n in notes], dtype=float)
    ref = float(np.median(qt))
    # phrases: split at rests of 0.3 s or more; one decision per phrase keeps its contour intact
    bounds = [0] + [i + 1 for i, (a, b) in enumerate(zip(notes, notes[1:])) if b.onset - a.offset >= 0.3] + [len(notes)]
    out = []
    for s0, s1 in zip(bounds, bounds[1:]):
        centre = float(np.mean(on[s0:s1]))
        near = qt[np.abs(on - centre) <= window_s]
        m = float(np.median(near)) if near.size else ref
        k = int(round((ref - m) / 24)) if abs(ref - m) > 14 else 0
        out += [Note(n.onset, n.offset, n.qt + 24 * k, n.cents + 1200 * k, n.velocity) for n in notes[s0:s1]]
    return out


def _melody_subdivision(notes: list[Note], phase: float, beat_s: float) -> bool | None:
    """True if the melody divides the beat into three (6/8), False if into two, None if unclear.

    Drum layers often play straight hi-hats even in a 6/8 song; the melody's note starts are a
    steadier witness of how the beat is divided.
    """
    if len(notes) < 16:
        return None
    x = ((np.array([n.onset for n in notes]) - phase) / beat_s) % 1.0
    thirds = int(np.sum((np.abs(x - 1 / 3) < 0.07) | (np.abs(x - 2 / 3) < 0.07)))
    halves = int(np.sum(np.abs(x - 0.5) < 0.07))
    if thirds >= 0.12 * len(x) and thirds > 1.6 * halves:
        return True
    if halves >= 0.12 * len(x) and halves > 1.6 * thirds / 2:
        return False
    return None


def _align_grid(notes: list[Note], phase: float, beat_s: float, compound: bool, beats_per_bar: float) -> float:
    """Shift the beat grid so the melody's notes start on beats and its strong notes on bar lines.

    The tempo tracker finds the beat period reliably, but its phase can lock onto hi-hats between
    the beats; the melody itself tells where the beats are.
    """
    if not notes:
        return phase
    sub = 3 if compound else 2
    on = np.array([n.onset for n in notes])
    w = np.array([min(n.dur, 2 * beat_s) for n in notes])
    best, best_s = phase, -1.0
    for j in range(sub):
        p = phase + j * beat_s / sub
        x = ((on - p) / beat_s) % 1.0
        d = np.minimum(x, 1 - x)
        sc = float(np.sum(w * (d < 0.12)))
        if sc > best_s:
            best, best_s = p, sc
    bpb = int(round(beats_per_bar)) or 1
    if bpb > 1:
        scores = []
        for b in range(bpb):
            p = best + b * beat_s
            x = ((on - p) / (beat_s * bpb)) % 1.0
            d = np.minimum(x, 1 - x) * bpb
            scores.append(float(np.sum(w * (d < 0.12))))
        best = best + int(np.argmax(scores)) * beat_s
    return best


def _min_note(detail: str, beat_s: float) -> float:
    """Shortest note kept as its own note (shorter ones fold into a neighbour).

    Kept below half an eighth even for the simple sheet: folding real eighth notes (which sound
    shorter than written because of articulation) turned running eighths into quarters.
    """
    return {"detailed": max(0.05, 0.07 * beat_s), "simple": max(0.09, 0.17 * beat_s)}.get(detail, max(0.07, 0.12 * beat_s))


def _contour_preview(lead: dict, offset: float, max_points: int = 1500) -> list:
    t, c = lead["times"], lead["cents"]
    step = max(1, len(t) // max_points)
    return [[round(float(t[i]), 3), (None if not np.isfinite(c[i]) else round(float(c[i] - offset), 1))]
            for i in range(0, len(t), step)]


def render(job_dir: str | Path, opts: dict | None = None) -> dict:
    """(Re)build analysis.json and every output file from notes.json and the user's options."""
    opts = dict(opts or {})
    job = Path(job_dir)
    base = json.loads((job / "notes.json").read_text(encoding="utf-8"))
    ranking = base["ranking"]
    pick = ranking[0]
    if opts.get("scale") and opts["scale"] != "auto" and opts["scale"] in SCALE_BY_ID:
        pick = next((r for r in ranking if r["id"] == opts["scale"]), {"id": opts["scale"], "tonic": pick["tonic"], "p": 0})
    detected_tonic = int(opts["tonic"]) if str(opts.get("tonic", "auto")) not in ("auto", "", "None") else pick["tonic"]
    scale = SCALE_BY_ID[pick["id"]]
    auto = pick is ranking[0] and str(opts.get("tonic", "auto")) in ("auto", "", "None")
    mode = base.get("mode", "full")
    try:
        semis = max(-11, min(11, int(opts.get("transpose", 0) or 0)))
    except (TypeError, ValueError):
        semis = 0
    tonic = (detected_tonic + 2 * semis) % 24
    sp = Speller(scale, tonic)
    second = next((r for r in ranking if r["id"] != scale.id), None)
    tb = base["tempo"]
    free = tb["confidence"] < 0.25
    layers = {k: [Note(n.onset, n.offset, n.qt + 2 * semis, n.cents + 100 * semis, n.velocity) for n in _de_notes(v["notes"])]
              for k, v in base["layers"].items()}
    kinds = {k: v["kind"] for k, v in base["layers"].items()}
    lead_notes = layers.get(base["lead"], [])
    compound = bool(tb.get("compound")) and not free
    if not free and opts.get("meter") in ("6/8", "4/4", "3/4", "2/4"):
        compound = opts["meter"] == "6/8"
    elif not free:
        mel = _melody_subdivision(lead_notes, tb["phase"], 60 / tb["bpm"])
        if mel is not None:
            compound = mel
    if free:
        iois = np.diff([n.onset for n in lead_notes]) if len(lead_notes) > 2 else np.array([0.6])
        beat_s = float(np.clip(np.median(iois) * 2, 0.4, 1.2))
        bpm = 60 / beat_s
    else:
        bpm = tb["bpm"]
        beat_s = 60 / bpm
    if free:
        meter, time_sig, quarter_s, tempo_unit, beat_q = 0, (4, 4), beat_s, "4", 1.0
    elif compound:
        # the beat is a dotted quarter: 6/8, bar = three quarter-note lengths
        meter, time_sig, quarter_s, tempo_unit, beat_q = 3, (6, 8), beat_s / 1.5, "4.", 1.5
    else:
        m = int(tb["meter"]) if int(tb["meter"]) in (2, 3, 4) and not tb.get("compound") else 4
        if opts.get("meter") in ("4/4", "3/4", "2/4"):
            m = int(opts["meter"][0])
        meter, time_sig, quarter_s, tempo_unit, beat_q = m, (m, 4), beat_s, "4", 1.0
    detail = opts.get("detail", "simple" if mode == "sheet" else "normal")
    # an instrument sheet is written in eighths unless every ornament was asked for
    grid = 0.25 if (detail == "detailed" or (mode != "sheet" and detail == "normal")) else 0.5

    wanted = opts.get("layers") or ([base["lead"]] if mode == "sheet" else base["audible"])
    order = [base["lead"]] + [k for k in LAYER_ORDER if k != base["lead"]]
    wanted = [k for k in order if k in wanted and k in layers]
    first_on = min((n.onset for k in wanted for n in layers[k][:1]), default=0.0)
    if free:
        t0 = first_on
    else:
        t0 = _align_grid(lead_notes, tb["phase"], beat_s, compound, meter / beat_q if meter else 1)
        t0 = t0 + np.floor((first_on - t0) / (beat_s * max(1, meter / beat_q))) * beat_s * max(1, meter / beat_q)
    t0 = max(0.0, float(t0))
    instr = opts.get("instrument", "santur")

    parts = []
    if mode == "sheet" and base["lead"] in layers:
        notes = layers[base["lead"]]
        lo, hi, target = INSTRUMENT_RANGE.get(instr, INSTRUMENT_RANGE["santur"])
        notes = _even_phrase_octaves(notes)
        shift = place_in_range(notes, lo, hi, target)
        notes = [Note(n.onset, n.offset, n.qt + shift, n.cents, n.velocity) for n in notes]
        events = melody_events(notes, t0, quarter_s, sp, grid)
        if instr == "santur":
            santur_marks(events, beat_q, 1.5 if compound else 2.0)
        for t_sec, label in base.get("sections", []):
            b = (t_sec - t0) / quarter_s - grid
            ev = next((e for e in events if not e.is_rest and e.start >= b), None)
            if ev and not ev.label:
                ev.label = label
        parts.append(Part("melody", INSTRUMENTS.get(instr, "ملودی"), instr, "melody", "treble", events, "",
                          MIDI_PROGRAM_INSTR.get(instr, 15)))
        wanted = [k for k in wanted if k != base["lead"]]
    for k in wanted:
        notes = layers[k]
        info = STEM_INFO.get(k, {"fa": k, "en": k})
        kind = kinds[k]
        if kind == "drums":
            parts.append(Part(k, info["fa"], info["en"], "drums", "percussion", drum_events(notes, t0, quarter_s)))
        elif k == "piano" and notes:
            rh, lh = split_piano(notes)
            parts.append(Part("piano_rh", info["fa"], info["en"], "poly", "treble", poly_events(rh, t0, quarter_s), "piano", MIDI_PROGRAM["piano"]))
            parts.append(Part("piano_lh", info["fa"], info["en"], "poly", "bass", poly_events(lh, t0, quarter_s), "piano", MIDI_PROGRAM["piano"]))
        elif kind == "melody":
            parts.append(Part(k, info["fa"], info["en"], "melody", choose_clef(notes, "melody"),
                              melody_events(notes, t0, quarter_s, sp, grid), "", MIDI_PROGRAM.get(k, 0)))
        else:
            parts.append(Part(k, info["fa"], info["en"], "poly", choose_clef(notes, "poly"),
                              poly_events(notes, t0, quarter_s), "", MIDI_PROGRAM.get(k, 48)))
    parts = [p for p in parts if any(not e.is_rest for e in p.events)] or parts[:1]
    finalize(parts, meter)

    a440 = 440 * 2 ** (base["offset"] / 1200)
    table = tuning_table(scale, tonic, base["offset"] if not semis else 0.0)
    for r in table:
        r["degree_fa"] = fa(r["degree"])
        r["hz_fa"] = fa(f"{r['hz']:.1f}")
        r["dev_fa"] = ("+" if r["dev_cents"] >= 0 else "−") + fa(abs(r["dev_cents"]))
    methods = sorted({v["method"] for v in base["layers"].values()})
    sep = base["separation"]
    sep_fa = {"demucs": f"Demucs ({sep.get('model')})", "provided": "لایه‌های آماده",
              "stereo-fallback": "تقریبی (بدون Demucs)", "none": "بدون جداسازی (حالت سریع)"}.get(sep["method"], sep["method"])
    analysis = {
        "scale_id": scale.id, "scale_fa": scale.name, "scale_en": scale.name_en, "scale_note": scale.note,
        "tonic": tonic, "tonic_fa": sp.name(tonic), "tonic_en": sp.name_en(tonic),
        "confidence": pick["p"] if auto else None,
        "confidence_fa": f"اطمینان {fa(round(pick['p'] * 100))}٪" if auto else "انتخاب کاربر",
        "second": second, "second_fa": (f"{SCALE_BY_ID[second['id']].name} {Speller(SCALE_BY_ID[second['id']], second['tonic']).name(second['tonic'])}"
                                        f" ({fa(round(second['p'] * 100))}٪)") if second else "—",
        "offset": round(base["offset"], 1), "a440": round(a440, 2),
        "tuning_fa": f"لا = {fa(f'{a440:.1f}')} هرتز ({'+' if base['offset'] >= 0 else '−'}{fa(abs(round(base['offset'])))} سنت)",
        "quarter": base["quarter"],
        "tempo": {"bpm": round(bpm, 1), "meter": meter, "free": free, "confidence": round(tb["confidence"], 2),
                  "time_sig": list(time_sig), "compound": compound},
        "tempo_fa": ("آزاد، بی‌وزن" if free else
                     f"{fa(round(bpm))} ضرب در دقیقه · {fa(time_sig[0])}/{fa(time_sig[1])}"),
        "transpose": semis,
        "detected_tonic": detected_tonic, "detected_tonic_fa": Speller(scale, detected_tonic).name(detected_tonic),
        "sections": base.get("sections", []),
        "mode": mode,
        "layers_fa": "، ".join(STEM_INFO.get(k, {"fa": k})["fa"] for k in wanted),
        "instrument_fa": INSTRUMENTS.get(instr, "ساز"),
        "tuning_table": table,
        "method_fa": f"جداسازی: {sep_fa} · روش‌ها: {', '.join(methods)}",
        "lead": base["lead"],
    }
    title = (opts.get("title") or "").strip() or "بدون عنوان"
    artist = (opts.get("artist") or "").strip()
    key_txt = f"{scale.name} {sp.name(tonic)}"
    if semis:
        key_txt += f" (منتقل‌شده از {Speller(scale, detected_tonic).name(detected_tonic)})"
    subtitle = " · ".join(x for x in [artist if mode != "sheet" else "", key_txt] if x)
    sc = Score(title, subtitle, bpm, meter, scale, tonic, sp, parts, quarter_s, t0, analysis,
               time_sig=time_sig, tempo_unit=tempo_unit, tempo_value=round(bpm), composer=artist,
               instrument_fa=INSTRUMENTS.get(instr, "") if mode == "sheet" else "")

    files = {}
    ly_src = lilypond.build(sc, {"names": opts.get("names", mode != "sheet"), "tuning": opts.get("tuning", True)})
    pdf, lylog = lilypond.render(ly_src, job, "score")
    files["ly"] = "score.ly"
    if pdf:
        files["pdf"] = "score.pdf"
    (job / "lilypond.log").write_text(lylog, encoding="utf-8")
    (job / "score.musicxml").write_text(musicxml.build(sc), encoding="utf-8")
    files["musicxml"] = "score.musicxml"
    (job / "score.mid").write_bytes(midi.build(sc))
    files["midi"] = "score.mid"
    files.update({f"stem:{k}": v for k, v in base["stems"].items()})

    result = {
        "title": title, "subtitle": subtitle, "analysis": analysis,
        "ranking": [{**r, "name_fa": SCALE_BY_ID[r["id"]].name, "tonic_fa": Speller(SCALE_BY_ID[r["id"]], r["tonic"]).name(r["tonic"])}
                    for r in ranking[:5]],
        "hist": base["hist"], "contour": base["contour"],
        "layers": {k: {"kind": v["kind"], "method": v["method"], "count": len(v["notes"]),
                       "name_fa": STEM_INFO.get(k, {"fa": k})["fa"], "level_db": base["levels_db"].get(k)}
                   for k, v in base["layers"].items()},
        "all_stems": {k: {"file": f, "name_fa": STEM_INFO.get(k, {"fa": k})["fa"], "level_db": base["levels_db"].get(k),
                          "audible": k in base["audible"]} for k, f in base["stems"].items()},
        "parts": [{"id": p.id, "name_fa": p.name_fa, "events": sum(1 for e in p.events if not e.is_rest)} for p in parts],
        "separation": base["separation"], "duration": base["duration"], "truncated": base["truncated"],
        "files": files, "pdf_error": None if pdf else _short_log(lylog),
        "mode": mode, "quality": base.get("quality", "accurate"), "timing": base.get("timing"),
        "options": opts,
    }
    (job / "analysis.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    return result


def _short_log(text: str) -> str:
    lines = [l for l in text.splitlines() if "error" in l.lower()] or text.splitlines()[-8:]
    return "\n".join(lines[-12:])

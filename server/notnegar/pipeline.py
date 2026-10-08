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
from .score import (Part, Score, choose_clef, drum_events, finalize, melody_events, poly_events,
                    split_piano)
from .separate import STEM_INFO, separate
from .theory import SCALE_BY_ID, Speller, tuning_table
from .transcribe import drum_hits, melodic_layer, poly_layer

log = logging.getLogger(__name__)

FA_DIGITS = str.maketrans("0123456789.-+", "۰۱۲۳۴۵۶۷۸۹٫−+")
INSTRUMENTS = {"santur": "سنتور", "tar": "تار و سه‌تار", "kamancheh": "کمانچه", "ney": "نی",
               "piano": "پیانو یا ساز غربی", "voice": "آواز"}
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


def run(input_path: str | Path, job_dir: str | Path, opts: dict | None = None, progress_cb=None,
        stems_dir: str | Path | None = None) -> dict:
    """Process one song. ``stems_dir`` (optional) supplies already separated WAV stems (tests, re-runs)."""
    opts = dict(opts or {})
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
    else:
        P(0.05, "جداسازی لایه‌ها (این مرحله طولانی‌ترین بخش است)")
        stems, sep_info = separate(x, sr)
    levels = {k: audio.rms_db(v) for k, v in stems.items()}
    loudest = max(levels.values()) if levels else -120
    audible = {k for k, v in levels.items() if v > loudest - 28}
    P(0.45, "ذخیره‌ی لایه‌ها")
    stem_files = {}
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
    P(0.5, "تشخیص تمپو و ضرب")
    beat_src = stems["drums"].mean(0) if ("drums" in stems and "drums" in audible) else mix
    tb = dsp.tempo_and_beat(beat_src, sr)
    if tb["confidence"] < 0.25 and beat_src is not mix:
        tb = dsp.tempo_and_beat(mix, sr)

    # 3. lead melody → tuning, quarter-tones, dastgah
    lead_key = "vocals" if ("vocals" in stems and "vocals" in audible) else None
    if lead_key is None:
        cands = [k for k in ("centre", "other", "guitar", "piano") if k in stems and k in audible]
        lead_key = max(cands, key=lambda k: levels[k]) if cands else next(iter(stems))
    P(0.55, f"دنبال کردن ملودی اصلی ({STEM_INFO.get(lead_key, {}).get('fa', lead_key)})")
    lead_kind = lead_key if lead_key in MELODIC else "other"
    lead = melodic_layer(stems[lead_key], sr, lead_kind, progress=lambda f: P(0.55 + 0.1 * f, "دنبال کردن ملودی اصلی"))
    beat_s = 60 / tb["bpm"]
    min_note = _min_note(opts.get("detail", "normal"), beat_s)
    best = None
    for off in offset_candidates(lead["cents"], lead["conf"]):
        raw = segment_notes(lead["times"], lead["cents"], off)
        q, qf = has_quarter_tones(raw)
        nts = simplify_ornaments(quantize_pitch(raw, q), min_note)
        h, f, nf = pitch_profile(nts)
        rk = rank_scales(h, f, q, nf)
        if rk and (best is None or rk[0].score > best[0]):
            best = (rk[0].score, off, q, qf, nts, h, rk)
    _, offset, quarter, qfrac, lead_notes, hist, ranking = best

    # 4. the other layers
    layers = {lead_key: {"kind": "melody", "notes": lead_notes, "method": lead["method"]}}
    todo = [k for k in LAYER_ORDER if k in stems and k != lead_key and k in audible]
    for i, k in enumerate(todo):
        P(0.66 + 0.22 * i / max(1, len(todo)), f"نت‌نویسی {STEM_INFO.get(k, {}).get('fa', k)}")
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
        "version": 1,
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
        "hist": hist.tolist(),
        "ranking": [{"id": r.scale.id, "tonic": r.tonic, "p": r.p} for r in ranking],
        "contour": contour,
        "layers": {k: {"kind": v["kind"], "method": v["method"], "notes": _ser_notes(v["notes"])} for k, v in layers.items()},
        "elapsed_analysis": round(time.time() - t_start, 1),
    }
    (job / "notes.json").write_text(json.dumps(base), encoding="utf-8")
    P(0.9, "ساخت پارتیتور")
    result = render(job, opts)
    P(1.0, "تمام شد")
    return result


def _min_note(detail: str, beat_s: float) -> float:
    return {"detailed": max(0.05, 0.3 * beat_s / 4), "simple": 0.55 * beat_s / 2}.get(detail, max(0.07, 0.55 * beat_s / 4))


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
    tonic = int(opts["tonic"]) if str(opts.get("tonic", "auto")) not in ("auto", "", "None") else pick["tonic"]
    scale = SCALE_BY_ID[pick["id"]]
    auto = pick is ranking[0] and str(opts.get("tonic", "auto")) in ("auto", "", "None")
    sp = Speller(scale, tonic)
    second = next((r for r in ranking if r["id"] != scale.id), None)
    tb = base["tempo"]
    free = tb["confidence"] < 0.25
    layers = {k: _de_notes(v["notes"]) for k, v in base["layers"].items()}
    kinds = {k: v["kind"] for k, v in base["layers"].items()}
    lead_notes = layers.get(base["lead"], [])
    if free:
        iois = np.diff([n.onset for n in lead_notes]) if len(lead_notes) > 2 else np.array([0.6])
        beat_s = float(np.clip(np.median(iois) * 2, 0.4, 1.2))
        bpm = 60 / beat_s
    else:
        bpm = tb["bpm"]
        beat_s = 60 / bpm
    meter = 0 if free else int(tb["meter"])

    wanted = opts.get("layers") or base["audible"]
    wanted = [k for k in LAYER_ORDER if k in wanted and k in layers]
    first_on = min((n.onset for k in wanted for n in layers[k][:1]), default=0.0)
    phase = tb["phase"] if not free else first_on
    t0 = phase + np.floor((first_on - phase) / beat_s) * beat_s if not free else first_on
    t0 = max(0.0, float(t0))

    parts = []
    for k in wanted:
        notes = layers[k]
        info = STEM_INFO.get(k, {"fa": k, "en": k})
        kind = kinds[k]
        if kind == "drums":
            parts.append(Part(k, info["fa"], info["en"], "drums", "percussion", drum_events(notes, t0, beat_s)))
        elif k == "piano" and notes:
            rh, lh = split_piano(notes)
            parts.append(Part("piano_rh", info["fa"], info["en"], "poly", "treble", poly_events(rh, t0, beat_s), "piano", MIDI_PROGRAM["piano"]))
            parts.append(Part("piano_lh", info["fa"], info["en"], "poly", "bass", poly_events(lh, t0, beat_s), "piano", MIDI_PROGRAM["piano"]))
        elif kind == "melody":
            parts.append(Part(k, info["fa"], info["en"], "melody", choose_clef(notes, "melody"),
                              melody_events(notes, t0, beat_s, sp), "", MIDI_PROGRAM.get(k, 0)))
        else:
            parts.append(Part(k, info["fa"], info["en"], "poly", choose_clef(notes, "poly"),
                              poly_events(notes, t0, beat_s), "", MIDI_PROGRAM.get(k, 48)))
    parts = [p for p in parts if any(not e.is_rest for e in p.events)] or parts[:1]
    finalize(parts, meter)

    instr = opts.get("instrument", "santur")
    a440 = 440 * 2 ** (base["offset"] / 1200)
    table = tuning_table(scale, tonic, base["offset"])
    for r in table:
        r["degree_fa"] = fa(r["degree"])
        r["hz_fa"] = fa(f"{r['hz']:.1f}")
        r["dev_fa"] = ("+" if r["dev_cents"] >= 0 else "−") + fa(abs(r["dev_cents"]))
    methods = sorted({v["method"] for v in base["layers"].values()})
    sep = base["separation"]
    sep_fa = {"demucs": f"Demucs ({sep.get('model')})", "provided": "لایه‌های آماده",
              "stereo-fallback": "تقریبی (بدون Demucs)"}.get(sep["method"], sep["method"])
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
        "tempo": {"bpm": round(bpm, 1), "meter": meter, "free": free, "confidence": round(tb["confidence"], 2)},
        "tempo_fa": "آزاد، بی‌وزن" if free else f"{fa(round(bpm))} ضرب در دقیقه · {fa(meter)}/۴",
        "layers_fa": "، ".join(STEM_INFO.get(k, {"fa": k})["fa"] for k in wanted),
        "instrument_fa": INSTRUMENTS.get(instr, "ساز"),
        "tuning_table": table,
        "method_fa": f"جداسازی: {sep_fa} · روش‌ها: {', '.join(methods)}",
        "lead": base["lead"],
    }
    title = (opts.get("title") or "").strip() or "بدون عنوان"
    subtitle = " · ".join(x for x in [(opts.get("artist") or "").strip(), f"{scale.name} {sp.name(tonic)}"] if x)
    sc = Score(title, subtitle, bpm, meter, scale, tonic, sp, parts, beat_s, t0, analysis)

    files = {}
    ly_src = lilypond.build(sc, {"names": opts.get("names", True), "tuning": opts.get("tuning", True)})
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
        "options": opts,
    }
    (job / "analysis.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    return result


def _short_log(text: str) -> str:
    lines = [l for l in text.splitlines() if "error" in l.lower()] or text.splitlines()[-8:]
    return "\n".join(lines[-12:])

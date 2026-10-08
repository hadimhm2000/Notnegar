"""End-to-end tests on synthetic songs with known answers.

Run:  python -m pytest -q tests      (or simply:  python tests/test_pipeline.py)
With Demucs installed the mix is separated for real; set NOTNEGAR_TEST_STEMS=1 to feed the
known stems instead (fast, and isolates transcription from separation quality).
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from notnegar import audio, lilypond, pipeline  # noqa: E402
from notnegar.theory import SCALE_BY_ID, Speller  # noqa: E402
from tests.synth import song  # noqa: E402

OUT = Path(os.environ.get("NOTNEGAR_TEST_OUT", tempfile.mkdtemp(prefix="notnegar-test-")))


def _run(kind: str, use_stems: bool):
    stems, mix, exp = song(kind)
    d = OUT / f"{kind}-{'stems' if use_stems else 'mix'}"
    d.mkdir(parents=True, exist_ok=True)
    wav = d / "input.wav"
    audio.write_wav(wav, mix)
    stems_dir = None
    if use_stems:
        stems_dir = d / "given"
        stems_dir.mkdir(exist_ok=True)
        for k, v in stems.items():
            audio.write_wav(stems_dir / f"{k}.wav", v)
    res = pipeline.run(wav, d / "job", {"title": f"آزمون {kind}", "artist": "نت‌نگار", "instrument": "santur"},
                       stems_dir=stems_dir)
    return res, exp, d / "job"


def _check(res, exp, job: Path):
    a = res["analysis"]
    assert a["scale_id"] == exp["scale"], (a["scale_id"], exp)
    assert a["tonic"] % 24 == exp["tonic"], (a["tonic"], exp)
    assert a["quarter"] == exp["quarter"]
    assert abs(a["tempo"]["bpm"] - exp["bpm"]) < 3, a["tempo"]
    # files
    ET.parse(job / "score.musicxml")
    assert (job / "score.mid").read_bytes()[:4] == b"MThd"
    ly = (job / "score.ly").read_text(encoding="utf-8")
    assert ly.count("{") == ly.count("}"), "unbalanced braces in LilyPond source"
    assert ly.count("<<") == ly.count(">>")
    if exp["quarter"]:
        assert any(f"{l}k" in ly or f"{l}o" in ly for l in "abcdefg"), "quarter-tone note names missing"
        if lilypond.lily_available():
            log = (job / "lilypond.log").read_text()
            assert "cannot find glyph" not in log and "alteration not found" not in log, log[-2000:]
    if lilypond.lily_available():
        assert (job / "score.pdf").exists(), (job / "lilypond.log").read_text()[-3000:]
    data = json.loads((job / "analysis.json").read_text(encoding="utf-8"))
    assert data["parts"], "no parts in the score"


def test_segah_stems():
    res, exp, job = _run("segah", True)
    _check(res, exp, job)
    ids = {p["id"] for p in res["parts"]}
    assert {"vocals", "bass"} <= ids and ("piano_rh" in ids or "piano_lh" in ids), ids


def test_minor_stems():
    res, exp, job = _run("minor", True)
    _check(res, exp, job)


def test_segah_mix():
    """Full path including separation (Demucs if installed, otherwise the stereo fallback)."""
    res, exp, job = _run("segah", False)
    _check(res, exp, job)


def test_speller_and_pitch_names():
    sp = Speller(SCALE_BY_ID["shur"], 14)                    # Shur on G: A koron, B flat, E flat
    assert sp.key_signature() == {"A": "k", "B": "b", "E": "b"}
    assert sp.name(17) == "لا کرن"
    from notnegar.score import Score
    sc = Score("t", "", 90, 4, SCALE_BY_ID["shur"], 14, sp, [], 0.66, 0)
    assert lilypond.pitch(sc, 137) == "ak'"                   # A4 koron (persian.ly names)
    assert lilypond.pitch(sc, 140) == "bf'"                   # B4 flat
    assert lilypond.pitch(sc, 120) == "c'"


if __name__ == "__main__":
    print("output:", OUT)
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)

"""Smoke test against a running server: upload a synthetic Segah song, wait, check the results.

    python tests/api_smoke.py http://127.0.0.1:8000
"""
from __future__ import annotations

import json
import sys
import tempfile
import time
import urllib.request
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from notnegar.audio import write_wav  # noqa: E402
from tests.synth import song  # noqa: E402


def post_file(url: str, path: Path, fields: dict) -> dict:
    b = uuid.uuid4().hex
    body = b""
    for k, v in fields.items():
        body += f"--{b}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode()
    body += (f"--{b}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{path.name}\"\r\n"
             f"Content-Type: audio/wav\r\n\r\n").encode() + path.read_bytes() + f"\r\n--{b}--\r\n".encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": f"multipart/form-data; boundary={b}"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.loads(r.read())


def main(base: str) -> int:
    base = base.rstrip("/")
    print("health:", get_json(base + "/api/health"))
    _, mix, exp = song("segah")
    wav = Path(tempfile.mkdtemp()) / "segah.wav"
    write_wav(wav, mix)
    job = post_file(base + "/api/jobs", wav, {"title": "آزمون سه‌گاه", "instrument": "tar"})["id"]
    print("job:", job)
    st = {}
    for _ in range(360):
        st = get_json(f"{base}/api/jobs/{job}")
        if st["state"] in ("done", "error"):
            break
        time.sleep(5)
    print("state:", st.get("state"), st.get("error", ""), "elapsed:", st.get("elapsed"))
    if st.get("state") != "done":
        return 1
    r = st["result"]
    a = r["analysis"]
    print("result:", a["scale_id"], a["tonic"], a["tempo"], "quarter:", a["quarter"], "files:", sorted(r["files"]),
          "separation:", r["separation"], "pdf_error:", r.get("pdf_error"))
    ok = a["scale_id"] == exp["scale"] and a["tonic"] == exp["tonic"] and "pdf" in r["files"]
    with urllib.request.urlopen(f"{base}/api/jobs/{job}/file/score.pdf", timeout=60) as resp:
        pdf = resp.read()
    print("pdf bytes:", len(pdf))
    ok = ok and pdf[:4] == b"%PDF"
    print("OK" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"))

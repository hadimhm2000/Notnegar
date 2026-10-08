"""Turn test output into GitHub annotations (readable without downloading logs)."""
import json
import sys
from pathlib import Path


def enc(s: str) -> str:
    return s.replace("%", "%25").replace("\r", "").replace("\n", "%0A")


def main(log_path: str, out_dir: str, tag: str):
    log = Path(log_path).read_text(errors="replace") if Path(log_path).exists() else ""
    if "failed" in log.lower() or "error" in log.lower():
        tail = log[-6000:]
        print(f"::error title={tag} pytest::{enc(tail)}")
    for a in sorted(Path(out_dir).glob("**/job/analysis.json")):
        r = json.loads(a.read_text(encoding="utf-8"))
        an = r["analysis"]
        layers = {k: f"{v['count']} notes/{v['method']}" for k, v in r["layers"].items()}
        msg = (f"{a.parent.parent.name}: scale={an['scale_id']} tonic={an['tonic']} p={an['confidence']} "
               f"quarter={an['quarter']} tempo={an['tempo']} sep={r['separation']} layers={layers} "
               f"parts={[p['id'] + ':' + str(p['events']) for p in r['parts']]} pdf={'pdf' in r['files']}")
        print(f"::notice title={tag} result::{enc(msg)}")
        lylog = a.parent / "lilypond.log"
        if lylog.exists():
            warn = [l for l in lylog.read_text(errors="replace").splitlines() if "warning" in l or "error" in l]
            if warn:
                print(f"::warning title={tag} lilypond {a.parent.parent.name}::{enc(chr(10).join(warn[:25]))}")


if __name__ == "__main__":
    main(*sys.argv[1:4])

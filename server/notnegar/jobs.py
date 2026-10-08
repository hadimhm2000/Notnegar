"""A small persistent job queue: one folder per job, processed by a background worker pool."""
from __future__ import annotations

import json
import logging
import os
import re
import secrets
import shutil
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import mailer, pipeline

log = logging.getLogger(__name__)
ID_RE = re.compile(r"^[A-Za-z0-9_-]{8,32}$")


class JobManager:
    def __init__(self, data_dir: str | Path, workers: int = 1, ttl_hours: float = 72, public_url: str = ""):
        self.root = Path(data_dir) / "jobs"
        self.root.mkdir(parents=True, exist_ok=True)
        self.pool = ThreadPoolExecutor(max_workers=max(1, workers), thread_name_prefix="notnegar")
        self.lock = threading.Lock()
        self.ttl = ttl_hours * 3600
        self.public_url = public_url.rstrip("/")
        self.queue: list[str] = []
        for d in self.root.iterdir():                      # jobs interrupted by a restart
            st = self._read(d.name)
            if st and st.get("state") in ("queued", "running"):
                self._write(d.name, state="error", error="سرور در حین پردازش دوباره راه‌اندازی شد. فایل را دوباره بفرستید.")
        threading.Thread(target=self._janitor, daemon=True).start()

    # --- storage -------------------------------------------------------------------------
    def dir(self, job_id: str) -> Path:
        if not ID_RE.match(job_id or ""):
            raise KeyError(job_id)
        return self.root / job_id

    def _read(self, job_id: str) -> dict | None:
        p = self.root / job_id / "status.json"
        for attempt in range(5):                  # Windows: the file can be briefly locked by a writer
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except FileNotFoundError:
                return None
            except (PermissionError, json.JSONDecodeError):
                time.sleep(0.05 * (attempt + 1))
            except Exception:
                return None
        return None

    def _write(self, job_id: str, **upd) -> dict:
        with self.lock:
            st = self._read(job_id) or {}
            st.update(upd, updated=time.time())
            p = self.root / job_id / "status.json"
            tmp = p.with_suffix(".tmp")
            tmp.write_text(json.dumps(st, ensure_ascii=False), encoding="utf-8")
            for attempt in range(10):
                try:
                    tmp.replace(p)
                    break
                except PermissionError:           # Windows: a reader holds the file open
                    time.sleep(0.05 * (attempt + 1))
            return st

    def status(self, job_id: str) -> dict:
        st = self._read(job_id) if ID_RE.match(job_id or "") else None
        if st is None:
            raise KeyError(job_id)
        if st.get("state") == "queued" and job_id in self.queue:
            st["position"] = self.queue.index(job_id) + 1
        if st.get("state") == "done":
            try:
                st["result"] = json.loads((self.dir(job_id) / "analysis.json").read_text(encoding="utf-8"))
            except Exception:
                pass
        return st

    # --- lifecycle -----------------------------------------------------------------------
    def create(self, filename: str) -> tuple[str, Path]:
        job_id = secrets.token_urlsafe(12).replace("-", "x").replace("_", "y")
        d = self.root / job_id
        d.mkdir(parents=True)
        ext = Path(filename).suffix.lower()[:6] or ".audio"
        return job_id, d / f"input{ext}"

    def submit(self, job_id: str, input_path: Path, opts: dict) -> None:
        self._write(job_id, id=job_id, state="queued", progress=0, stage="در صف", created=time.time(),
                    options=opts, filename=opts.get("filename", ""))
        with self.lock:
            self.queue.append(job_id)
        self.pool.submit(self._run, job_id, input_path, opts)

    def queue_length(self) -> int:
        return len(self.queue)

    def _run(self, job_id: str, input_path: Path, opts: dict) -> None:
        with self.lock:
            if job_id in self.queue:
                self.queue.remove(job_id)
        self._write(job_id, state="running", progress=0.01, stage="شروع")
        t0 = time.time()
        try:
            def cb(frac, stage):
                self._write(job_id, progress=round(frac, 3), stage=stage)
            result = pipeline.run(input_path, self.dir(job_id), opts, cb)
            self._write(job_id, state="done", progress=1, stage="تمام شد", elapsed=round(time.time() - t0, 1))
            if opts.get("email") and mailer.configured():
                try:
                    mailer.send(opts["email"], result, self.dir(job_id), self.link(job_id))
                    self._write(job_id, emailed=opts["email"])
                except Exception as e:
                    log.exception("email failed")
                    self._write(job_id, email_error=str(e)[:300])
        except Exception as e:
            log.exception("job %s failed", job_id)
            self._write(job_id, state="error", error=_friendly(e))
        finally:
            if os.environ.get("NOTNEGAR_KEEP_INPUT") != "1":
                try:
                    input_path.unlink()
                except OSError:
                    pass

    def rerender(self, job_id: str, opts: dict) -> dict:
        st = self.status(job_id)
        if st.get("state") != "done":
            raise ValueError("job not finished")
        merged = {**st.get("options", {}), **opts}
        result = pipeline.render(self.dir(job_id), merged)
        self._write(job_id, options=merged)
        return result

    def link(self, job_id: str) -> str:
        return f"{self.public_url}/#{job_id}" if self.public_url else ""

    def _janitor(self) -> None:
        while True:
            time.sleep(1800)
            cutoff = time.time() - self.ttl
            for d in list(self.root.iterdir()):
                st = self._read(d.name) or {}
                if st.get("state") in ("queued", "running"):
                    continue
                if st.get("updated", d.stat().st_mtime) < cutoff:
                    shutil.rmtree(d, ignore_errors=True)


def _friendly(e: Exception) -> str:
    s = str(e)
    if "empty audio" in s or "Invalid data" in s or "ffmpeg" in s.lower():
        return "فایل صوتی خوانده نشد. یک فایل MP3، WAV یا FLAC سالم بفرستید."
    if isinstance(e, MemoryError) or "out of memory" in s.lower():
        return "حافظه‌ی سرور برای این فایل کافی نبود. فایل کوتاه‌تری بفرستید یا حافظه‌ی سرور را بیشتر کنید."
    return "پردازش با خطا متوقف شد: " + s[:200]

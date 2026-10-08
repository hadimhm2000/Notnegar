"""HTTP API and web page.  Run with:  uvicorn notnegar.app:app --host 0.0.0.0 --port 8000"""
from __future__ import annotations

import asyncio
import base64
import io
import logging
import os
import re
import secrets
import zipfile
from pathlib import Path

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, Response, StreamingResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from . import __version__, lilypond, mailer
from .jobs import JobManager
from .separate import demucs_available
from .transcribe import basic_pitch_available, crepe_available

logging.basicConfig(level=os.environ.get("NOTNEGAR_LOG", "INFO"),
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("notnegar")

STATIC = Path(__file__).resolve().parent.parent / "static"
DATA = Path(os.environ.get("NOTNEGAR_DATA", Path(__file__).resolve().parent.parent / "data"))
MAX_MB = float(os.environ.get("NOTNEGAR_MAX_UPLOAD_MB", "80"))
MAX_QUEUE = int(os.environ.get("NOTNEGAR_MAX_QUEUE", "20"))
ALLOWED = {".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac", ".opus", ".wma", ".aif", ".aiff", ".webm", ".mp4"}
FILE_RE = re.compile(r"^(score\.(pdf|musicxml|mid|ly)|analysis\.json|lilypond\.log|stems/[a-z_]+\.(mp3|wav))$")

jobs = JobManager(DATA, workers=int(os.environ.get("NOTNEGAR_WORKERS", "1")),
                  ttl_hours=float(os.environ.get("NOTNEGAR_TTL_HOURS", "72")),
                  public_url=os.environ.get("NOTNEGAR_PUBLIC_URL", ""))


class BasicAuth(BaseHTTPMiddleware):
    """Optional password for a private server: NOTNEGAR_BASIC_AUTH=user:password"""

    def __init__(self, app, creds: str):
        super().__init__(app)
        self.expected = "Basic " + base64.b64encode(creds.encode()).decode()

    async def dispatch(self, request, call_next):
        if request.url.path == "/api/health" or secrets.compare_digest(request.headers.get("authorization", ""), self.expected):
            return await call_next(request)
        return Response("Authentication required", 401, {"WWW-Authenticate": 'Basic realm="notnegar"'})


def err(msg: str, code: int = 400) -> JSONResponse:
    return JSONResponse({"error": msg}, status_code=code)


async def index(request: Request):
    return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-cache"})


async def health(request: Request):
    return JSONResponse({
        "ok": True, "version": __version__,
        "demucs": demucs_available(), "crepe": crepe_available(), "basic_pitch": basic_pitch_available(),
        "lilypond": lilypond.lily_available(), "email": mailer.configured(),
        "queue": jobs.queue_length(), "max_upload_mb": MAX_MB,
    })


def _bool(v, default=True) -> bool:
    if v is None:
        return default
    return str(v).lower() in ("1", "true", "on", "yes")


async def create_job(request: Request):
    if jobs.queue_length() >= MAX_QUEUE:
        return err("صف پردازش پر است. چند دقیقه‌ی دیگر دوباره امتحان کنید.", 503)
    form = await request.form(max_part_size=int(MAX_MB * 1024 * 1024) + 1024)
    up = form.get("file")
    if up is None or not getattr(up, "filename", ""):
        return err("فایل صوتی انتخاب نشده است.")
    ext = Path(up.filename).suffix.lower()
    if ext not in ALLOWED:
        return err("این نوع فایل پشتیبانی نمی‌شود. MP3، WAV، FLAC، OGG یا M4A بفرستید.")
    job_id, dest = jobs.create(up.filename)
    size = 0
    with open(dest, "wb") as f:
        while chunk := await up.read(1 << 20):
            size += len(chunk)
            if size > MAX_MB * 1024 * 1024:
                f.close()
                dest.unlink(missing_ok=True)
                return err(f"حجم فایل بیشتر از {int(MAX_MB)} مگابایت است.", 413)
            f.write(chunk)
    email = (form.get("email") or "").strip()
    if email and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        email = ""
    opts = {
        "filename": up.filename,
        "title": (form.get("title") or "").strip()[:120] or Path(up.filename).stem.replace("_", " ")[:120],
        "artist": (form.get("artist") or "").strip()[:120],
        "instrument": form.get("instrument") or "santur",
        "detail": form.get("detail") if form.get("detail") in ("simple", "normal", "detailed") else "normal",
        "names": _bool(form.get("names")),
        "tuning": _bool(form.get("tuning")),
        "email": email,
    }
    jobs.submit(job_id, dest, opts)
    return JSONResponse({"id": job_id}, status_code=201)


async def job_status(request: Request):
    try:
        st = jobs.status(request.path_params["job_id"])
    except KeyError:
        return err("این کار پیدا نشد یا حذف شده است.", 404)
    st.get("options", {}).pop("email", None)
    return JSONResponse(st)


async def rerender(request: Request):
    job_id = request.path_params["job_id"]
    try:
        body = await request.json()
    except Exception:
        body = {}
    allowed = {k: body[k] for k in ("scale", "tonic", "layers", "names", "tuning", "instrument", "title", "artist") if k in body}
    try:
        result = await asyncio.get_running_loop().run_in_executor(None, jobs.rerender, job_id, allowed)
    except KeyError:
        return err("این کار پیدا نشد.", 404)
    except ValueError:
        return err("پردازش این آهنگ هنوز تمام نشده است.", 409)
    return JSONResponse(result)


async def job_file(request: Request):
    job_id, name = request.path_params["job_id"], request.path_params["name"]
    if not FILE_RE.match(name):
        return err("فایل نامعتبر", 404)
    try:
        p = jobs.dir(job_id) / name
    except KeyError:
        return err("پیدا نشد", 404)
    if not p.exists():
        return err("این فایل ساخته نشده است.", 404)
    st = jobs.status(job_id)
    title = re.sub(r'[\\/:*?"<>|]+', " ", (st.get("options") or {}).get("title") or "notnegar").strip() or "notnegar"
    dl = request.query_params.get("download")
    fname = f"{title} - {Path(name).stem}{p.suffix}" if name.startswith("stems/") else f"{title}{p.suffix}"
    media = {".pdf": "application/pdf", ".mid": "audio/midi", ".musicxml": "application/vnd.recordare.musicxml+xml",
             ".mp3": "audio/mpeg", ".wav": "audio/wav", ".ly": "text/plain; charset=utf-8",
             ".log": "text/plain; charset=utf-8", ".json": "application/json"}.get(p.suffix, "application/octet-stream")
    return FileResponse(p, media_type=media, filename=fname if dl else None,
                        content_disposition_type="attachment" if dl else "inline")


async def stems_zip(request: Request):
    job_id = request.path_params["job_id"]
    try:
        d = jobs.dir(job_id) / "stems"
        st = jobs.status(job_id)
    except KeyError:
        return err("پیدا نشد", 404)
    if not d.exists():
        return err("لایه‌ای ذخیره نشده است.", 404)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as z:
        for f in sorted(d.iterdir()):
            z.write(f, f.name)
    title = re.sub(r'[\\/:*?"<>|]+', " ", (st.get("options") or {}).get("title") or "notnegar").strip()
    from urllib.parse import quote
    return Response(buf.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(title + ' - stems.zip')}"})


async def send_email(request: Request):
    job_id = request.path_params["job_id"]
    if not mailer.configured():
        return err("ارسال ایمیل روی این سرور تنظیم نشده است.", 501)
    body = await request.json()
    to = (body.get("email") or "").strip()
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", to):
        return err("نشانی ایمیل درست نیست.")
    try:
        st = jobs.status(job_id)
    except KeyError:
        return err("پیدا نشد", 404)
    if st.get("state") != "done":
        return err("پردازش هنوز تمام نشده است.", 409)
    try:
        await asyncio.get_running_loop().run_in_executor(None, mailer.send, to, st["result"], jobs.dir(job_id), jobs.link(job_id))
    except Exception as e:
        log.exception("email failed")
        return err("ارسال ایمیل ناموفق بود: " + str(e)[:200], 502)
    return JSONResponse({"sent": True})


middleware = []
if os.environ.get("NOTNEGAR_BASIC_AUTH"):
    middleware.append(Middleware(BasicAuth, creds=os.environ["NOTNEGAR_BASIC_AUTH"]))

app = Starlette(
    routes=[
        Route("/", index),
        Route("/api/health", health),
        Route("/api/jobs", create_job, methods=["POST"]),
        Route("/api/jobs/{job_id}", job_status),
        Route("/api/jobs/{job_id}/render", rerender, methods=["POST"]),
        Route("/api/jobs/{job_id}/email", send_email, methods=["POST"]),
        Route("/api/jobs/{job_id}/stems.zip", stems_zip),
        Route("/api/jobs/{job_id}/file/{name:path}", job_file),
        Mount("/static", StaticFiles(directory=str(STATIC)), name="static"),
    ],
    middleware=middleware,
)

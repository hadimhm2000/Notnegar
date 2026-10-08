"""Send the finished score by email (SMTP settings come from environment variables)."""
from __future__ import annotations

import os
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path


def configured() -> bool:
    return bool(os.environ.get("NOTNEGAR_SMTP_HOST") and os.environ.get("NOTNEGAR_SMTP_FROM"))


def send(to: str, result: dict, job_dir: str | Path, public_url: str = "") -> None:
    host = os.environ["NOTNEGAR_SMTP_HOST"]
    port = int(os.environ.get("NOTNEGAR_SMTP_PORT", "587"))
    user = os.environ.get("NOTNEGAR_SMTP_USER", "")
    pwd = os.environ.get("NOTNEGAR_SMTP_PASSWORD", "")
    sender = os.environ["NOTNEGAR_SMTP_FROM"]
    mode = os.environ.get("NOTNEGAR_SMTP_SECURITY", "starttls")    # starttls | ssl | none

    a = result["analysis"]
    msg = EmailMessage()
    msg["Subject"] = f"نت‌نگار: {result['title']} — {a['scale_fa']} {a['tonic_fa']}"
    msg["From"] = sender
    msg["To"] = to
    lines = [
        f"نتیجه‌ی تحلیل «{result['title']}»",
        "",
        f"دستگاه یا گام: {a['scale_fa']} ({a['confidence_fa']})",
        f"نت پایه: {a['tonic_fa']}",
        f"کوک مرجع: {a['tuning_fa']}",
        f"ربع‌پرده: {'دارد' if a['quarter'] else 'ندارد'}",
        f"تمپو و وزن: {a['tempo_fa']}",
        f"لایه‌ها: {a['layers_fa']}",
        "",
        "پارتیتور PDF و فایل MusicXML پیوست شده‌اند.",
    ]
    if public_url:
        lines += ["", f"مشاهده‌ی کامل و دانلود لایه‌ها: {public_url}"]
    msg.set_content("\n".join(lines))
    job = Path(job_dir)
    for key, mime in (("pdf", ("application", "pdf")), ("musicxml", ("application", "vnd.recordare.musicxml+xml"))):
        f = result["files"].get(key)
        if f and (job / f).exists():
            msg.add_attachment((job / f).read_bytes(), maintype=mime[0], subtype=mime[1],
                               filename=f"{result['title']}.{ 'pdf' if key == 'pdf' else 'musicxml'}")
    if mode == "ssl":
        with smtplib.SMTP_SSL(host, port, context=ssl.create_default_context(), timeout=30) as s:
            if user:
                s.login(user, pwd)
            s.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=30) as s:
            if mode == "starttls":
                s.starttls(context=ssl.create_default_context())
            if user:
                s.login(user, pwd)
            s.send_message(msg)

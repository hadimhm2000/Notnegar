"""Notnegar server: separation, analysis and transcription of Persian music."""
import os as _os
from pathlib import Path as _Path

__version__ = "1.1.0"


def _load_env_file() -> None:
    """Read server/.env (KEY=VALUE lines) without overriding variables already set.

    Docker passes .env itself; this makes the same file work for Windows and systemd-less installs.
    """
    p = _Path(_os.environ.get("NOTNEGAR_ENV_FILE", _Path(__file__).resolve().parent.parent / ".env"))
    try:
        lines = p.read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        return
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k and k not in _os.environ:
            _os.environ[k] = v


_load_env_file()

"""Audio I/O through ffmpeg (decoding anything) and plain WAV writing."""
from __future__ import annotations

import subprocess
import wave
from pathlib import Path

import numpy as np

SR = 44100


def decode(path: str | Path, sr: int = SR, max_seconds: float | None = None) -> tuple[np.ndarray, int]:
    """Decode any audio file to float32 stereo (2, N) at ``sr``."""
    cmd = ["ffmpeg", "-v", "error", "-nostdin", "-i", str(path)]
    if max_seconds:
        cmd += ["-t", str(max_seconds)]
    cmd += ["-f", "f32le", "-ac", "2", "-ar", str(sr), "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    x = np.frombuffer(raw, np.float32).reshape(-1, 2).T.copy()
    if x.shape[1] == 0:
        raise ValueError("empty audio")
    return x, sr


def duration(path: str | Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, encoding="utf-8", errors="replace")
    try:
        return float(out.stdout.strip())
    except ValueError:
        return 0.0


def write_wav(path: str | Path, x: np.ndarray, sr: int = SR) -> None:
    """16-bit PCM WAV; x is (channels, N) or (N,)."""
    x = np.atleast_2d(x)
    pcm = (np.clip(x, -1, 1) * 32767).astype("<i2").T.copy()
    with wave.open(str(path), "wb") as w:
        w.setnchannels(pcm.shape[1])
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())


def write_mp3(wav_path: str | Path, mp3_path: str | Path, bitrate: str = "192k") -> bool:
    r = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-y", "-i", str(wav_path), "-b:a", bitrate, str(mp3_path)],
                       capture_output=True)
    return r.returncode == 0


def rms_db(x: np.ndarray) -> float:
    v = float(np.sqrt(np.mean(np.square(x)))) if x.size else 0.0
    return 20 * np.log10(v + 1e-9)

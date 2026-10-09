"""Standard MIDI file export; quarter-tones are played with pitch bend (±2 semitone range)."""
from __future__ import annotations

import struct

from .score import Score

TPQ = 480


def _vlq(n: int) -> bytes:
    out = [n & 0x7F]
    n >>= 7
    while n:
        out.append((n & 0x7F) | 0x80)
        n >>= 7
    return bytes(reversed(out))


def _track(events: list[tuple[int, bytes]]) -> bytes:
    events.sort(key=lambda e: (e[0], e[1][0] & 0xF0 == 0x90))   # offs before ons at the same tick
    data, last = bytearray(), 0
    for tick, msg in events:
        data += _vlq(max(0, tick - last)) + msg
        last = tick
    data += b"\x00\xff\x2f\x00"
    return b"MTrk" + struct.pack(">I", len(data)) + bytes(data)


def build(sc: Score) -> bytes:
    tracks = []
    tempo = int(60_000_000 / max(20, sc.bpm))
    meta = [(0, b"\xff\x51\x03" + tempo.to_bytes(3, "big")),
            (0, b"\xff\x58\x04" + bytes([sc.time_sig[0], {4: 2, 8: 3, 2: 1}.get(sc.time_sig[1], 2), 24, 8]))]
    tracks.append(_track(meta))
    ch = 0
    for p in sc.parts:
        is_drum = p.kind == "drums"
        c = 9 if is_drum else ch
        if not is_drum:
            ch = ch + 1 if ch + 1 != 9 else 10
        ev = [(0, b"\xff\x03" + _vlq(len(p.name_en.encode())) + p.name_en.encode())]
        if not is_drum:
            ev.append((0, bytes([0xC0 | c, p.midi_program & 0x7F])))
            ev.append((0, bytes([0xB0 | c, 101, 0]))); ev.append((0, bytes([0xB0 | c, 100, 0])))
            ev.append((0, bytes([0xB0 | c, 6, 2]))); ev.append((0, bytes([0xB0 | c, 38, 0])))   # bend range ±2
        for e in p.events:
            if e.is_rest:
                continue
            on, off = int(e.start * TPQ), int((e.start + e.dur) * TPQ) - 10
            vel = max(1, min(127, int(e.velocity * 110)))
            if is_drum:
                ev.append((on, bytes([0x99, 38, vel]))); ev.append((on + TPQ // 8, bytes([0x89, 38, 0])))
                continue
            bend = 0
            for qt in e.qts:
                if qt % 2:
                    bend = -2048                    # koron/sori: lower note + quarter-tone bend
            ev.append((max(0, on - 1), bytes([0xE0 | c, (8192 + bend) & 0x7F, ((8192 + bend) >> 7) & 0x7F])))
            for qt in e.qts:
                key = (qt + 1) // 2 if qt % 2 else qt // 2
                key = max(0, min(127, key))
                ev.append((on, bytes([0x90 | c, key, vel])))
                ev.append((max(on + 1, off), bytes([0x80 | c, key, 0])))
        tracks.append(_track(ev))
    header = b"MThd" + struct.pack(">IHHH", 6, 1, len(tracks), TPQ)
    return header + b"".join(tracks)

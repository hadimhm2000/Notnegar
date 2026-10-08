"""Persian music theory: 24 quarter-tones per octave, dastgah templates, spelling and names.

Pitch convention used across the package: ``qt = 2 * midi`` (quarter-tone index).
C4 = midi 60 = qt 120, and ``qt % 24`` is the pitch class with C = 0.
"""
from __future__ import annotations

from dataclasses import dataclass

LETTERS = "CDEFGAB"
NAT = {"C": 0, "D": 4, "E": 8, "F": 10, "G": 14, "A": 18, "B": 22}
FA_LETTER = {"C": "دو", "D": "ر", "E": "می", "F": "فا", "G": "سل", "A": "لا", "B": "سی"}
FA_ACC = {"": "", "b": " بمل", "#": " دیز", "k": " کرن", "s": " سری"}
SHORT_ACC = {"": "", "b": "♭", "#": "♯", "k": "ک", "s": "س"}
EN_ACC = {"": "", "b": "b", "#": "#", "k": " koron", "s": " sori"}
ACC_ALTER = {"": 0.0, "b": -1.0, "#": 1.0, "k": -0.5, "s": 0.5}   # in semitones
ACC_OF_DIFF = {-2: "b", -1: "k", 0: "", 1: "s", 2: "#"}            # diff in quarter-tones

# default spelling of each pitch class: (letter, accidental, octave bump)
SPELL = [("C", "", 0), ("C", "s", 0), ("C", "#", 0), ("D", "k", 0), ("D", "", 0), ("D", "s", 0),
         ("E", "b", 0), ("E", "k", 0), ("E", "", 0), ("F", "k", 0), ("F", "", 0), ("F", "s", 0),
         ("F", "#", 0), ("G", "k", 0), ("G", "", 0), ("G", "s", 0), ("A", "b", 0), ("A", "k", 0),
         ("A", "", 0), ("A", "s", 0), ("B", "b", 0), ("B", "k", 0), ("B", "", 0), ("C", "k", 1)]

INTERVAL_FA = {2: "نیم پرده", 3: "سه‌ربع پرده", 4: "یک پرده", 5: "پنج‌ربع پرده", 6: "یک‌ونیم پرده"}


@dataclass(frozen=True)
class Scale:
    id: str
    name: str
    name_en: str
    deg: tuple
    note: str = ""

    @property
    def needs_quarter(self) -> bool:
        return any(d % 2 for d in self.deg)


SCALES = [
    Scale("shur", "شور", "Shur", (0, 3, 6, 10, 14, 16, 20),
          "آوازهای ابوعطا، دشتی، بیات ترک و افشاری هم از همین مجموعه‌ی نت‌ها ساخته شده‌اند؛ تفاوتشان در شاهد، ایست و گوشه‌هاست."),
    Scale("mahur", "ماهور", "Mahur", (0, 4, 8, 10, 14, 18, 22),
          "ماهور همان گام ماژور غربی است. راست‌پنجگاه هم همین نت‌ها را دارد و تفاوتش در شاهد و مسیر گوشه‌هاست."),
    Scale("minor", "مینور", "Minor", (0, 4, 6, 10, 14, 16, 20),
          "گام مینور غربی، که در موسیقی پاپ ایرانی رایج است و ربع‌پرده ندارد."),
    Scale("hminor", "مینور هارمونیک", "Harmonic minor", (0, 4, 6, 10, 14, 16, 22),
          "در تنظیم‌های پاپ، بیات اصفهان اغلب به همین شکل و بدون ربع‌پرده اجرا می‌شود."),
    Scale("homayun", "همایون", "Homayun", (0, 3, 8, 10, 14, 16, 20),
          "بیات اصفهان از متعلقات همایون است و نت‌های مشترک زیادی با آن دارد."),
    Scale("esfahan", "بیات اصفهان", "Bayat-e Esfahan", (0, 4, 6, 10, 14, 17, 22),
          "بیات اصفهان از متعلقات همایون است و نت‌های مشترک زیادی با آن دارد."),
    Scale("segah", "سه‌گاه", "Segah", (0, 3, 7, 11, 14, 17, 21)),
    Scale("chahargah", "چهارگاه", "Chahargah", (0, 3, 8, 10, 14, 17, 22)),
    Scale("nava", "نوا", "Nava", (0, 4, 6, 10, 14, 17, 20),
          "نوا همان نت‌های شور را از درجه‌ی دیگری دارد؛ نت پایه تعیین‌کننده است."),
]
SCALE_BY_ID = {s.id: s for s in SCALES}


def default_spell(qt: int):
    """(letter, acc, octave) without key context."""
    oct_ = qt // 24 - 1
    letter, acc, bump = SPELL[qt % 24]
    return letter, acc, oct_ + bump


def pc_name_default(pc: int) -> str:
    letter, acc, _ = SPELL[pc % 24]
    return FA_LETTER[letter] + FA_ACC[acc]


class Speller:
    """Spells pitches in the context of a scale: scale degrees get consecutive letters."""

    def __init__(self, scale: Scale, tonic: int):
        self.scale, self.tonic = scale, tonic % 24
        self.map = {}
        t_letter = SPELL[self.tonic][0]
        li = LETTERS.index(t_letter)
        for i, k in enumerate(scale.deg):
            pc = (self.tonic + k) % 24
            letter = LETTERS[(li + i) % 7]
            diff = ((pc - NAT[letter] + 36) % 24) - 12
            if diff in ACC_OF_DIFF:
                self.map[pc] = (letter, ACC_OF_DIFF[diff], diff)

    def spell(self, qt: int):
        """(letter, acc, octave) for an absolute quarter-tone index."""
        pc = qt % 24
        if pc in self.map:
            letter, acc, diff = self.map[pc]
            oct_ = (qt - diff - NAT[letter]) // 24 - 1
            return letter, acc, oct_
        return default_spell(qt)

    def name(self, pc: int) -> str:
        letter, acc, _ = self.spell(120 + pc % 24)
        return FA_LETTER[letter] + FA_ACC[acc]

    def name_en(self, pc: int) -> str:
        letter, acc, _ = self.spell(120 + pc % 24)
        return letter + EN_ACC[acc]

    def short(self, qt: int) -> str:
        letter, acc, _ = self.spell(qt)
        return FA_LETTER[letter] + SHORT_ACC[acc]

    def key_signature(self) -> dict:
        """letter -> accidental for the scale's altered degrees."""
        return {letter: acc for letter, acc, _ in self.map.values() if acc}


def tuning_table(scale: Scale, tonic: int, offset_cents: float) -> list[dict]:
    """One octave of the scale from the tonic (octave 4), with Hz and deviation from 12-TET."""
    sp = Speller(scale, tonic)
    degs = list(scale.deg) + [24]
    rows = []
    for i, k in enumerate(degs):
        qt = 120 + (tonic % 24) + k
        cents = (qt - 120) * 50 + offset_cents          # relative to C4 at A=440
        hz = 261.6256 * 2 ** (cents / 1200)
        dev = cents - round(cents / 100) * 100
        rows.append({
            "degree": i + 1,
            "name": sp.name((tonic + k) % 24),
            "name_en": sp.name_en((tonic + k) % 24),
            "hz": round(hz, 2),
            "step": INTERVAL_FA.get(k - degs[i - 1], "") if i else "—",
            "dev_cents": round(dev),
            "quarter": (tonic + k) % 2 == 1,
        })
    return rows

\version "2.24.0"
\include "persian.ly"
#(set-global-staff-size 18)
\paper {
  #(set-paper-size "a4")
  top-margin = 12\mm bottom-margin = 12\mm left-margin = 14\mm right-margin = 14\mm
  ragged-bottom = ##t
  ragged-last-bottom = ##t
  system-system-spacing.basic-distance = #14
  print-page-number = ##t
  oddFooterMarkup = \markup \fill-line { \override #'(font-name . "Vazirmatn, Noto Naskh Arabic, Noto Sans Arabic, Tahoma, DejaVu Sans") \fontsize #-3 "آزمون segah  ·  نت‌نگار" \fontsize #-3 \fromproperty #'page:page-number-string }
  evenFooterMarkup = \oddFooterMarkup
}
\header { tagline = ##f }

global = { \time 4/4 \tempo 4 = 96 \set Staff.keyAlterations = #`((2 . ,KORON) (6 . ,KORON)) }

\markup \override #'(font-name . "Vazirmatn, Noto Naskh Arabic, Noto Sans Arabic, Tahoma, DejaVu Sans") \column {
  \fill-line { \fontsize #6 \bold "آزمون segah" }
  \vspace #0.3
  \fill-line { \fontsize #-1 "" \fontsize #1 "نت‌نگار" }
  \fill-line { "" \fontsize #-2 "نت‌نگار · سه‌گاه می کرن" }
}

\score {
  <<
    \new Staff = "vocals" \with { instrumentName = \markup \override #'(font-name . "Vazirmatn, Noto Naskh Arabic, Noto Sans Arabic, Tahoma, DejaVu Sans") "آواز" shortInstrumentName = \markup \override #'(font-name . "Vazirmatn, Noto Naskh Arabic, Noto Sans Arabic, Tahoma, DejaVu Sans") "آواز" }
    \new Voice = "vvocals" { \global \clef "treble" \compressMMRests {
      r8 ek'4 f'8 g'8 f'4 ek'4 r8 f'8 g'4 a'8 g'8 f'4 ek'2 r4 g'4 a'4
      bk'8 a'8 g'4 f'8 ek'8 f'4 ek'2 r8 r8 ek'4 f'8 g'8 f'4 ek'4 r8 f'8
      g'4 a'8 g'8 f'4 ek'2 r4 g'4 a'4 bk'8 a'8 g'4 f'8 ek'8 f'4 ek'2 r8
      R1
    } }
    \new Lyrics \with { \override LyricText.font-name = "Vazirmatn, Noto Naskh Arabic, Noto Sans Arabic, Tahoma, DejaVu Sans" \override LyricText.font-size = #-2 } \lyricsto "vvocals" { "میک" "فا" "سل" "فا" "میک" "فا" "سل" "لا" "سل" "فا" "میک" "سل" "لا" "سیک" "لا" "سل" "فا" "میک" "فا" "میک" "میک" "فا" "سل" "فا" "میک" "فا" "سل" "لا" "سل" "فا" "میک" "سل" "لا" "سیک" "لا" "سل" "فا" "میک" "فا" "میک" }
  \new PianoStaff \with { instrumentName = \markup \override #'(font-name . "Vazirmatn, Noto Naskh Arabic, Noto Sans Arabic, Tahoma, DejaVu Sans") "پیانو و کیبورد" shortInstrumentName = \markup \override #'(font-name . "Vazirmatn, Noto Naskh Arabic, Noto Sans Arabic, Tahoma, DejaVu Sans") "پیانو" } <<
    \new Staff = "piano_rh" \with { }
    \new Voice = "vpianorh" { \global \clef "treble" \compressMMRests {
      r2 r8 <g' b''>4~ <g' b''>16 r16 r16 g'16 r2 <a' cs'''>4 r8 r2 r8 <g' b''>4. r2 r8 <a' cs'''>4
      r8 r2 r8 <g' b''>4~ <g' b''>16 r16 r2 r8 <a' cs'''>4 r8 r2 r8 <g' b''>4~ <g' b''>16 r16 r16
      g'16 r2 <a' cs'''>4 r8 r2 r8 <g' b''>4~ <g' b''>16 r16 r2 r8 <a' cs'''>4 r8 R1
    } }
    \new Staff = "piano_lh" \with { }
    \new Voice = "vpianolh" { \global \clef "bass" \compressMMRests {
      r8 <ek bk>4.~ <ek bk>16 r16 <bk, g bk>2 <ek bk>8. ek16 ek8. r16 <d a>2 <ek bk>8 ek4~ ek16 r16 <bk, g bk>2 <ek bk>4.~
      <ek bk>16 r16 <d a>2 <ek bk>2 <bk, g bk>4.~ <bk, g bk>16 r16 <ek bk>4.~ <ek bk>16 r16 <d a>2 <ek bk>4.~ <ek bk>16 r16 <bk, g bk>4.~ <bk, g bk>16
      r16 <ek bk>16 ek8 ek4 r16 <d a>2 <ek bk>4.~ <ek bk>16 r16 <bk, g bk>4.~ <bk, g bk>16 r16 <ek bk>4.~ <ek bk>16 r16 <d a>2
      r2. r8
    } }
  >>
  \new Staff = "bass" \with { instrumentName = \markup \override #'(font-name . "Vazirmatn, Noto Naskh Arabic, Noto Sans Arabic, Tahoma, DejaVu Sans") "بیس" shortInstrumentName = \markup \override #'(font-name . "Vazirmatn, Noto Naskh Arabic, Noto Sans Arabic, Tahoma, DejaVu Sans") "بیس" }
    \new Voice = "vbass" { \global \clef "bass" \compressMMRests {
      r8 ek,4~ ek,16 r8. bk,,4~ bk,,16 r16 r8 ek,4~ ek,16 r8. d,4~ d,16 r16 r8 ek,4~
      ek,16 r8. bk,,4~ bk,,16 r16 r8 ek,4~ ek,16 r8. d,4~ d,16 r16 r8 ek,4~ ek,16 r8.
      bk,,4~ bk,,16 r16 r8 ek,4~ ek,16 r8. d,4~ d,16 r16 r8 ek,4~ ek,16 r8. bk,,4 r8
      r8 ek,4~ ek,16 r8. d,4~ d,16 r16 r8 ek,4~ ek,16 r8. bk,,4~ bk,,16 r16 r8 ek,4~
      ek,16 r8. d,4~ d,16 r16 R1
    } }
  \new RhythmicStaff = "drums" \with { instrumentName = \markup \override #'(font-name . "Vazirmatn, Noto Naskh Arabic, Noto Sans Arabic, Tahoma, DejaVu Sans") "ضرب و درامز" shortInstrumentName = \markup \override #'(font-name . "Vazirmatn, Noto Naskh Arabic, Noto Sans Arabic, Tahoma, DejaVu Sans") "ضرب" }
    \new Voice = "vdrums" { \global \compressMMRests {
      r8 c4 c4 c4 c4 c4 c4 c4 c4 c4 c4 c4 c4 c4 c4 c4
      c4 c4 c4 c4 c4 c4 c4 c4 c4 c4 c4 c4 c4 c4 c4 c4
      c4 c4 c4 c4 c4 c4 c4 c8. c16 c4 r2. r8
    } }
  >>
  \layout {
    \context { \Score \override BarNumber.font-size = #-2 }
    \context { \Voice
      \remove Note_heads_engraver \consists Completion_heads_engraver
      \remove Rest_engraver \consists Completion_rest_engraver
    }
  }
}

\pageBreak
\markup \override #'(font-name . "Vazirmatn, Noto Naskh Arabic, Noto Sans Arabic, Tahoma, DejaVu Sans") \column {
  \fill-line { "" \fontsize #6 \bold "آزمون segah" }
  \vspace #0.4 \fill-line { "" \fontsize #1 "نت‌نگار · سه‌گاه می کرن" }
  \vspace #1 \draw-hline \vspace #0.6
  \fill-line { "" \line { "سه‌گاه  (اطمینان ۱۰۰٪)" \hspace #1 \bold "دستگاه یا گام:" } }
  \fill-line { "" \line { "می کرن" \hspace #1 \bold "نت پایه:" } }
  \fill-line { "" \line { "نوا سل (۰٪)" \hspace #1 \bold "گزینه‌ی بعدی:" } }
  \fill-line { "" \line { "لا = ۴۴۱٫۸ هرتز (+۷ سنت)" \hspace #1 \bold "کوک مرجع:" } }
  \fill-line { "" \line { "دارد" \hspace #1 \bold "ربع‌پرده:" } }
  \fill-line { "" \line { "۹۶ ضرب در دقیقه · ۴/۴" \hspace #1 \bold "تمپو و وزن:" } }
  \fill-line { "" \line { "آواز، پیانو و کیبورد، بیس، ضرب و درامز" \hspace #1 \bold "لایه‌ها:" } }
  \vspace #1.2 \fill-line { "" \fontsize #2 \bold "کوک سنتور" }
  \vspace #0.5
  \fill-line { \line { \hcenter-in #26 \bold "اختلاف با پیانو (سنت)" \hcenter-in #24 \bold "فاصله از درجه‌ی قبل" \hcenter-in #18 \bold "فرکانس (هرتز)" \hcenter-in #16 \bold "نت" \hcenter-in #8 \bold "درجه" } }
  \vspace #0.2 \fill-line { \line { \hcenter-in #26 "−۴۳" \hcenter-in #24 "—" \hcenter-in #18 "۳۲۱٫۶" \hcenter-in #16 "می کرن" \hcenter-in #8 "۱" } }
  \vspace #0.2 \fill-line { \line { \hcenter-in #26 "+۷" \hcenter-in #24 "سه‌ربع پرده" \hcenter-in #18 "۳۵۰٫۶" \hcenter-in #16 "فا" \hcenter-in #8 "۲" } }
  \vspace #0.2 \fill-line { \line { \hcenter-in #26 "+۷" \hcenter-in #24 "یک پرده" \hcenter-in #18 "۳۹۳٫۶" \hcenter-in #16 "سل" \hcenter-in #8 "۳" } }
  \vspace #0.2 \fill-line { \line { \hcenter-in #26 "+۷" \hcenter-in #24 "یک پرده" \hcenter-in #18 "۴۴۱٫۸" \hcenter-in #16 "لا" \hcenter-in #8 "۴" } }
  \vspace #0.2 \fill-line { \line { \hcenter-in #26 "−۴۳" \hcenter-in #24 "سه‌ربع پرده" \hcenter-in #18 "۴۸۱٫۸" \hcenter-in #16 "سی کرن" \hcenter-in #8 "۵" } }
  \vspace #0.2 \fill-line { \line { \hcenter-in #26 "+۷" \hcenter-in #24 "سه‌ربع پرده" \hcenter-in #18 "۵۲۵٫۴" \hcenter-in #16 "دو" \hcenter-in #8 "۶" } }
  \vspace #0.2 \fill-line { \line { \hcenter-in #26 "+۷" \hcenter-in #24 "یک پرده" \hcenter-in #18 "۵۸۹٫۷" \hcenter-in #16 "ر" \hcenter-in #8 "۷" } }
  \vspace #0.2 \fill-line { \line { \hcenter-in #26 "−۴۳" \hcenter-in #24 "سه‌ربع پرده" \hcenter-in #18 "۶۴۳٫۱" \hcenter-in #16 "می کرن" \hcenter-in #8 "۸" } }
  \vspace #1 \fill-line { "" \fontsize #-2 "جداسازی: لایه‌های آماده · روش‌ها: basic-pitch, onsets, salience, salience+crepe" }
}

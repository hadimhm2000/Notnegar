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
  oddFooterMarkup = \markup \fill-line { \override #'(font-name . "Vazirmatn, Noto Naskh Arabic, Noto Sans Arabic, Tahoma, DejaVu Sans") \fontsize #-3 "آزمون minor  ·  نت‌نگار" \fontsize #-3 \fromproperty #'page:page-number-string }
  evenFooterMarkup = \oddFooterMarkup
}
\header { tagline = ##f }

global = { \time 4/4 \tempo 4 = 100 \set Staff.keyAlterations = #`() }

\markup \override #'(font-name . "Vazirmatn, Noto Naskh Arabic, Noto Sans Arabic, Tahoma, DejaVu Sans") \column {
  \fill-line { \fontsize #6 \bold "آزمون minor" }
  \vspace #0.3
  \fill-line { \fontsize #-1 "" \fontsize #1 "نت‌نگار" }
  \fill-line { "" \fontsize #-2 "نت‌نگار · مینور لا" }
}

\score {
  <<
    \new Staff = "vocals" \with { instrumentName = \markup \override #'(font-name . "Vazirmatn, Noto Naskh Arabic, Noto Sans Arabic, Tahoma, DejaVu Sans") "آواز" shortInstrumentName = \markup \override #'(font-name . "Vazirmatn, Noto Naskh Arabic, Noto Sans Arabic, Tahoma, DejaVu Sans") "آواز" }
    \new Voice = "vvocals" { \global \clef "treble" \compressMMRests {
      r8 a'4 b'8 c''8 d''4 e''4 d''8 c''8 b'4 a'2 r4 c''4 d''4 e''8 f''8 e''4
      d''4 c''8 b'8 a'2 r4 a'4 b'8 c''8 d''4 e''4 d''8 c''8 b'4 a'2 r4 c''4
      d''4 e''8 f''8 e''4 d''4 c''8 b'8 a'2 r8 R1
    } }
    \new Lyrics \with { \override LyricText.font-name = "Vazirmatn, Noto Naskh Arabic, Noto Sans Arabic, Tahoma, DejaVu Sans" \override LyricText.font-size = #-2 } \lyricsto "vvocals" { "لا" "سی" "دو" "ر" "می" "ر" "دو" "سی" "لا" "دو" "ر" "می" "فا" "می" "ر" "دو" "سی" "لا" "لا" "سی" "دو" "ر" "می" "ر" "دو" "سی" "لا" "دو" "ر" "می" "فا" "می" "ر" "دو" "سی" "لا" }
  \new PianoStaff \with { instrumentName = \markup \override #'(font-name . "Vazirmatn, Noto Naskh Arabic, Noto Sans Arabic, Tahoma, DejaVu Sans") "پیانو و کیبورد" shortInstrumentName = \markup \override #'(font-name . "Vazirmatn, Noto Naskh Arabic, Noto Sans Arabic, Tahoma, DejaVu Sans") "پیانو" } <<
    \new Staff = "piano_rh" \with { }
    \new Voice = "vpianorh" { \global \clef "treble" \compressMMRests {
      r8 <c' e' c'' b'' af'''>2 <c' d' f' d''>2 <d' d'' a''>2 <e' b' e'' b''>8. b''8. r8 <c' e' c''>2 <c' d' f' d''>2 <d' d'' a''>2 <e' b' e'' b''>4 b''8 r8 <c' e' c'' b''>2 <c' d' f' d''>2 <d' d'' a''>2
      <e' b' e'' b''>4 b''8 r8 <c' e' c'' b'' af'''>2 <c' d' f' d''>2 <d' d'' a''>2 <e' b' e'' b''>8. b''8. r8 <c' e' c''>2 <c' d' f' d''>2 <d' d'' a''>2 r4.
    } }
    \new Staff = "piano_lh" \with { }
    \new Voice = "vpianolh" { \global \clef "bass" \compressMMRests {
      r8 a2 f2 <g b>2 <fs b>2 a2 f2 <g b>2 <fs b>2 a2 f4.~ f16 r16 <g b>2 <fs b>4.~ <fs b>16
      r16 a2 f4.~ f16 r16 <g b>2 <fs b>4.~ <fs b>16 r16 a2 f4.~ f16 r16 <g b>2 r4.
    } }
  >>
  \new Staff = "bass" \with { instrumentName = \markup \override #'(font-name . "Vazirmatn, Noto Naskh Arabic, Noto Sans Arabic, Tahoma, DejaVu Sans") "بیس" shortInstrumentName = \markup \override #'(font-name . "Vazirmatn, Noto Naskh Arabic, Noto Sans Arabic, Tahoma, DejaVu Sans") "بیس" }
    \new Voice = "vbass" { \global \clef "bass" \compressMMRests {
      r8 a,4~ a,16 r8. f,4~ f,16 r16 r8 g,4~ g,16 r8. fs,4~ fs,16 r16 r8 a,4~
      a,16 r8. f,4~ f,16 r16 r8 g,4~ g,16 r8. fs,4~ fs,16 r16 r8 a,4~ a,16 r8.
      f,4~ f,16 r16 r8 g,4~ g,16 r8. fs,4~ fs,16 r16 r8 a,4~ a,16 r8. f,4~ f,16
      r16 r8 g,4~ g,16 r8. fs,4~ fs,16 r16 r8 a,4~ a,16 r8. f,4~ f,16 r16 r8
      g,4~ g,16 r2 r16
    } }
  \new RhythmicStaff = "drums" \with { instrumentName = \markup \override #'(font-name . "Vazirmatn, Noto Naskh Arabic, Noto Sans Arabic, Tahoma, DejaVu Sans") "ضرب و درامز" shortInstrumentName = \markup \override #'(font-name . "Vazirmatn, Noto Naskh Arabic, Noto Sans Arabic, Tahoma, DejaVu Sans") "ضرب" }
    \new Voice = "vdrums" { \global \compressMMRests {
      r8 c16 c8. c16 c8. c16 c8. c16 c8. c16 c8. c16 c8. c16 c8. c16
      c8. c16 c8. c16 c8. c4 c16 c8. c16 c8. c4 c4 c16 c8. c4 c4
      c4 c4 c4 c4 c4 c4 c4 c4 c4 c4 c4 c4 c4 c4 c4 c4
      c4 c8. c16 c8. c16 c4 r4.
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
  \fill-line { "" \fontsize #6 \bold "آزمون minor" }
  \vspace #0.4 \fill-line { "" \fontsize #1 "نت‌نگار · مینور لا" }
  \vspace #1 \draw-hline \vspace #0.6
  \fill-line { "" \line { "مینور  (اطمینان ۵۰٪)" \hspace #1 \bold "دستگاه یا گام:" } }
  \fill-line { "" \line { "لا" \hspace #1 \bold "نت پایه:" } }
  \fill-line { "" \line { "مینور هارمونیک لا (۵۰٪)" \hspace #1 \bold "گزینه‌ی بعدی:" } }
  \fill-line { "" \line { "لا = ۴۴۰٫۲ هرتز (+۱ سنت)" \hspace #1 \bold "کوک مرجع:" } }
  \fill-line { "" \line { "ندارد" \hspace #1 \bold "ربع‌پرده:" } }
  \fill-line { "" \line { "۱۰۰ ضرب در دقیقه · ۴/۴" \hspace #1 \bold "تمپو و وزن:" } }
  \fill-line { "" \line { "آواز، پیانو و کیبورد، بیس، ضرب و درامز" \hspace #1 \bold "لایه‌ها:" } }
  \vspace #0.5 \fill-line { "" \italic \fontsize #-1 "گام مینور غربی، که در موسیقی پاپ ایرانی رایج است و ربع‌پرده ندارد." }
  \vspace #1.2 \fill-line { "" \fontsize #2 \bold "کوک سنتور" }
  \vspace #0.5
  \fill-line { \line { \hcenter-in #26 \bold "اختلاف با پیانو (سنت)" \hcenter-in #24 \bold "فاصله از درجه‌ی قبل" \hcenter-in #18 \bold "فرکانس (هرتز)" \hcenter-in #16 \bold "نت" \hcenter-in #8 \bold "درجه" } }
  \vspace #0.2 \fill-line { \line { \hcenter-in #26 "+۱" \hcenter-in #24 "—" \hcenter-in #18 "۴۴۰٫۲" \hcenter-in #16 "لا" \hcenter-in #8 "۱" } }
  \vspace #0.2 \fill-line { \line { \hcenter-in #26 "+۱" \hcenter-in #24 "یک پرده" \hcenter-in #18 "۴۹۴٫۱" \hcenter-in #16 "سی" \hcenter-in #8 "۲" } }
  \vspace #0.2 \fill-line { \line { \hcenter-in #26 "+۱" \hcenter-in #24 "نیم پرده" \hcenter-in #18 "۵۲۳٫۵" \hcenter-in #16 "دو" \hcenter-in #8 "۳" } }
  \vspace #0.2 \fill-line { \line { \hcenter-in #26 "+۱" \hcenter-in #24 "یک پرده" \hcenter-in #18 "۵۸۷٫۶" \hcenter-in #16 "ر" \hcenter-in #8 "۴" } }
  \vspace #0.2 \fill-line { \line { \hcenter-in #26 "+۱" \hcenter-in #24 "یک پرده" \hcenter-in #18 "۶۵۹٫۵" \hcenter-in #16 "می" \hcenter-in #8 "۵" } }
  \vspace #0.2 \fill-line { \line { \hcenter-in #26 "+۱" \hcenter-in #24 "نیم پرده" \hcenter-in #18 "۶۹۸٫۷" \hcenter-in #16 "فا" \hcenter-in #8 "۶" } }
  \vspace #0.2 \fill-line { \line { \hcenter-in #26 "+۱" \hcenter-in #24 "یک پرده" \hcenter-in #18 "۷۸۴٫۳" \hcenter-in #16 "سل" \hcenter-in #8 "۷" } }
  \vspace #0.2 \fill-line { \line { \hcenter-in #26 "+۱" \hcenter-in #24 "یک پرده" \hcenter-in #18 "۸۸۰٫۴" \hcenter-in #16 "لا" \hcenter-in #8 "۸" } }
  \vspace #1 \fill-line { "" \fontsize #-2 "جداسازی: لایه‌های آماده · روش‌ها: basic-pitch, onsets, salience, salience+crepe" }
}

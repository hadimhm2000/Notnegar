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
  oddFooterMarkup = \markup \fill-line { \override #'(font-name . "Vazirmatn, Noto Naskh Arabic, Noto Sans Arabic, Tahoma, DejaVu Sans") \fontsize #-3 "آزمون  ·  نت‌نگار" \fontsize #-3 \fromproperty #'page:page-number-string }
  evenFooterMarkup = \oddFooterMarkup
}
\header { tagline = ##f }

global = { \time 6/8 \tempo 4. = 80 \set Staff.keyAlterations = #`() }

\markup \override #'(font-name . "Vazirmatn, Noto Naskh Arabic, Noto Sans Arabic, Tahoma, DejaVu Sans") \column {
  \fill-line { \fontsize #6 \bold "آزمون" }
  \vspace #0.3
  \fill-line { \fontsize #-1 "نت سنتور" \fontsize #1 "" }
  \fill-line { "" \fontsize #-2 "مینور لا (منتقل‌شده از سل)" }
}

\score {
  <<
    \new Staff = "melody" \with { }
    \new Voice = "vmelody" { \global \clef "treble" \compressMMRests {
      e''8^\markup \override #'(font-name . "Vazirmatn, Noto Naskh Arabic, Noto Sans Arabic, Tahoma, DejaVu Sans") \box \bold "شعر" f''8-\upbow e''8 d''8 c''8-\upbow d''8 e''4.:32 r4. d''8 e''8-\upbow d''8 c''8 b'8-\upbow c''8 a'4.:32 r4.
      a''4 g''8-\upbow f''4 e''8-\upbow f''8 e''8-\upbow d''8 c''4.:32 b'8 c''8-\upbow d''8 c''8 b'8-\upbow a'2.:32~ a'8:32 e''8
      f''8-\upbow e''8 d''8 c''8-\upbow d''8 e''4.:32 r4. d''8 e''8-\upbow d''8 c''8 b'8-\upbow c''8 a'4.:32 r4. a''4
      g''8-\upbow f''4 e''8-\upbow f''8 e''8-\upbow d''8 c''4.:32 b'8 c''8-\upbow d''8 c''8 b'8-\upbow a'2.:32~ a'8:32
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
  \fill-line { "" \fontsize #6 \bold "آزمون" }
  \vspace #0.4 \fill-line { "" \fontsize #1 "مینور لا (منتقل‌شده از سل)" }
  \vspace #1 \draw-hline \vspace #0.6
  \fill-line { "" \line { "مینور  (اطمینان ۸۴٪)" \hspace #1 \bold "دستگاه یا گام:" } }
  \fill-line { "" \line { "لا" \hspace #1 \bold "نت پایه:" } }
  \fill-line { "" \line { "مینور هارمونیک سل (۱۶٪)" \hspace #1 \bold "گزینه‌ی بعدی:" } }
  \fill-line { "" \line { "لا = ۴۴۰٫۸ هرتز (+۳ سنت)" \hspace #1 \bold "کوک مرجع:" } }
  \fill-line { "" \line { "ندارد" \hspace #1 \bold "ربع‌پرده:" } }
  \fill-line { "" \line { "۸۰ ضرب در دقیقه · ۶/۸" \hspace #1 \bold "تمپو و وزن:" } }
  \fill-line { "" \line { "" \hspace #1 \bold "لایه‌ها:" } }
  \vspace #0.5 \fill-line { "" \italic \fontsize #-1 "گام مینور غربی، که در موسیقی پاپ ایرانی رایج است و ربع‌پرده ندارد." }
  \vspace #1.2 \fill-line { "" \fontsize #2 \bold "کوک سنتور" }
  \vspace #0.5
  \fill-line { \line { \hcenter-in #26 \bold "اختلاف با پیانو (سنت)" \hcenter-in #24 \bold "فاصله از درجه‌ی قبل" \hcenter-in #18 \bold "فرکانس (هرتز)" \hcenter-in #16 \bold "نت" \hcenter-in #8 \bold "درجه" } }
  \vspace #0.2 \fill-line { \line { \hcenter-in #26 "+۰" \hcenter-in #24 "—" \hcenter-in #18 "۴۴۰٫۰" \hcenter-in #16 "لا" \hcenter-in #8 "۱" } }
  \vspace #0.2 \fill-line { \line { \hcenter-in #26 "+۰" \hcenter-in #24 "یک پرده" \hcenter-in #18 "۴۹۳٫۹" \hcenter-in #16 "سی" \hcenter-in #8 "۲" } }
  \vspace #0.2 \fill-line { \line { \hcenter-in #26 "+۰" \hcenter-in #24 "نیم پرده" \hcenter-in #18 "۵۲۳٫۲" \hcenter-in #16 "دو" \hcenter-in #8 "۳" } }
  \vspace #0.2 \fill-line { \line { \hcenter-in #26 "+۰" \hcenter-in #24 "یک پرده" \hcenter-in #18 "۵۸۷٫۳" \hcenter-in #16 "ر" \hcenter-in #8 "۴" } }
  \vspace #0.2 \fill-line { \line { \hcenter-in #26 "+۰" \hcenter-in #24 "یک پرده" \hcenter-in #18 "۶۵۹٫۳" \hcenter-in #16 "می" \hcenter-in #8 "۵" } }
  \vspace #0.2 \fill-line { \line { \hcenter-in #26 "+۰" \hcenter-in #24 "نیم پرده" \hcenter-in #18 "۶۹۸٫۵" \hcenter-in #16 "فا" \hcenter-in #8 "۶" } }
  \vspace #0.2 \fill-line { \line { \hcenter-in #26 "+۰" \hcenter-in #24 "یک پرده" \hcenter-in #18 "۷۸۴٫۰" \hcenter-in #16 "سل" \hcenter-in #8 "۷" } }
  \vspace #0.2 \fill-line { \line { \hcenter-in #26 "+۰" \hcenter-in #24 "یک پرده" \hcenter-in #18 "۸۸۰٫۰" \hcenter-in #16 "لا" \hcenter-in #8 "۸" } }
  \vspace #1 \fill-line { "" \fontsize #-2 "جداسازی: لایه‌های آماده · روش‌ها: salience+crepe+salience" }
}

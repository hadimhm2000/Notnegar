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
  oddFooterMarkup = \markup \fill-line { \override #'(font-name . "Vazirmatn, Noto Naskh Arabic, Noto Sans Arabic, Tahoma, DejaVu Sans") \fontsize #-3 "سریع  ·  نت‌نگار" \fontsize #-3 \fromproperty #'page:page-number-string }
  evenFooterMarkup = \oddFooterMarkup
}
\header { tagline = ##f }

global = { \time 6/8 \tempo 4. = 80 \set Staff.keyAlterations = #`((6 . ,FLAT) (2 . ,FLAT)) }

\markup \override #'(font-name . "Vazirmatn, Noto Naskh Arabic, Noto Sans Arabic, Tahoma, DejaVu Sans") \column {
  \fill-line { \fontsize #6 \bold "سریع" }
  \vspace #0.3
  \fill-line { \fontsize #-1 "نت سنتور" \fontsize #1 "" }
  \fill-line { "" \fontsize #-2 "مینور سل" }
}

\score {
  <<
    \new Staff = "melody" \with { }
    \new Voice = "vmelody" { \global \clef "treble" \compressMMRests {
      d''8 ef''8-\upbow d''8 c''8 bf'8-\upbow c''8 d''4.:32 r4. c''8 d''8-\upbow c''8 bf'8 a'8-\upbow bf'8 g'4.:32 r4.
      g''4 f''8-\upbow ef''4 d''8-\upbow ef''8 d''8-\upbow c''8 bf'4.:32 a'8 bf'8-\upbow c''8 bf'8 a'8-\upbow g'2.:32~ g'8:32 d''8
      ef''8-\upbow d''8 c''8 bf'8-\upbow c''8 d''4.:32 r4. c''8 d''8-\upbow c''8 bf'8 a'8-\upbow bf'8 g'4.:32 r4. g''4
      f''8-\upbow ef''4 d''8-\upbow ef''8 d''8-\upbow c''8 bf'4.:32 a'8 bf'8-\upbow c''8 bf'8 a'8-\upbow g'2.:32~ g'8:32
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
  \fill-line { "" \fontsize #6 \bold "سریع" }
  \vspace #0.4 \fill-line { "" \fontsize #1 "مینور سل" }
  \vspace #1 \draw-hline \vspace #0.6
  \fill-line { "" \line { "مینور  (اطمینان ۸۳٪)" \hspace #1 \bold "دستگاه یا گام:" } }
  \fill-line { "" \line { "سل" \hspace #1 \bold "نت پایه:" } }
  \fill-line { "" \line { "مینور هارمونیک سل (۱۶٪)" \hspace #1 \bold "گزینه‌ی بعدی:" } }
  \fill-line { "" \line { "لا = ۴۴۱٫۱ هرتز (+۵ سنت)" \hspace #1 \bold "کوک مرجع:" } }
  \fill-line { "" \line { "ندارد" \hspace #1 \bold "ربع‌پرده:" } }
  \fill-line { "" \line { "۸۰ ضرب در دقیقه · ۶/۸" \hspace #1 \bold "تمپو و وزن:" } }
  \fill-line { "" \line { "" \hspace #1 \bold "لایه‌ها:" } }
  \vspace #0.5 \fill-line { "" \italic \fontsize #-1 "گام مینور غربی، که در موسیقی پاپ ایرانی رایج است و ربع‌پرده ندارد." }
  \vspace #1.2 \fill-line { "" \fontsize #2 \bold "کوک سنتور" }
  \vspace #0.5
  \fill-line { \line { \hcenter-in #26 \bold "اختلاف با پیانو (سنت)" \hcenter-in #24 \bold "فاصله از درجه‌ی قبل" \hcenter-in #18 \bold "فرکانس (هرتز)" \hcenter-in #16 \bold "نت" \hcenter-in #8 \bold "درجه" } }
  \vspace #0.2 \fill-line { \line { \hcenter-in #26 "+۵" \hcenter-in #24 "—" \hcenter-in #18 "۳۹۳٫۰" \hcenter-in #16 "سل" \hcenter-in #8 "۱" } }
  \vspace #0.2 \fill-line { \line { \hcenter-in #26 "+۵" \hcenter-in #24 "یک پرده" \hcenter-in #18 "۴۴۱٫۱" \hcenter-in #16 "لا" \hcenter-in #8 "۲" } }
  \vspace #0.2 \fill-line { \line { \hcenter-in #26 "+۵" \hcenter-in #24 "نیم پرده" \hcenter-in #18 "۴۶۷٫۴" \hcenter-in #16 "سی بمل" \hcenter-in #8 "۳" } }
  \vspace #0.2 \fill-line { \line { \hcenter-in #26 "+۵" \hcenter-in #24 "یک پرده" \hcenter-in #18 "۵۲۴٫۶" \hcenter-in #16 "دو" \hcenter-in #8 "۴" } }
  \vspace #0.2 \fill-line { \line { \hcenter-in #26 "+۵" \hcenter-in #24 "یک پرده" \hcenter-in #18 "۵۸۸٫۹" \hcenter-in #16 "ر" \hcenter-in #8 "۵" } }
  \vspace #0.2 \fill-line { \line { \hcenter-in #26 "+۵" \hcenter-in #24 "نیم پرده" \hcenter-in #18 "۶۲۳٫۹" \hcenter-in #16 "می بمل" \hcenter-in #8 "۶" } }
  \vspace #0.2 \fill-line { \line { \hcenter-in #26 "+۵" \hcenter-in #24 "یک پرده" \hcenter-in #18 "۷۰۰٫۳" \hcenter-in #16 "فا" \hcenter-in #8 "۷" } }
  \vspace #0.2 \fill-line { \line { \hcenter-in #26 "+۵" \hcenter-in #24 "یک پرده" \hcenter-in #18 "۷۸۶٫۰" \hcenter-in #16 "سل" \hcenter-in #8 "۸" } }
  \vspace #1 \fill-line { "" \fontsize #-2 "جداسازی: بدون جداسازی (حالت سریع) · روش‌ها: salience+crepe" }
}

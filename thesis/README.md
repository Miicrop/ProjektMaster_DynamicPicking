# Thesis – Projektarbeit

LaTeX (KOMA `scrreprt`), Deutsch, Zitierstil IEEE über `biblatex` (`style=ieee`) mit `biber`.

## Struktur

| Pfad | Inhalt |
|---|---|
| `main.tex` | Präambel, Metadaten (Titel, Autoren), Kapitelreihenfolge |
| `chapters/` | Ein File pro Kapitel; Modulkapitel 05–08 schreibt die jeweils verantwortliche Person |
| `references.bib` | Literatur – nur verifizierte Einträge (DOI prüfen) |
| `figures/` | Abbildungen (PDF/PNG), eingebunden per `\includegraphics{name}` |

## Bauen

**Lokal** (MiKTeX oder TeX Live mit `latexmk`, `biber`, Pakete `biblatex-ieee`, `acro`, `koma-script`):

```bash
cd thesis
latexmk main.tex        # Ausgabe: build/main.pdf
```

**Overleaf:** Ordner als ZIP hochladen, Compiler *pdfLaTeX*; biber wird automatisch erkannt.

## Zitieren

```latex
Die Marker werden nach~\cite{garrido2014} detektiert.
```

Abkürzungen stehen in `chapters/00_abkuerzungen.tex` und werden mit `\ac{ocr}` verwendet.

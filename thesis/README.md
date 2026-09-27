# Thesis – Projektarbeit

LaTeX (KOMA `scrreprt`), Deutsch, Zitierstil IEEE über `biblatex` (`style=ieee`) mit `biber`.

**Gesamtplan, Stand und Vorgehen fürs Weiterschreiben:** [blueprint.md](blueprint.md) (§7 „So geht es weiter“).

## Struktur

| Pfad | Inhalt |
|---|---|
| `blueprint.md` | Gesamtplan: Rahmen, Kapitelplan mit Umfang, Konventionen, Quellenliste, nächste Schritte |
| `main.tex` | Präambel, Metadaten (Titel, Autoren), Kapitelreihenfolge |
| `chapters/` | Ein File pro Kapitel (siehe unten) |
| `references.bib` | Literatur – nur verifizierte Einträge (DOI prüfen) |
| `figures/` | Abbildungen (PDF/PNG), eingebunden per `\includegraphics{name}`; Unterordner je Thema (z. B. `grob/`), Dateinamen ohne Leerzeichen |

| Datei | Kapitel | Verantwortlich |
|---|---|---|
| `01_abstract.tex` | Kurzfassung | alle |
| `02_einleitung.tex` | Einleitung | alle |
| `02b_vorprojekt.tex` | Vorprojekt: KI-basierte Roboterbahnen (GROB) | alle (Abschnitt „Alternative Verfahren“: Kommilitone) |
| `03_grundlagen.tex` | Grundlagen | alle (Abschnitt lernbasiertes Greifen: Person 4) |
| `04_systemkonzept.tex` | Systemkonzept | Niklas |
| `05_objekterkennung.tex` | Objekterkennung (M1) | Person 1 |
| `06_robotersteuerung.tex` | Robotersteuerung (M2) | Person 2 |
| `07_sichtpruefung.tex` | Sichtprüfung (M3) | Person 3 |
| `08_ki_greifen.tex` | KI-basiertes Greifen (M4) | Person 4 |
| `09_integration.tex` | Integration und Bedienung | Niklas |
| `10_evaluation.tex` | Evaluation | alle |
| `11_fazit.tex` | Fazit und Ausblick | alle |

## Bauen

**Lokal** (MiKTeX oder TeX Live mit `latexmk`, `biber`, Pakete `biblatex-ieee`, `acro`, `koma-script`,
`todonotes`, `algorithmicx`, `pgf/tikz`):

```bash
cd thesis
latexmk main.tex        # Ausgabe: build/main.pdf
```

**Overleaf:** Ordner als ZIP hochladen, Compiler *pdfLaTeX*; biber wird automatisch erkannt.

## Konventionen

- **Kein Quellcode** im Text – Abläufe als Grafik (TikZ-Ablaufdiagramm), nicht als Pseudocode. Die Stile
  `pap term`, `pap proc`, `pap dec`, `pap arr`, `pap lbl`, `pap good`, `pap bad` stehen in `main.tex`.
- **Offene Punkte** als `\todo[inline]{…}`, fehlende Bilder als `\missingfigure{…}` – beides erscheint im PDF orange bzw. grau.
- **Abkürzungen** in `chapters/00_abkuerzungen.tex`, im Text mit `\ac{ocr}` (in Abbildungen `\acs{…}`).
- **Querverweise** mit `\cref{…}`; Labels: `ch:`, `sec:`, `fig:`, `tab:`, `eq:`.
- Beschrieben wird nur, was im Code umgesetzt ist; Probleme und Ergebnisse erst nach echten Tests.

## Zitieren

```latex
Die Marker werden nach~\cite{garrido2014} detektiert.
```

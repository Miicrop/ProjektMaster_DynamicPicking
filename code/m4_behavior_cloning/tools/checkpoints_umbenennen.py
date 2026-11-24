"""Checkpoint-Ordner sprechend umbenennen (Anwender 2026-11-17).

``checkpoints/var_C3`` sagt nicht, was drinsteckt. Neue Namen tragen die
Aenderung gegenueber der Basis im Namen (GUI-Reiter Betrieb zeigt die
Ordnernamen). Mitgezogen werden alle Pfadangaben ``checkpoints/var_X`` in
Skripten, Doku, Berichtsdaten und den summary.json der Rollouts (report_rollouts
findet darueber train_log.csv). Freitext in Testprotokollen bleibt historisch.

    python tools/checkpoints_umbenennen.py            # nur anzeigen
    python tools/checkpoints_umbenennen.py --ausfuehren
"""
import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

NAMEN = {
    "var_A": "A_basis",
    "var_B": "B_pause_kurz",
    "var_C": "C_nur_griff",
    "var_C2": "C2_nur_griff_ohne_1111",
    "var_C3": "C3_wie_C2_drehung_gewichtet",
    "var_C3a": "C3a_wie_C2_plus_ausgeduennt",
    "var_D": "D_eine_drehung",
    "var_F": "F_licht_augment",
}

# Pfad "checkpoints" + Trenner (/, \ oder JSON-\\) + alter Name, nicht von
# weiteren Wortzeichen gefolgt (var_C trifft nicht var_C2).
MUSTER = re.compile(r"(checkpoints(?:/|\\\\|\\))(%s)(?![A-Za-z0-9_])"
                    % "|".join(sorted(map(re.escape, NAMEN), key=len, reverse=True)))
TESTPFAD = re.compile(r'("checkpoints"\s*/\s*")(%s)(")' % "|".join(map(re.escape, NAMEN)))

DATEIEN = ["apps/*.py", "bc/**/*.py", "tools/*.py", "tests/*.py", "Dokumentation/*.md",
           "Berichte/*/skripte/*", "Berichte/*/daten/*.json", "checkpoints/*/policy/rollouts/*/summary.json"]


def ersetzen(text):
    neu = MUSTER.sub(lambda m: m.group(1) + NAMEN[m.group(2)], text)
    return TESTPFAD.sub(lambda m: m.group(1) + NAMEN[m.group(2)] + m.group(3), neu)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ausfuehren", action="store_true")
    args = ap.parse_args()
    ck = ROOT / "checkpoints"
    for alt, neu in NAMEN.items():
        if (ck / neu).exists():
            sys.exit("Ziel existiert schon: checkpoints/%s" % neu)
    if args.ausfuehren:
        for alt, neu in NAMEN.items():
            if (ck / alt).exists():
                (ck / alt).rename(ck / neu)
                print("checkpoints/%s -> %s" % (alt, neu))
    else:
        for alt, neu in NAMEN.items():
            print("checkpoints/%-7s -> %s%s" % (alt, neu, "" if (ck / alt).exists() else "  (fehlt)"))
    me = Path(__file__).resolve()
    n = 0
    for muster in DATEIEN:
        for f in sorted(ROOT.glob(muster)):
            if not f.is_file() or f.resolve() == me or f.suffix not in (".py", ".sh", ".md", ".json"):
                continue
            text = f.read_text(encoding="utf-8")
            neu = ersetzen(text)
            if neu != text:
                n += 1
                k = len(MUSTER.findall(text)) + len(TESTPFAD.findall(text))
                print("  %3d Pfade in %s" % (k, f.relative_to(ROOT)))
                if args.ausfuehren:
                    f.write_text(neu, encoding="utf-8", newline="")
    print("%d Dateien %s" % (n, "angepasst" if args.ausfuehren else "wuerden angepasst"))


if __name__ == "__main__":
    main()

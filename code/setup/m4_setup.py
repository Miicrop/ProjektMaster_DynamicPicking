"""M4-Setup: Einstieg fuer Fenster und Kommandozeile.

Ohne Argumente oeffnet sich das Fenster (fenster.py). Gibt es kein tkinter,
oder ist eine der Optionen unten gesetzt, laeuft alles in der Konsole.

    python setup\\m4_setup.py                      Fenster
    python setup\\m4_setup.py --status             was ist da, was fehlt
    python setup\\m4_setup.py --befehle            nur anzeigen, was liefe
    python setup\\m4_setup.py --installieren       Vorauswahl installieren
    python setup\\m4_setup.py --installieren --nur torch,lerobot
    python setup\\m4_setup.py --reparieren gui,opencv
    python setup\\m4_setup.py --deinstallieren ffmpeg,gxipy
    python setup\\m4_setup.py --umgebung-loeschen
    python setup\\m4_setup.py --checkliste         Datei fuer den Laborbetreuer
    python setup\\m4_setup.py --wheelhouse-befehle D:\\wheels   Offline-Pakete sammeln

Gemeinsame Optionen: --ziel ORDNER, --gpu/--cpu, --basis-python PFAD,
--wheelhouse ORDNER (offline), --ffmpeg-zip DATEI, --ja (ohne Rueckfrage).
"""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import kern  # noqa: E402
import komponenten as K  # noqa: E402


def _ids(text):
    if not text:
        return None
    ids = [t.strip() for t in text.split(",") if t.strip()]
    falsch = [i for i in ids if i not in kern.ALLE]
    if falsch:
        sys.exit("Unbekannte Komponente(n): %s\nBekannt: %s"
                 % (", ".join(falsch), ", ".join(kern.ALLE)))
    return ids


def _ziel(args):
    ziel = kern.lade_einstellungen()
    if args.ziel:
        ziel.venv = Path(args.ziel)
    if args.cpu:
        ziel.build = "cpu"
    if args.gpu:
        ziel.build = "gpu"
    if args.basis_python:
        ziel.basis_python = args.basis_python
    if args.wheelhouse:
        ziel.wheelhouse = args.wheelhouse
    if args.ffmpeg_zip:
        ziel.ffmpeg_zip = args.ffmpeg_zip
    return ziel


def zeige_status(ziel, befunde):
    print("Zielordner: %s   Build: %s" % (ziel.venv, ziel.build.upper()))
    for gid, titel in K.GRUPPEN:
        print("\n" + titel)
        for k in K.KOMPONENTEN:
            if k["gruppe"] != gid:
                continue
            b = befunde[k["id"]]
            print("  %-12s %-15s %s  %s" % (k["id"], kern.STATUS_TEXT[b.status], k["titel"],
                                           ("(" + b.detail + ")") if b.detail else ""))


def main(argv=None):
    for strom in (sys.stdout, sys.stderr):       # cp1252-Konsole: nie an Sonderzeichen sterben
        try:
            strom.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass
    p = argparse.ArgumentParser(description="M4-Setup (Behavior Cloning)",
                                formatter_class=argparse.RawDescriptionHelpFormatter,
                                epilog=__doc__)
    a = p.add_mutually_exclusive_group()
    a.add_argument("--status", action="store_true")
    a.add_argument("--befehle", action="store_true")
    a.add_argument("--installieren", action="store_true")
    a.add_argument("--reparieren", metavar="IDS")
    a.add_argument("--deinstallieren", metavar="IDS")
    a.add_argument("--umgebung-loeschen", action="store_true")
    a.add_argument("--checkliste", action="store_true")
    a.add_argument("--wheelhouse-befehle", metavar="ORDNER")
    p.add_argument("--nur", metavar="IDS", help="Komponenten, Komma-getrennt")
    p.add_argument("--ziel")
    b = p.add_mutually_exclusive_group()
    b.add_argument("--gpu", action="store_true")
    b.add_argument("--cpu", action="store_true")
    p.add_argument("--basis-python")
    p.add_argument("--wheelhouse")
    p.add_argument("--ffmpeg-zip")
    p.add_argument("--ja", action="store_true", help="ohne Rueckfrage")
    p.add_argument("--konsole", action="store_true", help="nie das Fenster oeffnen")
    args = p.parse_args(argv)

    nur_fenster = not any([args.status, args.befehle, args.installieren, args.reparieren,
                           args.deinstallieren, args.umgebung_loeschen, args.checkliste,
                           args.wheelhouse_befehle, args.konsole])
    if nur_fenster:
        try:
            import fenster
        except ImportError as exc:        # tkinter fehlt in manchen Python-Installationen
            print("Fenster nicht verfuegbar (%s) -- Konsolenmodus.\n" % exc)
            args.status = True
        else:
            return fenster.starte(_ziel(args))

    ziel = _ziel(args)
    if args.wheelhouse_befehle:
        for cmd in kern.wheelhouse_befehle(args.wheelhouse_befehle, ziel.build):
            print(" ".join(kern._quote(str(c)) for c in cmd))
        print("\nAuf einem Rechner MIT Internet ausfuehren, den Ordner mitnehmen, dann:\n"
              "  setup_m4.bat --installieren --wheelhouse <ordner>")
        return 0

    print("Pruefe ...")
    befunde = kern.pruefe_alle(ziel)
    if args.status or args.konsole:
        zeige_status(ziel, befunde)
        return 0
    if args.checkliste:
        datei = kern.SETUP_DIR / "Checkliste_Laborbetreuer.md"
        datei.write_text(kern.checkliste(ziel, befunde), encoding="utf-8")
        print("Geschrieben: %s" % datei)
        return 0

    if args.umgebung_loeschen:
        aktion, ids = "deinstallieren", ["venv", "bc_python"]
    elif args.deinstallieren:
        aktion, ids = "deinstallieren", _ids(args.deinstallieren)
    elif args.reparieren:
        aktion, ids = "reparieren", _ids(args.reparieren)
    else:
        aktion, ids = "installieren", _ids(args.nur) or kern.vorauswahl(befunde)

    try:
        schritte = kern.plane(aktion, ids, ziel, befunde)
    except kern.PlanFehler as exc:
        print("Nicht moeglich: %s" % exc)
        return 2
    if not schritte:
        print("Nichts zu tun -- alles Ausgewaehlte ist schon vorhanden.")
        return 0
    print("\nGeplant (%s, Ziel %s):" % (aktion, ziel.venv))
    for s in schritte:
        print("  " + s.als_text())
    if args.befehle:
        return 0
    if not args.ja:
        if input("\nAusfuehren? [j/N] ").strip().lower() not in ("j", "ja", "y"):
            print("Nichts geaendert.")
            return 1
    kern.speichere_einstellungen(ziel)
    ok = kern.Lauf(print)(schritte)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

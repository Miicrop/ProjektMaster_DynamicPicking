"""Dreht die Policy richtig -- und liegt ein Drehrichtungs-Bias in den Demos?

Anlass (Anlage 2026-11-17): Lag PICK gegen die Startstellung nach MINUS
gedreht (70-78 Grad bei Start 103), drehte die Policy in 2 von 3 Fahrten
nach PLUS und stand ~50 Grad daneben; nach plus gedrehte Lagen gingen.

Drehung = Richtung der Werkzeug-x-Achse um die Senkrechte, volle 360 Grad
(das Objekt hat eine Fase, die Handgelenkkamera schaut zu ihr -- die
Richtung ist eindeutig). "noetig" = PICK gegen Start, "gedreht" = Ende
gegen Start, "Fehler" = Ende gegen PICK.

  # Policy-Fahrten (Ordner mit rollout_*.npz, auch mehrere / Elternordner)
  python tools/analyse_drehung.py rollouts checkpoints/C2_nur_griff_ohne_1111/policy/rollouts

  # Demos (Aufnahme-Ordner mit index.json, auch mehrere / Elternordner)
  python tools/analyse_drehung.py demos data/2026-11-02 data/2026-11-03

Mit ``--csv DATEI`` zusaetzlich jede Zeile als CSV.
"""

import argparse
import csv
import sys
from pathlib import Path

import _bootstrap  # noqa: F401

import numpy as np

from bc import config, geometry

#: ab so viel noetiger Drehung zaehlt die Richtung ("klein" darunter)
RICHTUNG_AB_DEG = 10.0


def yaw360(pose):
    """Richtung der Werkzeug-x-Achse in der Basis-xy-Ebene, Grad 0..360."""
    R = geometry.quat_to_matrix(np.asarray(pose, dtype=float)[3:7])
    return float(np.degrees(np.arctan2(R[1, 0], R[0, 0])) % 360.0)


def diff(a, b):
    """a - b auf -180..180 Grad."""
    return float((a - b + 180.0) % 360.0 - 180.0)


def richtung(deg):
    if abs(deg) < RICHTUNG_AB_DEG:
        return "klein"
    return "plus" if deg > 0 else "minus"


# -- Policy-Fahrten -------------------------------------------------------

def _lokalisierung(npz_path):
    """Lokalisierungs-Protokoll der Fahrt aus summary.json daneben, oder None."""
    import json

    path = Path(npz_path).with_name("summary.json")
    try:
        episodes = json.loads(path.read_text(encoding="utf-8")).get("episodes") or []
        ep = int(Path(npz_path).stem.split("_")[-1])
        for e in episodes:
            if int(e.get("episode", -1)) == ep:
                return e.get("lokalisierung")
    except (OSError, ValueError):
        pass
    return None


def rollout_rows(roots):
    files = []
    for root in roots:
        root = Path(root)
        files += [root] if root.suffix == ".npz" else sorted(root.rglob("rollout_*.npz"))
    rows = []
    for f in files:
        z = np.load(f)
        if "lage_pick" not in z.files or "tcp" not in z.files or not len(z["tcp"]):
            continue
        start, end, pick = yaw360(z["tcp"][0]), yaw360(z["tcp"][-1]), yaw360(z["lage_pick"])
        # PICK aus M1 mit Fase: volle Richtung (bis 2026-11-17 mittags wurde PICK
        # bei grossen Drehungen um 180 Grad umgeklappt -- hier korrigiert)
        quelle = "PICK"
        lokal = _lokalisierung(f)
        if lokal and lokal.get("gripper_yaw360_deg") is not None:
            m1 = float((lokal["gripper_yaw360_deg"]
                        + (config.LOCALIZE_CHAMFER_OFFSET_DEG or 0.0)) % 360.0)
            if abs(diff(m1, pick)) > 90:
                quelle = "M1 (PICK war umgeklappt)"
            pick = m1
        noetig, gedreht = diff(pick, start), diff(end, start)
        row = {"datei": str(f), "pick": pick, "start": start, "ende": end,
               "noetig": noetig, "gedreht": gedreht, "fehler": diff(end, pick),
               "richtung_noetig": richtung(noetig), "quelle": quelle}
        row["falsch_herum"] = (row["richtung_noetig"] != "klein"
                               and richtung(gedreht) not in ("klein", row["richtung_noetig"]))
        # rohe Vorhersagen (ab 2026-11-17): Streuung der Drehung am Chunk-Ende
        if "pred_chunk" in z.files:
            row["vorhersagen"] = int(len(z["pred_chunk"]))
        rows.append(row)
    return rows


def report_rollouts(rows):
    print("%-44s %6s %6s %6s | %7s %7s %7s  %s"
          % ("Fahrt", "PICK", "Start", "Ende", "noetig", "gedreht", "Fehler", ""))
    for r in rows:
        name = "/".join(Path(r["datei"]).parts[-2:])
        print("%-44s %6.0f %6.0f %6.0f | %+7.0f %+7.0f %+7.0f  %s"
              % (name[-44:], r["pick"], r["start"], r["ende"], r["noetig"], r["gedreht"],
                 r["fehler"], ("FALSCH HERUM " if r["falsch_herum"] else "")
                 + ("[%s]" % r["quelle"] if r["quelle"] != "PICK" else "")))
    print()
    for key in ("plus", "klein", "minus"):
        group = [r for r in rows if r["richtung_noetig"] == key]
        if not group:
            continue
        err = np.array([abs(r["fehler"]) for r in group])
        print("noetige Drehung %-5s: %2d Fahrten, |Fehler| median %4.0f Grad, max %4.0f, "
              "falsch herum %d" % (key, len(group), np.median(err), err.max(),
                                   sum(r["falsch_herum"] for r in group)))
    if len(rows) >= 3:
        need = np.array([r["noetig"] for r in rows])
        done = np.array([r["gedreht"] for r in rows])
        slope = np.polyfit(need, done, 1)
        print("gedreht ~ %.2f x noetig %+.0f Grad  (ideal 1.00 x %+.0f; Steigung < 1: dreht "
              "zu wenig, Achsabschnitt > 0: Hang nach plus)" % (slope[0], slope[1], 0))


# -- Demos ----------------------------------------------------------------

def demo_rows(roots):
    from bc import replay

    sets = []
    for root in roots:
        root = Path(root)
        sets += [root] if (root / "index.json").is_file() else sorted(
            p.parent for p in root.rglob("index.json"))
    rows = []
    for root in sets:
        for index in replay.usable_episodes(root):
            try:
                # nur den Zustand lesen (npz laedt je Schluessel -- ohne Bilder schnell)
                with np.load(replay.episode_dir(root, index) / "arrays.npz") as z:
                    state = np.asarray(z["observation__state"], dtype=float)
            except Exception as exc:
                print("  %s Episode %d: nicht lesbar (%s)" % (root, index, exc), file=sys.stderr)
                continue
            grip = state[:, 13] > config.GRIPPER_THRESHOLD
            closing = np.flatnonzero(grip[1:] & ~grip[:-1])
            if not closing.size:
                continue
            at = int(closing[0]) + 1
            start, greif = yaw360(state[0, 6:13]), yaw360(state[at, 6:13])
            rows.append({"datei": "%s#%d" % (root, index), "start": start, "griff": greif,
                         "noetig": diff(greif, start), "richtung": richtung(diff(greif, start))})
    return rows


def report_demos(rows):
    if not rows:
        print("keine Demos mit Griff gefunden")
        return
    need = np.array([r["noetig"] for r in rows])
    starts = np.array([r["start"] for r in rows])
    print("%d Demos mit Griff, Startdrehung %.0f..%.0f Grad (median %.0f)"
          % (len(rows), starts.min(), starts.max(), np.median(starts)))
    print("Drehung Start -> Griff: median %+.0f, Mittel %+.0f, 10..90 %% %+.0f..%+.0f Grad"
          % (np.median(need), need.mean(), np.percentile(need, 10), np.percentile(need, 90)))
    for key in ("plus", "klein", "minus"):
        n = sum(r["richtung"] == key for r in rows)
        print("  %-5s: %4d (%3.0f %%)" % (key, n, 100.0 * n / len(rows)))
    edges = np.arange(-90, 91, 15)
    hist, _ = np.histogram(np.clip(need, -90, 90), bins=edges)
    print("Verteilung (je 15 Grad):")
    for lo, n in zip(edges[:-1], hist):
        print("  %+4d..%+4d  %4d  %s" % (lo, lo + 15, n, "#" * int(round(60.0 * n / max(hist.max(), 1)))))


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("art", choices=("rollouts", "demos"))
    parser.add_argument("ordner", nargs="+")
    parser.add_argument("--csv", default=None)
    args = parser.parse_args()
    if args.art == "rollouts":
        rows = rollout_rows(args.ordner)
        report_rollouts(rows)
    else:
        rows = demo_rows(args.ordner)
        report_demos(rows)
    if args.csv and rows:
        with open(args.csv, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=sorted({k for r in rows for k in r}),
                                    delimiter=";")
            writer.writeheader()
            writer.writerows(rows)
        print("CSV: %s" % args.csv)


if __name__ == "__main__":
    main()

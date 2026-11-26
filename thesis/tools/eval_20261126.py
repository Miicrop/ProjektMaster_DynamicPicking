"""Auswertung Labortag 2026-11-26 (Zyklusprotokoll + Nachauswertung der Prüfbilder).

    .venv\\Scripts\\python thesis\\tools\\eval_20261126.py

1. Zyklusprotokoll code/logs/cycles_20261126.csv zusammenfassen.
2. Alle Prüfbilder (logs/20261126/*/steps/m3_01_original.jpg) mit dem aktuellen Code neu auswerten
   und für dieselbe Lochkontur den alten Ellipsen-Fit und den neuen Kreis-Fit vergleichen.
3. Abbildungen nach thesis/figures/eval/ schreiben.

Ausgabe: thesis/figures/eval/*.pdf|png, thesis/tools/out/eval_20261126*.csv, Kennzahlen auf stdout.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path
from statistics import mean, median, stdev

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "code"))

import cv2  # noqa: E402
import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from common.config import load_config  # noqa: E402
from common.interfaces import InspectionError  # noqa: E402
from m3_inspection.inspector import InspectionPipeline  # noqa: E402

DAY = "20261126"
LOGS = ROOT / "code" / "logs"
RUNS = LOGS / DAY
FIG = ROOT / "thesis" / "figures" / "eval"
OUT = ROOT / "thesis" / "tools" / "out"
FIX_TIME = "10:20"   # ab 10:28 entsprechen die Protokollwerte dem Kreis-Fit (Nachauswertung)


def read_cycles() -> list[dict]:
    with open(LOGS / f"cycles_{DAY}.csv", encoding="utf-8") as f:
        rows = list(csv.DictReader(f, delimiter=";"))
    for r in rows:
        r["clock"] = r["time"][11:16]
        r["run"] = Path(r["images"]).name if r["images"] else ""
        r["dur"] = float(r["duration_s"])
        r["has_part"] = bool(r["x_mm"])
        r["hole"] = float(r["hole_mm"]) if r["hole_mm"] else None
    return rows


def summarise_cycles(rows: list[dict]) -> None:
    empty = [r for r in rows if r["ok"] == "True" and not r["has_part"]]
    errors = [r for r in rows if r["ok"] == "False"]
    full = [r for r in rows if r["hole"] is not None]
    print(f"Zeilen {len(rows)}: ohne Bauteil {len(empty)}, Fehler {len(errors)}, mit Prüfung {len(full)}")
    for r in errors:
        print(f"  Fehler {r['clock']}: {r['error']}")
    for label, sel in (("vor Fix", [r for r in full if r["clock"] < FIX_TIME]),
                       ("nach Fix", [r for r in full if r["clock"] >= FIX_TIME])):
        holes = [r["hole"] for r in sel]
        good = sum(r["good"] == "True" for r in sel)
        print(f"  {label}: n={len(sel)} gut={good} Loch {min(holes):.3f}..{max(holes):.3f} "
              f"Mittel {mean(holes):.3f} s={stdev(holes):.3f}")
        for r in sel:
            if r["good"] != "True":
                print(f"    schlecht {r['clock']}: {r['reasons']}")
    durs = sorted(r["dur"] for r in full)
    print(f"  Dauer mit Prüfung: {durs}")


def old_ellipse_mm(details, mm_per_px: float) -> float | None:
    if details.hole is None:
        return None
    (_, _), (a, b), _ = cv2.fitEllipse(details.hole.contour)
    return (a + b) / 2.0 * mm_per_px


def reevaluate(cycles: list[dict]) -> list[dict]:
    cfg = load_config()
    pipe = InspectionPipeline(cfg)
    by_run = {r["run"]: r for r in cycles if r["run"]}
    res = []
    for d in sorted(RUNS.iterdir()):
        img_path = d / "steps" / "m3_01_original.jpg"
        if not img_path.exists():
            continue
        img = cv2.imread(str(img_path))
        row = {"run": d.name, "clock": f"{d.name[:2]}:{d.name[2:4]}"}
        c = by_run.get(d.name)
        row["csv_hole"] = c["hole"] if c else None
        row["csv_good"] = c["good"] if c else ""
        try:
            det = pipe.process(img)
        except InspectionError as e:
            row["error"] = str(e)
            res.append(row)
            continue
        r = det.result
        mmpp = cfg["inspection"]["part_height_mm"] / det.part_box[3]
        row.update(serial=r.serial_number, conf=round(det.ocr_confidence, 3),
                   notch=r.notch_present, good=r.is_good, reasons="; ".join(r.reasons),
                   hole_circle=r.hole_diameter_mm, hole_ellipse=old_ellipse_mm(det, mmpp))
        res.append(row)
        print(f"  {d.name}: {'GOOD' if r.is_good else 'BAD '} ser={r.serial_number} "
              f"conf={det.ocr_confidence:.2f} ell={row['hole_ellipse'] or 0:.3f} "
              f"circ={row['hole_circle'] or 0:.3f} csv={row['csv_hole']} {row['reasons']}")
    OUT.mkdir(parents=True, exist_ok=True)
    keys = ["run", "clock", "csv_hole", "csv_good", "hole_ellipse", "hole_circle", "serial", "conf",
            "notch", "good", "reasons", "error"]
    with open(OUT / f"eval_{DAY}_reeval.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, keys, delimiter=";", extrasaction="ignore")
        w.writeheader()
        w.writerows(res)
    return res


def unique_images(res: list[dict]) -> list[dict]:
    """Läufe ohne neues Bauteil fotografieren dasselbe Teil erneut -> Duplikate (gleiche Messung)
    für die Statistik zusammenfassen: ein Eintrag je Zyklus mit Prüfung im Protokoll."""
    return [r for r in res if r.get("csv_hole") is not None and "error" not in r]


def plot_holes(res: list[dict], nominal: float, tol: float) -> None:
    rows = unique_images(res)
    x = list(range(1, len(rows) + 1))
    fig, ax = plt.subplots(figsize=(6.3, 3.0))
    ax.axhspan(nominal - tol, nominal + tol, color="#2a9d8f", alpha=0.12, lw=0)
    ax.axhline(nominal, color="#2a9d8f", lw=0.8, ls="--")
    ax.axhline(nominal - tol, color="#2a9d8f", lw=0.8)
    ax.text(len(rows) + 0.4, nominal - tol, "untere\nToleranzgrenze", fontsize=7, va="center",
            color="#2a9d8f")
    ax.plot(x, [r["hole_ellipse"] for r in rows], "o", mfc="white", mec="#e76f51", ms=5,
            label="Ellipsen-Fit (bisher)")
    ax.plot(x, [r["hole_circle"] for r in rows], "o", color="#264653", ms=4,
            label="Kreis-Fit ohne Reflexionspunkte")
    for i, r in enumerate(rows, 1):
        if not r.get("serial"):
            ax.annotate("Teil kopfüber:\nRückseite geprüft", (i, r["hole_circle"]), (i + 3.5, 9.345),
                        fontsize=6.5, arrowprops=dict(arrowstyle="-", lw=0.6, color="0.4"))
    ax.set_xticks(x, [r["clock"] for r in rows], rotation=90, fontsize=6.5)
    ax.set_xlabel("Zyklus (Uhrzeit)", fontsize=8)
    ax.set_ylabel("Lochdurchmesser / mm", fontsize=8)
    ax.set_xlim(0.3, len(rows) + 3.2)
    ax.set_ylim(9.3, 10.1)
    ax.tick_params(axis="y", labelsize=7)
    ax.legend(fontsize=7, loc="upper left", frameon=False, ncol=2)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.tight_layout()
    FIG.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG / "lochdurchmesser_20261126.pdf")
    fig.savefig(FIG / "lochdurchmesser_20261126.png", dpi=200)
    plt.close(fig)


def stats(res: list[dict], nominal: float, tol: float) -> None:
    rows = unique_images(res)
    for key in ("hole_ellipse", "hole_circle"):
        v = [r[key] for r in rows if r[key]]
        inside = sum(abs(h - nominal) <= tol for h in v)
        print(f"  {key}: n={len(v)} {min(v):.3f}..{max(v):.3f} Mittel {mean(v):.3f} "
              f"Median {median(v):.3f} s={stdev(v):.3f} in Toleranz {inside}/{len(v)}")
    good = sum(bool(r.get("good")) for r in rows)
    print(f"  Urteil neu (aktueller Code): gut {good}/{len(rows)}")
    conf = [r["conf"] for r in rows]
    print(f"  OCR-Konfidenz neu: min {min(conf):.2f} Median {median(conf):.2f}")


def crop_part(img, pad=0.06):
    h, w = img.shape[:2]
    return img[int(0.42 * h):int(0.88 * h), int(0.06 * w):int(0.94 * w)]


def before_after(run: str) -> None:
    """Dieselbe Lochkontur (Prüfbild 09:45, damals Schlechtteil): links Ellipsen-Fit über alle
    Konturpunkte, rechts Kreis-Fit nach Verwerfen der durch die Spiegelung nach innen gezogenen
    Punkte (gleicher Algorithmus wie m3_inspection.features._outer_circle_diameter)."""
    import numpy as np
    from matplotlib.patches import Circle, Ellipse
    from m3_inspection.features import _fit_circle

    cfg = load_config()
    ic = cfg["inspection"]
    img = cv2.imread(str(RUNS / run / "steps" / "m3_01_original.jpg"))
    det = InspectionPipeline(cfg).process(img)
    mmpp = ic["part_height_mm"] / det.part_box[3]
    p = det.hole.contour.reshape(-1, 2).astype(float)
    (ex, ey), (ea, eb), eang = cv2.fitEllipse(det.hole.contour)
    keep = p
    for _ in range(5):
        cx, cy, r = _fit_circle(keep)
        outer = p[np.hypot(p[:, 0] - cx, p[:, 1] - cy) > 0.98 * r]
        if len(outer) < 0.3 * len(p):
            break
        keep = outer
    cx, cy, r = _fit_circle(keep)
    dropped = p[np.hypot(p[:, 0] - cx, p[:, 1] - cy) <= 0.98 * r]

    m = 1.25 * r
    x0, y0 = int(cx - m), int(cy - m)
    crop = cv2.cvtColor(img[y0:int(cy + m), x0:int(cx + m)], cv2.COLOR_BGR2RGB)
    fig, axs = plt.subplots(1, 2, figsize=(6.3, 3.2))
    titles = (f"Ellipsen-Fit über alle Konturpunkte\n{(ea + eb) / 2 * mmpp:.2f} mm → Schlechtteil",
              f"Kreis-Fit ohne Reflexionspunkte\n{2 * r * mmpp:.2f} mm → Gutteil")
    for ax, title in zip(axs, titles):
        ax.imshow(crop)
        ax.set_title(title.replace(".", ","), fontsize=8)
        ax.axis("off")
    axs[0].plot(p[:, 0] - x0, p[:, 1] - y0, ".", color="#ffd166", ms=1.2)
    axs[0].add_patch(Ellipse((ex - x0, ey - y0), ea, eb, angle=eang, fill=False, ec="#e76f51", lw=1.6))
    axs[1].plot(keep[:, 0] - x0, keep[:, 1] - y0, ".", color="#ffd166", ms=1.2, label="genutzt")
    axs[1].plot(dropped[:, 0] - x0, dropped[:, 1] - y0, ".", color="#bbbbbb", ms=1.2,
                label="verworfen (Spiegelung)")
    axs[1].add_patch(Circle((cx - x0, cy - y0), r, fill=False, ec="#06d6a0", lw=1.6))
    axs[1].legend(fontsize=6.5, loc="lower center", markerscale=6, frameon=True, ncol=2)
    fig.tight_layout(pad=0.3)
    fig.savefig(FIG / "loch_vorher_nachher.png", dpi=250, bbox_inches="tight")
    plt.close(fig)


def pipeline_strip(run: str, names: list[tuple[str, str]], out: str, cols: int = 4) -> None:
    rows_n = (len(names) + cols - 1) // cols
    fig, axs = plt.subplots(rows_n, cols, figsize=(6.3, 1.25 * rows_n * 6.3 / cols / 1.6))
    for ax in axs.flat:
        ax.axis("off")
    for ax, (fn, label) in zip(axs.flat, names):
        img = cv2.imread(str(RUNS / run / "steps" / fn))
        if img.ndim == 2 or img.shape[2] == 1:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        ax.imshow(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        ax.set_title(label, fontsize=7)
    fig.tight_layout(pad=0.3)
    fig.savefig(FIG / out, dpi=250, bbox_inches="tight")
    plt.close(fig)


def failure_cases() -> None:
    """Die beiden Fehlerbilder des Tages: Hand verdeckt Marker 2 beim Nachlegen (Abbruch vor dem
    Greifen) und Teil kopfüber eingelegt (Prüfung der Rückseite -> Schlechtteil)."""
    fig, axs = plt.subplots(1, 2, figsize=(6.3, 2.3), gridspec_kw={"width_ratios": [1.33, 1.78]})
    a = cv2.imread(str(RUNS / "111559_c006" / "steps" / "m1_02_aruco_markers.jpg"))
    b = cv2.imread(str(RUNS / "112017_c003" / "steps" / "m3_01_original.jpg"))
    h, w = b.shape[:2]
    b = b[int(0.40 * h):int(0.90 * h), int(0.06 * w):int(0.96 * w)]
    for ax, img, t in ((axs[0], a, "a) Hand über Marker 2: Abbruch vor dem Greifen"),
                       (axs[1], b, "b) Teil kopfüber: Rückseite ohne Etikett und Kerbe")):
        ax.imshow(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        ax.set_title(t, fontsize=7.5)
        ax.axis("off")
    fig.tight_layout(pad=0.3)
    fig.savefig(FIG / "fehlerfaelle_20261126.png", dpi=250, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    failure_cases()
    cycles = read_cycles()
    print("== Zyklusprotokoll")
    summarise_cycles(cycles)
    print("== Nachauswertung Prüfbilder")
    res = reevaluate(cycles)
    ic = load_config()["inspection"]
    stats(res, ic["hole_nominal_mm"], ic["hole_tolerance_mm"])
    plot_holes(res, ic["hole_nominal_mm"], ic["hole_tolerance_mm"])
    before_after("094541_c001")
    pipeline_strip("114227_c001", [
        ("m3_01_original.jpg", "1 Original"), ("m3_04_part_closed.png", "2 Bauteilmaske"),
        ("m3_05_part_box.jpg", "3 Bauteil + Maßstab"), ("m3_06_label_roi.jpg", "4 Etikett (OCR)"),
        ("m3_08_hole_mask.png", "5 Lochmaske"), ("m3_09_hole_candidates.jpg", "6 Lochkandidaten"),
        ("m3_13_notch_candidates.jpg", "7 Kerbe"), ("m3_14_result.jpg", "8 Ergebnis")],
        "m3_pipeline_20261126.png")
    pipeline_strip("114227_c001", [
        ("m1_01_original.jpg", "1 Original"), ("m1_02_aruco_markers.jpg", "2 ArUco-Marker"),
        ("m1_03_rectified.jpg", "3 Entzerrt"), ("m1_04_part_mask.png", "4 Farbmaske"),
        ("m1_07_part_closed.png", "5 Bereinigt"), ("m1_08_part_candidates.jpg", "6 Kandidaten"),
        ("m1_09_part_pose.jpg", "7 Pose + Fase"), ("m1_10_result.jpg", "8 Ergebnis")],
        "m1_pipeline_20261126.png")
    print(f"Abbildungen in {FIG}")


if __name__ == "__main__":
    main()

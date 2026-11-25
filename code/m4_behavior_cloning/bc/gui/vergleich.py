"""Modellvergleich an der Anlage (Anwender 2026-11-24).

Mehrere Policies an DENSELBEN Lagen: je Lage faehrt jedes Modell nacheinander
``fahrten`` Mal an (Probegriff "objekt", ohne Experte -- die Policy haelt den
gewaehlten Abstand ueber dem Objekt, dann senkrecht hoch und zurueck zum
Start). Danach legt der Experte das Teil an eine neue Lage (``infer.py
--nur-umlegen``), und alles wiederholt sich:

    Lage 0: A, A, B, B, C, C, umlegen
    Lage 1: A, A, B, B, C, C, umlegen
    ...

Jede Fahrt ist ein eigener Aufruf von apps/infer.py (``--episodes 1``):
frisch verbunden fuhr die Policy an der Anlage zuverlaessig an, die zweite
Fahrt im selben Prozess nicht immer (Befund 2026-11-24, "arm steht"). Der
Reiter (bc/gui/tab_comparison.py) startet die Aufrufe nacheinander -- STOPP
beendet so die laufende Fahrt selbst, nicht nur ein Steuerprogramm darueber.

Qt-frei: Plan, Kommandozeilen, Auswertung je Fahrt und je Modell.
"""

import csv
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from . import operation

FAHRT, UMLEGEN = "fahrt", "umlegen"

#: Ordner der Vergleiche, relativ zum Arbeitsordner
ROOT = "vergleiche"

CSV_COLUMNS = ("lage", "modell", "fahrt", "erfolg", "bewertung", "quer_mm", "laengs_mm",
               "spiel_min_mm", "gruende", "xy_mm", "dz_mm", "drehung_grad",
               "tisch_min_mm", "takte", "vorhersage_ms", "ueberlaeufe", "stopp", "rueckzug",
               "griff_x_mm", "griff_y_mm", "pick_x_mm", "pick_y_mm", "pick_drehung_grad",
               "trainingsabstand_mm", "trainingslagen_umkreis", "ordner")

#: Lage gilt als "bekannt", wenn eine Trainingsepisode des Modells naeher als
#: so viel daneben gegriffen hat (nur xy: bc_policy.json fuehrt die Drehung
#: der Trainingslagen nicht mit)
KNOWN_RADIUS_M = 0.02
#: Trainingsdichte je Fahrt: Trainingslagen des Modells in diesem Umkreis
DENSITY_RADIUS_M = 0.03
#: Feldgroesse der Heatmap in der Draufsicht
HEAT_CELL_M = 0.02


@dataclass
class Step:
    kind: str           # FAHRT oder UMLEGEN
    lage: int
    model: str          # Checkpoint (Pfad wie in der Auswahl)
    index: int = 0      # Fahrt dieses Modells an dieser Lage
    out: str = ""       # Protokollordner, relativ zum Vergleichsordner
    target: list = None  # UMLEGEN: vorab geplante Ablagepose (7,), sonst None

    @property
    def label(self):
        if self.kind == UMLEGEN:
            return "Lage %d: Experte legt um" % (self.lage + 1)
        return "Lage %d: %s, Fahrt %d" % (self.lage + 1, model_name(self.model), self.index + 1)


def model_name(model):
    """Anzeigename: Ordner des Laufs (``checkpoints/G2/policy`` -> G2)."""
    path = Path(str(model).replace("\\", "/"))
    if path.name == "policy":
        path = path.parent
    if path.parent.name == "checkpoints" and path.name.startswith("step_"):
        return "%s/%s" % (path.parent.parent.name, path.name)
    return path.name


def plan(models, fahrten, lagen):
    """Alle Schritte in Reihenfolge. Nach der letzten Lage wird nicht umgelegt."""
    models = [m for m in models if m]
    if not models:
        raise ValueError("kein Modell gewaehlt")
    if fahrten < 1 or lagen < 1:
        raise ValueError("Fahrten und Lagen muessen mindestens 1 sein")
    names = [model_name(m) for m in models]
    if len(set(names)) != len(names):
        raise ValueError("zwei Modelle mit demselben Namen: %s" % ", ".join(names))
    steps = []
    for lage in range(lagen):
        for model, name in zip(models, names):
            for k in range(fahrten):
                steps.append(Step(FAHRT, lage, model, k,
                                  "lage_%02d/%s_fahrt%d" % (lage + 1, name, k + 1)))
        if lage + 1 < lagen:
            steps.append(Step(UMLEGEN, lage, models[0], 0, "lage_%02d/umlegen" % (lage + 1)))
    return steps


def step_argv(step, root, probe_gap_mm, regrasp=True, **common):
    """Kommandozeile fuer apps/infer.py. ``common``: wie operation.infer_argv
    (robot_kind, camera_specs, override, glaettung, real_robot, ...)."""
    out = Path(root) / step.out
    if step.kind == FAHRT:
        return operation.infer_argv(
            step.model, episodes=1, known_pose=True, probe="objekt",
            probe_gap_mm=probe_gap_mm, expert=False, camera_check="warnen",
            out=out, **common)
    argv = operation.infer_argv(
        step.model, episodes=1, known_pose=True, probe="objekt",
        probe_gap_mm=probe_gap_mm, expert=True, regrasp=regrasp, camera_check="aus",
        out=out, **common)
    argv = argv + ["--nur-umlegen"]
    if step.target is not None:
        argv += ["--ablage-pose", ",".join("%.6f" % float(v) for v in step.target)]
    return argv


def attach_targets(steps, planned):
    """Vorab geplante Lagen an die Umlege-Schritte haengen: nach Lage k wird an
    ``planned[k]`` (Lage k+2) gelegt. Fehlt eine, waehlt der Experte selbst."""
    for step in steps:
        if step.kind == UMLEGEN and step.lage < len(planned):
            step.target = [float(v) for v in planned[step.lage]["pose"]]
    return steps


def plan_poses(known, count, rng, history=(), center_shift_deg=None, reachable=None):
    """``count`` Lagen nacheinander wie der Experte (bc/known_pose.new_place_pose):
    jede zaehlt fuer die naechste als belegt, dazu die frueheren Ablagen
    (``history``). ``reachable(pose) -> bool``: Kandidaten, die nicht passen,
    werden uebersprungen. Rueckgabe Liste ``{"pose", "xy", "turn_deg"}``.
    """
    from dataclasses import replace

    from .. import known_pose

    reference = np.asarray(known.pick, dtype=float).copy()
    current, used, out = known, list(history), []
    for _ in range(int(count)):
        chosen = None
        for pose, xy, turn in known_pose.new_place_pose(current, reference, rng, used_xy=used,
                                                        center_shift_deg=center_shift_deg):
            if reachable is None or reachable(pose):
                chosen = (pose, xy, turn)
                break
        if chosen is None:
            break
        pose, xy, turn = chosen
        out.append({"pose": [float(v) for v in pose], "xy": (float(xy[0]), float(xy[1])),
                    "turn_deg": float(turn)})
        used.append(xy)
        current = replace(current, pick=np.asarray(pose, dtype=float))
    return out


#: Lagenwahl im Vergleich: Raster (systematisch, Anwender 2026-11-24) oder Zufall wie der Experte
LAGEN_RASTER, LAGEN_ZUFALL = "raster", "zufall"
#: kleinster Rasterabstand -- darunter wird nicht weiter verdichtet
GRID_MIN_SPACING_M = 0.005
#: Schrittweite der Ersatzdrehungen, wenn die Wunschdrehung nicht geht (Kamera/IK)
GRID_TURN_STEP_DEG = 5.0
_GOLDEN = (np.sqrt(5.0) - 1.0) / 2.0


def plan_grid_poses(known, count, center_shift_deg=None, reachable=None, yaw_range_deg=None):
    """``count`` Lagen systematisch auf einem Raster (Anwender 2026-11-24).

    Bereich wie beim Experten (Tischpunkte minus Randabstand, ohne Sperrzonen).
    Der Rasterabstand richtet sich nach ``count``: vom Wert, bei dem ``count``
    Punkte die Flaeche gleichmaessig fuellen, wird so lange verkleinert, bis
    genug erlaubte Punkte da sind -- mehr Lagen, engeres Raster. Sind es mehr
    Punkte als noetig, bleiben die am weitesten auseinander liegenden
    (beginnend weit weg von der Startlage, ``known.pick``). Reihenfolge
    schlangenfoermig Reihe fuer Reihe (kurze Umlegewege). Drehung gleichmaessig
    ueber den Drehbereich (Goldener-Schnitt-Folge), deterministisch; geht die
    Wunschdrehung nicht (Kamera am Rand, ``reachable``), die naechste im
    Raster ``GRID_TURN_STEP_DEG``. Rueckgabe wie :func:`plan_poses` plus
    ``raster_mm``.
    """
    from ..auto_layout import Coverage, place_pose
    from ..table import align_pose, yaw_deg
    from .. import config

    count = int(count)
    if count <= 0:
        return []
    if not known.region or len(known.region) < 3:
        raise ValueError("Raster braucht mindestens drei Tischpunkte")
    reference = np.asarray(known.pick, dtype=float)
    height = known.pick_above_table_m
    yaw_range = float(config.AUTO_YAW_RANGE_DEG if yaw_range_deg is None else yaw_range_deg)
    cov = Coverage(known.region, yaw_deg(reference, known.table), keepouts=known.keepouts or (),
                   yaw_range_deg=yaw_range, rng=np.random.default_rng(0), camera_guard=True,
                   center_shift_deg=center_shift_deg)
    upright = align_pose(reference, known.table, height)
    hull = np.asarray(cov.hull, dtype=float)
    x_lo, x_hi = hull[:, 0].min() + cov.margin, hull[:, 0].max() - cov.margin
    y_lo, y_hi = hull[:, 1].min() + cov.margin, hull[:, 1].max() - cov.margin
    area = max(1e-6, (x_hi - x_lo) * (y_hi - y_lo))
    centre = cov.center_shift
    steps = int(np.floor(yaw_range / GRID_TURN_STEP_DEG))
    offsets = sorted((k * GRID_TURN_STEP_DEG for k in range(-steps, steps + 1)), key=abs)

    def wish_turn(k):
        return centre + yaw_range * (2.0 * ((0.5 + k * _GOLDEN) % 1.0) - 1.0)

    def pose_for(xy, k):
        want = wish_turn(k)
        for off in [0.0] + [o for o in offsets if o != 0.0]:
            turn = want + off
            if abs(turn - centre) > yaw_range + 1e-6:
                continue
            pose = place_pose(upright, known.table, xy, turn, height)
            if cov.camera_blocked(pose) or (reachable is not None and not reachable(pose)):
                continue
            return pose, turn
        return None

    spacing = 1.2 * np.sqrt(area / count)
    while spacing >= GRID_MIN_SPACING_M:
        nx = int(np.floor((x_hi - x_lo) / spacing)) + 1
        ny = int(np.floor((y_hi - y_lo) / spacing)) + 1
        x0 = x_lo + 0.5 * ((x_hi - x_lo) - (nx - 1) * spacing)
        y0 = y_lo + 0.5 * ((y_hi - y_lo) - (ny - 1) * spacing)
        cand = [(i, j, np.array([x0 + i * spacing, y0 + j * spacing]))
                for j in range(ny) for i in range(nx)]
        cand = [c for c in cand if cov.allowed(c[2])]
        bad = set()
        while len(cand) - len(bad) >= count:
            pool = [c for n, c in enumerate(cand) if n not in bad]
            pts = np.array([c[2] for c in pool])
            # am weitesten auseinander, beginnend weit weg von der Startlage
            dist = np.linalg.norm(pts - reference[:2], axis=1)
            chosen = []
            for _ in range(count):
                k = int(np.argmax(dist))
                chosen.append(k)
                dist = np.minimum(dist, np.linalg.norm(pts - pts[k], axis=1))
                dist[chosen] = -1.0
            sel = sorted((pool[k] for k in chosen),
                         key=lambda c: (c[1], c[0] if c[1] % 2 == 0 else -c[0]))
            out, failed = [], None
            for k, (i, j, xy) in enumerate(sel):
                got = pose_for(xy, k)
                if got is None:
                    failed = (i, j)
                    break
                pose, turn = got
                out.append({"pose": [float(v) for v in pose], "xy": (float(xy[0]), float(xy[1])),
                            "turn_deg": float(turn), "raster_mm": round(1e3 * spacing, 1)})
            if failed is None:
                return out
            bad.add(next(n for n, c in enumerate(cand) if (c[0], c[1]) == failed))
        spacing *= 0.93
    raise ValueError("Kein Raster mit %d erlaubten Lagen (Bereich zu klein, Sperrzonen, "
                     "Erreichbarkeit?)" % count)


def training_xy(info):
    """Greiflagen (x, y) aller Trainingsepisoden eines Modells, oder None.

    Ganz oder gar nicht (Anwender 2026-11-24): nur wenn fuer JEDE Episode des
    Datensatzes eine Greifpose vorliegt -- eine Teilmenge liesse eine Lage
    faelschlich "unbekannt" aussehen.
    """
    grasps = ((info or {}).get("reference") or {}).get("grasp_tcp") or []
    episodes = ((info or {}).get("dataset") or {}).get("episodes")
    if not grasps or episodes is None or len(grasps) != int(episodes):
        return None
    if any(g is None or len(g) < 2 for g in grasps):
        return None
    return np.asarray([[float(g[0]), float(g[1])] for g in grasps], dtype=float)


def training_density(xy, train, radius=None):
    """Trainingslagen des Modells im Umkreis ``radius`` um ``xy``; None ohne Abdeckung."""
    if train is None or xy is None:
        return None
    radius = DENSITY_RADIUS_M if radius is None else float(radius)
    return int(np.sum(np.linalg.norm(train - np.asarray(xy, dtype=float)[:2], axis=1) <= radius))


def heat_grid(train, cell=None):
    """Heatmap der Trainingslagen: ``{"x0", "y0", "cell", "counts"}`` (counts[i][j]:
    Feld i in x, j in y) -- oder None ohne Abdeckung."""
    if train is None or len(train) == 0:
        return None
    cell = HEAT_CELL_M if cell is None else float(cell)
    x0, y0 = (np.floor(train.min(axis=0) / cell) * cell).tolist()
    idx = np.floor((train - [x0, y0]) / cell).astype(int)
    nx, ny = idx.max(axis=0) + 1
    counts = np.zeros((nx, ny), dtype=int)
    np.add.at(counts, (idx[:, 0], idx[:, 1]), 1)
    return {"x0": float(x0), "y0": float(y0), "cell": cell, "counts": counts.tolist()}


def training_distance(xy, train):
    """Abstand (m) von ``xy`` zur naechsten Trainingslage; None ohne Abdeckung."""
    if train is None or xy is None or len(train) == 0:
        return None
    return float(np.min(np.linalg.norm(train - np.asarray(xy, dtype=float)[:2], axis=1)))


def evaluate(step, summary, code):
    """Ergebnis eines Schritts: ``(zeile | None, abbruchgrund | None)``.

    Abgebrochen wird, sobald der Arm nicht sicher wieder am Start steht oder
    die Steuerung nicht mitgemacht hat -- der naechste Schritt finge sonst
    an einer unbekannten Stelle an (Befund 2026-11-24: Rueckzug hing ueber
    dem Objekt, der naechste Lauf fuhr per PTP durchs Teil).
    """
    if code != 0 or not summary:
        return None, "%s: abgebrochen (Rueckgabewert %s)" % (step.label, code)
    if step.kind == UMLEGEN:
        result = summary.get("umlegen") or {}
        if not result.get("ok"):
            return None, "%s: %s" % (step.label, result.get("result") or "nicht umgelegt")
        return None, None
    episodes = summary.get("episodes") or []
    if not episodes:
        return None, "%s: keine Fahrt (Kamerapruefung oder Start gescheitert)" % step.label
    ep = episodes[0]
    lage = ep.get("lage") or {}
    at = lage.get("predicted") or lage.get("at_stop") or {}
    pick = lage.get("pick") or [None, None]
    pose = (lage.get("predicted") or {}).get("pose") or [None, None]
    check = ep.get("grasp_check") or lage.get("grasp_check") or {}
    row = {
        "lage": step.lage + 1,
        "modell": model_name(step.model),
        "fahrt": step.index + 1,
        "erfolg": bool(ep.get("success")),
        # Griffpruefung (bc/known_pose.grasp_check, Anwender 2026-11-25)
        "bewertung": ep.get("grasp_level") or ("erfolg" if ep.get("success") else "kein_erfolg"),
        "quer_mm": _mm(check.get("quer_m")),
        "laengs_mm": _mm(check.get("laengs_m")),
        "spiel_min_mm": _mm(check.get("spiel_min_m")),
        "gruende": "; ".join(check.get("gruende") or ()),
        "xy_mm": _mm(ep.get("grasp_error_m")),
        "dz_mm": _mm(at.get("dz_m")),
        "drehung_grad": _num(at.get("yaw_deg")),
        "tisch_min_mm": _mm(lage.get("table_min_m")),
        "takte": ep.get("steps"),
        "vorhersage_ms": _num(ep.get("predict_ms_median")),
        "ueberlaeufe": ep.get("pacer_overruns"),
        "stopp": ep.get("stop_reason"),
        "rueckzug": ep.get("rueckzug"),
        "griff_x_mm": _mm(pose[0]),
        "griff_y_mm": _mm(pose[1]),
        "pick_x_mm": _mm(pick[0]),
        "pick_y_mm": _mm(pick[1]),
        "pick_drehung_grad": _num(lage.get("pick_yaw_deg")),
        "ordner": step.out,
    }
    stop = str(ep.get("stop_reason") or "")
    retreat = str(ep.get("rueckzug") or "")
    if stop.startswith("arm steht"):
        return row, "%s: %s" % (step.label, stop)
    if not retreat.startswith("ohne Experte"):
        return row, "%s: Arm nicht sicher am Start (%s)" % (step.label, retreat or stop)
    return row, None


def aggregate(rows, models=None):
    """Kennzahlen je Modell (Reihenfolge wie ``models``, sonst wie die Zeilen)."""
    order = [model_name(m) for m in models] if models else []
    for row in rows:
        if row["modell"] not in order:
            order.append(row["modell"])
    out = []
    for name in order:
        mine = [r for r in rows if r["modell"] == name]
        xy = _values(mine, "xy_mm")
        yaw = [abs(v) for v in _values(mine, "drehung_grad")]
        out.append({
            "modell": name,
            "fahrten": len(mine),
            "erfolg": sum(1 for r in mine if r["erfolg"]),
            "warnung": sum(1 for r in mine if r.get("bewertung") == "warnung"),
            "lagen": len({r["lage"] for r in mine}),
            "xy_median_mm": _stat(xy, np.median),
            "xy_mittel_mm": _stat(xy, np.mean),
            "xy_max_mm": _stat(xy, np.max),
            "xy_streuung_mm": _spread_within_lage(mine),
            "drehung_median_grad": _stat(yaw, np.median),
            "dz_median_mm": _stat(_values(mine, "dz_mm"), np.median),
            "takte_median": _stat(_values(mine, "takte"), np.median),
        })
    return out


def write_results(root, rows, stats, meta=None):
    """``vergleich.csv`` (je Fahrt) und ``vergleich.json`` (je Modell + Rahmen)."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    with open(root / "vergleich.csv", "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter=";")
        writer.writerow(CSV_COLUMNS)
        for row in rows:
            writer.writerow(["" if row.get(c) is None else row.get(c) for c in CSV_COLUMNS])
    data = {"modelle": stats, "fahrten": rows}
    data.update(meta or {})
    (root / "vergleich.json").write_text(json.dumps(data, indent=2, ensure_ascii=False),
                                         encoding="utf-8")


def stats_row(stat):
    """Zeile fuer die Tabelle im Reiter."""
    def fmt(value, unit=""):
        return "-" if value is None else "%.1f%s" % (value, unit)
    return [stat["modell"], "%d" % stat["fahrten"],
            "%d / %d" % (stat["erfolg"], stat["fahrten"]),
            "%d" % stat.get("warnung", 0),
            fmt(stat["xy_median_mm"], " mm"), fmt(stat["xy_max_mm"], " mm"),
            fmt(stat["xy_streuung_mm"], " mm"), fmt(stat["drehung_median_grad"], "°"),
            fmt(stat["dz_median_mm"], " mm"), fmt(stat["takte_median"])]


STATS_HEADER = ["Modell", "Fahrten", "Erfolg", "davon Warnung", "xy Median", "xy max",
                "Streuung je Lage", "Drehung Median", "dz Median", "Takte"]


def result_text(row):
    """Ergebnis einer Fahrt: Stufe der Griffpruefung (ohne Angabe wie bisher)."""
    level = row.get("bewertung")
    if level == "warnung":
        return "Erfolg mit Warnung"
    if level == "erfolg" or (level is None and row["erfolg"]):
        return "Erfolg"
    return "kein Erfolg"


def run_row(row):
    def fmt(value, unit=""):
        return "-" if value is None else "%.1f%s" % (value, unit)
    return ["%d" % row["lage"], row["modell"], "%d" % row["fahrt"],
            result_text(row), fmt(row.get("quer_mm"), " mm"), fmt(row.get("laengs_mm"), " mm"),
            fmt(row.get("spiel_min_mm"), " mm"), fmt(row["xy_mm"], " mm"),
            fmt(row["drehung_grad"], "°"), fmt(row["dz_mm"], " mm"),
            fmt(row.get("trainingsabstand_mm"), " mm"),
            "-" if row.get("trainingslagen_umkreis") is None
            else "%d" % row["trainingslagen_umkreis"],
            "-" if row["takte"] is None else "%d" % row["takte"],
            operation.stop_text(row["stopp"])]


RUNS_HEADER = ["Lage", "Modell", "Fahrt", "Ergebnis", "quer", "längs", "Spiel min", "xy", "Drehung", "dz",
               "Trainingsabstand", "Training ≤3 cm", "Takte", "Stopp"]


def lagen_view(rows, plan_xy=(), current=None, training=None, placed_xy=None):
    """Lagen fuer die Draufsicht (bc/gui/pick_view.PickState.lagen).

    ``plan_xy``: je Lage (ab Lage 1) ``(xy, yaw_deg)`` -- vorab geplant;
    angefahrene Lagen nehmen den PICK der ersten Fahrt dort. ``current``:
    Index der Lage in Arbeit (0-basiert), sonst die letzte angefahrene.
    ``placed_xy``: gerade umgelegt (ohne Plan) -- wird die aktuelle Lage.
    ``training``: {Modell: (N, 2) | None} -> ``known`` "alle"/"keins"/"teils"/None.
    """
    visited = {}
    for row in rows:
        if row["lage"] not in visited and row.get("pick_x_mm") is not None:
            visited[row["lage"]] = ((row["pick_x_mm"] / 1e3, row["pick_y_mm"] / 1e3),
                                    row.get("pick_drehung_grad"))
    count = max([len(plan_xy)] + list(visited))
    if placed_xy is not None and count <= max(list(visited) or [0]):
        count += 1
    if current is None:
        current = (count - 1) if placed_xy is not None else (max(visited) - 1 if visited else 0)
    out = []
    for k in range(count):
        if (k + 1) in visited:
            xy, yaw = visited[k + 1]
            status = "erledigt"
        elif k < len(plan_xy):
            xy, yaw = plan_xy[k]
            status = "geplant"
        elif placed_xy is not None and k == count - 1:
            xy, yaw, status = placed_xy, None, "geplant"
        else:
            continue
        if k == current:
            status = "aktuell"
        out.append({"xy": (float(xy[0]), float(xy[1])), "yaw_deg": yaw, "label": str(k + 1),
                    "current": k == current, "status": status,
                    "known": _known_by(xy, training)})
    return out


def _known_by(xy, training):
    if not training:
        return None
    flags = [training_distance(xy, train) <= KNOWN_RADIUS_M
             for train in training.values() if train is not None]
    if not flags:
        return None
    return "alle" if all(flags) else "keins" if not any(flags) else "teils"


# -- intern -------------------------------------------------------------------

def _mm(value):
    return None if value is None else round(1e3 * float(value), 2)


def _num(value):
    return None if value is None else round(float(value), 2)


def _values(rows, key):
    return [float(r[key]) for r in rows if r.get(key) is not None]


def _stat(values, fn):
    return round(float(fn(values)), 2) if values else None


def _spread_within_lage(rows):
    """Wie weit liegen die Fahrten EINES Modells an derselben Lage auseinander?

    Groesster Abstand zwischen den vorhergesagten Griffpunkten (x, y) einer
    Lage, gemittelt ueber die Lagen -- die Varianz von Lauf zu Lauf, ohne
    den gemeinsamen Versatz gegen PICK.
    """
    spans = []
    for lage in {r["lage"] for r in rows}:
        points = [(r["griff_x_mm"], r["griff_y_mm"]) for r in rows
                  if r["lage"] == lage and r.get("griff_x_mm") is not None
                  and r.get("griff_y_mm") is not None]
        if len(points) >= 2:
            pts = np.asarray(points, dtype=float)
            spans.append(max(float(np.hypot(*(a - b))) for i, a in enumerate(pts)
                             for b in pts[i + 1:]))
    return round(float(np.mean(spans)), 2) if spans else None

"""Geschlossene Auswertung einer Policy-Fahrt in der MuJoCo-Taktiksimulation.

In der Sim ist die Wahrheit bekannt: wo das Objekt liegt (Testlage), ob es am
Ende im Greifer haengt, wie der Greifer beim Schliessen dazu stand. Je Fahrt
(``bewerte``) und je Satz (``zusammenfassen``):

=====================  ==========================================================
griff                  Objekt haengt am Ende am Greifer UND ist >= 20 mm angehoben
greifbefehl            die Policy hat ueberhaupt geschlossen
annaeherung_mm         kleinster Abstand TCP -- Soll-Greifpunkt (3D) der Lage
greif_xy_mm            TCP xy beim ersten Schliessen gegen die Objektmitte
greif_quer/laengs_mm   dasselbe zerlegt: quer = Backenachse, laengs = Objekt-x
gier_fehler_grad       Greifer-y gegen Objekt-x beim Schliessen, -180..180
                       (mit Fase: 180 Grad verdreht ist auch ein Fehler)
tisch_min_mm           kleinster Abstand Werkzeugspitze -- Tischebene
unter_tisch / ..._10   tisch_min < 0 bzw. < -10 mm
sprung_max_rad         je Gelenk max |Ziel der Policy - Ist| (Grenze 0,35)
sprung_takte           je Gelenk: Takte ueber SERVO_MAX_TARGET_GAP_RAD
quer_p95_mm            Abstand des TCP zur idealen Bahn der Lage (p95, bis Griff)
welligkeit_mm          p95 der Abweichung nach Abzug eines gleitenden Mittels
                       (1 s) -- wie Berichte/.../skripte/schwingen.py
abbruch                endstellung | max_steps | sprung | servoguard |
                       kollisionsmodell | geofence | stopp | sonst
=====================  ==========================================================

Ideale Bahn: ``testlagen.py`` hat sie je Lage mit dem Planer der Aufnahme
gerechnet (ohne Rauschen, ohne Anflug-Versatz). Querabweichung heisst hier
also "Abstand zur Bahn, die der Experte gefahren waere".
"""

import math
import re

import numpy as np

from .. import config

GRIFF_HUB_M = 0.020


def _abbruch(stop_reason):
    text = str(stop_reason or "")
    if text in ("endstellung", "max_steps", "griff"):
        return text
    if "von der Ist-Stellung entfernt" in text:
        return "sprung"
    if "servo_j abgelehnt" in text or "Action ungueltig" in text:
        return "servoguard"
    if text.startswith("geofence"):
        return "geofence"
    if text.startswith("stopp"):
        return "stopp"
    if "Kollision" in text or "Tisch" in text or "Sperrzone" in text or "Hindernis" in text:
        return "kollisionsmodell"
    return "sonst"


def _sprung_gelenk(stop_reason):
    m = re.search(r"Gelenk (\d)", str(stop_reason or ""))
    return int(m.group(1)) if m and "von der Ist-Stellung entfernt" in str(stop_reason) else None


def _closest_vectors(points, path):
    """Vektor vom naechsten Punkt der Polylinie ``path`` zu jedem Punkt."""
    if len(path) == 1:
        return points - path[0]
    a, b = path[:-1], path[1:]
    ab = b - a
    denom = np.maximum((ab * ab).sum(axis=1), 1e-12)
    ap = points[:, None, :] - a[None, :, :]
    t = np.clip((ap * ab[None]).sum(axis=2) / denom[None], 0.0, 1.0)
    closest = a[None] + t[..., None] * ab[None]
    d = points[:, None, :] - closest
    k = np.argmin(np.linalg.norm(d, axis=2), axis=1)
    return d[np.arange(len(points)), k]


def _smooth(x, w=int(config.CONTROL_RATE_HZ)):
    if len(x) < 2:
        return x
    k = np.ones(w) / w
    return np.stack([np.convolve(np.pad(x[:, i], (w // 2, w // 2), mode="edge"), k, mode="valid")[:len(x)]
                     for i in range(x.shape[1])], 1)


def bewerte(log, lage, welt, plane):
    """Kennzahlen einer Fahrt. ``log``: Rueckgabe von infer.run_episode,
    ``lage``: Eintrag aus testlagen_v1.json, ``welt``: die Sim-Welt NACH der
    Fahrt, ``plane``: Tischebene (bc.table.TablePlane)."""
    def arr(key, cols=None):
        v = log.get(key)
        v = np.zeros((0,) if cols is None else (0, cols)) if v is None else np.asarray(v, dtype=float)
        return v.reshape(-1, cols) if cols else v.ravel()

    joints = arr("joints", 6)
    tcp = arr("tcp", 7)[:, :3]
    if log.get("final_tcp") is not None:
        tcp_all = np.vstack([tcp, np.asarray(log["final_tcp"], dtype=float)[None, :3]])
    else:
        tcp_all = tcp
    action = arr("action", 7)
    grip = arr("gripper_cmd")
    obj = lage["objekt"]
    obj_xy = np.array([obj["x_m"], obj["y_m"]])
    pick = np.asarray(lage["pick_pose"][:3], dtype=float)
    out = {"lage": lage["id"], "takte": int(len(joints)),
           "stop_reason": str(log.get("stop_reason")), "abbruch": _abbruch(log.get("stop_reason")),
           "sprung_gelenk_abbruch": _sprung_gelenk(log.get("stop_reason"))}

    # Griff: Zustand der Welt am Ende
    x, y, _yaw, T_obj = welt.objekt_lage()
    z_tisch = plane.height_at(x, y) - plane.correction_at(x, y)
    hub = float(T_obj[2, 3] - z_tisch - welt.par["objekt"]["hoehe_m"] / 2)
    out["griff"] = bool(welt.angeheftet is not None and hub >= GRIFF_HUB_M)
    out["objekt_hub_mm"] = round(1e3 * hub, 1)
    events = [e for e in welt.ereignisse]
    out["greifer_ereignisse"] = [[round(t, 3), k] for t, k, _xy in events][-6:]

    if len(tcp_all):
        out["annaeherung_mm"] = round(1e3 * float(np.min(np.linalg.norm(tcp_all - pick, axis=1))), 1)
        h = np.array([p[2] - (plane.height_at(p[0], p[1]) - plane.correction_at(p[0], p[1]))
                      for p in tcp_all])
        out["tisch_min_mm"] = round(1e3 * float(h.min()), 1)
        out["unter_tisch"] = bool(h.min() < 0.0)
        out["unter_tisch_10"] = bool(h.min() < -0.010)

    # Erstes Schliessen (der erste Greiferbefehl ist der Startzustand)
    close = [i for i in range(1, len(grip)) if grip[i] >= 0.5 > grip[i - 1]]
    out["greifbefehl"] = bool(close)
    k_grasp = close[0] if close else None
    if k_grasp is not None:
        d = tcp[k_grasp, :2] - obj_xy
        G = welt.greifer_matrix(joints[k_grasp])
        gx, gy = G[:3, 0], G[:3, 1]
        yaw_o = math.radians(obj["gier_grad"])
        ox = np.array([math.cos(yaw_o), math.sin(yaw_o)])
        out["greif_takt"] = int(k_grasp)
        out["greif_xy_mm"] = round(1e3 * float(np.linalg.norm(d)), 1)
        jaw = gx[:2] / max(np.linalg.norm(gx[:2]), 1e-9)
        out["greif_quer_mm"] = round(1e3 * float(np.dot(d, jaw)), 1)
        out["greif_laengs_mm"] = round(1e3 * float(np.dot(d, ox)), 1)
        a = math.degrees(math.atan2(gy[1], gy[0]) - math.atan2(ox[1], ox[0]))
        out["gier_fehler_grad"] = round((a + 180.0) % 360.0 - 180.0, 1)
        h_grasp = tcp[k_grasp, 2] - (plane.height_at(*tcp[k_grasp, :2])
                                     - plane.correction_at(*tcp[k_grasp, :2]))
        out["greif_hoehe_mm"] = round(1e3 * float(h_grasp), 1)

    # Spruenge je Gelenk: Ziel der Policy gegen die Ist-Stellung
    if len(action):
        gap = np.abs(action[:, :6] - joints)
        out["sprung_max_rad"] = [round(float(v), 3) for v in gap.max(axis=0)]
        out["sprung_takte"] = [int(v) for v in (gap > config.SERVO_MAX_TARGET_GAP_RAD).sum(axis=0)]

    # Querabweichung und Welligkeit gegen die ideale Bahn (bis zum Griff)
    ideal = np.asarray(lage.get("ideal_tcp_mm") or [], dtype=float) / 1e3
    if len(ideal) and len(tcp):
        n_ideal = lage.get("ideal_greiftakt") or len(ideal)
        n_run = (k_grasp + 1) if k_grasp is not None else len(tcp)
        dev = _closest_vectors(tcp[:n_run], ideal[:n_ideal + 1])
        out["quer_p95_mm"] = round(1e3 * float(np.percentile(np.linalg.norm(dev, axis=1), 95)), 1)
        out["welligkeit_mm"] = round(
            1e3 * float(np.percentile(np.linalg.norm(dev - _smooth(dev), axis=1), 95)), 1)
    return out


def zusammenfassen(rows):
    """Kennzahlen ueber alle Fahrten eines Modells."""
    if not rows:
        return {}
    n = len(rows)

    def med(key):
        vals = [r[key] for r in rows if r.get(key) is not None]
        return round(float(np.median(vals)), 1) if vals else None

    def p90(key, absolute=False):
        vals = [abs(r[key]) if absolute else r[key] for r in rows if r.get(key) is not None]
        return round(float(np.percentile(vals, 90)), 1) if vals else None

    abbruch = {}
    for r in rows:
        abbruch[r["abbruch"]] = abbruch.get(r["abbruch"], 0) + 1
    sprung = np.array([r.get("sprung_takte") or [0] * 6 for r in rows])
    return {
        "fahrten": n,
        "griff_quote": round(sum(r["griff"] for r in rows) / n, 3),
        "greifbefehl_quote": round(sum(r["greifbefehl"] for r in rows) / n, 3),
        "annaeherung_mm_median": med("annaeherung_mm"),
        "greif_xy_mm_median": med("greif_xy_mm"),
        "greif_xy_mm_p90": p90("greif_xy_mm"),
        "gier_fehler_grad_median_abs": (round(float(np.median([abs(r["gier_fehler_grad"]) for r in rows
                                                               if r.get("gier_fehler_grad") is not None])), 1)
                                        if any(r.get("gier_fehler_grad") is not None for r in rows) else None),
        "gier_fehler_ueber_90": sum(1 for r in rows if r.get("gier_fehler_grad") is not None
                                    and abs(r["gier_fehler_grad"]) > 90),
        "tisch_min_mm_median": med("tisch_min_mm"),
        "unter_tisch": sum(1 for r in rows if r.get("unter_tisch")),
        "unter_tisch_10": sum(1 for r in rows if r.get("unter_tisch_10")),
        "fahrten_mit_sprung_je_gelenk": [int(v) for v in (sprung > 0).sum(axis=0)],
        "quer_p95_mm_median": med("quer_p95_mm"),
        "welligkeit_mm_median": med("welligkeit_mm"),
        "abbruch": abbruch,
    }


def zeile(r):
    """Eine Ergebniszeile fuer das Terminal."""
    def mm(k):
        return "-" if r.get(k) is None else "%.1f" % r[k]
    return ("Lage %2d: %s, Annaeherung %s mm, Greif-xy %s mm, Gier %s Grad, Tisch min %s mm, "
            "quer p95 %s mm, Welligkeit %s mm, Ende %s"
            % (r["lage"], "GRIFF" if r["griff"] else ("geschlossen" if r["greifbefehl"] else "kein Griff"),
               mm("annaeherung_mm"), mm("greif_xy_mm"), mm("gier_fehler_grad"), mm("tisch_min_mm"),
               mm("quer_p95_mm"), mm("welligkeit_mm"), r["abbruch"]))

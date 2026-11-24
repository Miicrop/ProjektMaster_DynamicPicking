"""Abnahmebilder der MuJoCo-Taktiksimulation (Phase 0/1).

    python -m bc.sim_mujoco.abnahme referenz           # Render neben Referenzbild
    python -m bc.sim_mujoco.abnahme episode --daten data_sim_mujoco/2026-11-20 --episode 0

``referenz``: Arm an CLEAR_FOV (dort entstehen die Referenzbilder beim Start
jedes Aufrufs), beide Kameras in 320 x 240 neben den Referenzbildern vom
19.11. Dazu die ArUco-Marker in Referenz und Render (Render dafuer in
720 x 540) -- der mittlere Abstand der Markerecken in Pixeln (umgerechnet auf
320 x 240) ist die Zahl zu "Ausschnitt und Blickwinkel grob gleich".

``episode``: Wrist- und Szenenbilder einer aufgenommenen Episode in
gleichen Abstaenden (wie sie im Datensatz stehen).

Ausgabe nach ``Dokumentation/Bilder/MuJoCo`` (``--ziel``).
"""

import argparse
import json
from pathlib import Path

import numpy as np

ZIEL = Path("Dokumentation/Bilder/MuJoCo")
REF = Path("data/2026-11-19/referenzbilder")
#: Referenz an CLEAR_FOV (Marker sichtbar) und mit gegriffenem Teil
REF_CLEAR = "2026-11-19_15-22-00_B66"
REF_HELD = "2026-11-19_14-07-47_B34"


def _bgr(img):
    import cv2

    return cv2.cvtColor(img, cv2.COLOR_RGB2BGR)


def _label(img, text):
    import cv2

    out = img.copy()
    cv2.rectangle(out, (0, 0), (8 + 7 * len(text), 16), (0, 0, 0), -1)
    cv2.putText(out, text, (4, 12), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1, cv2.LINE_AA)
    return out


def _marker_error(ref_path, sim_img_rgb):
    """Mittlerer Eckenabstand (px bei 320 x 240) der gemeinsam gefundenen Marker."""
    import cv2

    from .kalibrierung import detect

    ref, size = detect(ref_path)
    sim, sim_size = detect(_bgr(sim_img_rgb))
    common = sorted(set(ref) & set(sim))
    if not common:
        return None, 0, len(ref), len(sim)
    s_ref = 320.0 / size[0]
    s_sim = 320.0 / sim_size[0]
    d = [np.linalg.norm(ref[i] * s_ref - sim[i] * s_sim, axis=1).mean() for i in common]
    return float(np.mean(d)), len(common), len(ref), len(sim)


def referenz(ziel=ZIEL, verbose=True):
    import cv2

    from ..clock import SimClock
    from .szene import Welt

    ziel = Path(ziel)
    ziel.mkdir(parents=True, exist_ok=True)
    welt = Welt(clock=SimClock())
    q = np.asarray(welt.punkte["punkte"]["CLEAR_FOV"]["joints"], dtype=float)
    welt.setze_gelenke(q, welt.now())
    rows, report = [], {}
    for cam in ("scene", "wrist"):
        ref_path = REF / ("%s_%s.png" % (REF_CLEAR, cam))
        ref = cv2.resize(cv2.imread(str(ref_path)), (320, 240), interpolation=cv2.INTER_AREA)
        sim = welt.render(cam, 320, 240)
        big = welt.render(cam, 720, 540)
        err, n, n_ref, n_sim = _marker_error(ref_path, big)
        report[cam] = {"marker_px": err, "marker_gemeinsam": n, "ref": n_ref, "sim": n_sim}
        cv2.imwrite(str(ziel / ("render_%s_clear_fov.png" % cam)), _bgr(sim))
        rows.append(np.hstack([_label(ref, "Referenz %s (B66)" % cam),
                               _label(_bgr(sim), "MuJoCo %s, CLEAR_FOV" % cam)]))
    # Wrist-Licht schaltbar (Versuch V4): dieselbe Stellung ohne Licht
    welt.wrist_licht = False
    dark = welt.render("wrist", 320, 240)
    welt.wrist_licht = True
    cv2.imwrite(str(ziel / "render_wrist_clear_fov_licht_aus.png"), _bgr(dark))
    report["wrist_licht"] = {"helligkeit_an": float(welt.render("wrist", 320, 240).mean()),
                             "helligkeit_aus": float(dark.mean())}
    # Gegriffenes Teil vor der Wrist-Kamera (wie B34): an PICK greifen, anheben
    pick = np.asarray(welt.punkte["punkte"]["PICK"]["joints"], dtype=float)
    welt.setze_gelenke(pick, welt.now())
    welt.greifer(True)
    pose = welt.tool_matrix(pick)
    from ..adapters.sim_robot import SimRobot  # nur fuer die IK

    class _Ik(SimRobot):
        def _frame_transform(self, joints, frame):
            T = super()._frame_transform(joints, frame)
            return T @ welt.tool_offset if frame == "tool" else T

    from .. import geometry

    target = np.concatenate([pose[:3, 3] + [0, 0, 0.05], geometry.matrix_to_quat(pose[:3, :3])])
    welt.setze_gelenke(_Ik().ik(target, pick), welt.now())
    ref = cv2.resize(cv2.imread(str(REF / ("%s_wrist.png" % REF_HELD))), (320, 240),
                     interpolation=cv2.INTER_AREA)
    held = welt.render("wrist", 320, 240)
    cv2.imwrite(str(ziel / "render_wrist_gegriffen.png"), _bgr(held))
    rows.append(np.hstack([_label(ref, "Referenz wrist, Teil gegriffen (B34)"),
                           _label(_bgr(held), "MuJoCo wrist, 5 cm ueber PICK")]))
    out = ziel / "abnahme_render_referenz.png"
    cv2.imwrite(str(out), np.vstack(rows))
    (ziel / "abnahme_render_referenz.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    welt.close()
    if verbose:
        for cam, r in report.items():
            if cam == "wrist_licht":
                print("Wrist-Licht: mittlere Helligkeit an %.1f, aus %.1f"
                      % (r["helligkeit_an"], r["helligkeit_aus"]))
                continue
            print("%s: Marker %d gemeinsam (Referenz %d, Render %d), mittlerer Eckenabstand %s px "
                  "(320 x 240)" % (cam, r["marker_gemeinsam"], r["ref"], r["sim"],
                                   "-" if r["marker_px"] is None else "%.1f" % r["marker_px"]))
        print("-> %s" % out)
    return report


def episode(daten, index, ziel=ZIEL, n=6, verbose=True):
    import cv2

    daten = Path(daten)
    entry = json.loads((daten / "index.json").read_text(encoding="utf-8"))["episodes"][index]
    folder = daten / entry["dir"]
    meta = json.loads((folder / "meta.json").read_text(encoding="utf-8"))
    with np.load(folder / "arrays.npz") as z:
        wrist = z["observation__images__wrist"]
        scene = z["observation__images__scene"]
        grip = z["action"][:, 6]
    steps = np.linspace(0, len(wrist) - 1, n).astype(int)
    rows = []
    for name, imgs in (("wrist", wrist), ("scene", scene)):
        rows.append(np.hstack([_label(_bgr(imgs[i]), "%s Takt %d%s" % (
            name, i, " zu" if grip[i] >= 0.5 else "")) for i in steps]))
    ziel = Path(ziel)
    ziel.mkdir(parents=True, exist_ok=True)
    out = ziel / ("episode_%s_%s.png" % (daten.name, entry["dir"]))
    cv2.imwrite(str(out), np.vstack(rows))
    for i in steps[[0, len(steps) // 2, -1]]:
        for name, imgs in (("wrist", wrist), ("scene", scene)):
            cv2.imwrite(str(ziel / ("episode_%s_%s_takt%03d_%s.png" % (daten.name, entry["dir"], i, name))),
                        _bgr(imgs[i]))
    if verbose:
        md = meta["metadata"]
        print("%s: %d Takte, Erfolg %s, Drehversatz %s, Lage x %.0f y %.0f mm -> %s"
              % (entry["dir"], len(wrist), meta.get("success"), md.get("anflug_drehung_grad"),
                 1e3 * md["object_xy_m"][0], 1e3 * md["object_xy_m"][1], out))
    return out


def experte(auswahl="0-9", ziel=ZIEL, verbose=True):
    """Auswertung an Expertenfahrten pruefen: die ideale Bahn jeder Testlage
    (ohne Rauschen) durch den Recorder -- Griff muss gelingen, Greif-xy und
    Gier-Fehler muessen klein sein. Das ist die Abnahme von auswertung.py."""
    from ..clock import SimClock
    from ..adapters.mujoco_robot import MujocoRobot
    from ..noise import generate_plan
    from ..recorder import EpisodeRecorder
    from ..table import TablePlane
    from . import auswertung, testlagen

    data = testlagen.laden()
    lagen = testlagen.auswahl(data, auswahl)
    clock = SimClock()
    robot = MujocoRobot(clock=clock).connect()
    seq, resolved, kin, werkzeug = testlagen._planer(robot)
    plane = TablePlane.from_dict(robot.welt.punkte["table"])
    recorder = EpisodeRecorder(robot, [], clock)
    rows = []
    for lage in lagen:
        xy = np.array([lage["pick_pose"][0], lage["pick_pose"][1]])
        _info, (ideal, joints_ideal, waypoints, ws) = testlagen.plane_lage(
            robot, seq, resolved, kin, werkzeug, xy, lage["greifer_drehung_grad"], intern=True)
        plan = generate_plan(kin, ws, ideal, waypoints[0].joints, noise_scale=0.0,
                             joints_ideal=joints_ideal, rng=np.random.default_rng(0))
        robot.gripper_command(False)
        robot.objekt_fuer_griff(lage["pick_joints"])
        robot.move_to_joints(plan.joints_noisy[0])
        episode = recorder.record(plan)
        st = np.asarray(episode.arrays["observation.state"], dtype=float)
        act = np.asarray(episode.arrays["action"], dtype=float)
        log = {"joints": st[:, :6], "tcp": st[:, 6:13], "action": act, "gripper_cmd": act[:, 6],
               "final_tcp": robot.read_state().tcp_quat, "stop_reason": "endstellung"}
        r = auswertung.bewerte(log, lage, robot.welt, plane)
        rows.append(r)
        if verbose:
            print("   %s" % auswertung.zeile(r))
    z = auswertung.zusammenfassen(rows)
    Path(ziel).mkdir(parents=True, exist_ok=True)
    (Path(ziel) / "abnahme_auswertung_experte.json").write_text(
        json.dumps({"zusammenfassung": z, "fahrten": rows}, indent=1, ensure_ascii=False),
        encoding="utf-8")
    if verbose:
        print("Experte: %s" % json.dumps(z, ensure_ascii=False))
    return z, rows


def main(argv=None):
    parser = argparse.ArgumentParser(description="Abnahmebilder der MuJoCo-Taktiksimulation")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("referenz")
    p.add_argument("--ziel", default=str(ZIEL))
    p = sub.add_parser("experte")
    p.add_argument("--lagen", default="0-9")
    p.add_argument("--ziel", default=str(ZIEL))
    p = sub.add_parser("episode")
    p.add_argument("--daten", required=True)
    p.add_argument("--episode", type=int, default=0)
    p.add_argument("--ziel", default=str(ZIEL))
    args = parser.parse_args(argv)
    if args.cmd == "referenz":
        referenz(args.ziel)
    elif args.cmd == "experte":
        experte(args.lagen, args.ziel)
    else:
        episode(args.daten, args.episode, args.ziel)


if __name__ == "__main__":
    main()

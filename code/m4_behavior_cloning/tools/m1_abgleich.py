"""M1-Lokalisierung gegen PICK pruefen (vor der DAgger-Aufnahme, 2026-11-16).

Liegt das Teil genau am geteachten PICK, muss die Lokalisierung der Gruppe
(bc/lokalisierung.py: M1 + Greifkonvention von M2) denselben PICK ergeben.
Das Werkzeug zeigt die Abweichung (dx, dy, Drehung) und speichert das Bild
mit der Erkennung von M1.

Ohne Roboter, auf einem Bild (z. B. data/<Tag>/referenzbilder/*_scene.png):
    python tools/m1_abgleich.py --bild <datei.png> [--pick-aus <episode/meta.json>]

Live (Steuerung verbunden, Szenenkamera von M4):
    python tools/m1_abgleich.py --camera scene=daheng:EBK24100634@60 [--fahren] [--real-robot]
    --fahren: vorher an die Fotostellung (Default Steuerungspunkt Home). Ohne
    --fahren muss der Arm schon dort stehen -- das Werkzeug bewegt dann nichts.
"""

import argparse
import json
import sys
import time
from pathlib import Path

import _bootstrap  # noqa: F401

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "apps"))

from bc import config, lokalisierung  # noqa: E402


def parse_args():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--bild", help="Vollbild der Szenenkamera (PNG/JPG) statt Live")
    p.add_argument("--pick-aus", help="mit --bild: meta.json einer Episode (PICK + Tischpunkte)")
    p.add_argument("--camera", action="append", default=[],
                   help="Live: Kamera wie apps/infer.py, z. B. scene=daheng:<Seriennummer>@60")
    p.add_argument("--foto-punkt", default=config.LOCALIZE_POINT)
    p.add_argument("--fahren", action="store_true", help="vorher an die Fotostellung fahren")
    p.add_argument("--real-robot", action="store_true")
    p.add_argument("--out", default="logs/m1_abgleich", help="Ordner fuer das Bild")
    return p.parse_args()


def table_from_points(points):
    from bc.table import fit_table

    pts = [v["pose_quat"] if isinstance(v, dict) else v for k, v in points.items()
           if k.startswith("ID")]
    return fit_table(pts) if len(pts) >= 3 else None


def report(loc, pick, plane, localizer, image_rgb, out):
    import cv2

    print(loc.describe())
    if pick is not None and plane is None:
        # ohne Tischpunkte: waagrechter Tisch PICK_HEIGHT_DEFAULT unter PICK
        from bc.table import fit_table

        z = float(pick[2]) - config.PICK_HEIGHT_DEFAULT_M
        plane = fit_table([[pick[0] + dx, pick[1] + dy, z, 1, 0, 0, 0]
                           for dx in (-0.1, 0.1) for dy in (-0.1, 0.1)])
        print("Hinweis: keine Tischpunkte -- waagrechter Tisch angenommen")
    if pick is not None:
        pose = lokalisierung.pick_pose(loc, pick, plane)
        d = lokalisierung.compare(pose, pick, plane)
        print("Gegen PICK: dx %.1f mm, dy %.1f mm (xy %.1f mm), Drehung %.1f Grad"
              % (1e3 * d["dx_m"], 1e3 * d["dy_m"], 1e3 * d["xy_m"], d["yaw_deg"]))
        verdict = "OK" if d["xy_m"] <= 0.003 and abs(d["yaw_deg"]) <= 3.0 else "PRUEFEN"
        print("Ergebnis: %s (Teil lag am PICK? dann <= 3 mm / 3 Grad erwartet)" % verdict)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    path = out / ("m1_abgleich_%s.jpg" % time.strftime("%Y-%m-%d_%H-%M-%S"))
    bgr = cv2.cvtColor(np.asarray(image_rgb, dtype=np.uint8), cv2.COLOR_RGB2BGR)
    cv2.imwrite(str(path), localizer.last_result.overlay_image(bgr))
    print("Bild: %s" % path)


def main():
    args = parse_args()
    localizer = lokalisierung.M1Localizer()
    if args.bild:
        import cv2

        bgr = cv2.imread(args.bild)
        if bgr is None:
            raise SystemExit("Bild nicht lesbar: %s" % args.bild)
        image = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        pick, plane = None, None
        if args.pick_aus:
            meta = json.loads(Path(args.pick_aus).read_text(encoding="utf-8"))
            points = (meta.get("metadata") or meta).get("points") or {}
            pick = np.asarray(points["PICK"]["pose_quat"], dtype=float)
            plane = table_from_points(points)
        try:
            loc = localizer.locate(image)
        except lokalisierung.LocalizationError as exc:
            raise SystemExit(str(exc))
        report(loc, pick, plane, localizer, image, args.out)
        return

    import infer
    from bc.adapters import camera_configs, open_robot, start_cameras
    from bc.clock import RealClock

    if args.real_robot:
        infer.confirm_real_robot()
    robot = open_robot("neura", allow_real=args.real_robot)
    robot.connect(power_on=args.fahren, ensure_automatic=args.fahren)
    clock = RealClock()
    cfgs = [c for c in camera_configs("real", specs=args.camera) if c.name == "scene"]
    captures, _ = start_cameras("real", clock, specs=args.camera, cfgs=cfgs)
    try:
        joints, _ = robot.get_point(args.foto_punkt)
        away = float(np.max(np.abs(robot.read_state().joints - np.asarray(joints))))
        if away > config.START_POSE_TOL_RAD:
            if not args.fahren:
                raise SystemExit("Arm steht nicht an '%s' (%.3f rad) -- dorthin fahren oder --fahren"
                                 % (args.foto_punkt, away))
            print("an die Fotostellung '%s'" % args.foto_punkt)
            robot.move_to_joints(np.asarray(joints))
        image = lokalisierung.full_frame(captures[0])
        loc = localizer.locate(image)
        pick = np.asarray(robot.get_point("PICK")[1], dtype=float)
        names = ["ID%d" % k for k in range(9)]
        points = {}
        for name in names:
            try:
                points[name] = robot.get_point(name)[1]
            except KeyError:
                pass
        report(loc, pick, table_from_points(points), localizer, image, args.out)
    except lokalisierung.LocalizationError as exc:
        raise SystemExit(str(exc))
    finally:
        for cap in captures:
            cap.stop()
        robot.close()


if __name__ == "__main__":
    main()

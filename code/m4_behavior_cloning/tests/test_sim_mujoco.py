"""MuJoCo-Taktiksimulation (bc/sim_mujoco, adapters/mujoco_robot.py, cam_mujoco.py).

Die Port-Zusagen prueft die Contract-Suite (``run_all.py --robot=mujoco
--camera=mujoco contract.test_robot_contract contract.test_camera_contract``).
Hier das, was die Taktiksimulation darueber hinaus verspricht: Kette wie die
Pipeline, Nachlauf statt Sprung, Greifen = Anheften, Bilder folgen dem Arm.

Ohne installiertes ``mujoco`` werden die Tests uebersprungen (nicht im
Standardlauf von run_all.py -- die Aufnahme-Laptops brauchen MuJoCo nicht).
"""

import _paths  # noqa: F401

import numpy as np

try:
    import mujoco  # noqa: F401

    HAVE_MUJOCO = True
except ImportError:  # pragma: no cover
    HAVE_MUJOCO = False

from bc import config
from bc.clock import SimClock


def _skip():
    if not HAVE_MUJOCO:
        import pytest

        pytest.skip("mujoco nicht installiert")


def _robot():
    from bc.adapters.mujoco_robot import MujocoRobot

    return MujocoRobot(clock=SimClock()).connect()


def test_kette_wie_pipeline():
    _skip()
    robot = _robot()
    rng = np.random.default_rng(3)
    for _ in range(10):
        q = rng.uniform(-1.2, 1.2, 6)
        robot.welt.setze_gelenke(q, robot._clock.now())
        p, R = robot.welt.tcp_site()
        T = robot._chain.fk(q) @ robot.welt.tool_offset
        assert np.linalg.norm(p - T[:3, 3]) < 1e-9
        assert np.abs(R - T[:3, :3]).max() < 1e-9
    # Werkzeug 197,5 mm vor dem Flansch
    q = robot.read_state().joints
    d = robot.fk(q, "tool")[:3] - robot.fk(q, "flange")[:3]
    assert abs(np.linalg.norm(d) - 0.1975) < 1e-9


def test_arm_laeuft_dem_sollwert_nach():
    _skip()
    robot = _robot()
    clock = robot._clock
    q0 = robot.read_state().joints
    robot.activate_servo()
    target = q0.copy()
    for k in range(1, 31):  # 0,5 s Rampe an Gelenk 6, 0,6 rad/s
        target[5] = q0[5] + 0.01 * k
        clock.sleep(1.0 / config.SERVO_RATE_HZ)
        robot.servo_j(target, [0.0] * 6, [0.0] * 6)
    lag = target[5] - robot.read_state().joints[5]
    assert 0.01 < lag < 0.15, lag  # haengt hinterher, aber nicht weit
    for _ in range(60):  # 1 s halten
        clock.sleep(1.0 / config.SERVO_RATE_HZ)
        robot.servo_j(target, [0.0] * 6, [0.0] * 6)
    assert abs(target[5] - robot.read_state().joints[5]) < 2e-3
    robot.deactivate_servo()


def test_greifen_heftet_an_und_legt_ab():
    _skip()
    robot = _robot()
    pick = robot.get_point("PICK")[0]
    robot.move_to_joints(pick)
    x0, y0, _ = robot.objekt_lage()
    robot.gripper_command(True)
    assert robot.griff_haelt()
    # anheben: Objekt kommt mit
    pose = robot.fk(pick, "tool")
    pose[0] += 0.05
    pose[2] += 0.08
    robot.move_to_joints(robot.ik(pose, pick))
    _x, _y, _yaw, T = robot.welt.objekt_lage()
    assert T[2, 3] > 0.07
    # oeffnen: liegt 5 cm weiter wieder auf dem Tisch
    robot.gripper_command(False)
    assert not robot.griff_haelt()
    x1, y1, _ = robot.objekt_lage()
    assert abs(x1 - x0 - 0.05) < 0.005 and abs(y1 - y0) < 0.005
    z_tisch = robot.welt.table.height_at(x1, y1) - robot.welt.table.correction_at(x1, y1)
    assert abs(robot.welt.objekt_lage()[3][2, 3] - z_tisch - 0.0075) < 1e-3


def test_greifer_verfehlt_versetztes_objekt():
    _skip()
    robot = _robot()
    pick = robot.get_point("PICK")[0]
    robot.move_to_joints(pick)
    x, y, yaw = robot.objekt_lage()
    robot.objekt_ablegen(x + 0.05, y, yaw)
    robot.gripper_command(True)
    assert not robot.griff_haelt()


def test_bilder_folgen_dem_arm():
    _skip()
    from bc.adapters import camera_config_for
    from bc.adapters.cam_mujoco import MujocoCamera

    robot = _robot()
    clock = robot._clock
    cams = {name: MujocoCamera(camera_config_for(name, "mujoco"), clock=clock, welt=robot.welt).open()
            for name in ("wrist", "scene")}
    first = {n: c.read() for n, c in cams.items()}
    for frame in first.values():
        assert frame.image.shape == (config.IMAGE_HEIGHT, config.IMAGE_WIDTH, 3)
        assert frame.image.dtype == np.uint8
        assert frame.timestamp == clock.now()
    robot.move_to_joints(robot.get_point("PICK")[0])
    second = {n: c.read() for n, c in cams.items()}
    for name in cams:
        diff = np.abs(first[name].image.astype(int) - second[name].image.astype(int)).mean()
        assert diff > 5, (name, diff)
    # gleiche Stellung -> gleiches Bild (deterministisch, keine Uhr im Bild)
    again = cams["scene"].read()
    assert np.array_equal(again.image, second["scene"].image)


def test_wrist_c2_dunkel_und_verrauscht():
    # Versuch V4: Licht aus + Verstaerkung -> ~0,43 der Helligkeit, Rauschen > 0
    _skip()
    from bc.adapters import camera_config_for, parse_camera_spec
    from bc.adapters.cam_mujoco import MujocoCamera

    assert parse_camera_spec("wrist=mujoco:c2") == ("wrist", "mujoco", "c2")
    robot = _robot()
    clock = robot._clock
    cfg = camera_config_for("wrist", "mujoco")
    hell = MujocoCamera(cfg, clock=clock, welt=robot.welt).open().read().image.astype(float)
    cfg.device = "c2"
    cam = MujocoCamera(cfg, clock=clock, welt=robot.welt).open()
    a, b = cam.read().image.astype(float), cam.read().image.astype(float)
    assert 0.35 < a.mean() / hell.mean() < 0.5, a.mean() / hell.mean()
    assert 1.0 < np.std(a - b) / np.sqrt(2) < 2.5
    assert cam.settings()["wrist_licht"] == "c2"
    robot.welt.wrist_licht = True


def test_verzoegerter_ensembler_wie_vm():
    # VM: Chunks 2 Takte nach der Beobachtung, meist 3 im Mittel; Greifer-Chunk
    # [0,0,0,0,1,1,1,1] mittelt dort zu 0,67 (schliesst), synchron nur zu 0,5.
    from bc.policy import ChunkEnsembler
    from bc.sim_mujoco.testfahrt import ensembler_klasse

    class Policy(object):
        def observe(self, obs):
            pass

        def snapshot(self, obs):
            return obs

        def predict_snapshot(self, obs):
            chunk = np.zeros((8, 7))
            chunk[4:, 6] = 1.0
            return chunk

        def reset(self):
            pass

    klasse = ensembler_klasse()
    verz = klasse(Policy(), replan_steps=2, decay=0.0)
    werte = [verz.next_action(None) for _ in range(12)]
    assert verz.last_count == 3 and verz.last_delay_steps == 2
    assert abs(werte[-1][6] - 2.0 / 3.0) < 1e-9
    sync = ChunkEnsembler(Policy(), replan_steps=2, decay=0.0)
    assert abs([sync.next_action(None) for _ in range(12)][-1][6] - 0.5) < 1e-9


def test_kamerazuordnung_mujoco():
    from bc.adapters import SOFT_BACKENDS, camera_config_for, parse_camera_spec

    assert parse_camera_spec("wrist=mujoco") == ("wrist", "mujoco", None)
    assert parse_camera_spec("wrist=mujoco:dunkel") == ("wrist", "mujoco", "dunkel")
    cfg = camera_config_for("scene", "mujoco")
    assert (cfg.backend, cfg.width, cfg.height) == ("mujoco", config.IMAGE_WIDTH, config.IMAGE_HEIGHT)
    assert "mujoco" in SOFT_BACKENDS
    try:
        parse_camera_spec("wrist=mujoco:blau")
        assert False, "ValueError erwartet"
    except ValueError:
        pass


def test_ik_analytische_jacobi_wie_numerisch():
    _skip()
    from bc.adapters.sim_robot import SimRobot

    robot = _robot()
    rng = np.random.default_rng(4)
    for _ in range(5):
        q = rng.uniform(-1.2, 1.2, 6)
        assert np.abs(robot._jacobian(q) - SimRobot._jacobian(robot, q)).max() < 1e-5


def test_ik_nahe_clear_fov():
    # Auf der PTP-Bahn ab CLEAR_FOV bleibt die gedaempfte Iteration bei ~0,02 mm
    # stehen; die Loesung muss trotzdem kommen (Rest < 0,1 mm), nicht IKError.
    _skip()
    robot = _robot()
    # Testlage 4, Schritt 14 der idealen Bahn: Startwert = Schritt 13
    q_seed = np.array([-0.207, -1.029, 1.904, -0.026, 1.675, 0.800])
    q_true = np.array([-0.214, -1.021, 1.905, -0.026, 1.672, 0.767])
    pose = robot.fk(q_true)
    q = robot.ik(pose, q_seed)
    q0 = q_seed
    assert np.linalg.norm(robot.fk(q)[:3] - pose[:3]) < 1e-4
    # wirklich unerreichbar: schnell und als IKError
    import time
    from bc.ports import IKError

    t0 = time.perf_counter()
    try:
        robot.ik(np.array([10.0, 10.0, 10.0, 1.0, 0.0, 0.0, 0.0]), q0)
        assert False, "IKError erwartet"
    except IKError:
        pass
    assert time.perf_counter() - t0 < 1.0


def test_testlagen_satz():
    _skip()
    from bc.sim_mujoco import testlagen

    data = testlagen.laden()
    lagen = data["lagen"]
    assert len(lagen) == testlagen.ANZAHL
    assert [l["id"] for l in lagen] == list(range(len(lagen)))
    assert [l["id"] for l in testlagen.auswahl(data, "2-4")] == [2, 3, 4]
    robot = _robot()
    lage = lagen[7]
    robot.objekt_fuer_griff(lage["pick_joints"])
    x, y, yaw = robot.objekt_lage()
    assert abs(x - lage["objekt"]["x_m"]) < 1e-4 and abs(y - lage["objekt"]["y_m"]) < 1e-4
    assert abs((yaw - lage["objekt"]["gier_grad"] + 180) % 360 - 180) < 0.05


def test_auswertung_griff_und_fehlgriff():
    _skip()
    from bc.sim_mujoco import auswertung, testlagen
    from bc.table import TablePlane

    lage = testlagen.laden()["lagen"][3]
    robot = _robot()
    plane = TablePlane.from_dict(robot.welt.punkte["table"])

    def fahrt(versatz_m):
        robot.gripper_command(False)
        robot.objekt_fuer_griff(lage["pick_joints"])
        pick = np.asarray(lage["pick_joints"], dtype=float)
        pose = robot.fk(pick)
        pose[0] += versatz_m
        q_grasp = robot.ik(pose, pick)
        pose[2] += 0.05
        q_up = robot.ik(pose, q_grasp)
        rows = []
        for q, g in ((q_grasp, 0.0), (q_grasp, 1.0), (q_up, 1.0)):
            robot.move_to_joints(q)
            robot.gripper_command(g >= 0.5)
            st = robot.read_state()
            rows.append((st.joints, st.tcp_quat, np.append(q, g), g))
        log = {"joints": np.array([r[0] for r in rows]), "tcp": np.array([r[1] for r in rows]),
               "action": np.array([r[2] for r in rows]), "gripper_cmd": np.array([r[3] for r in rows]),
               "final_tcp": robot.read_state().tcp_quat, "stop_reason": "endstellung"}
        return auswertung.bewerte(log, lage, robot.welt, plane)

    ok = fahrt(0.0)
    assert ok["griff"] and ok["greif_xy_mm"] < 0.5 and abs(ok["gier_fehler_grad"]) < 0.5
    assert ok["objekt_hub_mm"] > 40
    daneben = fahrt(0.04)
    assert not daneben["griff"] and daneben["greifbefehl"] and daneben["greif_xy_mm"] > 35
    z = auswertung.zusammenfassen([ok, daneben])
    assert z["griff_quote"] == 0.5 and z["fahrten"] == 2

"""Varianten, kontrollierter Zufall und gewoelbter Tisch (Anwender 2026-11-01).

bc/table.py (gewoelbte Flaeche), bc/auto_layout.py (Coverage, Varianten),
apps/record.py (Lage -> Varianten -> naechste Lage).
"""

import json

import _paths  # noqa: F401

import numpy as np

from bc import config, geometry
from bc.auto_layout import (
    Coverage,
    load_coverage,
    place_pose,
    variant_offsets,
    yaw_offset,
)
from bc.table import align_pose, clearance, fit_table, tilt_deg, yaw_deg

from test_auto_layout import _points, _record

DOWN = geometry.quat_from_axis_angle([1.0, 0.0, 0.0], np.pi)


def _grid(bulge=0.0, noise=0.0, seed=0, size=0.2, centre=(0.4, 0.0), z=0.011):
    """3x3-Raster, Mitte um ``bulge`` hoeher als die Ecken (Paraboloid)."""
    rng = np.random.default_rng(seed)
    out = []
    for u in (-1, 0, 1):
        for v in (-1, 0, 1):
            height = z + bulge * (1 - (u * u + v * v) / 2.0) + rng.normal(0, noise) if noise \
                else z + bulge * (1 - (u * u + v * v) / 2.0)
            out.append(np.r_[centre[0] + u * size / 2, centre[1] + v * size / 2, height, DOWN])
    return out


def test_curved_table_finds_the_bulge():
    table = fit_table(_grid(bulge=0.0015))
    assert table.curved and table.count == 9
    assert table.residual_m < 1e-6
    # Mitte 1,5 mm hoeher als die Ecken, gegen die beste Ebene etwa 1 mm Bauch
    assert np.isclose(table.height_at(0.4, 0.0) - table.height_at(0.3, -0.1), 0.0015)
    assert 0.0005 < table.bulge_m < 0.0015
    assert table.plane_residual_m > 0.0005
    # Senkrechte: in der Mitte gerade, am Rand nach aussen geneigt (Tisch faellt ab)
    assert np.allclose(table.normal_at(0.4, 0.0), [0, 0, 1], atol=1e-9)
    edge = table.normal_at(0.5, 0.0)
    assert edge[0] > 0
    assert "Bauch" in table.describe() and table.as_dict()["model"] == "gewoelbt"


def test_flat_or_noisy_points_stay_a_plane():
    flat = fit_table(_grid())
    assert not flat.curved and "eben" in flat.describe()
    # 0,2 mm Teach-Streuung: Woelbung bringt zu wenig -> Ebene
    noisy = fit_table(_grid(noise=0.0002, seed=3))
    assert not noisy.curved
    # vier Punkte: nie gewoelbt (zu wenige)
    corners = [p for k, p in enumerate(_grid(bulge=0.002)) if k in (0, 2, 6, 8)]
    assert not fit_table(corners).curved
    assert not fit_table(_grid(bulge=0.0015), curved=False).curved


def test_align_on_curved_table_follows_the_local_normal():
    table = fit_table(_grid(bulge=0.0015))
    pose = align_pose(np.r_[0.48, 0.05, 0.03, DOWN], table, 0.008)
    assert abs(clearance(table, pose) - 0.008) < 1e-9
    assert tilt_deg(pose, table) < 1e-6
    # gegen die Basis-z ist die Pose dort leicht geneigt (Tisch faellt nach aussen ab)
    rot = geometry.quat_to_matrix(pose[3:])
    assert np.degrees(np.arccos(abs(rot[2, 2]))) > 0.1
    turned = place_pose(pose, table, (0.35, -0.06), 20.0, 0.008)
    assert abs(clearance(table, turned) - 0.008) < 1e-9 and tilt_deg(turned, table) < 1e-6
    assert abs(yaw_offset(yaw_deg(turned, table), yaw_deg(pose, table)) - 20.0) < 0.2


def _square(half=0.15):
    return [np.r_[x, y, 0.0, DOWN] for x, y in
            ((0.4 - half, -half), (0.4 + half, -half), (0.4 + half, half), (0.4 - half, half))]


def test_coverage_fills_every_cell_before_repeating():
    cov = Coverage(_square(), base_yaw_deg=90.0, margin=0.03, yaw_range_deg=45.0,
                   cell_size=0.06, yaw_bins=6, rng=np.random.default_rng(1))
    assert cov.nx == cov.ny == 4 and len(cov.cells) == 16
    turns = []
    for _ in range(16):
        cell = cov.next_cell()
        xy = cov.point_in(cell)
        assert cov.cell_of(xy) == cell and cov.allowed(xy)
        turn = cov.next_turn()
        turns.append(turn)
        cov.add(xy, 90.0 + turn)
    assert sorted(cov.cell_count.values()) == [1] * 16
    # Drehung: 16 Lagen auf 6 Abschnitte -> jeder 2 oder 3 Mal
    assert min(cov.yaw_count) >= 2 and max(cov.yaw_count) <= 3
    assert all(abs(t) <= 45.0 for t in turns)
    assert "16 Felder" in cov.summary() and "leer 0" in cov.summary()


def test_coverage_prefers_the_far_side_and_respects_keepouts():
    from bc.table import Keepout

    zone = Keepout("IGNORE", (0.4, 0.0), half_size=0.03)
    cov = Coverage(_square(), base_yaw_deg=0.0, keepouts=[zone], margin=0.03,
                   rng=np.random.default_rng(2))
    for _ in range(5):
        cov.add((0.3, -0.1), 0.0)   # Ecke links unten belegt
    cell = cov.next_cell()
    centre = (cov.x_lo + (cell[0] + 0.5) * cov.cw, cov.y_lo + (cell[1] + 0.5) * cov.ch)
    assert centre[0] > 0.4 and centre[1] > 0.0   # gegenueber
    for _ in range(50):
        assert not zone.contains_xy(cov.point_in(cov.next_cell()))


def test_variant_offsets_are_spread():
    rng = np.random.default_rng(5)
    for n in (1, 2, 3, 4):
        offsets = variant_offsets(rng, n, 0.015, 15.0)
        assert len(offsets) == n
        for dx, dy, turn in offsets:
            assert 0.0075 - 1e-9 <= np.hypot(dx, dy) <= 0.015 + 1e-9
            assert 7.5 - 1e-9 <= abs(turn) <= 15.0 + 1e-9
        signs = [np.sign(t) for _, _, t in offsets]
        assert abs(sum(signs)) <= 1          # links und rechts ausgeglichen
    two = variant_offsets(np.random.default_rng(6), 2, 0.015, 15.0)
    # zwei Varianten zeigen in entgegengesetzte Richtungen
    assert np.dot(two[0][:2], two[1][:2]) < 0
    assert variant_offsets(rng, 0) == []


def test_load_coverage_reads_only_valid_episodes(tmp_path):
    for k, (xy, discarded) in enumerate(((None, False), ([0.4, 0.1], False),
                                         ([0.3, 0.0], True), ([0.5, -0.1], False))):
        folder = tmp_path / "tag" / ("ep_%05d" % k)
        folder.mkdir(parents=True)
        meta = {"discarded": discarded, "metadata": {}}
        if xy:
            meta["metadata"] = {"object_xy_m": xy, "object_yaw_deg": 30.0}
        (folder / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    found, files, seconds = load_coverage([tmp_path, tmp_path / "fehlt"])
    assert files == 4 and seconds < 5.0
    assert sorted(xy for xy, _ in found) == [(0.4, 0.1), (0.5, -0.1)]


def _metas(root):
    out = []
    for path in sorted((root / "data").glob("ep_*/meta.json")):
        out.append(json.loads(path.read_text(encoding="utf-8"))["metadata"])
    return out


def test_record_places_variants_and_then_changes_the_pose(tmp_path):
    points, _ = _points(size=0.12)
    error, log, opened = _record(tmp_path, ["--episodes", "3", "--lagen", "2"], points)
    assert error is None, log[-3000:]
    metas = _metas(tmp_path)
    assert [m["object_source"] for m in metas] == [
        "geteacht", "variante", "variante", "automatisch", "variante", "variante"]
    assert [m["variant_index"] for m in metas] == [0, 1, 2, 0, 1, 2]
    assert all(m["layout_mode"] == "varianten" for m in metas)
    # Lage = Block und Gruppe fuer die Validierungsaufteilung
    assert [m["block"] for m in metas] == ["B01"] * 3 + ["B02"] * 3
    assert len({m["repeat_group"] for m in metas[:3]}) == 1
    assert metas[0]["repeat_group"] != metas[3]["repeat_group"]
    # jede Fahrt eine eigene Pose, Varianten nahe ihrer Mitte
    xy = [np.asarray(m["object_xy_m"]) for m in metas]
    assert len({tuple(np.round(p, 4)) for p in xy}) == 6
    for centre, members in ((0, (1, 2)), (3, (4, 5))):
        for k in members:
            shift = np.linalg.norm(xy[k] - xy[centre])
            assert 0.5 * config.AUTO_VARIANT_SHIFT_M - 1e-3 < shift < config.AUTO_VARIANT_SHIFT_M + 1e-3
            turn = abs((metas[k]["object_yaw_deg"] - metas[centre]["object_yaw_deg"] + 90) % 180 - 90)
            assert 0.5 * config.AUTO_VARIANT_YAW_DEG - 0.2 < turn < config.AUTO_VARIANT_YAW_DEG + 0.2
        for k in members + (centre,):
            assert abs(metas[k]["pick_over_table_m"] - 0.008) < 5e-4
    # Rauschen: weiter auf jeder Fahrt, gestaffelt ueber den Lauf (6 Fahrten,
    # je eine aus jedem Sechstel)
    scales = sorted(m["noise_scale"] / m["noise_scale_max"] for m in metas)
    assert all(k / 6 <= s <= (k + 1) / 6 for k, s in enumerate(scales))
    assert metas[0]["noise_scale_mode"] == "gestaffelt ueber den Lauf"
    assert log.count("Ablegen: Variante") == 4
    assert "Umlegen: Objekt an Lage 2" in log and "Umlegen: Objekt an den geteachten PICK" in log
    assert "Abdeckung: 0 Lage(n) aus 0 Episode(n)" in log
    final = opened[-1].final_state
    assert np.allclose(final.joints, points["CLEAR_FOV"], atol=config.START_POSE_TOL_RAD)


def test_variants_grasp_at_the_taught_height(tmp_path):
    # Anlage 2026-11-02: PICK 6 mm ueber dem Tisch geteacht, Ablauf 8 mm --
    # Varianten und neue Lage muessen auf 6 mm greifen und ablegen, sonst
    # faellt das Objekt (zu hoch) oder wird am Ende eingedrueckt (zu tief)
    points, _ = _points(size=0.12, below=0.006)
    error, log, _ = _record(tmp_path, ["--episodes", "3", "--lagen", "2"], points)
    assert error is None, log[-3000:]
    metas = _metas(tmp_path)
    assert len(metas) == 6
    for m in metas:
        assert abs(m["pick_over_table_m"] - 0.006) < 5e-4, m["pick_over_table_m"]
    assert "HINWEIS: geteachter PICK liegt 6.0 mm ueber dem Tisch, Ablauf nennt 8.0 mm" in log


def test_fixed_pose_keeps_the_old_behaviour(tmp_path):
    points, _ = _points(size=0.12)
    error, log, _ = _record(tmp_path, ["--episodes", "2", "--feste-lage"], points)
    assert error is None, log[-2000:]
    metas = _metas(tmp_path)
    assert [m["object_source"] for m in metas] == ["geteacht", "geteacht"]
    assert metas[0]["object_xy_m"] == metas[1]["object_xy_m"]
    assert metas[0]["layout_mode"] == "feste_lage"
    assert "Ablegen: Variante" not in log


def test_second_run_counts_the_first(tmp_path):
    points, _ = _points(size=0.12)
    error, log, _ = _record(tmp_path, ["--episodes", "2", "--lagen", "2"], points)
    assert error is None, log[-2000:]
    error, log, _ = _record(tmp_path, ["--episodes", "1", "--lagen", "2",
                                       "--block", "B05"], points)
    assert error is None, log[-2000:]
    assert "Abdeckung: 4 Lage(n) aus 4 Episode(n)" in log


def test_put_back_to_a_variant_is_faster(tmp_path):
    from bc.put_back import plan_put_back
    from bc.collision import default_workspace
    from bc.kinematics import Kinematics
    from bc.sequence import parse_sequence, resolve_sequence
    from bc.adapters.sim_robot import SimRobot
    from bc.clock import SimClock
    from test_auto_layout import SEQ

    points, _ = _points()
    robot = SimRobot(clock=SimClock(), points=points).connect()
    resolved = resolve_sequence(parse_sequence(SEQ), robot)
    kin = Kinematics(robot)
    workspace = default_workspace(table_height_m=-1.0)
    slow = plan_put_back(kin, workspace, resolved.waypoints, fk=robot.fk, regrip=False,
                         slow_speed=0.02)
    fast = plan_put_back(kin, workspace, resolved.waypoints, fk=robot.fk, regrip=False,
                         slow=False)
    assert len(fast) < len(slow)
    # seit 2026-11-03 legt auch der Lagenwechsel mit Endanflug-Tempo ab
    default = plan_put_back(kin, workspace, resolved.waypoints, fk=robot.fk, regrip=False)
    assert len(default) == len(fast)


def test_record_logs_heights_at_grasp_and_place(tmp_path):
    # Anwender 2026-11-02: absolute z, Tischhoehe und Bewegung des Arms an
    # jedem Greiferwechsel -- beim Greifen (Episode) und beim Ablegen
    points, _ = _points(size=0.12)
    error, log, _ = _record(tmp_path, ["--episodes", "2", "--lagen", "1"], points)
    assert error is None, log[-3000:]
    metas = _metas(tmp_path)
    for m in metas:
        (grasp,) = m["greifer_hoehen"]
        assert grasp["greifer"] == "zu"
        assert abs(grasp["ueber_tisch_soll_mm"] - 8.0) < 0.5
        assert grasp["bewegung"] in ("steht", "hoch", "runter")
        for key in ("z_soll_mm", "z_ist_mm", "tisch_mm", "vz_mm_s", "nachlauf_mm"):
            assert key in grasp
    lines = [json.loads(line) for line in
             (tmp_path / "data" / "hoehen_protokoll.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [(l["fahrt"], l["greifer"]) for l in lines if l["fahrt"] == "episode"] == [
        ("episode", "zu")] * 2
    placed = [l for l in lines if l["fahrt"] == "zuruecklegen" and l["art"] == "ablegen"]
    # Ablage-Zugabe: oeffnen ueber der Greifhoehe
    assert len(placed) == 2 and all(
        abs(l["ueber_tisch_soll_mm"] - 8.0 - 1e3 * config.PUT_BACK_PLACE_OFFSET_M) < 0.1
        for l in placed)
    assert placed[0]["episode"] == "ep_00000"
    assert "Hoehe Greifen Greifer zu: z soll" in log and "Hoehe Ablegen Greifer auf" in log
    # zuletzt Umlegen an den geteachten PICK: mit Nachgreifen (zu, auf)
    assert [l["greifer"] for l in lines if l.get("art") == "nachgreifen"] == ["zu", "auf"]


def test_final_pose_becomes_the_new_pick(tmp_path):
    # Anwender 2026-11-03: am Ende an eine neue Lage und die als PICK
    # uebernehmen -- der naechste Lauf beginnt dort ohne Teachen
    points, _ = _points(size=0.12)
    taught = np.array(points["PICK"], dtype=float)
    saved = config.TOUCHUP_BACKUP_ROOT
    config.TOUCHUP_BACKUP_ROOT = str(tmp_path / "sicherungen")
    try:
        error, log, opened = _record(tmp_path, ["--episodes", "1", "--lagen", "1",
                                                "--schluss-lage", "neu"], points)
    finally:
        config.TOUCHUP_BACKUP_ROOT = saved
    assert error is None, log[-3000:]
    assert "Umlegen: Objekt an die Schluss-Lage (neuer PICK)" in log
    assert "PICK uebernommen: x" in log
    robot = opened[-1]
    new_pick = np.asarray(robot.point_record("PICK")["jointAngles"], dtype=float)
    assert float(np.max(np.abs(new_pick - taught))) > 1e-3
    # der Arm hat das Objekt genau dort abgelegt (Greifpose der Schluss-Lage)
    backups = list((tmp_path / "sicherungen").glob("*_PICK.json"))
    assert len(backups) == 1
    old = json.loads(backups[0].read_text(encoding="utf-8"))
    assert np.allclose(old["record"]["jointAngles"], taught)
    from bc.gui import recording

    line = [l for l in log.splitlines() if l.startswith("PICK uebernommen")][0]
    assert recording.adopted_pick_backup(line) == str(backups[0])


def test_final_pose_default_stays_at_the_taught_pick(tmp_path):
    points, _ = _points(size=0.12)
    taught = np.array(points["PICK"], dtype=float)
    error, log, opened = _record(tmp_path, ["--episodes", "1", "--lagen", "1"], points)
    assert error is None, log[-3000:]
    assert "PICK uebernommen" not in log
    assert np.allclose(opened[-1].point_record("PICK")["jointAngles"], taught)

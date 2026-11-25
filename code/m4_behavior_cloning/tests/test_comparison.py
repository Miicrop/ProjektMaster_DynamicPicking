"""Modellvergleich (bc/gui/vergleich.py, Reiter Vergleich; Anwender 2026-11-24)."""

import contextlib
import io
import json
import os
import sys
from pathlib import Path

import numpy as np

import _paths  # noqa: F401

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "apps"))

from bc.gui import vergleich as v

MODELS = ["checkpoints/G2_licht_langsam_nur_griff", "checkpoints/G2c_579_nur_griff"]


def _summary(kind, xy=0.004, gx=0.44, stop="kollision vorab (Nachlauf): tool an Tischebene",
             retreat="ohne Experte: angehoben, am Start (Objekt unberuehrt)", ok=True):
    if kind == v.UMLEGEN:
        return {"episodes": [], "umlegen": {"ok": ok, "result": "gegriffen" if ok else "IK"}}
    return {"episodes": [{
        "success": xy <= 0.01, "grasp_error_m": xy, "steps": 100, "pacer_overruns": 3,
        "predict_ms_median": 105.0, "stop_reason": stop, "rueckzug": retreat,
        "lage": {"pick": [0.44, -0.18, 0.008], "pick_yaw_deg": 81.0, "table_min_m": 0.018,
                 "predicted": {"pose": [gx, -0.18, 0.02], "dz_m": 0.009, "yaw_deg": -1.5}}}]}


def test_plan_runs_every_model_at_every_pose_then_relocates():
    steps = v.plan(MODELS, 2, 2)
    assert [s.label for s in steps] == [
        "Lage 1: G2_licht_langsam_nur_griff, Fahrt 1", "Lage 1: G2_licht_langsam_nur_griff, Fahrt 2",
        "Lage 1: G2c_579_nur_griff, Fahrt 1", "Lage 1: G2c_579_nur_griff, Fahrt 2",
        "Lage 1: Experte legt um",
        "Lage 2: G2_licht_langsam_nur_griff, Fahrt 1", "Lage 2: G2_licht_langsam_nur_griff, Fahrt 2",
        "Lage 2: G2c_579_nur_griff, Fahrt 1", "Lage 2: G2c_579_nur_griff, Fahrt 2"]
    assert len({s.out for s in steps}) == len(steps)          # eigener Ordner je Schritt
    for bad in (([], 1, 1), (MODELS, 0, 1), (["a/G2", "b/G2"], 1, 1)):
        try:
            v.plan(*bad)
            raise AssertionError("ValueError erwartet: %s" % (bad,))
        except ValueError:
            pass
    assert v.model_name("checkpoints/G2/checkpoints/step_004000") == "G2/step_004000"
    assert v.model_name("checkpoints\\G2\\policy") == "G2"


def test_command_lines_for_rides_and_relocation():
    ride, relocate = v.plan(MODELS[:1], 1, 2)[:2]
    argv = v.step_argv(ride, "vergleiche/x", 1.0, robot_kind="neura", override=0.5,
                       glaettung=0.5, real_robot=True)
    joined = " ".join(argv)
    for part in ("--episodes 1", "--lage-bekannt", "--probegriff objekt", "--probe-abstand 1",
                 "--ohne-experte", "--kamerapruefung warnen", "--real-robot"):
        assert part in joined, part
    assert "--nur-umlegen" not in argv
    argv = v.step_argv(relocate, "vergleiche/x", 1.0, regrasp=True, robot_kind="neura")
    assert "--nur-umlegen" in argv and "--nachgreifen" in argv
    assert "--ohne-experte" not in argv and "aus" == argv[argv.index("--kamerapruefung") + 1]


def test_evaluation_stops_the_series_when_the_arm_is_not_safely_back():
    ride = v.plan(MODELS[:1], 1, 1)[0]
    row, reason = v.evaluate(ride, _summary(v.FAHRT), 0)
    assert reason is None and row["xy_mm"] == 4.0 and row["griff_x_mm"] == 440.0
    _row, reason = v.evaluate(ride, _summary(v.FAHRT, stop="arm steht (faehrt nicht los): x",
                                             retreat="keiner -- Arm steht"), 0)
    assert "arm steht" in reason
    _row, reason = v.evaluate(ride, _summary(v.FAHRT, retreat="im transport: arm steht"), 0)
    assert "nicht sicher am Start" in reason
    assert v.evaluate(ride, None, 1)[1]
    relocate = v.Step(v.UMLEGEN, 0, MODELS[0], 0, "u")
    assert v.evaluate(relocate, _summary(v.UMLEGEN), 0) == (None, None)
    assert "IK" in v.evaluate(relocate, _summary(v.UMLEGEN, ok=False), 0)[1]


def test_aggregate_per_model_with_spread_between_runs_at_one_pose():
    rows = []
    for step, gx in zip(v.plan(MODELS, 2, 1), (0.440, 0.443, 0.450, 0.450)):
        rows.append(v.evaluate(step, _summary(v.FAHRT, xy=abs(gx - 0.44) + 0.002, gx=gx), 0)[0])
    stats = v.aggregate(rows, MODELS)
    assert [s["modell"] for s in stats] == ["G2_licht_langsam_nur_griff", "G2c_579_nur_griff"]
    assert stats[0]["xy_streuung_mm"] == 3.0 and stats[1]["xy_streuung_mm"] == 0.0
    assert stats[0]["erfolg"] == 2 and stats[1]["erfolg"] == 0      # 12 mm > 10 mm
    assert v.stats_row(stats[0])[2] == "2 / 2"


def test_pose_view_numbers_the_poses_and_marks_the_current_one():
    rows = [v.evaluate(step, _summary(v.FAHRT), 0)[0] for step in v.plan(MODELS, 1, 2)
            if step.kind == v.FAHRT]
    for row, x in zip(rows, (440.0, 440.0, 300.0, 300.0)):
        row["pick_x_mm"] = x
    lagen = v.lagen_view(rows)
    assert [l["label"] for l in lagen] == ["1", "2"] and lagen[-1]["current"]
    assert lagen[1]["xy"][0] == 0.3 and lagen[0]["yaw_deg"] == 81.0
    assert lagen[0]["status"] == "erledigt" and lagen[0]["known"] is None
    lagen = v.lagen_view(rows, placed_xy=(0.5, -0.1))           # gerade umgelegt
    assert lagen[-1]["xy"] == (0.5, -0.1) and lagen[-1]["label"] == "3"
    assert lagen[-1]["current"] and not lagen[1]["current"]
    # vorab geplant: alle Lagen sofort sichtbar, angefahrene mit dem echten PICK
    plan = [((0.44, -0.18), 81.0), ((0.30, -0.18), 10.0), ((0.25, -0.05), -20.0),
            ((0.50, -0.25), 30.0)]
    lagen = v.lagen_view(rows[:2], plan, current=1,
                         training={"A": np.array([[0.44, -0.18]]), "B": None})
    assert [l["status"] for l in lagen] == ["erledigt", "aktuell", "geplant", "geplant"]
    assert lagen[0]["known"] == "alle" and lagen[2]["known"] == "keins"
    assert v.run_row(rows[0])[-1] == "Probeabstand erreicht (mit Nachlauf)"


def test_training_coverage_is_all_or_nothing_with_density_and_heatmap():
    info = {"dataset": {"episodes": 3},
            "reference": {"grasp_tcp": [[0.40, -0.10, 0.007], [0.41, -0.10, 0.007],
                                        [0.30, -0.25, 0.007]]}}
    train = v.training_xy(info)
    assert train.shape == (3, 2)
    assert v.training_density((0.405, -0.10), train) == 2
    assert round(v.training_distance((0.30, -0.22), train), 3) == 0.03
    grid = v.heat_grid(train)
    assert sum(map(sum, grid["counts"])) == 3 and grid["cell"] == v.HEAT_CELL_M
    # unvollstaendig (weniger Greifposen als Episoden) -> gar keine Abdeckung
    info["dataset"]["episodes"] = 5
    assert v.training_xy(info) is None and v.heat_grid(None) is None
    info["dataset"]["episodes"] = 3
    info["reference"]["grasp_tcp"][1] = None
    assert v.training_xy(info) is None


def test_planned_poses_are_spread_and_go_to_the_relocation_steps():
    from test_known_pose import _down, _known

    known = _known()
    known.region = [_down(x, y, 0.0) for x, y in ((0.2, -0.3), (0.6, -0.3), (0.6, 0.1),
                                                  (0.2, 0.1))]
    planned = v.plan_poses(known, 5, np.random.default_rng(3), history=[(0.4, -0.1)])
    assert len(planned) == 5
    xy = np.array([p["xy"] for p in planned])
    gaps = [np.min(np.linalg.norm(xy[:k] - xy[k], axis=1)) for k in range(1, 5)]
    assert min(gaps) > 0.03, gaps
    # nicht erreichbare Kandidaten werden uebersprungen
    left = v.plan_poses(known, 3, np.random.default_rng(3), reachable=lambda pose: pose[1] < -0.1)
    assert all(p["xy"][1] < -0.1 for p in left)
    steps = v.attach_targets(v.plan(MODELS, 1, 3), planned)
    relocations = [s for s in steps if s.kind == v.UMLEGEN]
    assert [s.target for s in relocations] == [planned[0]["pose"], planned[1]["pose"]]
    argv = v.step_argv(relocations[0], "vergleiche/x", 1.0, robot_kind="sim")
    values = [float(t) for t in argv[argv.index("--ablage-pose") + 1].split(",")]
    assert np.allclose(values, planned[0]["pose"], atol=1e-6)


def test_infer_relocate_only_needs_the_expert_on_the_object():
    import infer

    saved = sys.argv
    try:
        for argv in (["--nur-umlegen"], ["--lage-bekannt", "--probegriff", "objekt",
                                         "--ohne-experte", "--nur-umlegen"]):
            sys.argv = ["infer.py", "--sim", "--checkpoint", "x"] + argv
            try:
                with contextlib.redirect_stderr(io.StringIO()):
                    infer.parse_args()
                raise AssertionError("muss scheitern: %s" % argv)
            except SystemExit:
                pass
    finally:
        sys.argv = saved


# -- Reiter (Qt offscreen, Fahrten nachgebildet) ------------------------------

def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        return None
    return QApplication.instance() or QApplication([])


class _FakeProcess(object):
    """Statt apps/infer.py: schreibt summary.json in den --out-Ordner."""

    def __init__(self, tab, fail_at=None):
        self.tab, self.fail_at, self.argvs, self.running = tab, fail_at, [], False

    def start(self, argv, stdin_text=None):
        self.argvs.append(argv)
        out = self.tab.workdir / argv[argv.index("--out") + 1]
        out.mkdir(parents=True, exist_ok=True)
        kind = v.UMLEGEN if "--nur-umlegen" in argv else v.FAHRT
        bad = self.fail_at is not None and len(self.argvs) - 1 == self.fail_at
        summary = _summary(kind, retreat="im transport: arm steht" if bad else
                           "ohne Experte: angehoben, am Start (Objekt unberuehrt)")
        (out / "summary.json").write_text(json.dumps(summary), encoding="utf-8")

    def stop(self):
        pass


def _tab(tmp_path):
    from bc.gui import session as session_module
    from bc.gui.runner import TaskRunner
    from bc.gui.tab_comparison import ComparisonTab

    runner = TaskRunner()
    tab = ComparisonTab(session_module.Session(), runner)
    tab.workdir = tmp_path
    tab.confirm = lambda *a: True
    tab.ensure_requirements = lambda *a, **k: True
    tab.models.clear()
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QListWidgetItem
    for path in MODELS:
        item = QListWidgetItem(v.model_name(path))
        item.setData(Qt.ItemDataRole.UserRole, path)
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(Qt.CheckState.Checked)
        tab.models.addItem(item)
    return tab, runner


def _drive(tab, fake):
    tab.process = fake
    tab.start()
    while tab._steps:
        tab._on_finished(0, "")


def test_comparison_tab_runs_the_whole_series(tmp_path):
    if _app() is None:
        return
    tab, runner = _tab(tmp_path)
    try:
        tab.fahrten.setValue(2)
        tab.lagen.setValue(2)
        fake = _FakeProcess(tab)
        _drive(tab, fake)
        assert len(fake.argvs) == 9 and "--nur-umlegen" in fake.argvs[4]
        assert tab.runs.topLevelItemCount() == 8 and tab.stats.topLevelItemCount() == 2
        assert tab.headline.text().startswith("Fertig")
        result = json.loads((tmp_path / tab._root / "vergleich.json").read_text(encoding="utf-8"))
        assert result["abgeschlossen"] is True and len(result["fahrten"]) == 8
        assert (tmp_path / tab._root / "vergleich.csv").is_file()
        first = tmp_path / tab._root / v.plan(MODELS, 2, 2)[0].out / v.STEP_LOG
        assert "Rueckgabewert 0" in first.read_text(encoding="utf-8")
        assert tab.btn_start.isEnabled() and not tab.btn_stop.isEnabled()
        assert [l["label"] for l in tab.pick_view.state.lagen] == ["1", "2"]
    finally:
        tab.shutdown()
        runner.shutdown()


def test_comparison_stops_when_a_retreat_hangs(tmp_path):
    if _app() is None:
        return
    tab, runner = _tab(tmp_path)
    try:
        tab.fahrten.setValue(2)
        tab.lagen.setValue(2)
        fake = _FakeProcess(tab, fail_at=1)
        _drive(tab, fake)
        assert len(fake.argvs) == 2                      # nach der haengenden Fahrt Schluss
        assert "nicht sicher am Start" in tab.step_line.text()
        result = json.loads((tmp_path / tab._root / "vergleich.json").read_text(encoding="utf-8"))
        assert result["abgeschlossen"] is False and result["abbruch"]
    finally:
        tab.shutdown()
        runner.shutdown()


def test_relocate_only_in_the_simulation_approaches_by_ptp(tmp_path):
    # Anlage 2026-11-24: Linearfahrt von der Startstellung -> Konfigurationssprung;
    # jetzt erst PTP ueber den PICK, dann der Experte wie nach einem Probestopp
    import infer
    from test_auto_layout import SEQ, _points

    from bc import config
    from bc.adapters.sim_robot import SimRobot

    source = (Path(__file__).resolve().parents[1] / "checkpoints" / "G2_licht_langsam_nur_griff"
              / "policy" / "bc_policy.json")
    if not source.is_file():
        return
    points, _probe = _points(size=0.12)
    info = json.loads(source.read_text(encoding="utf-8"))
    info["start_joints"] = [float(q) for q in SimRobot(points=points).connect().read_state().joints]
    ck = tmp_path / "M" / "policy"
    ck.mkdir(parents=True)
    (ck / "bc_policy.json").write_text(json.dumps(info), encoding="utf-8")
    seq = tmp_path / "ablauf.json"
    seq.write_text(json.dumps(SEQ), encoding="utf-8")
    saved = sys.argv, infer.open_robot, config.TOUCHUP_BACKUP_ROOT
    config.TOUCHUP_BACKUP_ROOT = str(tmp_path / "sicherungen")
    sys.argv = ["infer.py", "--sim", "--checkpoint", str(tmp_path / "M"), "--lage-bekannt",
                "--probegriff", "objekt", "--nur-umlegen", "--nachgreifen",
                "--kamerapruefung", "aus", "--ablauf", str(seq), "--out", str(tmp_path / "out")]
    infer.open_robot = lambda kind, clock=None, **kw: SimRobot(clock=clock, points=points)
    log = io.StringIO()
    try:
        with contextlib.redirect_stdout(log):
            infer.main()
    finally:
        sys.argv, infer.open_robot, config.TOUCHUP_BACKUP_ROOT = saved
    text = log.getvalue()
    assert "per PTP 100 mm ueber den PICK" in text, text[-3000:]
    result = json.loads((tmp_path / "out" / "summary.json").read_text(encoding="utf-8"))["umlegen"]
    assert result["ok"], result

    # vorab geplante Lage (Reiter Vergleich): dorthin, nicht automatisch
    from bc import known_pose
    robot = SimRobot(points=points).connect()
    known, _ = known_pose.load(seq, robot)
    known.pick = np.asarray(result["new_pick"], dtype=float)
    target = v.plan_poses(known, 1, np.random.default_rng(7))[0]
    sys.argv = ["infer.py", "--sim", "--checkpoint", str(tmp_path / "M"), "--lage-bekannt",
                "--probegriff", "objekt", "--nur-umlegen", "--kamerapruefung", "aus",
                "--ablauf", str(seq), "--out", str(tmp_path / "out2"),
                "--ablage-pose", ",".join("%.6f" % x for x in target["pose"])]
    infer.open_robot = lambda kind, clock=None, **kw: SimRobot(clock=clock, points=points)
    config.TOUCHUP_BACKUP_ROOT = str(tmp_path / "sicherungen")
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            infer.main()
    finally:
        sys.argv, infer.open_robot, config.TOUCHUP_BACKUP_ROOT = saved
    second = json.loads((tmp_path / "out2" / "summary.json").read_text(encoding="utf-8"))["umlegen"]
    assert second["ok"], second
    assert np.allclose(second["placed_xy"], target["xy"], atol=1e-4)


def test_grid_poses_spacing_follows_lage_count():
    from test_known_pose import _down, _known

    known = _known()
    known.region = [_down(x, y, 0.0) for x, y in ((0.2, -0.3), (0.6, -0.3), (0.6, 0.1),
                                                  (0.2, 0.1))]
    few, many = v.plan_grid_poses(known, 10), v.plan_grid_poses(known, 100)
    assert len(few) == 10 and len(many) == 100
    assert many[0]["raster_mm"] < few[0]["raster_mm"]

    def nearest(planned):
        xy = np.array([p["xy"] for p in planned])
        return min(np.min(np.delete(np.linalg.norm(xy - xy[k], axis=1), k)) for k in range(len(xy)))

    # Raster: kein Paar enger als der Rasterabstand (gleichmaessig, nicht gehaeuft)
    assert nearest(few) >= 0.999e-3 * few[0]["raster_mm"]
    assert nearest(many) >= 0.999e-3 * many[0]["raster_mm"]
    # deterministisch, Drehungen ueber den ganzen Bereich
    assert v.plan_grid_poses(known, 10) == few
    turns = [p["turn_deg"] for p in many]
    assert max(turns) - min(turns) > 60
    # nicht erreichbare Lagen werden ersetzt, nicht weggelassen
    left = v.plan_grid_poses(known, 4, reachable=lambda pose: pose[1] < -0.1)
    assert len(left) == 4 and all(p["xy"][1] < -0.1 for p in left)


def test_resume_point_keeps_finished_rides_and_redoes_the_broken_step(tmp_path):
    steps = v.plan(MODELS, 1, 2)                       # 2 Fahrten, Umlegen, 2 Fahrten
    summaries = {steps[0].out: _summary(v.FAHRT), steps[1].out: _summary(v.FAHRT),
                 steps[2].out: _summary(v.UMLEGEN, ok=False)}
    rows, index, note = v.resume_point(tmp_path, steps,
                                       lambda p: summaries.get(Path(p).relative_to(tmp_path)
                                                               .as_posix()))
    assert len(rows) == 2 and index == 2 and "IK" in note   # Umlegen neu
    del summaries[steps[2].out]
    assert v.resume_point(tmp_path, steps, lambda p: summaries.get(
        Path(p).relative_to(tmp_path).as_posix()))[1] == 2
    try:
        v.load_meta(tmp_path)
        raise AssertionError("ValueError erwartet")
    except ValueError:
        pass


def test_comparison_tab_resumes_an_aborted_series(tmp_path):
    if _app() is None:
        return
    for path in MODELS:
        (tmp_path / path).mkdir(parents=True)
    tab, runner = _tab(tmp_path)
    try:
        tab.fahrten.setValue(2)
        tab.lagen.setValue(2)
        _drive(tab, _FakeProcess(tab, fail_at=1))       # Abbruch nach Fahrt 2
        root = tab._root
        tab.runs.clear()
        tab.resume.setChecked(True)
        assert not tab.models.isEnabled() and tab.btn_start.text() == "Vergleich fortsetzen"
        assert tab.load_resume(tmp_path / root)
        assert "2 von 9 Schritten" in tab.resume_info.text()
        fake = _FakeProcess(tab)
        _drive(tab, fake)
        assert len(fake.argvs) == 7 and tab._root == root
        assert tab.runs.topLevelItemCount() == 8 and tab.headline.text().startswith("Fertig")
        result = json.loads((tmp_path / root / "vergleich.json").read_text(encoding="utf-8"))
        assert result["abgeschlossen"] is True and len(result["fahrten"]) == 8
        assert result["fortgesetzt"][0]["ab_schritt"] == 3
        assert not tab.load_resume(tmp_path / root)     # vollstaendig
        assert "|quer| Median" in v.STATS_HEADER
    finally:
        tab.shutdown()
        runner.shutdown()


def test_collapsible_box_gives_up_its_height(tmp_path):
    if _app() is None:
        return
    from PySide6.QtWidgets import QLabel, QVBoxLayout
    from bc.gui.widgets import CollapsibleBox
    box = CollapsibleBox("Ausgabe")
    QVBoxLayout(box.content).addWidget(QLabel("x"))
    assert box.is_expanded()
    box.set_expanded(False)
    assert box.frame.isHidden() and box.maximumHeight() < 80
    box.set_expanded(True)
    assert not box.frame.isHidden() and box.maximumHeight() > 1000

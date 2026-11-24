"""Modellvergleich (bc/gui/vergleich.py, Reiter Vergleich; Anwender 2026-11-24)."""

import contextlib
import io
import json
import os
import sys
from pathlib import Path

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
        assert tab.btn_start.isEnabled() and not tab.btn_stop.isEnabled()
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

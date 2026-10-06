from common.config import load_config
from common.interfaces import ObjectDetector
from m1_vision_topdown import MockDetector
from m2_robot_control import MockRobot
from m3_inspection import MockInspector
from orchestrator.state_machine import Orchestrator, State

CFG = load_config()


def make(detector=None, good_ratio=1.0):
    robot = MockRobot(CFG)
    orch = Orchestrator(CFG, detector or MockDetector(CFG, seed=0), robot,
                        MockInspector(CFG, good_ratio=good_ratio, seed=0))
    return orch, robot


def test_full_cycle_good_part_goes_to_good_bin():
    orch, robot = make(good_ratio=1.0)
    result = orch.run_cycle()
    assert result.ok and result.inspection.is_good
    assert result.states == [State.DETECT, State.PICK, State.PLACE_INSPECT, State.INSPECT,
                             State.PICK_INSPECT, State.SORT, State.IDLE]
    assert "place at bin_good" in robot.history


def test_no_home_detour_at_inspection():
    """The robot waits above the inspection fixture (outside the camera view); home only after SORT."""
    orch, robot = make()
    orch.run_cycle()
    moves = [h.split(" (")[0] for h in robot.history if h.startswith(("home", "pick", "place"))]
    assert moves == ["pick at object", "place at inspection", "pick at inspection", "place at bin_good", "home"]


def test_bad_part_goes_to_bad_bin():
    orch, robot = make(good_ratio=0.0)
    result = orch.run_cycle()
    assert not result.inspection.is_good
    assert "place at bin_bad" in robot.history


class _Empty(ObjectDetector):
    def detect(self):
        return None


class _Broken(ObjectDetector):
    def detect(self):
        raise RuntimeError("camera unplugged")


def test_no_part_returns_to_idle():
    orch, _ = make(detector=_Empty())
    result = orch.run_cycle()
    assert result.ok and result.states == [State.DETECT, State.IDLE]


def test_error_stops_robot():
    orch, robot = make(detector=_Broken())
    result = orch.run_cycle()
    assert not result.ok and orch.state is State.ERROR
    assert robot.history[-1] == "stop"
    orch.reset()
    assert orch.state is State.IDLE


def test_stop_then_reset_allows_new_cycles():
    orch, robot = make()
    robot.stop()                                 # NOT-STOPP between cycles
    result = orch.run_cycle()
    assert not result.ok and "acknowledge" in result.error
    orch.reset()                                 # "Fehler quittieren"
    assert orch.run_cycle().ok

from common.config import load_config
from m1_vision_topdown import MockDetector


def test_mock_pose_is_within_robot_limits():
    cfg = load_config()
    det = MockDetector(cfg, seed=1)
    limits = cfg["robot"]["limits_mm"]
    for _ in range(20):
        pose = det.detect()
        assert limits["x"][0] <= pose.x_mm <= limits["x"][1]
        assert limits["y"][0] <= pose.y_mm <= limits["y"][1]

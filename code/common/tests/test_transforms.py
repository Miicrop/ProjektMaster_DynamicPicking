import numpy as np
import pytest

from common.transforms import (apply_homography, fit_rigid_2d, normalize_angle,
                               rigid_2d, workspace_to_robot)


def test_fit_rigid_2d_recovers_transform():
    src = np.array([[0, 0], [600, 0], [600, 400], [0, 400]], dtype=float)
    dst = rigid_2d(src, 30.0, [250.0, -120.0])
    theta, t = fit_rigid_2d(src, dst)
    assert theta == pytest.approx(30.0)
    assert t == pytest.approx([250.0, -120.0])


def test_fit_rigid_2d_with_noise():
    rng = np.random.default_rng(0)
    src = np.array([[0, 0], [600, 0], [600, 400], [0, 400]], dtype=float)
    dst = rigid_2d(src, -15.0, [100.0, 50.0]) + rng.normal(0, 0.5, src.shape)
    theta, t = fit_rigid_2d(src, dst)
    assert theta == pytest.approx(-15.0, abs=0.2)
    assert t == pytest.approx([100.0, 50.0], abs=1.5)


def test_apply_homography_scale_and_shift():
    H = np.array([[2, 0, 10], [0, 2, 20], [0, 0, 1]], dtype=float)
    out = apply_homography(H, [[1, 1], [5, 0]])
    assert out == pytest.approx(np.array([[12, 22], [20, 20]]))


def test_normalize_angle():
    assert normalize_angle(-10) == pytest.approx(350)
    assert normalize_angle(190, period=180) == pytest.approx(10)


def test_workspace_to_robot():
    x, y, th = workspace_to_robot(100, 0, 10, 90.0, np.array([0.0, 0.0]))
    assert (x, y, th) == pytest.approx((0.0, 100.0, 100.0), abs=1e-9)


def test_fit_workspace_to_robot_residuals():
    from common.transforms import fit_workspace_to_robot
    ws = np.array([[-25, -25], [425, -25], [425, 425], [-25, 425]], dtype=float)
    robot = rigid_2d(ws, 90.0, [350.0, -180.0])
    rot, t, res = fit_workspace_to_robot(ws, robot)
    assert rot == pytest.approx(90.0) and t == pytest.approx([350.0, -180.0])
    assert res == pytest.approx(np.zeros(4), abs=1e-9)
    robot[2] += [3.0, 4.0]                 # one badly taught point -> visible residual
    _, _, res = fit_workspace_to_robot(ws, robot)
    assert res.argmax() == 2 and res.max() > 2.0


def test_fit_workspace_to_robot_needs_three_points():
    from common.transforms import fit_workspace_to_robot
    with pytest.raises(ValueError):
        fit_workspace_to_robot([[0, 0], [1, 0]], [[0, 0], [1, 0]])

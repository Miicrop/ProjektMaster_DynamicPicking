"""Coordinate transforms: image -> workspace -> robot base frame.

See plan/01_architektur.md, section "Koordinatensysteme und Kalibrierung".
"""
from __future__ import annotations

import math

import numpy as np


def apply_homography(H: np.ndarray, points: np.ndarray) -> np.ndarray:
    """Map Nx2 points with a 3x3 homography."""
    pts = np.asarray(points, dtype=float).reshape(-1, 2)
    homog = np.hstack([pts, np.ones((len(pts), 1))]) @ H.T
    return homog[:, :2] / homog[:, 2:3]


def fit_rigid_2d(src: np.ndarray, dst: np.ndarray) -> tuple[float, np.ndarray]:
    """Least-squares 2D rigid transform (rotation + translation, no scale).

    Finds R(theta), t minimising sum ||R @ src_i + t - dst_i||^2 (Kabsch/Umeyama).
    Used to compute workspace -> robot from taught marker positions.

    Returns (theta_deg, t) with t of shape (2,).
    """
    src = np.asarray(src, dtype=float).reshape(-1, 2)
    dst = np.asarray(dst, dtype=float).reshape(-1, 2)
    if len(src) < 2 or len(src) != len(dst):
        raise ValueError("Need at least two corresponding points")
    mu_s, mu_d = src.mean(axis=0), dst.mean(axis=0)
    C = (dst - mu_d).T @ (src - mu_s)
    U, _, Vt = np.linalg.svd(C)
    D = np.diag([1.0, np.sign(np.linalg.det(U @ Vt))])
    R = U @ D @ Vt
    t = mu_d - R @ mu_s
    return math.degrees(math.atan2(R[1, 0], R[0, 0])), t


def rigid_2d(points: np.ndarray, theta_deg: float, t: np.ndarray) -> np.ndarray:
    """Apply a 2D rigid transform to Nx2 points."""
    c, s = math.cos(math.radians(theta_deg)), math.sin(math.radians(theta_deg))
    R = np.array([[c, -s], [s, c]])
    return np.asarray(points, dtype=float).reshape(-1, 2) @ R.T + np.asarray(t, dtype=float)


def normalize_angle(theta_deg: float, period: float = 360.0) -> float:
    """Wrap an angle into [0, period). Use period=180 for symmetric parts."""
    return theta_deg % period


def workspace_to_robot(x_mm: float, y_mm: float, theta_deg: float,
                       rot_deg: float, t: np.ndarray) -> tuple[float, float, float]:
    """Transform a planar pose from the workspace frame into the robot base frame."""
    x, y = rigid_2d([[x_mm, y_mm]], rot_deg, t)[0]
    return float(x), float(y), theta_deg + rot_deg

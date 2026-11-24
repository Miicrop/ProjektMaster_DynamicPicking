"""pytest-Konfiguration: Auswahl der Port-Implementierung (AP 0.5).

    pytest                       # alles hardwarefrei (sim)
    pytest --robot=neura         # Contract-Tests gegen die Anlage
    pytest --camera=daheng       # Contract-Tests gegen die Daheng-Kamera
    pytest --camera=uvc --uvc-device=2   # gegen eine bestimmte Webcam
    pytest tests/contract --robot=mujoco --camera=mujoco   # Taktiksimulation

Die Contract-Suite ist die Abnahmeliste der Adapter: dieselben Tests, die
heute gegen die Simulation laufen, werden am Hardwaretag unveraendert
gegen die echten Adapter gefahren (AP 0.6).
"""

import _paths  # noqa: F401
import pytest

import _fixtures


def pytest_addoption(parser):
    parser.addoption("--robot", default="sim", choices=("sim", "neura", "mujoco"))
    parser.addoption("--camera", default="sim", choices=("sim", "uvc", "daheng", "mujoco"))
    parser.addoption("--uvc-device", default=None, type=int)


@pytest.fixture(autouse=True)
def _point_backups_in_tmp(tmp_path, monkeypatch):
    """record.py sichert PICK beim Ablegen -- nicht ins Arbeitsverzeichnis."""
    from bc import config

    monkeypatch.setattr(config, "TOUCHUP_BACKUP_ROOT", str(tmp_path / "punkt_sicherungen"))


@pytest.fixture
def robot(request):
    kind = request.config.getoption("--robot")
    bot = _fixtures.make_robot(kind)
    yield bot
    bot.close()


@pytest.fixture
def camera(request):
    kind = request.config.getoption("--camera")
    _fixtures.UVC_DEVICE["device"] = request.config.getoption("--uvc-device")
    cam = _fixtures.make_camera(kind)
    yield cam
    if cam.is_open:
        cam.close()

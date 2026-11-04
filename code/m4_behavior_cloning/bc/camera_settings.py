"""Belichtung und Gain der Daheng-Kameras aus der Oberflaeche (Anwender 2026-11-03).

Bisher standen Belichtung und Gain nur in ``config.py`` (``WRIST_CAMERA``
usw.). Im Fenster "Kameraeinstellungen" (bc/gui/camera_dialog.py) werden sie
an der offenen Vorschau ausprobiert und hier gespeichert; Vorschau und
``apps/record.py`` uebernehmen sie beim naechsten Oeffnen.

Gespeichert je GERAET, nicht je Platz: die Werte gehoeren zu Kamera und
Objektiv. Werden Wrist und Szene in der Zuordnung getauscht, wandern sie mit.

    einstellungen/kameras.local.json
    {"daheng:EBK24100633": {"exposure_us": 6000.0, "gain_db": 2.0}}

``None`` heisst Automatik, ein fehlender Schluessel die Vorgabe aus
``config.py``. Was tatsaechlich gilt, liest die Kamera zurueck
(``CameraPort.settings``) und steht in den Metadaten jeder Episode.

Qt-frei.
"""

import json
from dataclasses import replace
from pathlib import Path

#: Ablage, relativ zum Arbeitsordner (nicht eingecheckt: einstellungen/*.local.json)
SETTINGS_FILE = "einstellungen/kameras.local.json"
#: Werte, die hier eingestellt werden
KEYS = ("exposure_us", "gain_db")
#: Grenzen fuer die Eingabe (VEN-161-61U3C: Belichtung ab ~20 us, Gain 0-24 dB).
#: Mehr als ~16 ms Belichtung verwischt bei Armbewegung und begrenzt die Rate.
EXPOSURE_RANGE_US = (20.0, 30000.0)
GAIN_RANGE_DB = (0.0, 24.0)

_ROOT = Path(__file__).resolve().parents[1]


def device_key(cfg):
    """Schluessel fuer eine Kamera: Backend und Seriennummer (sonst Platz)."""
    if cfg.device:
        return "%s:%s" % (cfg.backend, cfg.device)
    return "%s@%s" % (cfg.backend, cfg.name)


def _path(root=None):
    return Path(root if root is not None else _ROOT) / SETTINGS_FILE


def load(root=None):
    """Gespeicherte Werte je Kamera; leer, wenn nichts da oder nicht lesbar."""
    try:
        data = json.loads(_path(root).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {key: {k: v for k, v in values.items() if k in KEYS}
            for key, values in data.items() if isinstance(values, dict)}


def save(cfg, values, root=None):
    """Werte fuer die Kamera ``cfg`` speichern. Rueckgabe: Pfad der Datei."""
    data = load(root)
    clean = {}
    for key in KEYS:
        if key in values:
            value = values[key]
            clean[key] = None if value is None else round(float(value), 2)
    data[device_key(cfg)] = clean
    path = _path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def apply(cfgs, root=None):
    """Gespeicherte Werte auf die Konfigurationen legen.

    Rueckgabe: (neue Liste, Textzeilen dazu). Nur Daheng -- die UVC-Webcam
    stellt Belichtung ueber OpenCV meist gar nicht verlaesslich ein.
    """
    stored = load(root)
    out, notes = [], []
    for cfg in cfgs:
        values = stored.get(device_key(cfg)) if cfg.backend == "daheng" else None
        if values:
            cfg = replace(cfg, **values)
            notes.append("%s: %s aus %s" % (cfg.name, describe(values), SETTINGS_FILE))
        out.append(cfg)
    return out, notes


def describe(values):
    bits = []
    if "exposure_us" in values:
        bits.append("Belichtung %s" % ("Automatik" if values["exposure_us"] is None
                                       else "%.0f us" % values["exposure_us"]))
    if "gain_db" in values:
        bits.append("Gain %s" % ("Automatik" if values["gain_db"] is None
                                 else "%.1f dB" % values["gain_db"]))
    return ", ".join(bits)

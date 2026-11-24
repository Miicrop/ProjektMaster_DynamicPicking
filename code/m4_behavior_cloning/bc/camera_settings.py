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
KEYS = ("exposure_us", "gain_db", "white_balance_ratios")
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
            if value is None:
                clean[key] = None
            elif key == "white_balance_ratios":
                clean[key] = [round(float(v), 3) for v in value]
            else:
                clean[key] = round(float(value), 2)
    data[device_key(cfg)] = clean
    path = _path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def apply(cfgs, root=None, default_wb=True):
    """Gespeicherte Werte auf die Konfigurationen legen.

    Rueckgabe: (neue Liste, Textzeilen dazu). Nur Daheng -- die UVC-Webcam
    stellt Belichtung ueber OpenCV meist gar nicht verlaesslich ein.
    """
    from . import config

    stored = load(root)
    out, notes = [], []
    for cfg in cfgs:
        values = dict(stored.get(device_key(cfg)) or {}) if cfg.backend == "daheng" else None
        if default_wb and values is not None and "white_balance_ratios" not in values \
                and device_key(cfg) in config.CAMERA_WHITE_BALANCE:
            # fester Weissabgleich als Standard (config.CAMERA_WHITE_BALANCE)
            values["white_balance_ratios"] = config.CAMERA_WHITE_BALANCE[device_key(cfg)]
        if values and values.get("white_balance_ratios") is not None:
            values["white_balance_ratios"] = tuple(float(v) for v in values["white_balance_ratios"])
        if values:
            cfg = replace(cfg, **values)
            notes.append("%s: %s (%s / config.CAMERA_WHITE_BALANCE)"
                         % (cfg.name, describe(values), SETTINGS_FILE))
        out.append(cfg)
    return out, notes


def recorded_white_balance(recorded, camera):
    """Fester Weissabgleich der Aufnahme fuer ``camera`` -- nur wenn alle
    Episoden denselben hatten (neue Datensaetze, config.CAMERA_WHITE_BALANCE),
    sonst None (aeltere Aufnahmen mit "Once": je Sitzung anders)."""
    seen = ((recorded or {}).get(camera) or {}).get("white_balance_ratios") or []
    distinct = {tuple(round(float(v), 2) for v in r) for r in seen if r}
    if len(distinct) != 1:
        return None
    return tuple(float(v) for v in seen[0])


def describe(values):
    bits = []
    if "exposure_us" in values:
        bits.append("Belichtung %s" % ("Automatik" if values["exposure_us"] is None
                                       else "%.0f us" % values["exposure_us"]))
    if "gain_db" in values:
        bits.append("Gain %s" % ("Automatik" if values["gain_db"] is None
                                 else "%.1f dB" % values["gain_db"]))
    if values.get("white_balance_ratios"):
        bits.append("Weissabgleich fest %s" % "/".join(
            "%.2f" % v for v in values["white_balance_ratios"]))
    return ", ".join(bits)


#: Was die Inferenz gegen die Aufnahme vergleicht (Analyse 2026-11-11) und ab
#: welcher Abweichung sie es meldet. Nur ein Hinweis: die alten Aufnahmen haben
#: den Weissabgleich je Sitzung neu gezogen, der Datensatz streut also ohnehin.
COMPARE_TOLERANCE = {"exposure_us": 50.0, "gain_db": 0.5}
COMPARE_MODES = ("exposure_auto", "gain_auto", "white_balance_auto")


def collect(per_episode):
    """Kameraeinstellungen vieler Episoden zusammenfassen (Export).

    ``per_episode``: Liste der ``camera_settings`` aus den Episoden-Metadaten
    ({Kamera: {Schluessel: Wert}}). Rueckgabe {Kamera: {Schluessel: [Werte]}}
    mit den vorkommenden Werten der verglichenen Schluessel.
    """
    out = {}
    for settings in per_episode:
        for cam, values in (settings or {}).items():
            slot = out.setdefault(cam, {})
            for key in tuple(COMPARE_TOLERANCE) + COMPARE_MODES + ("white_balance_ratios",):
                v = (values or {}).get(key)
                if v is not None and v not in slot.setdefault(key, []):
                    slot[key].append(v)
    return out


def compare(recorded, current):
    """Abweichungen der Kameraeinstellungen jetzt gegen die Aufnahme (Textzeilen).

    ``recorded`` wie :func:`collect`, ``current`` {Kamera: settings()}. Fehlt
    eine Seite (aeltere Aufnahme, UVC-Kamera), wird nichts gemeldet.
    """
    lines = []
    for cam, now in (current or {}).items():
        seen = (recorded or {}).get(cam) or {}
        for key, tol in COMPARE_TOLERANCE.items():
            values, v = seen.get(key) or [], (now or {}).get(key)
            if values and v is not None and min(abs(float(v) - float(w)) for w in values) > tol:
                lines.append("Kamera %s: %s jetzt %s, in der Aufnahme %s"
                             % (cam, key, v, ", ".join(str(w) for w in sorted(values))))
        for key in COMPARE_MODES:
            values, v = seen.get(key) or [], (now or {}).get(key)
            if values and v is not None and v not in values:
                lines.append("Kamera %s: %s jetzt %s, in der Aufnahme %s"
                             % (cam, key, v, ", ".join(str(w) for w in values)))
    return lines

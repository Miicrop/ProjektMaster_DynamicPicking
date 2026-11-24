"""Parameter der MuJoCo-Szene: eine JSON-Datei neben diesem Modul.

Getrennt vom Code, weil ein Teil davon *angepasst* ist (Kameralage aus den
Referenzbildern, ``kalibrierung.py``; Folgemodell aus den Aufnahmen,
``folgemodell.py``) und beim Nachschaerfen neu geschrieben wird. Jeder
Abschnitt nennt seine Quelle (Schluessel ``_quelle``).
"""

import copy
import json
from pathlib import Path

PATH = Path(__file__).resolve().parent / "parameter.json"

_CACHE = {}


def load(path=PATH):
    """Parameter als dict (Kopie -- Aenderungen gehen nur ueber :func:`save`)."""
    path = Path(path)
    key = (str(path), path.stat().st_mtime_ns)
    if key not in _CACHE:
        _CACHE.clear()
        _CACHE[key] = json.loads(path.read_text(encoding="utf-8"))
    return copy.deepcopy(_CACHE[key])


def save(data, path=PATH):
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _CACHE.clear()

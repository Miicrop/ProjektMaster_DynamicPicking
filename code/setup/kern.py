"""Kern des M4-Setup-Programms: pruefen, planen, ausfuehren, deinstallieren.

Ohne Fenster und nur mit der Standardbibliothek, damit es mit jedem Python
ab 3.8 laeuft, das schon auf dem Rechner ist, und damit es testbar bleibt.
Das Fenster (fenster.py) und die Kommandozeile (m4_setup.py) sind duenne
Schichten darueber.

Ablauf:
    ziel = Ziel(venv=..., build="gpu")
    befunde = pruefe_alle(ziel)               # {id: Befund}
    schritte = plane("installieren", ids, ziel, befunde)
    zeige(schritte)                           # "Befehle anzeigen" / --befehle
    fuehre_aus(schritte, ausgabe)             # schreibt auch die Logdatei

Grundsatz: Admin-Komponenten werden nie ausgefuehrt, nur geprueft und in die
Checkliste geschrieben. Alles andere landet im Zielordner der Umgebung
(Ausnahme: die Benutzervariable BC_PYTHON, wenn der Zielordner vom Standard
abweicht).
"""

import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

try:                                   # nur unter Windows vorhanden
    import winreg
except ImportError:                    # pragma: no cover - Tests unter Windows
    winreg = None

import komponenten as K

SETUP_DIR = Path(__file__).resolve().parent
CODE_DIR = SETUP_DIR.parent
M4_DIR = CODE_DIR / "m4_behavior_cloning"
STANDARD_VENV = M4_DIR / ".venv"
LOCK_DATEI = CODE_DIR / K.LOCK
CACHE_DIR = SETUP_DIR / "_cache"
LOG_DIR = SETUP_DIR / "logs"
EINSTELLUNGEN = SETUP_DIR / "einstellungen.json"

MIN_FREI_GB = 15
MIN_TREIBER = 570

# Status einer Komponente
OK = "ok"
FEHLT = "fehlt"
ABWEICHEND = "abweichend"      # installiert, aber falsche Version / falscher Build
ADMIN = "admin"                # fehlt und braucht Admin-Rechte
WARTET = "wartet"              # haengt an etwas anderem, das fehlt
NICHT_NOETIG = "nicht_noetig"
OFFEN = "offen"                # Test noch nicht gelaufen
WARNUNG = "warnung"

STATUS_TEXT = {
    OK: "vorhanden", FEHLT: "fehlt", ABWEICHEND: "abweichend",
    ADMIN: "Admin noetig", WARTET: "wartet", NICHT_NOETIG: "nicht noetig",
    OFFEN: "nicht gelaufen", WARNUNG: "Warnung",
}

ALLE = {k["id"]: k for k in K.KOMPONENTEN}


def komponente(kid):
    return ALLE[kid]


# --------------------------------------------------------------------------
# Ziel und Einstellungen
# --------------------------------------------------------------------------

class Ziel(object):
    """Wohin installiert wird und wie."""

    def __init__(self, venv=None, build="gpu", basis_python=None,
                 wheelhouse=None, ffmpeg_zip=None):
        self.venv = Path(venv) if venv else STANDARD_VENV
        self.build = build                    # "gpu" | "cpu"
        self.basis_python = basis_python      # None = automatisch suchen
        self.wheelhouse = wheelhouse          # Ordner mit Wheels = offline
        self.ffmpeg_zip = ffmpeg_zip

    @property
    def python(self):
        return self.venv / "Scripts" / "python.exe"

    @property
    def scripts(self):
        return self.venv / "Scripts"

    @property
    def ist_standardort(self):
        return _gleich(self.venv, STANDARD_VENV)

    def als_dict(self):
        return dict(venv=str(self.venv), build=self.build,
                    basis_python=self.basis_python, wheelhouse=self.wheelhouse,
                    ffmpeg_zip=self.ffmpeg_zip)


def lade_einstellungen():
    """Zuletzt benutztes Ziel; fehlt die Datei, die Standardwerte."""
    try:
        d = json.loads(EINSTELLUNGEN.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        d = {}
    build = d.get("build") or ("gpu" if nvidia_smi()[0] else "cpu")
    return Ziel(d.get("venv"), build, d.get("basis_python"),
                d.get("wheelhouse"), d.get("ffmpeg_zip"))


def speichere_einstellungen(ziel):
    try:
        EINSTELLUNGEN.write_text(json.dumps(ziel.als_dict(), indent=2), encoding="utf-8")
    except OSError:
        pass


def _gleich(a, b):
    return os.path.normcase(os.path.abspath(str(a))) == os.path.normcase(os.path.abspath(str(b)))


# --------------------------------------------------------------------------
# Hilfen: Prozesse, Versionen
# --------------------------------------------------------------------------

def _kind_env():
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    env.pop("PYTHONHOME", None)
    env.pop("PYTHONPATH", None)
    return env


def _flags():
    # Unter dem Fenster keine aufblitzenden Konsolen
    return getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0


def lauf(cmd, timeout=60, cwd=None):
    """Kurzer Aufruf fuer Pruefungen: (returncode, ausgabe). Nie eine Ausnahme."""
    try:
        p = subprocess.run([str(c) for c in cmd], capture_output=True, timeout=timeout,
                           cwd=str(cwd) if cwd else None, env=_kind_env(),
                           creationflags=_flags())
        text = (p.stdout + p.stderr).decode("utf-8", "replace").strip()
        return p.returncode, text
    except (OSError, subprocess.SubprocessError) as exc:
        return -1, "%s: %s" % (type(exc).__name__, exc)


def version_tupel(v):
    """'2.11.0+cu128' -> (2, 11, 0). Vorabversionen zaehlen wie die Release."""
    release = v.split("+", 1)[0]
    teile = []
    for t in release.split("."):
        m = re.match(r"\d+", t)
        if not m:
            break
        teile.append(int(m.group()))
    return tuple(teile)


def _vgl(a, b):
    n = max(len(a), len(b))
    a = a + (0,) * (n - len(a))
    b = b + (0,) * (n - len(b))
    return (a > b) - (a < b)


def erfuellt(version, spez):
    """Prueft eine Version gegen 'torch==2.11.0'-artige Angaben (ohne Namen)."""
    for klausel in [s.strip() for s in spez.split(",") if s.strip()]:
        m = re.match(r"(==|!=|>=|<=|~=|>|<)\s*(\S+)$", klausel)
        if not m:
            continue
        op, soll = m.groups()
        c = _vgl(version_tupel(version), version_tupel(soll))
        if op == "==" and "+" in soll:
            if version != soll:
                return False
        elif op == "==" and c != 0:
            return False
        elif op == "!=" and c == 0:
            return False
        elif op == ">=" and c < 0:
            return False
        elif op == "<=" and c > 0:
            return False
        elif op == ">" and c <= 0:
            return False
        elif op == "<" and c >= 0:
            return False
        elif op == "~=":
            s = version_tupel(soll)
            if c < 0 or version_tupel(version)[:len(s) - 1] != s[:-1]:
                return False
    return True


def zerlege(anforderung):
    """'PySide6>=6.6,<7' -> ('pyside6', '>=6.6,<7')."""
    m = re.match(r"\s*([A-Za-z0-9_.\-]+)\s*(\[[^\]]*\])?\s*(.*)$", anforderung.split(";")[0])
    return normname(m.group(1)), m.group(3).strip()


def normname(name):
    return re.sub(r"[-_.]+", "-", name).lower()


# --------------------------------------------------------------------------
# Pruefungen
# --------------------------------------------------------------------------

class Befund(object):
    def __init__(self, status, detail=""):
        self.status = status
        self.detail = detail

    @property
    def ok(self):
        return self.status in (OK, NICHT_NOETIG)

    def __repr__(self):
        return "Befund(%s, %r)" % (self.status, self.detail)


def finde_python312(vorgabe=None):
    """Pfad zu einem Python 3.12 oder None. Reihenfolge: Vorgabe, dieses Python,
    py-Launcher, uebliche Installationsorte."""
    kandidaten = []
    if vorgabe:
        kandidaten.append(vorgabe)
    kandidaten.append(sys.executable)
    rc, out = lauf(["py", "-3.12", "-c", "import sys; print(sys.executable)"], timeout=20)
    if rc == 0 and out:
        kandidaten.append(out.splitlines()[-1].strip())
    for basis in (os.environ.get("LOCALAPPDATA", ""), os.environ.get("ProgramFiles", "")):
        if basis:
            kandidaten.append(os.path.join(basis, "Programs", "Python", "Python312", "python.exe"))
            kandidaten.append(os.path.join(basis, "Python312", "python.exe"))
    for k in kandidaten:
        if not k or not os.path.isfile(k):
            continue
        if _ist_venv_python(k):            # eine venv als Basis waere verschachtelt
            continue
        rc, out = lauf([k, "-c", "import sys; print('%d.%d' % sys.version_info[:2])"], timeout=20)
        if rc == 0 and out.strip().endswith("3.12"):
            return k
        if vorgabe and k == vorgabe:
            return None                    # ausdrueckliche Vorgabe passt nicht
    return None


def _ist_venv_python(pfad):
    return (Path(pfad).parent.parent / "pyvenv.cfg").is_file()


def nvidia_smi():
    """(gefunden, gpu_name, treiber_version)"""
    rc, out = lauf(["nvidia-smi", "--query-gpu=name,driver_version",
                    "--format=csv,noheader"], timeout=20)
    if rc != 0 or not out:
        return False, "", ""
    teile = [t.strip() for t in out.splitlines()[0].split(",")]
    return True, teile[0], (teile[1] if len(teile) > 1 else "")


def _reg_wert(wurzel, schluessel, name):
    if winreg is None:
        return None
    for sicht in (0, getattr(winreg, "KEY_WOW64_64KEY", 0)):
        try:
            with winreg.OpenKey(wurzel, schluessel, 0, winreg.KEY_READ | sicht) as k:
                return winreg.QueryValueEx(k, name)[0]
        except OSError:
            continue
    return None


def galaxy_sdk_pfad():
    for basis in (os.environ.get("ProgramFiles", r"C:\Program Files"),
                  os.environ.get("ProgramFiles(x86)", "")):
        if basis:
            p = Path(basis) / K.GALAXY_SDK_PYTHON
            if (p / "gxipy").is_dir():
                return p
    return None


def installierte_pakete(ziel):
    """{normname: version} der Umgebung, leer wenn es sie nicht gibt."""
    if not ziel.python.is_file():
        return {}
    code = ("import json, importlib.metadata as m; "
            "print(json.dumps({d.metadata['Name']: d.version for d in m.distributions() "
            "if d.metadata['Name']}))")
    rc, out = lauf([ziel.python, "-c", code], timeout=60)
    if rc != 0:
        return {}
    try:
        roh = json.loads(out.splitlines()[-1])
    except (ValueError, IndexError):
        return {}
    return {normname(n): v for n, v in roh.items()}


def site_packages(ziel):
    return ziel.venv / "Lib" / "site-packages"


def _p_python312(k, ziel, ctx):
    p = finde_python312(ziel.basis_python)
    ctx["basis_python"] = p
    if p:
        return Befund(OK, p)
    if ziel.python.is_file():
        return Befund(NICHT_NOETIG, "Umgebung besteht schon")
    return Befund(FEHLT, "kein Python 3.12 gefunden")


def _p_nvidia(k, ziel, ctx):
    gefunden, name, treiber = nvidia_smi()
    if ziel.build == "cpu":
        return Befund(NICHT_NOETIG, "CPU-Build gewaehlt" + (" (%s vorhanden)" % name if gefunden else ""))
    if not gefunden:
        return Befund(ADMIN, "nvidia-smi nicht gefunden (keine NVIDIA-Karte oder kein Treiber)")
    major = version_tupel(treiber)[:1]
    if major and major[0] >= MIN_TREIBER:
        return Befund(OK, "%s, Treiber %s" % (name, treiber))
    return Befund(ADMIN, "%s, Treiber %s zu alt (>= %d noetig)" % (name, treiber, MIN_TREIBER))


def _p_vcredist(k, ziel, ctx):
    if winreg is not None:
        sch = r"SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64"
        if _reg_wert(winreg.HKEY_LOCAL_MACHINE, sch, "Installed") == 1:
            return Befund(OK, str(_reg_wert(winreg.HKEY_LOCAL_MACHINE, sch, "Version") or ""))
    dll = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "vcruntime140_1.dll"
    if dll.is_file():
        return Befund(OK, "vcruntime140_1.dll vorhanden")
    return Befund(ADMIN, "nicht gefunden")


def _p_speicher(k, ziel, ctx):
    p = ziel.venv
    while not p.exists() and p.parent != p:
        p = p.parent
    try:
        frei = shutil.disk_usage(str(p)).free / 1e9
    except OSError as exc:
        return Befund(WARNUNG, str(exc))
    text = "%.0f GB frei auf %s" % (frei, p.anchor or p)
    if frei >= MIN_FREI_GB or ziel.python.is_file():
        return Befund(OK, text)
    return Befund(WARNUNG, text + " (mind. %d GB empfohlen)" % MIN_FREI_GB)


def _p_venv(k, ziel, ctx):
    if not ziel.python.is_file():
        if ziel.venv.exists() and any(ziel.venv.iterdir()):
            return Befund(ABWEICHEND, "Ordner existiert, ist aber keine Umgebung")
        return Befund(FEHLT, str(ziel.venv))
    rc, out = lauf([ziel.python, "-c", "import sys; print('%d.%d.%d' % sys.version_info[:3])"])
    if rc != 0:
        return Befund(ABWEICHEND, "python.exe startet nicht: " + out[-200:])
    if not out.strip().startswith("3.12"):
        return Befund(ABWEICHEND, "Python %s statt 3.12 -> Umgebung loeschen und neu anlegen" % out.strip())
    return Befund(OK, "Python %s" % out.strip())


def _p_bc_python(k, ziel, ctx):
    if ziel.ist_standardort:
        return Befund(NICHT_NOETIG, "Standardort, wird automatisch gefunden")
    wert = _reg_wert(winreg.HKEY_CURRENT_USER, "Environment", "BC_PYTHON") if winreg else None
    if wert and _gleich(wert, ziel.python):
        return Befund(OK, wert)
    if wert:
        return Befund(ABWEICHEND, "zeigt auf " + wert)
    return Befund(FEHLT, "nicht gesetzt")


def _p_pip(k, ziel, ctx):
    if not ziel.python.is_file():
        return Befund(FEHLT, "Umgebung fehlt")
    pakete = ctx.get("pakete")
    if pakete is None:
        pakete = ctx["pakete"] = installierte_pakete(ziel)
    gefunden, fehlt, falsch = [], [], []
    for anf in k["pakete"]:
        name, spez = zerlege(anf)
        v = pakete.get(name)
        if v is None:
            fehlt.append(name)
            continue
        if not erfuellt(v, spez):
            falsch.append("%s %s (soll %s)" % (name, v, spez))
            continue
        if name == "torch":
            cuda = "+cu" in v
            if ziel.build == "gpu" and not cuda:
                falsch.append("torch %s ist CPU-Build" % v)
                continue
            if ziel.build == "cpu" and cuda:
                falsch.append("torch %s ist CUDA-Build" % v)
                continue
        gefunden.append("%s %s" % (name, v))
    if falsch:
        return Befund(ABWEICHEND, "; ".join(falsch))
    if fehlt and gefunden:
        return Befund(FEHLT, "fehlt: " + ", ".join(fehlt))
    if fehlt:
        return Befund(FEHLT, "")
    return Befund(OK, ", ".join(gefunden))


def _p_ffmpeg(k, ziel, ctx):
    if (ziel.scripts / "ffmpeg.exe").is_file():
        return Befund(OK, str(ziel.scripts / "ffmpeg.exe"))
    pfad = shutil.which("ffmpeg")
    if pfad:
        return Befund(OK, "im PATH: " + pfad)
    return Befund(FEHLT, "optional")


def _p_galaxy(k, ziel, ctx):
    p = galaxy_sdk_pfad()
    if p:
        return Befund(OK, str(p))
    return Befund(ADMIN, "nicht installiert")


def _p_gxipy(k, ziel, ctx):
    pth = site_packages(ziel) / "gxipy.pth"
    if pth.is_file():
        inhalt = pth.read_text(encoding="utf-8", errors="replace").strip()
        if (Path(inhalt) / "gxipy").is_dir():
            return Befund(OK, inhalt)
        return Befund(ABWEICHEND, "gxipy.pth zeigt auf fehlenden Ordner " + inhalt)
    if not galaxy_sdk_pfad():
        return Befund(WARTET, "wartet auf das Galaxy SDK")
    if not ziel.python.is_file():
        return Befund(FEHLT, "Umgebung fehlt")
    return Befund(FEHLT, "")


def _p_test(k, ziel, ctx):
    if k["id"] == "check_gpu" and ziel.build == "cpu":
        return Befund(NICHT_NOETIG, "CPU-Build")
    letzt = ctx.get("tests", {}).get(k["id"])
    return letzt or Befund(OFFEN, "")


PRUEFUNGEN = {
    "python312": _p_python312, "nvidia": _p_nvidia, "vcredist": _p_vcredist,
    "speicher": _p_speicher, "venv": _p_venv, "bc_python": _p_bc_python,
    "ffmpeg": _p_ffmpeg, "galaxy_sdk": _p_galaxy, "gxipy": _p_gxipy,
    "check_gpu": _p_test, "selbsttest": _p_test,
}


def pruefe(kid, ziel, ctx=None):
    ctx = {} if ctx is None else ctx
    k = komponente(kid)
    fn = _p_pip if k["art"] == "pip" else PRUEFUNGEN[kid]
    try:
        return fn(k, ziel, ctx)
    except Exception as exc:               # eine Pruefung darf das Programm nie beenden
        return Befund(WARNUNG, "%s: %s" % (type(exc).__name__, exc))


def pruefe_alle(ziel, ctx=None):
    ctx = {} if ctx is None else ctx
    return {k["id"]: pruefe(k["id"], ziel, ctx) for k in K.KOMPONENTEN}


def vorauswahl(befunde):
    """Was beim Start angehakt ist: Standardkomponenten, die noch nicht passen."""
    ids = []
    for k in K.KOMPONENTEN:
        if k["art"] == "admin" or k["id"] in K.NUR_PRUEFEN:
            continue
        b = befunde.get(k["id"])
        if not k.get("standard") or b is None:
            continue
        if b.status in (FEHLT, ABWEICHEND, OFFEN):
            ids.append(k["id"])
    return ids


# --------------------------------------------------------------------------
# Planen
# --------------------------------------------------------------------------

class Schritt(object):
    """Ein Arbeitsschritt: entweder ein Befehl oder eine Python-Funktion."""

    def __init__(self, kid, text, cmd=None, funktion=None, beschreibung=None,
                 cwd=None, darf_scheitern=False):
        self.kid = kid
        self.text = text
        self.cmd = [str(c) for c in cmd] if cmd else None
        self.funktion = funktion
        self.beschreibung = beschreibung      # fuer "Befehle anzeigen" bei Funktionen
        self.cwd = cwd
        self.darf_scheitern = darf_scheitern

    def als_text(self):
        if self.cmd:
            zeile = " ".join(_quote(c) for c in self.cmd)
            if self.cwd:
                zeile = "cd /d %s && %s" % (_quote(str(self.cwd)), zeile)
            return zeile
        return "rem " + (self.beschreibung or self.text)


def _quote(s):
    """Fuer cmd kopierbar: Leerzeichen und < > | & ^ (sonst Umleitung!) in Anfuehrungszeichen."""
    return '"%s"' % s if (not s or any(c in s for c in ' <>|&^')) else s


class PlanFehler(Exception):
    """Plan nicht ausfuehrbar; die Meldung erklaert, was fehlt."""


def constraints_datei(ziel):
    """Lock-Datei ohne BOM; fuer den CPU-Build ohne die '+cu128'-Pins."""
    roh = LOCK_DATEI.read_text(encoding="utf-8-sig").splitlines()
    zeilen = []
    for z in roh:
        if ziel.build == "cpu" and "+cu" in z:
            z = z.split("+", 1)[0]
        zeilen.append(z)
    CACHE_DIR.mkdir(exist_ok=True)
    ziel_datei = CACHE_DIR / ("constraints-%s.txt" % ziel.build)
    ziel_datei.write_text("\n".join(zeilen) + "\n", encoding="utf-8")
    return ziel_datei


def _pip_basis(ziel):
    return [ziel.python, "-m", "pip", "--disable-pip-version-check"]


def _pip_quelle(ziel):
    if ziel.wheelhouse:
        return ["--no-index", "--find-links", ziel.wheelhouse]
    # Der torch-Index gilt fuer jede Gruppe: sonst zoege z. B. lerobot ohne
    # vorher installiertes torch den CPU-Build von PyPI.
    return ["--extra-index-url", K.TORCH_INDEX[ziel.build]]


def plane(aktion, ids, ziel, befunde=None):
    """Liste von Schritten fuer 'installieren', 'reparieren' oder 'deinstallieren'.

    Komponenten, die schon passen, werden beim Installieren uebersprungen.
    Admin-Komponenten erzeugen nie einen Schritt.
    """
    befunde = befunde if befunde is not None else pruefe_alle(ziel)
    gewaehlt = sorted((komponente(i) for i in ids), key=lambda k: k.get("reihenfolge", 0))
    if aktion == "deinstallieren":
        return _plane_deinstallieren(gewaehlt, ziel, befunde)

    schritte = []
    venv_kommt = any(k["id"] == "venv" for k in gewaehlt) and befunde["venv"].status == FEHLT
    braucht_venv = [k for k in gewaehlt if k["art"] in ("pip", "aktion", "pruefung")
                    and k["id"] not in ("venv", "bc_python") + K.NUR_PRUEFEN]
    if braucht_venv and not ziel.python.is_file() and not venv_kommt:
        raise PlanFehler("Die Umgebung %s fehlt. 'Python-Umgebung anlegen' mit auswaehlen."
                         % ziel.venv)
    if befunde["venv"].status == ABWEICHEND and any(k["id"] == "venv" for k in gewaehlt):
        raise PlanFehler("Umgebung passt nicht (%s). Erst 'Umgebung loeschen', dann neu anlegen."
                         % befunde["venv"].detail)
    constraints = None

    for k in gewaehlt:
        kid, art, b = k["id"], k["art"], befunde.get(k["id"])
        if art == "admin" or kid in K.NUR_PRUEFEN:
            continue
        schon_ok = b is not None and b.status in (OK, NICHT_NOETIG)
        if aktion == "installieren" and schon_ok and art != "pruefung":
            continue

        if kid == "venv":
            basis = finde_python312(ziel.basis_python)
            if not basis:
                raise PlanFehler("Kein Python 3.12 gefunden. %s" % komponente("python312")["anleitung"])
            schritte.append(Schritt(kid, "Umgebung anlegen", [basis, "-m", "venv", ziel.venv]))
            schritte.append(Schritt(kid, "pip aktualisieren",
                                    _pip_basis(ziel) + ["install", "--upgrade", "pip"]
                                    + (_pip_quelle(ziel) if ziel.wheelhouse else [])))
        elif art == "pip":
            constraints = constraints or constraints_datei(ziel)
            cmd = _pip_basis(ziel) + ["install"] + list(k["pakete"]) + list(k.get("pip_extra", []))
            if aktion == "reparieren" and "--force-reinstall" not in cmd:
                cmd += ["--force-reinstall", "--no-deps"]
            cmd += ["-c", constraints] + _pip_quelle(ziel)
            schritte.append(Schritt(kid, k["titel"], cmd))
        elif kid == "bc_python":
            if ziel.ist_standardort:
                continue
            schritte.append(Schritt(kid, "BC_PYTHON setzen", ["setx", "BC_PYTHON", ziel.python]))
        elif kid == "ffmpeg":
            if not ziel.ffmpeg_zip:
                raise PlanFehler("FFmpeg: keine ZIP-Datei gewaehlt. " + k["anleitung"])
            z = ziel.ffmpeg_zip
            schritte.append(Schritt(kid, "FFmpeg kopieren", funktion=lambda log, z=z: ffmpeg_einspielen(z, ziel, log),
                                    beschreibung="ffmpeg.exe und DLLs aus %s nach %s kopieren" % (z, ziel.scripts)))
        elif kid == "gxipy":
            sdk = galaxy_sdk_pfad()
            if not sdk:
                continue                       # wartet auf das SDK; kein Fehler
            schritte.append(Schritt(kid, "gxipy einbinden", funktion=lambda log, s=sdk: gxipy_einbinden(s, ziel, log),
                                    beschreibung="Datei %s mit Inhalt %s schreiben"
                                    % (site_packages(ziel) / "gxipy.pth", sdk)))
        elif kid == "check_gpu":
            if ziel.build == "cpu":
                continue
            schritte.append(Schritt(kid, "GPU-Test", [ziel.python, "tools/check_gpu.py"],
                                    cwd=M4_DIR, darf_scheitern=True))
        elif kid == "selbsttest":
            schritte.append(Schritt(kid, "Hardwarefreie Tests", [ziel.python, "tests/run_all.py"],
                                    cwd=M4_DIR, darf_scheitern=True))
    return schritte


def _plane_deinstallieren(gewaehlt, ziel, befunde):
    schritte = []
    for k in reversed(gewaehlt):
        kid, art = k["id"], k["art"]
        if art in ("admin", "pruefung"):
            continue
        if art == "pip":
            if not ziel.python.is_file():
                continue
            namen = [zerlege(a)[0] for a in k["pakete"]]
            if kid == "torch":
                namen = [n for n in namen if n != "numpy"]   # brauchen auch andere
            schritte.append(Schritt(kid, "%s entfernen" % k["titel"],
                                    _pip_basis(ziel) + ["uninstall", "-y"] + namen))
        elif kid == "venv":
            schritte.append(Schritt(kid, "Umgebung loeschen",
                                    funktion=lambda log: umgebung_loeschen(ziel, log),
                                    beschreibung="Ordner %s komplett loeschen" % ziel.venv))
        elif kid == "bc_python":
            if befunde.get("bc_python") and befunde["bc_python"].status in (OK, ABWEICHEND):
                schritte.append(Schritt(kid, "BC_PYTHON entfernen",
                                        ["reg", "delete", r"HKCU\Environment", "/v", "BC_PYTHON", "/f"]))
        elif kid == "ffmpeg":
            schritte.append(Schritt(kid, "FFmpeg entfernen", funktion=lambda log: ffmpeg_entfernen(ziel, log),
                                    beschreibung="von FFmpeg kopierte Dateien aus %s loeschen" % ziel.scripts))
        elif kid == "gxipy":
            pth = site_packages(ziel) / "gxipy.pth"
            schritte.append(Schritt(kid, "gxipy.pth entfernen",
                                    funktion=lambda log, p=pth: _loesche_datei(p, log),
                                    beschreibung="Datei %s loeschen" % pth))
    # Umgebung loeschen macht Einzelschritte ueberfluessig
    if any(s.kid == "venv" for s in schritte):
        schritte = [s for s in schritte if s.kid in ("venv", "bc_python")]
    return schritte


# --------------------------------------------------------------------------
# Aktionen ohne Befehl
# --------------------------------------------------------------------------

FFMPEG_LISTE = "m4_setup_ffmpeg.txt"


def ffmpeg_einspielen(zip_pfad, ziel, log):
    """Kopiert ffmpeg.exe, ffprobe.exe und alle DLLs aus bin/ nach Scripts.
    Merkt sich die Dateien, damit Deinstallieren genau diese entfernt."""
    kopiert = []
    with zipfile.ZipFile(str(zip_pfad)) as z:
        for name in z.namelist():
            teile = name.replace("\\", "/").split("/")
            datei = teile[-1]
            if len(teile) < 2 or teile[-2] != "bin" or not datei:
                continue
            if not (datei.lower().endswith(".dll") or datei.lower() in ("ffmpeg.exe", "ffprobe.exe")):
                continue
            ziel_datei = ziel.scripts / datei
            if ziel_datei.exists() and not _von_uns(ziel, datei):
                log("  uebersprungen (existiert schon): %s" % datei)
                continue
            with z.open(name) as quelle, open(str(ziel_datei), "wb") as aus:
                shutil.copyfileobj(quelle, aus)
            kopiert.append(datei)
    if "ffmpeg.exe" not in kopiert and not (ziel.scripts / "ffmpeg.exe").is_file():
        raise RuntimeError("In der ZIP-Datei liegt kein bin/ffmpeg.exe (Build 'shared' gewaehlt?)")
    alt = _ffmpeg_liste(ziel)
    (ziel.venv / FFMPEG_LISTE).write_text("\n".join(sorted(set(alt) | set(kopiert))) + "\n", encoding="utf-8")
    log("  %d Dateien nach %s kopiert" % (len(kopiert), ziel.scripts))


def _ffmpeg_liste(ziel):
    p = ziel.venv / FFMPEG_LISTE
    if not p.is_file():
        return []
    return [z.strip() for z in p.read_text(encoding="utf-8").splitlines() if z.strip()]


def _von_uns(ziel, datei):
    return datei in _ffmpeg_liste(ziel)


def ffmpeg_entfernen(ziel, log):
    for datei in _ffmpeg_liste(ziel):
        _loesche_datei(ziel.scripts / datei, log, leise=True)
    _loesche_datei(ziel.venv / FFMPEG_LISTE, log, leise=True)
    log("  FFmpeg-Dateien entfernt")


def gxipy_einbinden(sdk_pfad, ziel, log):
    pth = site_packages(ziel) / "gxipy.pth"
    pth.write_text(str(sdk_pfad) + "\n", encoding="utf-8")
    log("  %s -> %s" % (pth, sdk_pfad))


def _loesche_datei(pfad, log, leise=False):
    try:
        Path(pfad).unlink()
        if not leise:
            log("  geloescht: %s" % pfad)
    except FileNotFoundError:
        pass


def umgebung_loeschen(ziel, log):
    """Loescht den Umgebungsordner -- aber nur, wenn er wirklich eine venv ist."""
    if not ziel.venv.exists():
        log("  %s existiert nicht" % ziel.venv)
        return
    if not (ziel.venv / "pyvenv.cfg").is_file():
        raise RuntimeError("%s enthaelt keine pyvenv.cfg -- wird aus Sicherheitsgruenden "
                           "nicht geloescht." % ziel.venv)
    if _gleich(ziel.venv, CODE_DIR) or _gleich(ziel.venv, M4_DIR) or len(ziel.venv.parts) < 3:
        raise RuntimeError("%s ist kein erlaubter Umgebungsordner." % ziel.venv)

    def schreibbar_machen(fn, pfad, _info):
        os.chmod(pfad, 0o700)
        fn(pfad)

    shutil.rmtree(str(ziel.venv), onerror=schreibbar_machen)
    log("  %s geloescht" % ziel.venv)


# --------------------------------------------------------------------------
# Ausfuehren
# --------------------------------------------------------------------------

class Lauf(object):
    """Fuehrt Schritte nacheinander aus und schreibt alles in eine Logdatei.

    ausgabe(text) bekommt jede Zeile (Fenster oder Konsole). abbrechen() ist
    aus einem anderen Thread erlaubt.
    """

    def __init__(self, ausgabe=print):
        self.ausgabe = ausgabe
        self._abbruch = False
        self._prozess = None
        LOG_DIR.mkdir(exist_ok=True)
        self.log_datei = LOG_DIR / ("setup_%s.log" % datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))
        self._log = open(str(self.log_datei), "a", encoding="utf-8")
        self.ergebnisse = {}           # kid -> Befund (fuer Tests)

    def zeile(self, text):
        self._log.write(text + "\n")
        self._log.flush()
        try:
            self.ausgabe(text)
        except UnicodeError:           # Konsole in cp1252 kann z. B. tqdm-Balken nicht
            self.ausgabe(text.encode("ascii", "replace").decode("ascii"))

    def abbrechen(self):
        self._abbruch = True
        p = self._prozess
        if p is not None and p.poll() is None:
            p.terminate()

    def __call__(self, schritte):
        """True, wenn alle Pflichtschritte geklappt haben."""
        alles_ok = True
        try:
            for i, s in enumerate(schritte, 1):
                if self._abbruch:
                    self.zeile("Abgebrochen.")
                    return False
                self.zeile("")
                self.zeile("[%d/%d] %s" % (i, len(schritte), s.text))
                self.zeile("> " + s.als_text())
                ok = self._ein_schritt(s)
                if s.kid in ("check_gpu", "selbsttest"):
                    self.ergebnisse[s.kid] = Befund(OK if ok else WARNUNG,
                                                    "bestanden" if ok else "Fehler, siehe Log")
                if not ok and not s.darf_scheitern:
                    self.zeile("FEHLER in Schritt %d (%s). Abgebrochen; Log: %s"
                               % (i, s.text, self.log_datei))
                    return False
                if not ok:
                    alles_ok = False
                    self.zeile("Warnung: Schritt mit Fehlern beendet, es geht weiter.")
            self.zeile("")
            self.zeile("Fertig. Log: %s" % self.log_datei)
            return alles_ok
        finally:
            self._log.close()

    def _ein_schritt(self, s):
        if s.funktion is not None:
            try:
                s.funktion(self.zeile)
                return True
            except Exception as exc:
                self.zeile("  %s: %s" % (type(exc).__name__, exc))
                return False
        try:
            self._prozess = subprocess.Popen(
                s.cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                cwd=str(s.cwd) if s.cwd else None, env=_kind_env(), creationflags=_flags())
        except OSError as exc:
            self.zeile("  kann nicht starten: %s" % exc)
            return False
        for roh in iter(self._prozess.stdout.readline, b""):
            self.zeile("  " + roh.decode("utf-8", "replace").rstrip())
        rc = self._prozess.wait()
        self._prozess.stdout.close()
        self._prozess = None
        if rc != 0:
            self.zeile("  Rueckgabewert %d" % rc)
        return rc == 0


# --------------------------------------------------------------------------
# Checkliste fuer den Laborbetreuer, Offline-Paketordner
# --------------------------------------------------------------------------

def checkliste(ziel, befunde):
    """Markdown: Admin-Punkte mit Status, dann die Freigabeliste aller Komponenten."""
    heute = datetime.date.today().isoformat()
    z = ["# M4-Einrichtung: Checkliste fuer den Laborbetreuer", "",
         "Erzeugt am %s auf `%s` vom Setup-Programm (`code/setup`)." % (heute, os.environ.get("COMPUTERNAME", "?")),
         "", "Zielordner der Umgebung: `%s` (Build: %s)" % (ziel.venv, ziel.build.upper()), "",
         "## 1. Braucht Admin-Rechte (gemeinsamer Termin)", "",
         "| erledigt | Punkt | Stand | Was zu tun ist |", "|---|---|---|---|"]
    for k in K.KOMPONENTEN:
        if k["art"] != "admin":
            continue
        b = befunde[k["id"]]
        haken = "x" if b.ok else " "
        z.append("| [%s] | %s | %s %s | %s |" % (haken, k["titel"], STATUS_TEXT[b.status],
                                              _md(b.detail), _md(k.get("anleitung", ""))))
    z += ["", "## 2. Ohne Admin-Rechte, in den Zielordner (Freigabeliste)", "",
          "| Komponente | Pakete / Inhalt | Quelle | Groesse | Stand |", "|---|---|---|---|---|"]
    for k in K.KOMPONENTEN:
        if k["art"] in ("admin",) or k["id"] in K.NUR_PRUEFEN:
            continue
        b = befunde[k["id"]]
        inhalt = ", ".join(k.get("pakete", [])) or k.get("info", "")
        z.append("| %s | %s | %s | %s | %s |" % (k["titel"], _md(inhalt), _md(k.get("quelle", "")),
                                              k.get("groesse", ""), STATUS_TEXT[b.status]))
    z += ["", "Exakte Versionen aller mitgezogenen Pakete: `code/%s`." % K.LOCK,
          "Python-Pakete kommen aus pypi.org bzw. %s." % K.TORCH_INDEX[ziel.build],
          "", "## 3. Systempruefung", "", "| Punkt | Stand |", "|---|---|"]
    for kid in ("python312", "speicher"):
        b = befunde[kid]
        z.append("| %s | %s %s |" % (komponente(kid)["titel"], STATUS_TEXT[b.status], _md(b.detail)))
    return "\n".join(z) + "\n"


def _md(text):
    return str(text).replace("|", "/").replace("\n", " ")


def wheelhouse_befehle(ordner, build="gpu"):
    """pip-download-Befehle, um auf einem Rechner MIT Internet alle Pakete fuer
    eine Offline-Installation zu sammeln (Python 3.12, win_amd64)."""
    ziel = Ziel(build=build)
    c = constraints_datei(ziel)
    pakete = [p for k in K.KOMPONENTEN if k["art"] == "pip" for p in k["pakete"]]
    return [[sys.executable, "-m", "pip", "download", "--dest", ordner,
             "--only-binary=:all:", "--platform", "win_amd64", "--python-version", "3.12",
             "-c", str(c), "--extra-index-url", K.TORCH_INDEX[build], "pip"] + pakete]

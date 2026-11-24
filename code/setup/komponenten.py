"""Komponenten-Katalog des M4-Setup-Programms.

Die einzige Stelle, an der steht, was installiert wird. Fenster, Kommandozeile
und die Checkliste fuer den Laborbetreuer lesen alle diese Liste. Wer etwas
hinzufuegt oder eine Version aendert, tut es hier (und in
m4_behavior_cloning/Dokumentation/environment-lock.txt).

Bewusst eine Python-Datei statt YAML: Das Setup-Programm laeuft mit dem
Python, das auf dem Rechner schon da ist, und braucht nur die
Standardbibliothek (PyYAML gibt es dort noch nicht).

Felder je Komponente
    id           eindeutiger Schluessel (Kommandozeile: --nur torch,lerobot)
    gruppe       Schluessel aus GRUPPEN
    titel        eine Zeile im Fenster
    info         warum die Komponente gebraucht wird (Tooltip/Checkliste)
    groesse      ungefaehrer Download, nur zur Anzeige
    art          "pip"      pip install in die M4-Umgebung (kein Admin)
                 "aktion"   eigene Funktion des Setup-Programms (kein Admin)
                 "admin"    wird NIE automatisch installiert, nur geprueft und in
                            die Checkliste fuer den Laborbetreuer geschrieben
                 "pruefung" installiert nichts; System-Pruefung oder Abnahmetest
    standard     beim Start angehakt, sofern es noch fehlt
    pakete       nur "pip": Anforderungen wie in requirements.txt
    pip_extra    nur "pip": zusaetzliche pip-Argumente
    anleitung    was man von Hand tun muss (Handinstallation / Admin-Termin)
    quelle       woher es kommt (fuer die Freigabe-Checkliste)
    reihenfolge  Installationsreihenfolge (klein zuerst)

Wie die Pruefung je Komponente aussieht, steht in kern.py (PRUEFUNGEN).
"""

#: Exakte Versionen des abgenommenen Trainings-PCs (RTX 5070 Ti, 11.09.2026).
#: Wird bei jedem pip-Aufruf als Constraints-Datei (-c) mitgegeben: Damit landen
#: auch alle mitgezogenen Pakete auf diesen Versionen, obwohl die Gruppen einzeln
#: installiert werden.
LOCK = "m4_behavior_cloning/Dokumentation/environment-lock.txt"

TORCH_INDEX = {
    "gpu": "https://download.pytorch.org/whl/cu128",
    "cpu": "https://download.pytorch.org/whl/cpu",
}

GALAXY_SDK_PYTHON = r"Daheng Imaging\GalaxySDK\Development\Samples\Python"

GRUPPEN = [
    ("system", "1  System (nur Pruefung)"),
    ("umgebung", "2  M4-Umgebung"),
    ("torch", "3  PyTorch"),
    ("training", "4  LeRobot und Training"),
    ("werkzeuge", "5  Oberflaeche und Werkzeuge"),
    ("hardware", "6  Roboter und Kameras"),
    ("abschluss", "7  Abnahme"),
]

KOMPONENTEN = [
    # -- 1 System -----------------------------------------------------------
    dict(id="python312", gruppe="system", art="pruefung", standard=True,
         titel="Python 3.12 als Basis fuer die Umgebung",
         info="LeRobot 0.6.1 verlangt Python 3.12.",
         quelle="python.org",
         anleitung="python.org -> Windows installer (64-bit) 3.12.x. "
                   "'Install for me only' geht ohne Admin; 'py launcher' anhaken. "
                   "Liegt Python woanders: im Fenster 'Basis-Python' waehlen."),
    dict(id="nvidia", gruppe="system", art="admin", standard=True,
         titel="NVIDIA-Treiber mit CUDA >= 12.8 (Treiber >= 570)",
         info="Training und Policy-Fahrt auf der GPU. Ohne GPU den CPU-Build "
              "waehlen: Aufnahme und Export gehen, Training nicht.",
         quelle="nvidia.com/drivers",
         anleitung="Aktuellen Studio- oder Game-Ready-Treiber (>= 570) installieren. "
                   "Braucht Admin -> Laborbetreuer."),
    dict(id="vcredist", gruppe="system", art="admin", standard=True,
         titel="Microsoft Visual C++ Redistributable 2015-2022 (x64)",
         info="PyTorch laedt ohne es seine DLLs nicht (Fehler bei c10.dll).",
         quelle="https://aka.ms/vs/17/release/vc_redist.x64.exe",
         anleitung="vc_redist.x64.exe ausfuehren. Braucht Admin -> Laborbetreuer."),
    dict(id="speicher", gruppe="system", art="pruefung", standard=True,
         titel="Freier Speicher am Zielort (mind. 15 GB)",
         info="Umgebung ca. 8-10 GB, dazu der pip-Zwischenspeicher.",
         anleitung="Anderen Zielordner waehlen oder Platz schaffen."),

    # -- 2 Umgebung ---------------------------------------------------------
    dict(id="venv", gruppe="umgebung", art="aktion", standard=True, reihenfolge=10,
         titel="Python-Umgebung anlegen (venv mit Python 3.12)",
         info="Ein abgekapselter Ordner; das System wird nicht veraendert. "
              "Loeschen des Ordners entfernt alles wieder.",
         quelle="Python-Standardbibliothek",
         anleitung="<basis-python> -m venv <ziel>\n"
                   "<ziel>\\Scripts\\python.exe -m pip install --upgrade pip"),
    dict(id="bc_python", gruppe="umgebung", art="aktion", standard=True, reihenfolge=11,
         titel="Benutzervariable BC_PYTHON auf die Umgebung setzen",
         info="Nur noetig, wenn die Umgebung NICHT unter "
              "code\\m4_behavior_cloning\\.venv liegt: Projekt-GUI und "
              "BC-Oberflaeche finden sie dann ueber diese Variable. "
              "Benutzer-Variable, kein Admin.",
         quelle="Windows (setx)",
         anleitung="setx BC_PYTHON \"<ziel>\\Scripts\\python.exe\""),

    # -- 3 PyTorch ----------------------------------------------------------
    dict(id="torch", gruppe="torch", art="pip", standard=True, reihenfolge=20,
         titel="torch 2.11.0 + torchvision 0.26.0",
         info="GPU: CUDA-12.8-Build (enthaelt sm_120 fuer RTX 50xx). "
              "CPU: kleiner Build ohne CUDA. Umschaltbar oben im Fenster.",
         groesse="2,5 GB / 250 MB",
         quelle="download.pytorch.org",
         pakete=["torch==2.11.0", "torchvision==0.26.0", "numpy>=2.0,<2.3"]),

    # -- 4 Training ---------------------------------------------------------
    dict(id="lerobot", gruppe="training", art="pip", standard=True, reihenfolge=30,
         titel="LeRobot 0.6.1 mit diffusers und datasets",
         info="Version ist fest: Datensaetze (Format v3.0) und Checkpoints haengen "
              "daran (bc.config.LEROBOT_VERSION).",
         groesse="400 MB",
         quelle="pypi.org",
         pakete=["lerobot==0.6.1", "diffusers==0.39.0", "datasets==4.8.5"]),
    dict(id="video", gruppe="training", art="pip", standard=True, reihenfolge=31,
         titel="Video: torchcodec 0.11.1 + PyAV 15.1.0",
         info="Episodenvideos schreiben (PyAV) und beim Training lesen (torchcodec).",
         groesse="60 MB",
         quelle="pypi.org",
         pakete=["torchcodec==0.11.1", "av==15.1.0"]),
    dict(id="ffmpeg", gruppe="training", art="aktion", standard=False, reihenfolge=32,
         titel="FFmpeg (LGPL, shared) in die Umgebung kopieren",
         info="Optional, schnelleres Dekodieren beim Training. Ohne FFmpeg nimmt "
              "LeRobot PyAV. Kein PATH-Eintrag: die Dateien liegen nur in "
              "<ziel>\\Scripts. Braucht eine heruntergeladene ZIP-Datei.",
         groesse="100 MB",
         quelle="z. B. github.com/BtbN/FFmpeg-Builds (win64-lgpl-shared)",
         anleitung="Build 'win64-lgpl-shared' als ZIP herunterladen und im Fenster "
                   "auswaehlen (oder --ffmpeg-zip). Von Hand: bin\\*.dll und "
                   "ffmpeg.exe nach <ziel>\\Scripts kopieren."),

    # -- 5 Werkzeuge --------------------------------------------------------
    dict(id="gui", gruppe="werkzeuge", art="pip", standard=True, reihenfolge=40,
         titel="Bedienoberflaeche: PySide6",
         info="BC-Oberflaeche (python -m bc.gui).",
         groesse="200 MB",
         quelle="pypi.org",
         pakete=["PySide6>=6.6,<7"]),
    dict(id="gamepad", gruppe="werkzeuge", art="pip", standard=True, reihenfolge=41,
         titel="Gamepad zum Teachen: pygame",
         groesse="10 MB",
         quelle="pypi.org",
         pakete=["pygame>=2.5,<3"]),
    dict(id="tests", gruppe="werkzeuge", art="pip", standard=True, reihenfolge=42,
         titel="Tests: pytest, scipy",
         groesse="40 MB",
         quelle="pypi.org",
         pakete=["pytest>=8,<9", "scipy>=1.13,<2"]),
    dict(id="report", gruppe="werkzeuge", art="pip", standard=False, reihenfolge=43,
         titel="Diagramme fuer Berichte: matplotlib",
         info="Nur fuer tools/report_*.py.",
         groesse="10 MB",
         quelle="pypi.org",
         pakete=["matplotlib>=3.8,<4"]),
    dict(id="opencv", gruppe="werkzeuge", art="pip", standard=True, reihenfolge=49,
         titel="OpenCV mit Fenstern (opencv-python statt headless)",
         info="LeRobot zieht opencv-python-headless, die Kamera-Vorschau braucht "
              "cv2.imshow. Deshalb immer ZULETZT und ohne Abhaengigkeiten.",
         groesse="40 MB",
         quelle="pypi.org",
         pakete=["opencv-python>=4.9,<4.14"],
         pip_extra=["--force-reinstall", "--no-deps"]),

    # -- 6 Hardware ---------------------------------------------------------
    dict(id="neurapy", gruppe="hardware", art="pip", standard=True, reihenfolge=45,
         titel="Roboter-Client neurapy: prettytable, pywin32",
         info="neurapy liegt im Repo, braucht aber diese beiden Pakete.",
         groesse="15 MB",
         quelle="pypi.org",
         pakete=["prettytable>=3.0", "pywin32>=306"]),
    dict(id="galaxy_sdk", gruppe="hardware", art="admin", standard=True,
         titel="Daheng Galaxy SDK (Kameratreiber)",
         info="Draufsicht- und Wrist-Kamera. Installiert Treiber, braucht deshalb Admin.",
         quelle="Daheng Imaging (Download-Bereich)",
         anleitung="Galaxy SDK fuer Windows installieren (Kamera-Inbetriebnahme.md). "
                   "Braucht Admin -> Laborbetreuer."),
    dict(id="gxipy", gruppe="hardware", art="aktion", standard=True, reihenfolge=50,
         titel="gxipy aus dem Galaxy SDK in die Umgebung einbinden",
         info="Legt nur die Datei gxipy.pth in der Umgebung an, kein Admin.",
         quelle="Galaxy SDK (lokal)",
         anleitung="Datei <ziel>\\Lib\\site-packages\\gxipy.pth mit dem Pfad "
                   "...\\" + GALAXY_SDK_PYTHON + " anlegen."),

    # -- 7 Abnahme ----------------------------------------------------------
    dict(id="check_gpu", gruppe="abschluss", art="pruefung", standard=True, reihenfolge=90,
         titel="GPU-Test (tools/check_gpu.py: sm_120, Durchsatz)",
         info="Nur mit GPU-Build sinnvoll.",
         anleitung="<ziel>\\Scripts\\python.exe tools\\check_gpu.py"),
    dict(id="selbsttest", gruppe="abschluss", art="pruefung", standard=True, reihenfolge=91,
         titel="Hardwarefreie Tests (tests/run_all.py)",
         info="Bekannt: test_rectify::test_homography_recovers_marker_positions "
              "schlaegt auch auf dem Trainings-PC fehl.",
         anleitung="<ziel>\\Scripts\\python.exe tests\\run_all.py"),
]

#: Komponenten, die das System nur pruefen und nicht anfassen
NUR_PRUEFEN = ("python312", "nvidia", "vcredist", "speicher", "galaxy_sdk")

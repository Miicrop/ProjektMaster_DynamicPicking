@echo off
rem Richtet einmalig die eigene Python-Umgebung von M4 (Behavior Cloning) ein:
rem   code\m4_behavior_cloning\.venv  mit Python 3.12, torch, lerobot 0.6.1
rem Die GUI (start_gui.bat) nimmt sie danach automatisch fuer Training, Export und Inferenz.
rem
rem Warum eigen: lerobot 0.6.1 braucht Python 3.12, und torch/OpenCV vertragen sich nicht mit
rem EasyOCR (M3) in der GUI-Umgebung. Versionen wie von Person 4 festgelegt
rem (m4_behavior_cloning\Dokumentation\environment-lock.txt, Environment-Laptop.md).
rem
rem   setup_m4.bat          mit NVIDIA-Karte: torch mit CUDA (cu128), sonst CPU-Build
rem   setup_m4.bat --cpu    immer CPU-Build (Laptop: Aufnahme, Export, Tests; kein Training)
setlocal
cd /d "%~dp0m4_behavior_cloning"
set "PY=.venv\Scripts\python.exe"
set "PIP=%PY% -m pip install --disable-pip-version-check"

if not exist "%PY%" (
    py -3.12 --version >nul 2>&1 || (
        echo Python 3.12 fehlt. Installieren von https://www.python.org/downloads/ ^(Python Launcher "py" mit^),
        echo dann setup_m4.bat erneut starten.
        pause & exit /b 1
    )
    echo Lege die M4-Umgebung an: %CD%\.venv
    py -3.12 -m venv .venv || (pause & exit /b 1)
)
%PY% -m pip install --upgrade pip --disable-pip-version-check || (pause & exit /b 1)

set "GPU=0"
if /i not "%~1"=="--cpu" (
    nvidia-smi >nul 2>&1 && set "GPU=1"
)

if "%GPU%"=="1" (
    echo NVIDIA-Karte gefunden: torch mit CUDA ^(cu128, ca. 2,5 GB^)
    %PIP% -r Dokumentation\environment-lock.txt --extra-index-url https://download.pytorch.org/whl/cu128 || (pause & exit /b 1)
) else (
    echo Keine NVIDIA-Karte ^(oder --cpu^): torch als CPU-Build - Training verweigert die GUI dann mit Hinweis
    %PIP% "numpy>=2.0,<2.3" "torch==2.11.0" "torchvision==0.26.0" "lerobot==0.6.1" "diffusers==0.39.0" "torchcodec==0.11.1" "av==15.1.0" "datasets==4.8.5" || (pause & exit /b 1)
)
%PIP% "PySide6>=6.6,<7" "scipy>=1.13,<2" "prettytable>=3.0" "pywin32>=306" "pygame>=2.5,<3" || (pause & exit /b 1)
rem lerobot zieht opencv-python-headless; die Werkzeuge brauchen die Variante mit Fenstern -> zuletzt
%PIP% "opencv-python>=4.9,<4.14" --upgrade --force-reinstall --no-deps || (pause & exit /b 1)

rem Daheng-Kameras (Draufsicht = Szenenkamera, Wrist): gxipy kommt aus dem Galaxy SDK, nicht von pip
set "GX=C:\Program Files\Daheng Imaging\GalaxySDK\Development\Samples\Python"
if exist "%GX%\gxipy" (
    for /f "delims=" %%s in ('%PY% -c "import sysconfig; print(sysconfig.get_paths()['purelib'])"') do echo %GX%> "%%s\gxipy.pth"
    echo gxipy aus dem Galaxy SDK eingebunden.
) else (
    echo Hinweis: Galaxy SDK nicht gefunden - fuer die Daheng-Kameras installieren ^(Kamera-Inbetriebnahme.md^).
)

if "%GPU%"=="1" %PY% tools\check_gpu.py
echo.
echo Fertig. Pruefen: im Reiter "M4 Behavior Cloning" -^> Training zeigt torch und lerobot als vorhanden.
echo FFmpeg ^(fuer Export/Training^): ffmpeg.exe nach %CD%\.venv\Scripts legen, siehe Environment-Laptop.md 5.3.
pause
endlocal

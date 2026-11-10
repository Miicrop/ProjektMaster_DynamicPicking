@echo off
rem M4-Setup (Behavior Cloning): richtet die eigene Python-Umgebung von M4 ein.
rem
rem Doppelklick oeffnet das Setup-Fenster: jede Komponente mit Haekchen und Status,
rem nach Themen sortiert. Admin-Punkte (Treiber, Kamera-SDK) werden nur geprueft und
rem als Checkliste fuer den Laborbetreuer ausgegeben, nie selbst installiert.
rem
rem Beispiele (alles Weitere: setup_m4.bat --help, oder setup\README.md):
rem   setup_m4.bat                       Fenster
rem   setup_m4.bat --cpu                 Fenster, CPU-Build vorgewaehlt
rem   setup_m4.bat --status              nur pruefen, in der Konsole
rem   setup_m4.bat --befehle             zeigen, was installiert wuerde
rem   setup_m4.bat --installieren --ja   Vorauswahl ohne Fenster installieren
rem
rem Das Setup-Programm braucht nur ein beliebiges Python ab 3.8 (Standardbibliothek).
rem Die Umgebung selbst wird mit Python 3.12 angelegt (Vorgabe von LeRobot 0.6.1).
setlocal
cd /d "%~dp0"

set "PY="
py -3 -c "" >nul 2>&1 && set "PY=py -3"
if not defined PY python -c "" >nul 2>&1 && set "PY=python"
if not defined PY (
    echo Kein Python gefunden. Python 3.12 von https://www.python.org/downloads/ installieren
    echo ^("Install for me only" geht ohne Admin, "py launcher" anhaken^), dann erneut starten.
    pause & exit /b 1
)

%PY% setup\m4_setup.py %*
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" pause
endlocal & exit /b %RC%

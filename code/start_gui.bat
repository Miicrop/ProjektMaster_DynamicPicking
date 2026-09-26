@echo off
rem Startet die GUI per Doppelklick. Voraussetzung: venv eingerichtet (siehe README.md).
rem Optional: start_gui.bat --tab m2   (auto, m1, m2, m3, settings)
cd /d "%~dp0"
call .venv\Scripts\activate.bat
python -m gui %*
if errorlevel 1 pause

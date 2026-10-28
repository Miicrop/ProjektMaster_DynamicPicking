@echo off
rem Startet die GUI per Doppelklick. Voraussetzung: venv eingerichtet (siehe README.md).
rem Optional: start_gui.bat --tab m2   (auto, m1, m2, m3, m4, settings)
rem M4 (Behavior Cloning) uses its own Python from m4_behavior_cloning\.venv for training/inference.
cd /d "%~dp0"
call .venv\Scripts\activate.bat
python -m gui %*
if errorlevel 1 pause

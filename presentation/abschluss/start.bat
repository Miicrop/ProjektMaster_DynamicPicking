@echo off
rem Abschlusspraesentation offline starten (dist/ per Vite-Preview, sonst Python)
cd /d "%~dp0"
if not exist dist\index.html (
  echo dist\ fehlt - einmal "npm run build" ausfuehren.
  pause
  exit /b 1
)
where node >nul 2>nul
if %errorlevel%==0 if exist node_modules\vite\bin\vite.js (
  node node_modules\vite\bin\vite.js preview --port 8124 --open
  pause
  exit /b
)
cd dist
start "" http://localhost:8124/
python "%~dp0serve.py" 8124
pause

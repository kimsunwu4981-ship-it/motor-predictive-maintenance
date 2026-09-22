@echo off
rem run_dashboard_electrical.bat - opens the ELECTRICAL fault dashboard (offline).
rem Path may contain spaces/Korean: use %~dp0 and never pass absolute paths as arguments.
cd /d "%~dp0"
where node >nul 2>nul
if errorlevel 1 (
  echo Node.js is required. Install from https://nodejs.org and run again.
  pause
  exit /b 1
)
if not exist "dist\index.html" (
  echo dist\index.html not found. Run "npm run build" first.
  pause
  exit /b 1
)
node serve.cjs --open electrical

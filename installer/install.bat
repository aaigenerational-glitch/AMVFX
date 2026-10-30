@echo off
rem AMVFX installer (Windows): checkbox GUI when possible.
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py install.py %*
) else (
  python install.py %*
)
pause

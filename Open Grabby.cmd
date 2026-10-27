@echo off
where pythonw >nul 2>&1
if not errorlevel 1 (
  start "" pythonw "%~dp0grabby.py" gui
) else (
  python "%~dp0grabby.py" gui
)

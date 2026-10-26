@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  set "PYCMD=python"
) else (
  set "PYCMD=py -3"
)
%PYCMD% -c "import reportlab, docx" >nul 2>nul
if errorlevel 1 (
  echo Installing PDF and document dependencies...
  %PYCMD% -m pip install -r requirements.txt
  if errorlevel 1 (
    echo PDF export requires reportlab and python-docx.
    echo Run: %PYCMD% -m pip install -r requirements.txt
    pause
    exit /b 1
  )
)
echo PATHFINDER EDU local server launching...
%PYCMD% server.py
if errorlevel 1 (
  echo Server error. Please copy the error message above.
  pause
)

@echo off
setlocal
cd /d "%~dp0"
echo PATHFINDER EDU - administrator API setup
 echo Open the browser, login as ADMIN, and choose API key and tracking settings.
echo Secret keys are encrypted with the current Windows user account.
where py >nul 2>nul
if errorlevel 1 (
  set "PYCMD=python"
) else (
  set "PYCMD=py -3"
)
%PYCMD% -c "import reportlab, docx" >nul 2>nul
if errorlevel 1 (
  %PYCMD% -m pip install -r requirements.txt
  if errorlevel 1 (
    echo Python requirements installation failed.
    pause
    exit /b 1
  )
)
%PYCMD% api_launcher.py
if errorlevel 1 (
 echo See the error message above.
 pause
)

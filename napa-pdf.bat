@echo off
rem napa-pdf launcher - finds a usable Python and starts the TUI
setlocal enabledelayedexpansion

set "PY="
call :try "%USERPROFILE%\.workbuddy\binaries\python\envs\default\Scripts\python.exe"
call :try "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
call :try "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
if not defined PY call :try python

if not defined PY goto :nopy

cd /d "%~dp0"
"%PY%" -X utf8 main.py %*
if errorlevel 1 pause
endlocal
exit /b 0

:try
if defined PY exit /b 0
if exist "%~1" (
    set "PY=%~1"
    exit /b 0
)
exit /b 0

:nopy
echo [napa-pdf] No usable Python interpreter was found.
echo.
echo Please install Python 3.10+ and then run:
echo     pip install pymupdf fonttools prompt_toolkit
echo.
pause
endlocal
exit /b 1
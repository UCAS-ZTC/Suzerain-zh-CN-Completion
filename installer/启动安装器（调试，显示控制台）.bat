@echo off
setlocal
rem Debug launcher: same installer, console stays open, errors are visible.
powershell.exe -NoProfile -ExecutionPolicy Bypass -STA -File "%~dp0Installer.ps1" %*
set EXITCODE=%ERRORLEVEL%
echo.
if not "%EXITCODE%"=="0" (echo Installer exited with code %EXITCODE%. & pause)
exit /b %EXITCODE%

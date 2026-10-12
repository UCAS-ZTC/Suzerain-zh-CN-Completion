@echo off
rem Suzerain CN installer (GUI). Needs Windows PowerShell 5.1, which is built into Windows 10 / 11.
rem If no window appears, run the "Debug" launcher in this folder instead: it keeps the console open and shows errors.
start "" powershell.exe -NoProfile -ExecutionPolicy Bypass -STA -WindowStyle Hidden -File "%~dp0Installer.ps1" %*

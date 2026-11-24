@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install-Korean.ps1" -Uninstall -GameDir "%~1"
pause

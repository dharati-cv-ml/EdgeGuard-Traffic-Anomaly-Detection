@echo off
 cd /d "%~dp0"
 py -3.14 -m edgeguard.desktop
 if errorlevel 1 (
   echo.
   echo If Python 3.14 is unavailable, run: py -m edgeguard.desktop
   pause
 )

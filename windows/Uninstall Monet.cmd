@echo off
rem Double-click to remove Monet Bridge. Windows will ask for permission.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Uninstall-Monet.ps1" %*

@echo off
rem Double-click to install Monet Bridge. Windows will ask for permission.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install-Monet.ps1" %*

@echo off
setlocal
title Monet
cls
echo.
echo     Monet is installing Windows for your games.
echo     Your PC restarts when it is ready.
echo.
"%SYSTEMDRIVE%\monet\monet-setup-check.exe" --deploy "%SYSTEMDRIVE%\monet\deployment.json"
if errorlevel 1 goto fail
echo.
echo     Windows is installed. Restarting...
wpeutil reboot
exit /b 0

:fail
echo.
echo     Windows setup stopped safely. The details are shown above.
echo     Your PC returns to Monet in a minute so you can try again.
ping -n 60 127.0.0.1 >nul
wpeutil reboot
exit /b 1

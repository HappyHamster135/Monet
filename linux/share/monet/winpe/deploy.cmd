@echo off
rem Monet: installs Windows for games, with no questions.
rem Started by monet-start.cmd with the setup partition's drive letter.
setlocal
title Monet
cls
echo.
echo     Monet is installing Windows for your games.
echo     This takes about 10 minutes. Your PC restarts by itself.
echo.

set "SETUP=%~1"
set "TARGET="
for %%d in (C D E F G H I J K L M N O P Q R S T U V W Y Z) do (
    vol %%d: 2>nul | find /i "MONETWIN" >nul && set "TARGET=%%d"
)
if not defined TARGET goto fail

rem Monet made this partition for Windows; empty it first, in case an earlier
rem try stopped halfway.
format %TARGET%: /fs:ntfs /q /y /v:MONETWIN >nul
if errorlevel 1 goto fail
dism /apply-image /imagefile:%SETUP%:\sources\install.swm /swmfile:%SETUP%:\sources\install*.swm /index:1 /applydir:%TARGET%:\
if errorlevel 1 goto fail
label %TARGET%: Windows

rem Boot files go on the EFI partition Monet shares with Windows.
set "ESP="
for %%l in (S R Q P O N) do (
    if not defined ESP if not exist %%l:\ set "ESP=%%l"
)
mountvol %ESP%: /s >nul 2>&1 && (
    bcdboot %TARGET%:\Windows /s %ESP%: /f UEFI >nul
) || (
    bcdboot %TARGET%:\Windows /f UEFI >nul
)
if errorlevel 1 goto fail

md %TARGET%:\Windows\Panther 2>nul
copy /y %SETUP%:\monet\unattend.xml %TARGET%:\Windows\Panther\unattend.xml >nul
xcopy /e /i /y /q %SETUP%:\monet\bridge %TARGET%:\ProgramData\Monet\Setup >nul

echo.
echo     Windows is installed. Restarting...
wpeutil reboot
goto :eof

:fail
echo.
echo     Windows couldn't be installed. Your PC goes back to Monet in a minute.
echo     In Monet, choose Windows in the app menu to try again.
ping -n 60 127.0.0.1 >nul
wpeutil reboot

@echo off
rem Only run Monet's trusted copy inside the WinPE RAM image.
wpeinit
call "%SYSTEMDRIVE%\monet\deploy.cmd"
exit /b %errorlevel%

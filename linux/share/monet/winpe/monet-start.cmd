@echo off
rem Monet: runs instead of the Windows Setup wizard. Finds Monet's setup
rem partition and starts the install script on it.
wpeinit
for %%d in (C D E F G H I J K L M N O P Q R S T U V W Y Z) do (
    if exist %%d:\monet\deploy.cmd (
        call %%d:\monet\deploy.cmd %%d
        exit /b
    )
)
echo.
echo     Monet's setup files weren't found. Your PC restarts in a minute.
ping -n 60 127.0.0.1 >nul
wpeutil reboot

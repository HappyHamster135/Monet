<#
.SYNOPSIS
    Removes Monet Bridge from Windows. Your games and settings are not touched.
#>
param(
    [switch]$NoPause
)

$ErrorActionPreference = 'Continue'

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$isAdmin = ([Security.Principal.WindowsPrincipal]$identity).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Start-Process powershell.exe -Verb RunAs -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "`"$PSCommandPath`"")
    exit
}

Write-Host 'Removing Monet Bridge...'

Get-ScheduledTask -TaskPath '\Monet\' -ErrorAction SilentlyContinue | ForEach-Object {
    Stop-ScheduledTask -InputObject $_ -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -InputObject $_ -Confirm:$false
}
& schtasks.exe /delete /tn '\Monet' /f 2>$null | Out-Null
Get-Process monet-bridge -ErrorAction SilentlyContinue | Stop-Process -Force

$startMenu = Join-Path $env:ProgramData 'Microsoft\Windows\Start Menu\Programs'
$desktop = [Environment]::GetFolderPath('CommonDesktopDirectory')
Remove-Item -Force -ErrorAction SilentlyContinue (Join-Path $startMenu 'Back to Monet.lnk'), (Join-Path $desktop 'Back to Monet.lnk')

Remove-Item -Recurse -Force -ErrorAction SilentlyContinue (Join-Path $env:ProgramFiles 'Monet'), (Join-Path $env:ProgramData 'Monet')
Remove-Item -Force -ErrorAction SilentlyContinue (Join-Path $env:ProgramData 'Microsoft\Windows\Start Menu\Programs\StartUp\Finish Monet setup.cmd')
Remove-Item -Recurse -Force -ErrorAction SilentlyContinue 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Monet'

Write-Host ''
Write-Host 'Monet Bridge is removed.' -ForegroundColor Green
if (-not $NoPause) {
    Write-Host ''
    Read-Host 'Press Enter to close'
}

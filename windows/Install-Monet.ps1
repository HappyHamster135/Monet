<#
.SYNOPSIS
    Installs Monet Bridge, the Windows half of Monet.

.DESCRIPTION
    - Copies monet-bridge.exe to C:\Program Files\Monet
    - Turns on full hibernation and turns off Fast Startup, so Windows can
      resume in seconds when you switch from Monet
    - Creates three scheduled tasks under \Monet\ (agent, launcher, back)
    - Adds "Back to Monet" to the Start menu and the desktop

    Nothing is removed from Windows. For the optional performance settings,
    run GameProfile.ps1 afterwards.

.PARAMETER GameProfile
    Also apply the safe performance settings from GameProfile.ps1.
#>
param(
    [switch]$GameProfile
)

$ErrorActionPreference = 'Stop'

# Ask for administrator rights if we don't have them yet.
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$isAdmin = ([Security.Principal.WindowsPrincipal]$identity).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    $argList = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "`"$PSCommandPath`"")
    if ($GameProfile) { $argList += '-GameProfile' }
    Start-Process powershell.exe -Verb RunAs -ArgumentList $argList
    exit
}

function Say($text) { Write-Host $text }
function Done {
    Write-Host ''
    Read-Host 'Press Enter to close'
}

trap {
    Write-Host ''
    Write-Host "Monet couldn't be installed: $_" -ForegroundColor Red
    Done
    exit 1
}

Say ''
Say 'Installing Monet Bridge...'

if ($env:firmware_type -and $env:firmware_type -ne 'UEFI') {
    throw 'This PC started in legacy BIOS mode. Monet needs UEFI.'
}

$source = $PSScriptRoot
$installDir = Join-Path $env:ProgramFiles 'Monet'
$dataDir = Join-Path $env:ProgramData 'Monet'
$exe = Join-Path $installDir 'monet-bridge.exe'
$icon = Join-Path $installDir 'monet.ico'

# Stop a running agent so the program file can be replaced.
Get-ScheduledTask -TaskPath '\Monet\' -ErrorAction SilentlyContinue | Stop-ScheduledTask -ErrorAction SilentlyContinue
Get-Process monet-bridge -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 500

# 1. Program files
New-Item -ItemType Directory -Force -Path $installDir | Out-Null
Copy-Item -Force (Join-Path $source 'monet-bridge.exe') $exe
Copy-Item -Force (Join-Path $source 'monet.ico') $icon
foreach ($file in 'Uninstall-Monet.ps1', 'GameProfile.ps1') {
    Copy-Item -Force (Join-Path $source $file) (Join-Path $installDir $file)
}
Unblock-File -Path $exe -ErrorAction SilentlyContinue

# 2. Data folder: administrators write, everyone else only reads.
New-Item -ItemType Directory -Force -Path $dataDir | Out-Null
& icacls.exe $dataDir /inheritance:r /grant:r '*S-1-5-32-544:(OI)(CI)F' '*S-1-5-18:(OI)(CI)F' '*S-1-5-32-545:(OI)(CI)RX' | Out-Null

# 3. Fast switching: full hibernation on, Fast Startup off.
Say '  Turning on hibernation for fast switching'
& powercfg.exe /hibernate on | Out-Null
& powercfg.exe /h /type full | Out-Null
Set-ItemProperty -Path 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Power' -Name HiberbootEnabled -Value 0 -Type DWord

# 4. Scheduled tasks
Say '  Creating background tasks'
# The person signed in at the screen, even if another account approved the UAC prompt.
$user = (Get-CimInstance Win32_ComputerSystem).UserName
if (-not $user) { $user = "$env:USERDOMAIN\$env:USERNAME" }
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew -StartWhenAvailable
$admin = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Highest
$normal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -Force -TaskPath '\Monet\' -TaskName 'Agent' `
    -Description 'Starts games requested from Monet and returns to Monet when they close.' `
    -Action (New-ScheduledTaskAction -Execute $exe -Argument 'agent') `
    -Trigger (New-ScheduledTaskTrigger -AtLogOn -User $user) `
    -Principal $admin -Settings $settings | Out-Null

Register-ScheduledTask -Force -TaskPath '\Monet\' -TaskName 'Launch' `
    -Description 'Starts a game as the signed-in user.' `
    -Action (New-ScheduledTaskAction -Execute $exe -Argument 'launch-pending') `
    -Principal $normal -Settings $settings | Out-Null

Register-ScheduledTask -Force -TaskPath '\Monet\' -TaskName 'Back' `
    -Description 'Restarts in Monet.' `
    -Action (New-ScheduledTaskAction -Execute $exe -Argument 'back') `
    -Principal $admin -Settings $settings | Out-Null

# 5. "Back to Monet" shortcuts
Say '  Adding "Back to Monet" to Start and the desktop'
$shell = New-Object -ComObject WScript.Shell
$startMenu = Join-Path $env:ProgramData 'Microsoft\Windows\Start Menu\Programs'
$desktop = [Environment]::GetFolderPath('CommonDesktopDirectory')
foreach ($folder in $startMenu, $desktop) {
    $link = $shell.CreateShortcut((Join-Path $folder 'Back to Monet.lnk'))
    $link.TargetPath = $exe
    $link.Arguments = 'back'
    $link.IconLocation = $icon
    $link.Description = 'Restart in Monet'
    $link.Save()
}

if ($GameProfile) {
    & (Join-Path $installDir 'GameProfile.ps1') -NoPause
}

# 6. Start the agent now, so the games list reaches Monet right away.
Start-ScheduledTask -TaskPath '\Monet\' -TaskName 'Agent'

Say ''
Write-Host 'Monet Bridge is installed.' -ForegroundColor Green
Say 'Your Windows games will show up in Monet the next time you go back.'
Say 'To go back now, use "Back to Monet" on the desktop.'
Done

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

.PARAMETER RemoveApps
    With -GameProfile: also remove preinstalled apps games never need.

.PARAMETER InstallSteam
    Install Steam if it isn't there yet (used when Monet installed Windows).

.PARAMETER FromMonet
    Used when Monet prepared or installed Windows and this runs once at
    sign-in. Cleans up Monet's setup files and goes back to Monet.
#>
param(
    [switch]$GameProfile,
    [switch]$RemoveApps,
    [switch]$InstallSteam,
    [switch]$FromMonet
)

$ErrorActionPreference = 'Stop'

# Ask for administrator rights if we don't have them yet.
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$isAdmin = ([Security.Principal.WindowsPrincipal]$identity).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    $argList = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "`"$PSCommandPath`"")
    if ($GameProfile) { $argList += '-GameProfile' }
    if ($RemoveApps) { $argList += '-RemoveApps' }
    if ($InstallSteam) { $argList += '-InstallSteam' }
    if ($FromMonet) { $argList += '-FromMonet' }
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
if ($FromMonet) {
    Say 'Finishing Monet setup. This takes a few seconds...'
} else {
    Say 'Installing Monet Bridge...'
}

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

# 0. Wi-Fi from Monet, so Windows is online right away.
$wifi = Join-Path $source 'wifi'
if (Test-Path $wifi) {
    Say '  Connecting to Wi-Fi'
    foreach ($wlan in Get-ChildItem -Path $wifi -Filter *.xml) {
        & netsh.exe wlan add profile filename="$($wlan.FullName)" user=all | Out-Null
    }
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $wifi
}

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

# 6. Steam, for a Windows that Monet installed.
$steamExe = Join-Path ${env:ProgramFiles(x86)} 'Steam\steam.exe'
if ($InstallSteam -and -not (Test-Path $steamExe)) {
    Say '  Installing Steam'
    $setup = Join-Path $env:TEMP 'SteamSetup.exe'
    $url = 'https://cdn.cloudflare.steamstatic.com/client/installer/SteamSetup.exe'
    for ($try = 1; $try -le 10 -and -not (Test-Path $setup); $try++) {
        try {
            Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $setup -ErrorAction Stop
        } catch {
            Remove-Item -Force -ErrorAction SilentlyContinue $setup
            Start-Sleep -Seconds 15   # Wi-Fi may still be connecting
        }
    }
    if (Test-Path $setup) {
        Start-Process -FilePath $setup -ArgumentList '/S' -Wait
        Remove-Item -Force -ErrorAction SilentlyContinue $setup
    } else {
        Say "  Steam couldn't be downloaded. Install it from store.steampowered.com."
    }
}

# 7. Listed in Settings > Apps, so it can be removed like any other app.
$uninstallKey = 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Monet'
New-Item -Path $uninstallKey -Force | Out-Null
$uninstaller = Join-Path $installDir 'Uninstall-Monet.ps1'
$values = @{
    DisplayName     = 'Monet Bridge'
    DisplayVersion  = '@VERSION@'
    Publisher       = 'Monet'
    DisplayIcon     = $icon
    InstallLocation = $installDir
    UninstallString = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$uninstaller`""
}
foreach ($name in $values.Keys) { Set-ItemProperty -Path $uninstallKey -Name $name -Value $values[$name] }
Set-ItemProperty -Path $uninstallKey -Name NoModify -Value 1 -Type DWord
Set-ItemProperty -Path $uninstallKey -Name NoRepair -Value 1 -Type DWord

if ($GameProfile) {
    Say '  Applying the Game Profile'
    & (Join-Path $installDir 'GameProfile.ps1') -NoPause -RemoveApps:$RemoveApps
}

# 8. Start the agent now, so the games list reaches Monet right away.
Start-ScheduledTask -TaskPath '\Monet\' -TaskName 'Agent'

if ($FromMonet) {
    # Setup ran once from the Startup folder; remove it and head back.
    $startup = Join-Path $env:ProgramData 'Microsoft\Windows\Start Menu\Programs\StartUp\Finish Monet setup.cmd'
    Remove-Item -Force -ErrorAction SilentlyContinue $startup
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue (Join-Path $dataDir 'Setup')

    # After Monet installed Windows: give the setup partition's space to C:.
    $setupVolume = Get-Volume -FileSystemLabel 'MONETSETUP' -ErrorAction SilentlyContinue
    if ($setupVolume) {
        Say '  Cleaning up the Windows installer'
        Get-Partition -Volume $setupVolume | Remove-Partition -Confirm:$false -ErrorAction SilentlyContinue
        $max = (Get-PartitionSupportedSize -DriveLetter C).SizeMax
        if ($max -gt (Get-Partition -DriveLetter C).Size) {
            Resize-Partition -DriveLetter C -Size $max -ErrorAction SilentlyContinue
        }
    }
    Start-Process -FilePath $exe -ArgumentList 'finish-setup'
    exit 0
}

Say ''
Write-Host 'Monet Bridge is installed.' -ForegroundColor Green
Say 'Your Windows games will show up in Monet the next time you go back.'
Say 'To go back now, use "Back to Monet" on the desktop.'
Done

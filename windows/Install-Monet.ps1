<#
.SYNOPSIS
    Installs Monet Bridge, the Windows half of Monet.

.DESCRIPTION
    - Copies monet-bridge.exe to C:\Program Files\Monet
    - Turns off Fast Startup, so Windows always shuts down fully and Monet
      can safely read its drive, and reads the PC's clock as UTC, as Monet does
    - Creates scheduled tasks under \Monet\ for the agent, game launch,
      return to Monet, and staging and applying Bridge updates
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

.PARAMETER Quiet
    Used by Update-Monet.ps1: no questions, nothing to press at the end.
#>
param(
    [switch]$GameProfile,
    [switch]$RemoveApps,
    [switch]$InstallSteam,
    [switch]$FromMonet,
    [switch]$Quiet
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
    if ($Quiet) { $argList += '-Quiet' }
    Start-Process powershell.exe -Verb RunAs -ArgumentList $argList
    exit
}

function Say($text) { Write-Host $text }
function Done {
    if ($Quiet) { return }
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

# Stop a running agent so the program file can be replaced (not Update, which may be
# what's running this).
Get-ScheduledTask -TaskPath '\Monet\' -ErrorAction SilentlyContinue | Where-Object { $_.TaskName -ne 'Update' } |
    Stop-ScheduledTask -ErrorAction SilentlyContinue
Get-Process monet-bridge -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 500

# 1. Program files
New-Item -ItemType Directory -Force -Path $installDir | Out-Null
# In one step: a copy cut short (the power going, say) never leaves half a program.
Copy-Item -Force (Join-Path $source 'monet-bridge.exe') "$exe.new"
Move-Item -Force "$exe.new" $exe
Copy-Item -Force (Join-Path $source 'monet.ico') $icon
foreach ($file in 'Uninstall-Monet.ps1', 'GameProfile.ps1', 'Update-Monet.ps1', 'Update-Windows.ps1', 'Install-Launcher.ps1', 'Setup-Functions.ps1') {
    Copy-Item -Force (Join-Path $source $file) (Join-Path $installDir $file)
}
# The cover over Windows during a trip (the painting, the mark, Monet's serif): without them
# it's a plain one.
foreach ($file in 'cover.jpg', 'monet-mark.png', 'Fraunces-Light.ttf', 'Fraunces-Regular.ttf', 'OFL-Fraunces.txt') {
    $from = Join-Path $source $file
    if (Test-Path $from) { Copy-Item -Force $from (Join-Path $installDir $file) }
}
Unblock-File -Path $exe -ErrorAction SilentlyContinue

# 2. Data folder: administrators write, everyone else only reads.
New-Item -ItemType Directory -Force -Path $dataDir | Out-Null
& icacls.exe $dataDir /inheritance:r /grant:r '*S-1-5-32-544:(OI)(CI)F' '*S-1-5-18:(OI)(CI)F' '*S-1-5-32-545:(OI)(CI)RX' | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Could not protect the Monet data directory.' }

. (Join-Path $installDir 'Setup-Functions.ps1')
$wifiResult = Import-MonetWifi -Source (Join-Path $source 'wifi') -Pending (Join-Path $dataDir 'wifi')
if ($wifiResult.Pending -gt 0) {
    Say '  Wi-Fi is not ready. Saved profiles will be retried by Monet Bridge after the network driver is installed.'
}

# 3. Fast Startup off: it leaves Windows' drive half asleep, and Monet restarts
#    Windows instead of hibernating it.
Set-ItemProperty -Path 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Power' -Name HiberbootEnabled -Value 0 -Type DWord
# The PC's clock keeps UTC, as Monet does; otherwise Windows reads it as local
# time and is off by the time zone after every switch.
Set-ItemProperty -Path 'HKLM:\SYSTEM\CurrentControlSet\Control\TimeZoneInformation' -Name RealTimeIsUniversal -Value 1 -Type DWord

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

# Left as it is when it's what's running this (Update-Monet.ps1 -> -Quiet).
if (-not $Quiet -or -not (Get-ScheduledTask -TaskPath '\Monet\' -TaskName 'Update' -ErrorAction SilentlyContinue)) {
    $updater = Join-Path $installDir 'Update-Monet.ps1'
    Register-ScheduledTask -Force -TaskPath '\Monet\' -TaskName 'Update' `
        -Description 'Installs a staged Monet Bridge update before restarting into Monet.' `
        -Action (New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$updater`"") `
        -Principal $admin -Settings $settings | Out-Null
}
$updater = Join-Path $installDir 'Update-Monet.ps1'
$stageTrigger = New-ScheduledTaskTrigger -AtLogOn -User $user
$stageTrigger.Delay = 'PT2M'
Register-ScheduledTask -Force -TaskPath '\Monet\' -TaskName 'StageUpdate' `
    -Description 'Checks for and downloads Monet Bridge updates after sign-in.' `
    -Action (New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$updater`" -Stage") `
    -Trigger $stageTrigger -Principal $admin -Settings $settings | Out-Null

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
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $installDir 'Install-Launcher.ps1') `
        -Launcher steam -Installer (Join-Path $source 'SteamSetup.exe')
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $steamExe)) {
        Say '  Steam still needs installing. Connect to the internet, then open Install Steam on the desktop.'
        $retry = '@echo off' + "`r`n" + 'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%ProgramFiles%\Monet\Install-Launcher.ps1" -Launcher steam' + "`r`npause`r`n"
        Set-Content -LiteralPath (Join-Path $desktop 'Install Steam.cmd') -Value $retry -Encoding ASCII
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
    # A Windows that Monet installed wears Monet's painting, so a trip there looks like
    # home. A Windows kept from before keeps its own: its setup carries no wallpaper.jpg.
    # Only a look: if Windows won't have it, setup carries on.
    $painting = Join-Path $source 'wallpaper.jpg'
    if (Test-Path $painting) {
        try {
            $wallpaper = Join-Path $dataDir 'wallpaper.jpg'
            Copy-Item -Force $painting $wallpaper
            Set-ItemProperty -Path 'HKCU:\Control Panel\Desktop' -Name WallpaperStyle -Value '10'
            Set-ItemProperty -Path 'HKCU:\Control Panel\Desktop' -Name TileWallpaper -Value '0'
            Add-Type -Namespace Monet -Name Desktop -MemberDefinition '[DllImport("user32.dll", CharSet = CharSet.Unicode)] public static extern bool SystemParametersInfo(int action, int param, string value, int flags);'
            [Monet.Desktop]::SystemParametersInfo(0x14, 0, $wallpaper, 3) | Out-Null
        } catch {
            Say "  Windows kept its own wallpaper ($_)"
        }
        # And its taskbar slides away until it's pointed at, so a trip shows Monet's cover,
        # not Windows (from the next sign-in).
        try {
            $rects = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\StuckRects3'
            $bar = (Get-ItemProperty -Path $rects -Name Settings -ErrorAction Stop).Settings
            $bar[8] = $bar[8] -bor 1
            Set-ItemProperty -Path $rects -Name Settings -Value $bar
        } catch {
            Say "  The taskbar stays as it is ($_)"
        }
    }

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

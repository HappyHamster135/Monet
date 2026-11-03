<#
.SYNOPSIS
    Monet's Windows Game Profile: makes Windows quieter and faster for games.

.DESCRIPTION
    Default (safe, nothing is removed):
      - Let the CPU idle while plugged in (battery behavior is unchanged)
      - Windows Game Mode and hardware-accelerated GPU scheduling on
      - Fewer tips, ads and suggestions; Widgets and Copilot off

    Never touched: Windows Update, Windows Security (Defender), TPM, Secure
    Boot, WebView2, DirectX and Visual C++ runtimes, Xbox identity / Gaming Services.

.PARAMETER RemoveApps
    Also uninstall preinstalled apps that games never need (news, weather,
    solitaire, Clipchamp, ...). They can be reinstalled from the Microsoft Store.

.PARAMETER DisableMemoryIntegrity
    Turn off Memory Integrity (HVCI). Gains a few percent of FPS, but lowers
    protection against malicious drivers, and a few anti-cheats require it on.
    Only use this on a PC that is just for games.
#>
param(
    [switch]$RemoveApps,
    [switch]$DisableMemoryIntegrity,
    [switch]$NoPause
)

$ErrorActionPreference = 'Stop'
$cleanupFailed = $false

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$isAdmin = ([Security.Principal.WindowsPrincipal]$identity).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    $argList = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "`"$PSCommandPath`"")
    if ($RemoveApps) { $argList += '-RemoveApps' }
    if ($DisableMemoryIntegrity) { $argList += '-DisableMemoryIntegrity' }
    if ($NoPause) { $argList += '-NoPause' }
    Start-Process powershell.exe -Verb RunAs -ArgumentList $argList
    exit
}

function Set-Value($path, $name, $value) {
    if (-not (Test-Path $path)) { New-Item -Path $path -Force | Out-Null }
    Set-ItemProperty -Path $path -Name $name -Value $value -Type DWord
}

Write-Host 'Applying the Monet Game Profile...'

Write-Host '  Letting the CPU idle between games'
# The previous 100% minimum needlessly kept laptops hot at the desktop. Keep
# the maximum and boost policy as they are, so games can still use full speed.
& powercfg.exe /setacvalueindex SCHEME_CURRENT SUB_PROCESSOR PROCTHROTTLEMIN 5
if ($LASTEXITCODE -ne 0) { throw 'Windows could not change the processor idle policy.' }
& powercfg.exe /setactive SCHEME_CURRENT
if ($LASTEXITCODE -ne 0) { throw 'Windows could not activate the power policy.' }

Write-Host '  Game Mode and GPU scheduling on'
Set-Value 'HKCU:\Software\Microsoft\GameBar' 'AutoGameModeEnabled' 1
Set-Value 'HKCU:\Software\Microsoft\GameBar' 'AllowAutoGameMode' 1
Set-Value 'HKLM:\SYSTEM\CurrentControlSet\Control\GraphicsDrivers' 'HwSchMode' 2

Write-Host '  Fewer tips, ads and suggestions'
$cdm = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager'
foreach ($name in 'SubscribedContent-338388Enabled', 'SubscribedContent-338389Enabled', 'SubscribedContent-353694Enabled',
                  'SubscribedContent-353696Enabled', 'SystemPaneSuggestionsEnabled', 'SoftLandingEnabled',
                  'SilentInstalledAppsEnabled') {
    Set-Value $cdm $name 0
}
Set-Value 'HKLM:\SOFTWARE\Policies\Microsoft\Dsh' 'AllowNewsAndInterests' 0
Set-Value 'HKCU:\Software\Policies\Microsoft\Windows\WindowsCopilot' 'TurnOffWindowsCopilot' 1
Set-Value 'HKCU:\Software\Microsoft\Windows\CurrentVersion\BackgroundAccessApplications' 'GlobalUserDisabled' 1

# Keep the browser and WebView2 available to game sign-in pages, but don't
# prelaunch Edge at sign-in or leave background apps running after it closes.
Set-Value 'HKLM:\SOFTWARE\Policies\Microsoft\Edge' 'StartupBoostEnabled' 0
Set-Value 'HKLM:\SOFTWARE\Policies\Microsoft\Edge' 'BackgroundModeEnabled' 0

if ($RemoveApps) {
    Write-Host '  Removing apps games never need'
    $apps = @(
        'Clipchamp.Clipchamp',
        'Microsoft.BingNews',
        'Microsoft.BingWeather',
        'Microsoft.GetHelp',
        'Microsoft.Getstarted',
        'Microsoft.MicrosoftOfficeHub',
        'Microsoft.OutlookForWindows',
        'Microsoft.GamingApp',
        'Microsoft.XboxApp',
        'Microsoft.MicrosoftSolitaireCollection',
        'Microsoft.People',
        'Microsoft.PowerAutomateDesktop',
        'Microsoft.Todos',
        'Microsoft.WindowsFeedbackHub',
        'Microsoft.ZuneMusic',
        'Microsoft.ZuneVideo',
        'MicrosoftCorporationII.QuickAssist',
        'MSTeams'
    )
    foreach ($app in $apps) {
        try {
            Get-AppxPackage -Name $app -ErrorAction Stop | Remove-AppxPackage -ErrorAction Stop
        } catch {
            $cleanupFailed = $true
            Write-Warning "Could not remove $app. $($_.Exception.Message)"
        }
    }
}

if ($DisableMemoryIntegrity) {
    Write-Host '  Memory Integrity off'
    Set-Value 'HKLM:\SYSTEM\CurrentControlSet\Control\DeviceGuard\Scenarios\HypervisorEnforcedCodeIntegrity' 'Enabled' 0
}

Write-Host ''
if ($cleanupFailed) { Write-Warning 'Some optional apps could not be removed. Run the profile again to retry.' }
else { Write-Host 'Done. Some changes take effect after a restart.' -ForegroundColor Green }
if (-not $NoPause) {
    Write-Host ''
    Read-Host 'Press Enter to close'
}
if ($cleanupFailed) { exit 1 }

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
    solitaire, Clipchamp, ...), including Windows' provisioned copies.
    They can be reinstalled from the Microsoft Store.

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

function Remove-MonetOptionalApps {
    $apps = @(
        'Clipchamp.Clipchamp',
        'Microsoft.BingNews',
        'Microsoft.BingWeather',
        'Microsoft.GetHelp',
        'Microsoft.Getstarted',
        'Microsoft.MicrosoftOfficeHub',
        'Microsoft.MicrosoftSolitaireCollection',
        'Microsoft.OutlookForWindows',
        'Microsoft.People',
        'Microsoft.PowerAutomateDesktop',
        'Microsoft.Todos',
        'Microsoft.WindowsFeedbackHub',
        'Microsoft.WindowsMaps',
        'Microsoft.ZuneMusic',
        'Microsoft.ZuneVideo',
        'MicrosoftCorporationII.MicrosoftFamily',
        'MicrosoftCorporationII.QuickAssist',
        'Microsoft.Copilot',
        'microsoft.windowscommunicationsapps',
        'MSTeams'
    )
    $succeeded = $true
    try {
        # Deprovision first so Windows does not register these apps for new users.
        foreach ($package in Get-AppxProvisionedPackage -Online -ErrorAction Stop) {
            if ($package.DisplayName -notin $apps) { continue }
            try {
                Remove-AppxProvisionedPackage -Online -PackageName $package.PackageName -ErrorAction Stop | Out-Null
            } catch {
                $succeeded = $false
                Write-Warning "Could not deprovision $($package.DisplayName). $($_.Exception.Message)"
            }
        }
    } catch {
        $succeeded = $false
        Write-Warning "Could not read Windows' provisioned apps. $($_.Exception.Message)"
    }
    # Windows inventories every user's packages. Read each type once, and read
    # Main after Bundle removals so we only act on standalone packages left.
    foreach ($type in 'Bundle', 'Main') {
        try {
            $packages = @(Get-AppxPackage -AllUsers -PackageTypeFilter $type -ErrorAction Stop |
                Where-Object { $_.Name -in $apps })
        } catch {
            $succeeded = $false
            Write-Warning "Could not read Windows' $type app packages. $($_.Exception.Message)"
            continue
        }
        foreach ($package in $packages) {
            try {
                Remove-AppxPackage -AllUsers -Package $package.PackageFullName -ErrorAction Stop | Out-Null
            } catch {
                $succeeded = $false
                Write-Warning "Could not remove $($package.PackageFullName). $($_.Exception.Message)"
            }
        }
    }
    try {
        $remaining = @(
            Get-AppxProvisionedPackage -Online -ErrorAction Stop | Where-Object { $_.DisplayName -in $apps } |
                Select-Object -ExpandProperty DisplayName
            Get-AppxPackage -AllUsers -PackageTypeFilter Bundle,Main -ErrorAction Stop | Where-Object { $_.Name -in $apps } |
                Select-Object -ExpandProperty Name
        ) | Sort-Object -Unique
        if ($remaining) {
            Write-Warning "Windows still lists these optional apps: $($remaining -join ', ')."
            $succeeded = $false
        }
    } catch {
        $succeeded = $false
        Write-Warning "Could not verify optional app removal. $($_.Exception.Message)"
    }
    return $succeeded
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
    $cleanupFailed = -not (Remove-MonetOptionalApps)
    Set-Value 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\CloudContent' 'DisableWindowsConsumerFeatures' 1

    Set-Value 'HKLM:\SOFTWARE\Policies\Microsoft\EdgeUpdate' 'CreateDesktopShortcutDefault' 0
    $shortcutFolders = @([Environment]::GetFolderPath('DesktopDirectory'),
                         [Environment]::GetFolderPath('CommonDesktopDirectory'),
                         [Environment]::GetFolderPath('Programs'),
                         [Environment]::GetFolderPath('CommonPrograms'))
    foreach ($folder in $shortcutFolders) {
        if ($folder) {
            $shortcut = Join-Path $folder 'Microsoft Edge.lnk'
            try {
                if (Test-Path -LiteralPath $shortcut) {
                    Remove-Item -LiteralPath $shortcut -ErrorAction Stop
                }
            } catch {
                Write-Warning "Could not remove an Edge shortcut. $($_.Exception.Message)"
            }
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

#requires -Version 5.1
<#
.SYNOPSIS
    Apply a hardware-matched offline repair built by prepare-windows-repair.py.
.DESCRIPTION
    Checks every payload hash before installing. PnPUtil verifies signed driver
    catalogs and selects matching hardware; it never forces a lower-ranked driver.
    No BIOS updates, pairing-key changes, partition changes or automatic restarts.
#>
param([switch]$NoPause)
$ErrorActionPreference = 'Stop'
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
if (-not ([Security.Principal.WindowsPrincipal]$identity).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    $arguments = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "`"$PSCommandPath`"")
    if ($NoPause) { $arguments += '-NoPause' }
    $child = Start-Process powershell.exe -Verb RunAs -ArgumentList $arguments -Wait -PassThru
    exit $child.ExitCode
}

$mutex = New-Object Threading.Mutex($false, 'Global\MonetWindowsRepair')
$locked = $false
$transcript = $false
$code = 1
try {
    try { $locked = $mutex.WaitOne(0) } catch [Threading.AbandonedMutexException] { $locked = $true }
    if (-not $locked) { throw 'Another Windows repair is already running.' }
    . (Join-Path $PSScriptRoot 'Setup-Functions.ps1')
    $manifest = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'repair-manifest.json') -Raw | ConvertFrom-Json
    $computer = Get-CimInstance Win32_ComputerSystem
    Test-MonetRepairBundle $PSScriptRoot $manifest $computer.Manufacturer $computer.Model

    $data = Join-Path $env:ProgramData 'Monet'
    New-Item -ItemType Directory -Force -Path $data | Out-Null
    & icacls.exe $data /inheritance:r /grant:r '*S-1-5-32-544:(OI)(CI)F' '*S-1-5-18:(OI)(CI)F' '*S-1-5-32-545:(OI)(CI)RX' | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Could not protect repair logs and saved Wi-Fi profiles.' }
    Start-Transcript -Path (Join-Path $data ('repair-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.log')) | Out-Null
    $transcript = $true
    $results = @()
    $failures = @()
    $rebootNeeded = $false
    Write-Host 'Repairing Windows drivers. Internet is not needed for this step.'
    foreach ($driver in $manifest.drivers) {
        Write-Host "  $($driver.name)"
        foreach ($inf in $driver.infs) {
            $path = Resolve-MonetBundleFile $PSScriptRoot $inf
            # Deliberately omit /reboot. Windows keeps signature enforcement and
            # device matching enabled; no generic driver updater is involved.
            & "$env:SystemRoot\System32\pnputil.exe" /add-driver $path /install
            $result = $LASTEXITCODE
            $results += [pscustomobject]@{ inf = $inf; exit_code = $result }
            if ($result -eq 3010) { $rebootNeeded = $true }
            elseif ($result -ne 0) { $failures += "Driver installation returned $result for $inf" }
        }
    }
    & "$env:SystemRoot\System32\pnputil.exe" /scan-devices
    if ($LASTEXITCODE -ne 0) { $failures += 'Windows could not complete a hardware rescan.' }

    $wifi = Import-MonetWifi -Source (Join-Path $data 'wifi') -Pending (Join-Path $data 'wifi')
    if ($wifi.Pending -gt 0) { Write-Warning 'Wi-Fi profiles are saved for retry after a restart.' }

    Write-Host 'Installing Steam...'
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'Install-Launcher.ps1') `
        -Launcher steam -Installer (Join-Path $PSScriptRoot $manifest.steam.path)
    $steamCode = $LASTEXITCODE
    $steam = Join-Path ${env:ProgramFiles(x86)} 'Steam\steam.exe'
    if ($steamCode -ne 0 -or -not (Test-Path -LiteralPath $steam)) { $failures += 'Steam still needs installing; run this repair again after networking is working.' }
    else {
        $shell = New-Object -ComObject WScript.Shell
        $desktop = [Environment]::GetFolderPath('CommonDesktopDirectory')
        $shortcut = $shell.CreateShortcut((Join-Path $desktop 'Steam.lnk'))
        $shortcut.TargetPath = $steam
        $shortcut.Save()
        Remove-Item -LiteralPath (Join-Path $desktop 'Install Steam.cmd') -Force -ErrorAction SilentlyContinue
    }

    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'GameProfile.ps1') -RemoveApps -NoPause
    if ($LASTEXITCODE -ne 0) { $failures += 'Some optional app cleanup failed; see the repair log.' }

    # Record hardware status without account names, Wi-Fi profiles or pairing keys.
    $problems = @(Get-CimInstance Win32_PnPEntity | Where-Object { $_.ConfigManagerErrorCode -ne 0 } |
        Select-Object Name, PNPClass, ConfigManagerErrorCode)
    $report = [ordered]@{
        version = 1; time = (Get-Date).ToString('o'); model = $computer.Model
        state = $(if ($failures.Count) { 'needs-attention' } else { 'installed-needs-hardware-check' })
        restart_requested_by_driver = $rebootNeeded; drivers = $results
        steam_installed = (Test-Path -LiteralPath $steam); wifi_pending = $wifi.Pending
        problems = $problems; failures = $failures
    }
    $report | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $data 'repair-report.json') -Encoding UTF8
    Write-Host ''
    if ($failures.Count) { $failures | ForEach-Object { Write-Warning $_ } }
    else { $code = 0; Write-Host 'Driver packages and Steam are installed.' -ForegroundColor Green }
    Write-Host 'Restart Windows normally, then check the touchpad, Wi-Fi, Ethernet and Bluetooth.'
    Write-Host 'Steam needs internet for its first update and sign-in. Bluetooth devices still need pairing in Windows.'
    Write-Host "Report: $data\repair-report.json"
} catch {
    Write-Host "Repair stopped: $_" -ForegroundColor Red
} finally {
    if ($transcript) { Stop-Transcript | Out-Null }
    if ($locked) { $mutex.ReleaseMutex() }
    $mutex.Dispose()
}
if (-not $NoPause) { Read-Host 'Press Enter to close' | Out-Null }
exit $code

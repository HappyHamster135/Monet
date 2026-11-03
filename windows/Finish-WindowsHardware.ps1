#requires -Version 5.1
<#
.SYNOPSIS
    Finish installing missing Windows hardware drivers now that networking works.
.DESCRIPTION
    Uses Windows Update for currently missing devices only. Leaves working drivers,
    firmware and boot settings alone. Never forces a service to stop or restarts.
    Run from the Windows desktop, let it finish, then restart Windows normally.
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
$code = 1
$transcript = $false
try {
    . (Join-Path $PSScriptRoot 'Setup-Functions.ps1')
    $data = Join-Path $env:ProgramData 'Monet'
    New-Item -ItemType Directory -Force -Path $data | Out-Null
    Start-Transcript -Path (Join-Path $data ('hardware-completion-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.log')) | Out-Null
    $transcript = $true
    $system = New-Object -ComObject Microsoft.Update.SystemInfo
    if ($system.RebootRequired) {
        throw 'Windows needs to finish a pending restart. Restart Windows normally, then run this action again.'
    }
    $missing = @(Get-CimInstance Win32_PnPEntity | Where-Object { $_.ConfigManagerErrorCode -eq 28 })
    $ids = @($missing | ForEach-Object { $_.HardwareID } | Where-Object { $_ } | Sort-Object -Unique)
    $result = [ordered]@{ time=(Get-Date).ToString('o'); state='checking'; missing_before=$missing.Count; updates=@(); reboot=$false }
    if ($ids.Count -eq 0) {
        Write-Host 'Windows reports no devices missing a driver.'
        $result.state = 'done'; $code = 0
    } else {
        Write-Host "Windows reports $($missing.Count) devices without drivers. Checking Windows Update..."
        $session = New-Object -ComObject Microsoft.Update.Session
        $session.ClientApplicationID = 'Monet hardware completion'
        $installer = $session.CreateUpdateInstaller()
        for ($attempt = 0; $installer.IsBusy -and $attempt -lt 12; $attempt++) {
            Write-Host 'Windows Update is already installing. Waiting for it to finish...'
            Start-Sleep -Seconds 5
        }
        if ($installer.IsBusy) { throw 'Windows Update is still busy. Leave Windows open until it finishes, then retry.' }
        $found = $session.CreateUpdateSearcher().Search("IsInstalled=0 and IsHidden=0 and Type='Driver'").Updates
        $wanted = New-Object -ComObject Microsoft.Update.UpdateColl
        foreach ($update in $found) {
            if (-not (Test-MonetMissingDriver $update $ids)) { continue }
            Write-Host "  $($update.Title)"
            if (-not $update.EulaAccepted) { $update.AcceptEula() }
            [void]$wanted.Add($update)
        }
        if ($wanted.Count -eq 0) {
            $result.state = 'needs-oem-drivers'
            Write-Warning 'Windows Update has no matching drivers for the remaining devices. Keep this report for Monet support.'
        } else {
            Write-Host 'Downloading required drivers. Keep Windows open; graphics drivers can be large.'
            $downloader = $session.CreateUpdateDownloader(); $downloader.Updates = $wanted
            $download = $downloader.Download()
            if ($download.ResultCode -ne 2) { throw "Driver download did not complete (result $($download.ResultCode)). Retry when networking is ready." }
            Write-Host 'Installing required drivers. The screen may blink.'
            $installer.Updates = $wanted
            $installed = $installer.Install()
            $result.reboot = [bool]$installed.RebootRequired
            for ($index=0; $index -lt $wanted.Count; $index++) {
                $item = $installed.GetUpdateResult($index)
                $result.updates += [pscustomobject]@{title=$wanted.Item($index).Title; result=[int]$item.ResultCode; hresult=$item.HResult}
            }
            if ($installed.ResultCode -ne 2) { $result.state = 'partial'; Write-Warning 'Some drivers did not install. See the report and retry after restarting Windows.' }
            else { $result.state='installed'; $code=0 }
        }
    }
    $result.missing_after = @(Get-CimInstance Win32_PnPEntity | Where-Object { $_.ConfigManagerErrorCode -eq 28 } |
        Select-Object Name, PNPClass, HardwareID).Count
    if ($result.missing_after -gt 0 -and -not $result.reboot) {
        $result.state = 'needs-oem-drivers'; $code = 1
        Write-Warning "$($result.missing_after) devices still need drivers. The hardware setup is not complete."
    }
    $result | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $data 'hardware-completion.json') -Encoding UTF8
    Write-Host ''
    Write-Host 'If drivers were installed, restart Windows normally before switching back to Monet.'
    Write-Host 'Let Windows finish any remaining update activity first. No restart has been requested by this tool.'
} catch {
    $code = 1
    Write-Host "Hardware setup needs attention: $_" -ForegroundColor Yellow
} finally {
    if ($transcript) { Stop-Transcript | Out-Null }
}
if (-not $NoPause) { Read-Host 'Press Enter to close' | Out-Null }
exit $code

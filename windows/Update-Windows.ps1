<#
.SYNOPSIS
    Brings Windows up to date on Monet's update trip (monet-bridge runs it, as administrator).

.DESCRIPTION
    Looks for Windows' own updates with Windows Update (not drivers: Monet keeps the graphics
    driver the game needs), downloads and installs them, and says how it's going in
    %ProgramData%\Monet\windows-update.json, which Monet's cover shows:

        {"state": "searching" | "downloading" | "installing" | "done" | "failed", "count": 3, "reboot": false}

    "reboot" says Windows wants a restart to finish; Monet Bridge then restarts it once
    before switching the PC off.
#>

$ErrorActionPreference = 'Stop'
$status = Join-Path $env:ProgramData 'Monet\windows-update.json'

function Tell([string]$state, [int]$count = 0, [bool]$reboot = $false) {
    $said = [ordered]@{ state = $state; count = $count; reboot = $reboot } | ConvertTo-Json -Compress
    [IO.File]::WriteAllText("$status.tmp", $said)
    Move-Item -Force "$status.tmp" $status
}

try {
    Tell 'searching'
    $session = New-Object -ComObject Microsoft.Update.Session
    $session.ClientApplicationID = 'Monet'
    $found = $session.CreateUpdateSearcher().Search("IsInstalled=0 and IsHidden=0 and Type='Software'").Updates
    $wanted = New-Object -ComObject Microsoft.Update.UpdateColl
    foreach ($update in $found) {
        # Nobody is there to answer an update that asks something.
        if ($update.InstallationBehavior.CanRequestUserInput) { continue }
        if (-not $update.EulaAccepted) { $update.AcceptEula() }
        [void]$wanted.Add($update)
    }
    if ($wanted.Count -eq 0) {
        Tell 'done'
        exit 0
    }
    Tell 'downloading' $wanted.Count
    $downloader = $session.CreateUpdateDownloader()
    $downloader.Updates = $wanted
    [void]$downloader.Download()
    Tell 'installing' $wanted.Count
    $installer = $session.CreateUpdateInstaller()
    $installer.Updates = $wanted
    $result = $installer.Install()
    Tell 'done' $wanted.Count $result.RebootRequired
} catch {
    Tell 'failed'
    exit 1
}

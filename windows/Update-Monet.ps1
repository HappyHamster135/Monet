<#
.SYNOPSIS
    Keeps Monet Bridge up to date, on the way back to Monet.

.DESCRIPTION
    Monet Bridge runs this (the \Monet\Update task) when you go back to Monet,
    after the game has closed. At most once a day it asks GitHub for Monet's
    newest release; when that's newer than this Bridge, it downloads the
    release's Monet-X-Windows.zip, checks it against the release's
    SHA256SUMS.txt, and installs it (Install-Monet.ps1 -Quiet). Then it
    restarts into Monet, whatever happened: an update never keeps the PC in
    Windows. Bridge hands the restart over by leaving update-then-restart in
    C:\ProgramData\Monet, which this renames to update-claimed as it starts.

.PARAMETER CheckOnly
    Only say whether a newer Monet Bridge is out; change nothing.
#>
param(
    [switch]$CheckOnly
)

$ErrorActionPreference = 'Stop'
# Windows PowerShell's progress bar slows downloads and unpacking down, even unseen.
$ProgressPreference = 'SilentlyContinue'
$Repository = 'HappyHamster135/Monet'
$installDir = Join-Path $env:ProgramFiles 'Monet'
$dataDir = Join-Path $env:ProgramData 'Monet'
$marker = Join-Path $dataDir 'update-then-restart'
$claimed = Join-Path $dataDir 'update-claimed'
$checked = Join-Path $dataDir 'update-checked'
$work = Join-Path $dataDir 'Update'

function Log($text) {
    if (-not $CheckOnly) {
        Add-Content -Path (Join-Path $dataDir 'update.log') -Value ('{0:yyyy-MM-dd HH:mm} {1}' -f (Get-Date), $text)
    }
}

# This Bridge's version, as its installer left it in Settings > Apps (monet-bridge.exe is a
# windowed program, whose printing a script can't always catch).
function Installed {
    $key = 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Monet'
    return [version](Get-ItemProperty -Path $key -Name DisplayVersion).DisplayVersion
}

# Monet's newest release on GitHub: its version, and its Windows package and checksums.
# (Every Monet is a pre-release while it's a preview, which GitHub's "latest" leaves out.)
function Newest {
    $releases = Invoke-RestMethod -UseBasicParsing -TimeoutSec 15 `
        -Uri "https://api.github.com/repos/$Repository/releases?per_page=10" -Headers @{ 'User-Agent' = 'Monet-Bridge' }
    $release = $releases | Where-Object { -not $_.draft -and $_.tag_name -match '^v\d+\.\d+\.\d+$' } |
        Sort-Object { [version]($_.tag_name -replace '^v', '') } -Descending | Select-Object -First 1
    $version = $release.tag_name -replace '^v', ''
    return [pscustomobject]@{
        Version = [version]$version
        Package = $release.assets | Where-Object { $_.name -eq "Monet-$version-Windows.zip" } | Select-Object -First 1
        Sums    = $release.assets | Where-Object { $_.name -eq 'SHA256SUMS.txt' } | Select-Object -First 1
    }
}

$restart = $false
if (-not $CheckOnly -and (Test-Path $marker)) {
    Move-Item -Force $marker $claimed
    $restart = $true
}
# Started too late, after Bridge restarted by itself: Windows is going down, so not now.
if (-not $CheckOnly -and -not $restart) { return }
# The PC is on its way back to Monet: an update that takes longer waits for another day.
$deadline = (Get-Date).AddSeconds(75)
try {
    # Once a day is enough; the rest of the time this only restarts.
    $last = if (Test-Path $checked) { (Get-Item $checked).LastWriteTime } else { [datetime]::MinValue }
    if ($CheckOnly -or (Get-Date) - $last -gt [timespan]::FromHours(20)) {
        $have = Installed
        $newest = Newest
        if (-not $CheckOnly) { Set-Content -Path $checked -Value (Get-Date -Format o) }
        if ($CheckOnly) {
            if ($newest.Version -gt $have) { "Monet Bridge $($newest.Version) is out (this is $have)." }
            else { "Monet Bridge $have is the newest." }
        } elseif ($newest.Version -gt $have -and $newest.Package -and $newest.Sums) {
            Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $work
            New-Item -ItemType Directory -Force -Path $work | Out-Null
            $zip = Join-Path $work $newest.Package.name
            $sums = Join-Path $work 'SHA256SUMS.txt'
            Invoke-WebRequest -UseBasicParsing -TimeoutSec 120 -Uri $newest.Package.browser_download_url -OutFile $zip
            Invoke-WebRequest -UseBasicParsing -TimeoutSec 30 -Uri $newest.Sums.browser_download_url -OutFile $sums
            $want = Get-Content $sums | Where-Object { $_ -match ('\s\*?' + [regex]::Escape($newest.Package.name) + '$') } |
                ForEach-Object { ($_ -split '\s+')[0] } | Select-Object -First 1
            if (-not $want -or $want -ne (Get-FileHash -Algorithm SHA256 $zip).Hash) {
                Log "$($newest.Package.name) didn't match its checksum; not installed"
            } elseif ((Get-Date) -gt $deadline) {
                Log "the download took too long; the update waits for the next trip"
                Remove-Item -Force -ErrorAction SilentlyContinue $checked
            } else {
                Expand-Archive -Force -Path $zip -DestinationPath $work
                $installer = Get-ChildItem -Path $work -Recurse -Filter 'Install-Monet.ps1' | Select-Object -First 1
                Log "updating Monet Bridge $have to $($newest.Version)"
                & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $installer.FullName -Quiet
                Log "Install-Monet.ps1 finished ($LASTEXITCODE)"
            }
        }
    }
} catch {
    Log "couldn't update: $_"
    if ($CheckOnly) { "Couldn't check: $_" }
} finally {
    if ($restart) {
        Remove-Item -Force -ErrorAction SilentlyContinue $claimed
        & shutdown.exe /r /t 0
    }
}

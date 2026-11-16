<#
.SYNOPSIS
    Keeps Monet Bridge up to date: a newer Bridge downloads while Windows is in
    use and installs on the way back to Monet.

.DESCRIPTION
    A couple of minutes after sign-in, the \Monet\StageUpdate task runs this
    with -Stage. At most once a day it asks GitHub for Monet's newest release;
    when that's newer than this Bridge, it downloads the release's
    Monet-X-Windows.zip, checks it against the release's SHA256SUMS.txt and
    keeps it in C:\ProgramData\Monet\update-ready. Only a whole, checked
    download ever goes there.

    Monet Bridge runs this (the \Monet\Update task) when you go back to Monet,
    after the game has closed: when an update is waiting, or when Bridge hasn't
    looked for one in a while. It checks the waiting update again and installs
    it (Install-Monet.ps1 -Quiet). With nothing waiting and no look in the last
    day (a Bridge from before 0.9.8-7 always runs this and has no StageUpdate
    task, and a trip can be too short for it), it looks and downloads on the way
    out, as Bridge always did; an update that isn't downloaded within 75 seconds
    installs on the next trip. Then it restarts into Monet, whatever happened:
    an update never keeps the PC in Windows. Bridge hands the restart over by
    leaving update-then-restart in C:\ProgramData\Monet, which this renames to
    update-claimed as it starts.

.PARAMETER CheckOnly
    Only say whether a newer Monet Bridge is out; change nothing.

.PARAMETER Stage
    Download and check a newer Monet Bridge, to install on the way back to Monet.
#>
param(
    [switch]$CheckOnly,
    [switch]$Stage
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
$ready = Join-Path $dataDir 'update-ready'
$applying = Join-Path $dataDir 'update-applying'
$lockFile = Join-Path $dataDir 'update.lock'

function Log($text) {
    if (-not $CheckOnly) {
        Add-Content -Path (Join-Path $dataDir 'update.log') -Value ('{0:yyyy-MM-dd HH:mm} {1}' -f (Get-Date), $text)
    }
}

# This Bridge's version, as its installer left it in Settings > Apps (monet-bridge.exe is a
# windowed program, whose printing a script can't always catch).
function Installed {
    $key = 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Monet'
    return (Get-ItemProperty -Path $key -Name DisplayVersion).DisplayVersion
}

# Monet's fourth number identifies an update after the three-part release. A beta
# (v0.9.8-7-beta.1) isn't one, so Bridge never installs a beta by itself.
# (Monet hands this updater to a Bridge from 0.9.8 and before, as long as it has this function.)
function ReleaseOrder([string]$name) {
    if ($name -notmatch '^\d+\.\d+\.\d+(?:-\d+)?$') { return $null }
    $parts = $name -split '[.-]'
    if ($parts.Count -eq 3) { $parts += '0' }
    $order = $null
    if ([version]::TryParse(($parts -join '.'), [ref]$order)) { return $order }
    return $null
}

function InstalledOrder([string]$have) {
    $order = ReleaseOrder $have
    if (-not $order) { throw "Unrecognized installed Monet Bridge version: $have" }
    return $order
}

# Monet's newest release on GitHub with its Windows package and checksums (one still being
# published waits until it has both): its version, and those two files.
# (Every Monet is a pre-release while it's a preview, which GitHub's "latest" leaves out.)
function Newest {
    $releases = Invoke-RestMethod -UseBasicParsing -TimeoutSec 15 `
        -Uri "https://api.github.com/repos/$Repository/releases?per_page=10" -Headers @{ 'User-Agent' = 'Monet-Bridge' }
    $latest = $releases | Where-Object { -not $_.draft -and $_.tag_name -match '^v\d' } | ForEach-Object {
        $version = $_.tag_name.Substring(1)
        $order = ReleaseOrder $version
        $package = $_.assets | Where-Object { $_.name -ceq "Monet-$version-Windows.zip" } | Select-Object -First 1
        $sums = $_.assets | Where-Object { $_.name -ceq 'SHA256SUMS.txt' } | Select-Object -First 1
        if ($order -and $package -and $sums) {
            [pscustomobject]@{ Version = $version; Order = $order; Package = $package; Sums = $sums }
        }
    } | Sort-Object Order -Descending | Select-Object -First 1
    if (-not $latest) { throw 'GitHub did not offer a Monet release.' }
    return $latest
}

# Once a day is enough. A look dated in the future (the clock was changed) doesn't count.
function CheckDue {
    if (-not (Test-Path -LiteralPath $checked)) { return $true }
    $age = (Get-Date) - (Get-Item -LiteralPath $checked).LastWriteTime
    return ($age -lt [timespan]::Zero -or $age -gt [timespan]::FromHours(20))
}

# The package matches its line in the release's SHA256SUMS.txt, listed there exactly once.
function Verified([string]$zip, [string]$sums) {
    $name = Split-Path -Leaf $zip
    $want = @(Get-Content -LiteralPath $sums | Where-Object { $_ -match ('^[0-9a-f]{64}\s+\*?' + [regex]::Escape($name) + '$') } |
        ForEach-Object { $_.Substring(0, 64) })
    return ($want.Count -eq 1 -and $want[0] -eq (Get-FileHash -Algorithm SHA256 -LiteralPath $zip).Hash)
}

# One download at a time: the one after sign-in can still be going when the PC heads back.
# Nothing when another has it; it's let go when the script ends, however it ends.
function Lock {
    try {
        return [IO.File]::Open($lockFile, [IO.FileMode]::OpenOrCreate, [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)
    } catch {
        return $null
    }
}

# Downloads the newest Bridge when it's newer than this one and checks it. update-ready gets
# it whole, in one step, or not at all.
function Download {
    $have = Installed
    $installedOrder = InstalledOrder $have
    $newest = Newest
    Set-Content -Path $checked -Value (Get-Date -Format o)
    # Also what an updater from before 0.9.8-7 left there after installing.
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $work
    if ($newest.Order -le $installedOrder) { return }
    New-Item -ItemType Directory -Force -Path $work | Out-Null
    try {
        $zip = Join-Path $work $newest.Package.name
        $sums = Join-Path $work 'SHA256SUMS.txt'
        Invoke-WebRequest -UseBasicParsing -TimeoutSec 120 -Uri $newest.Package.browser_download_url -OutFile $zip
        Invoke-WebRequest -UseBasicParsing -TimeoutSec 30 -Uri $newest.Sums.browser_download_url -OutFile $sums
        if (-not (Verified $zip $sums)) { throw "$($newest.Package.name) didn't match its checksum" }
        [IO.Directory]::Move($work, $ready)
    } catch {
        Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $work
        throw
    }
    Log "downloaded Monet Bridge $($newest.Version); it installs on the way back to Monet"
}

# Installs the update waiting in update-ready, checked again first. It's used once, whatever
# happens: the next look downloads it again if it didn't install.
function InstallWaiting {
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $applying
    [IO.Directory]::Move($ready, $applying)
    $zip = @(Get-ChildItem -LiteralPath $applying -File -Filter 'Monet-*-Windows.zip')
    if ($zip.Count -ne 1) { throw 'the waiting update is incomplete' }
    $version = $zip[0].Name -creplace '^Monet-(.+)-Windows\.zip$', '$1'
    $order = ReleaseOrder $version
    if (-not $order) { throw "the waiting update has no version: $($zip[0].Name)" }
    $have = Installed
    if ($order -le (InstalledOrder $have)) {
        Log "Monet Bridge $have is already as new as the waiting $version"
        return
    }
    if (-not (Verified $zip[0].FullName (Join-Path $applying 'SHA256SUMS.txt'))) {
        throw "$($zip[0].Name) didn't match its checksum"
    }
    Expand-Archive -LiteralPath $zip[0].FullName -DestinationPath $applying
    $installer = Join-Path (Join-Path $applying 'Monet for Windows') 'Install-Monet.ps1'
    if (-not (Test-Path -LiteralPath $installer -PathType Leaf)) { throw "$($zip[0].Name) has no Install-Monet.ps1" }
    Log "updating Monet Bridge $have to $version"
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $installer -Quiet
    Log "Install-Monet.ps1 finished ($LASTEXITCODE)"
}

if ($CheckOnly) {
    try {
        $have = Installed
        $installedOrder = InstalledOrder $have
        $newest = Newest
        if ($newest.Order -gt $installedOrder) { "Monet Bridge $($newest.Version) is out (this is $have)." }
        else { "Monet Bridge $have is the newest." }
    } catch {
        "Couldn't check: $_"
    }
    return
}

# In the background after sign-in (the StageUpdate task): download only, never a restart.
if ($Stage) {
    $lock = Lock
    if (-not $lock) { return }
    try {
        if (-not (Test-Path -LiteralPath $ready) -and (CheckDue)) { Download }
    } catch {
        Log "couldn't download the update: $_"
    } finally {
        $lock.Dispose()
    }
    return
}

$restart = $false
if (Test-Path $marker) {
    Move-Item -Force $marker $claimed
    $restart = $true
}
# Started too late, after Bridge restarted by itself: Windows is going down, so not now.
if (-not $restart) { return }
# The PC is on its way back to Monet: an update that takes longer waits for the next trip.
$deadline = (Get-Date).AddSeconds(75)
$lock = $null
try {
    $lock = Lock
    # Nothing downloaded after sign-in, and no download going: look now.
    if ($lock -and -not (Test-Path -LiteralPath $ready) -and (CheckDue)) { Download }
    if (Test-Path -LiteralPath $ready) {
        if ((Get-Date) -gt $deadline) {
            Log "the download took too long; the update installs on the next trip"
        } else {
            InstallWaiting
        }
    }
} catch {
    Log "couldn't update: $_"
} finally {
    if ($lock) { $lock.Dispose() }
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $applying
    # update-claimed stays until Bridge's next hand-over, so a restart that comes quickly
    # still reads to Bridge as the task having taken over.
    & shutdown.exe /r /t 0
}

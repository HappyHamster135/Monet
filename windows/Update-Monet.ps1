<#
.SYNOPSIS
    Stages Monet Bridge updates after Windows sign-in and installs them on return.

.DESCRIPTION
    The StageUpdate task checks for releases and downloads a verified package
    while Windows is running. Back to Monet only starts the Update task when
    that package is ready. Update claims the restart, installs the local package,
    then restarts Windows even if installation failed.

.PARAMETER CheckOnly
    Report whether a newer Monet Bridge is available.

.PARAMETER Stage
    Download and verify an available update while Windows is running.
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

function Log($text) {
    if (-not $CheckOnly) {
        Add-Content -Path (Join-Path $dataDir 'update.log') -Value ('{0:yyyy-MM-dd HH:mm} {1}' -f (Get-Date), $text)
    }
}

function ReleaseVersion([string]$name) {
    # Monet uses a numeric suffix for a revision of an already published build.
    if ($name -notmatch '^([0-9]+\.[0-9]+\.[0-9]+)(?:-([1-9][0-9]*))?$') { return }
    $revision = if ($Matches[2]) { $Matches[2] } else { '0' }
    $number = $null
    if ([version]::TryParse("$($Matches[1]).$revision", [ref]$number)) { return $number }
}

# This Bridge's version, as its installer left it in Settings > Apps (monet-bridge.exe is a
# windowed program, whose printing a script can't always catch).
function Installed {
    $key = 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Monet'
    $label = (Get-ItemProperty -Path $key -Name DisplayVersion).DisplayVersion
    $number = ReleaseVersion $label
    if (-not $number) { throw "Unrecognized installed Monet Bridge version: $label" }
    return [pscustomobject]@{ Version = $number; Label = $label }
}

# Monet's newest release on GitHub: its version, and its Windows package and checksums.
# (Every Monet is a pre-release while it's a preview, which GitHub's "latest" leaves out.)
function Newest {
    $releases = Invoke-RestMethod -UseBasicParsing -TimeoutSec 15 `
        -Uri "https://api.github.com/repos/$Repository/releases?per_page=10" -Headers @{ 'User-Agent' = 'Monet-Bridge' }
    $available = foreach ($release in $releases) {
        if ($release.draft -or $release.tag_name -cnotmatch '^v(.+)$') { continue }
        $label = $Matches[1]
        $number = ReleaseVersion $label
        if (-not $number) { continue }
        $package = $release.assets | Where-Object { $_.name -ceq "Monet-$label-Windows.zip" } | Select-Object -First 1
        $sums = $release.assets | Where-Object { $_.name -ceq 'SHA256SUMS.txt' } | Select-Object -First 1
        if ($package -and $sums) {
            [pscustomobject]@{ Version = $number; Label = $label; Package = $package; Sums = $sums }
        }
    }
    return $available | Sort-Object Version -Descending | Select-Object -First 1
}

function VerifyPackage($zip, $sums) {
    $name = Split-Path -Leaf $zip
    $expected = Get-Content -LiteralPath $sums | Where-Object {
        $_ -match ('^[a-f0-9]{64}\s+\*?' + [regex]::Escape($name) + '$')
    } | ForEach-Object { ($_ -split '\s+')[0] }
    return @($expected).Count -eq 1 -and $expected -eq (Get-FileHash -Algorithm SHA256 -LiteralPath $zip).Hash
}

$restart = $false
try {
    if ($CheckOnly -or $Stage) {
        if ($Stage -and -not $CheckOnly) {
            if (Test-Path $ready) { return }
            $last = if (Test-Path $checked) { (Get-Item $checked).LastWriteTime } else { [datetime]::MinValue }
            $age = (Get-Date) - $last
            if ($age -ge [timespan]::Zero -and $age -lt [timespan]::FromHours(20)) { return }
        }
        $have = Installed
        $newest = Newest
        $updateAvailable = $newest -and $newest.Version -gt $have.Version
        if ($CheckOnly) {
            if ($updateAvailable) { "Monet Bridge $($newest.Label) is out (this is $($have.Label))." }
            elseif ($newest) { "Monet Bridge $($have.Label) is up to date." }
            else { "No downloadable Monet Bridge releases were found." }
        } elseif ($updateAvailable) {
            Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $work
            New-Item -ItemType Directory -Force -Path $work | Out-Null
            $zip = Join-Path $work $newest.Package.name
            $sums = Join-Path $work 'SHA256SUMS.txt'
            Invoke-WebRequest -UseBasicParsing -TimeoutSec 120 -Uri $newest.Package.browser_download_url -OutFile $zip
            Invoke-WebRequest -UseBasicParsing -TimeoutSec 30 -Uri $newest.Sums.browser_download_url -OutFile $sums
            if (-not (VerifyPackage $zip $sums)) { throw "$($newest.Package.name) didn't match its checksum" }
            [IO.Directory]::Move($work, $ready)
            Log "staged Monet Bridge $($newest.Label)"
        }
        if (-not $CheckOnly) { Set-Content -Path $checked -Value (Get-Date -Format o) }
        return
    }

    if (-not (Test-Path $marker)) { return }
    # Claim the restart before touching the staged download. A late task cannot
    # claim a marker Bridge has already removed.
    Move-Item -Force $marker $claimed
    $restart = $true
    if (-not (Test-Path $ready -PathType Container)) { return }
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $applying
    [IO.Directory]::Move($ready, $applying)
    $zip = @(Get-ChildItem -LiteralPath $applying -File -Filter 'Monet-*-Windows.zip')
    if ($zip.Count -ne 1 -or $zip[0].Name -cnotmatch '^Monet-(.+)-Windows\.zip$') { throw 'Invalid staged package' }
    $label = $Matches[1]
    $version = ReleaseVersion $label
    $have = Installed
    if (-not $version -or $version -le $have.Version) { return }
    if (-not (VerifyPackage $zip[0].FullName (Join-Path $applying 'SHA256SUMS.txt'))) { throw 'Invalid staged checksum' }
    Expand-Archive -LiteralPath $zip[0].FullName -DestinationPath $applying
    $installer = Join-Path (Join-Path $applying 'Monet for Windows') 'Install-Monet.ps1'
    if (-not (Test-Path -LiteralPath $installer -PathType Leaf)) { throw 'Staged installer missing' }
    Log "updating Monet Bridge $($have.Label) to $label"
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $installer -Quiet
    if ($LASTEXITCODE -ne 0) { throw "Install-Monet.ps1 finished ($LASTEXITCODE)" }
} catch {
    Log "couldn't update: $_"
    if ($CheckOnly) { "Couldn't check: $_" }
    elseif ($Stage) { Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $work }
    elseif ($restart) { Remove-Item -Force -ErrorAction SilentlyContinue $checked }
} finally {
    if ($restart) {
        Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $applying
        # Bridge clears the receipt before its next request. Keep it visible
        # even when rejecting a package takes less than one polling interval.
        & shutdown.exe /r /t 0
    }
}

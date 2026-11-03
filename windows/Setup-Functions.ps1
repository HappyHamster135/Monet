# Shared setup operations. Dot-sourcing this file has no side effects.
function Test-MonetMissingDriver($Update, [string[]]$MissingHardwareIds) {
    # Repair missing devices only. Never replace a working graphics/storage
    # driver or select firmware from an ordinary hardware completion action.
    $classes = @('Display', 'Net', 'Bluetooth', 'HIDClass', 'Mouse', 'Keyboard', 'System', 'Media', 'USB', 'Biometric',
                 'Ports', 'Sensor', 'Camera', 'Image', 'SmartCardReader', 'SoftwareComponent', 'Extension')
    return $Update.Type -eq 2 -and $Update.DriverClass -in $classes -and
        $Update.DriverHardwareID -in $MissingHardwareIds -and
        -not $Update.InstallationBehavior.CanRequestUserInput
}

function Resolve-MonetBundleFile([string]$Root, [string]$Relative) {
    # Bundle manifests never name absolute paths, streams or parent directories.
    if (-not $Relative -or $Relative -match '(^[/\\]|:|(^|[/\\])\.\.?([/\\]|$))') {
        throw 'Invalid path in the repair manifest.'
    }
    $path = Join-Path $Root $Relative
    $item = Get-Item -LiteralPath $path -ErrorAction Stop
    if ($item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        throw 'Repair payload is not a regular file.'
    }
    $parent = $item.Directory
    $rootPath = [IO.Path]::GetFullPath($Root).TrimEnd([IO.Path]::DirectorySeparatorChar)
    while ($parent -and $parent.FullName.TrimEnd([IO.Path]::DirectorySeparatorChar) -ne $rootPath) {
        if ($parent.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Linked repair directories are not supported.' }
        $parent = $parent.Parent
    }
    if (-not $parent) { throw 'Repair payload is outside the bundle.' }
    return $item.FullName
}

function Test-MonetRepairBundle([string]$Root, $Manifest, [string]$Vendor, [string]$Model) {
    if ($Manifest.version -ne 1 -or $Vendor -ne $Manifest.vendor -or $Model.Length -lt 4 -or
        $Model.Substring(0, 4) -notin $Manifest.models) {
        throw 'This driver bundle does not match this computer.'
    }
    if (@($Manifest.drivers).Count -eq 0) { throw 'No drivers in the repair bundle.' }
    foreach ($driver in $Manifest.drivers) {
        if (@($driver.files).Count -eq 0 -or @($driver.infs).Count -eq 0) { throw 'Incomplete driver package.' }
        foreach ($inf in $driver.infs) {
            if ($inf -notmatch '(?i)\.inf$' -or $inf -notin $driver.files.path) { throw 'Driver INF is missing from the manifest.' }
        }
    }
    foreach ($file in @($Manifest.drivers | ForEach-Object { $_.files }) + @($Manifest.steam)) {
        $path = Resolve-MonetBundleFile $Root $file.path
        if ($file.sha256 -notmatch '^[a-fA-F0-9]{64}$' -or
            (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash -ne $file.sha256) {
            throw "Repair file failed its integrity check: $($file.path)"
        }
    }
}

function Import-MonetWifi([string]$Source, [string]$Pending) {
    # Pending is inside the administrators-only Monet data directory. Setup can
    # then remove its temporary files without losing profiles when drivers are absent.
    New-Item -ItemType Directory -Force -Path $Pending | Out-Null
    & icacls.exe $Pending /inheritance:r /grant:r '*S-1-5-32-544:(OI)(CI)F' '*S-1-5-18:(OI)(CI)F' | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Could not protect saved Wi-Fi profiles.' }
    if ((Test-Path -LiteralPath $Source) -and
        [IO.Path]::GetFullPath($Source) -ne [IO.Path]::GetFullPath($Pending)) {
        foreach ($profile in Get-ChildItem -LiteralPath $Source -Filter '*.xml' -File) {
            $saved = Join-Path $Pending (([guid]::NewGuid().ToString('N')) + '.xml')
            Copy-Item -LiteralPath $profile.FullName -Destination $saved -ErrorAction Stop
            Remove-Item -LiteralPath $profile.FullName -Force -ErrorAction Stop
        }
    }
    $imported = 0
    foreach ($profile in Get-ChildItem -LiteralPath $Pending -Filter '*.xml' -File) {
        & netsh.exe wlan add profile "filename=$($profile.FullName)" user=all | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Remove-Item -LiteralPath $profile.FullName -Force
            $imported++
        }
    }
    # Never include SSIDs, profile contents or passwords in setup logs.
    return [pscustomobject]@{ Imported = $imported; Pending = @(Get-ChildItem -LiteralPath $Pending -Filter '*.xml' -File).Count }
}

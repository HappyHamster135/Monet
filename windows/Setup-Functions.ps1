# Shared setup operations. Dot-sourcing this file has no side effects.
function Initialize-MonetFirstSignIn {
    # Run during specialize, before Windows copies the template to the first account.
    # Start's welcome window can cover the return controls. Mark the welcome as seen.
    $hive = Join-Path $env:SystemDrive 'Users\Default\NTUSER.DAT'
    $mount = 'HKLM\MonetSetupDefaultUser'
    $reg = Join-Path $env:SystemRoot 'System32\reg.exe'
    & $reg load $mount $hive | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Warning 'Could not load the default profile to skip the Start welcome.'
        return
    }
    try {
        & $reg add "$mount\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced" `
            /v StartShownOnUpgrade /t REG_DWORD /d 1 /f | Out-Null
        if ($LASTEXITCODE -ne 0) { Write-Warning 'Could not skip the Start welcome.' }
    } finally {
        & $reg unload $mount | Out-Null
        if ($LASTEXITCODE -ne 0) { Write-Warning 'Could not unload the default profile.' }
    }
}

function Get-MonetInstallerPartition([string]$SystemDrive) {
    $checkpointPath = Join-Path "$SystemDrive\" '.monet-setup.json'
    $checkpointFile = Get-Item -LiteralPath $checkpointPath -Force -ErrorAction SilentlyContinue
    if (-not $checkpointFile -or $checkpointFile.Length -gt 4096) { return }
    $checkpoint = Get-Content -LiteralPath $checkpointPath -Raw | ConvertFrom-Json
    if ($checkpoint.version -ne 1 -or $checkpoint.phase -ne 'complete' -or
        $checkpoint.manifest_sha256 -notmatch '^[0-9a-f]{64}$') { return }

    $windows = Get-Partition -DriveLetter $SystemDrive[0]
    $disk = Get-Disk -Number $windows.DiskNumber
    $basicData = [guid]'ebd0a0a2-b9e5-4433-87c0-68b6b72699c7'
    if ($disk.PartitionStyle -ne 'GPT' -or [guid]$windows.GptType -ne $basicData) { return }

    # Monet stages its FAT32 installer immediately after the Windows partition.
    $setup = Get-Partition -DiskNumber $windows.DiskNumber | Where-Object {
        $_.Offset -eq ($windows.Offset + $windows.Size) -and [guid]$_.GptType -eq $basicData -and
        $_.DriveLetter -match '^[A-Z]$' -and -not ($_.IsBoot -or $_.IsSystem -or $_.IsHidden -or $_.IsReadOnly)
    }
    if (@($setup).Count -ne 1) { return }
    $volume = Get-Volume -Partition $setup
    if ($volume.FileSystemLabel -ne 'MONETSETUP' -or $volume.FileSystem -ne 'FAT32') { return }

    $jobPath = Join-Path "$($setup.DriveLetter):\" 'monet/deployment.json'
    $jobFile = Get-Item -LiteralPath $jobPath -ErrorAction SilentlyContinue
    if (-not $jobFile -or $jobFile.Length -gt 1MB) { return }
    $stream = [IO.File]::OpenRead($jobFile.FullName)
    try {
        if ($stream.Length -gt 1MB) { return }
        $sha256 = (Get-FileHash -InputStream $stream -Algorithm SHA256).Hash
        if ($sha256 -ne $checkpoint.manifest_sha256) { return }
        $stream.Position = 0
        $reader = [IO.StreamReader]::new($stream)
        try { $job = $reader.ReadToEnd() | ConvertFrom-Json } finally { $reader.Dispose() }
    } finally { $stream.Dispose() }

    $identity = $job.partitions
    if ($job.version -eq 1 -and $job.id -eq $checkpoint.job_id -and $identity.version -eq 1 -and
        [guid]$identity.disk_guid -eq [guid]$disk.Guid -and
        [guid]$identity.windows.guid -eq [guid]$windows.Guid -and
        $identity.windows.offset -eq $windows.Offset -and $identity.windows.length -eq $windows.Size -and
        [guid]$identity.setup.guid -eq [guid]$setup.Guid -and
        $identity.setup.offset -eq $setup.Offset -and $identity.setup.length -eq $setup.Size) {
        $setup
    }
}

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

function Test-MonetRepairBundle([string]$Root, $Manifest, [string]$Vendor, [string]$Model, [switch]$DriversOnly) {
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
    $files = @($Manifest.drivers | ForEach-Object { $_.files })
    if (-not $DriversOnly) { $files += @($Manifest.steam) }
    foreach ($file in $files) {
        $path = Resolve-MonetBundleFile $Root $file.path
        if ($file.sha256 -notmatch '^[a-fA-F0-9]{64}$' -or
            (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash -ne $file.sha256) {
            throw "Repair file failed its integrity check: $($file.path)"
        }
    }
}

function Install-MonetOfflineDrivers([string]$Root, $Manifest) {
    foreach ($driver in $Manifest.drivers) {
        Write-Host "  $($driver.name)"
        foreach ($inf in $driver.infs) {
            $path = Resolve-MonetBundleFile $Root $inf
            & "$env:SystemRoot\System32\pnputil.exe" /add-driver $path /install | Out-Host
            [pscustomobject]@{ inf = $inf; exit_code = $LASTEXITCODE }
        }
    }
}

function Initialize-MonetHardware([string]$Root) {
    $manifestPath = Join-Path $Root 'repair-manifest.json'
    if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) { return }
    $report = [ordered]@{ state = 'checking'; drivers = @() }
    try {
        $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
        $computer = Get-CimInstance Win32_ComputerSystem
        Test-MonetRepairBundle $Root $manifest $computer.Manufacturer $computer.Model -DriversOnly
        $report.drivers = @(Install-MonetOfflineDrivers $Root $manifest)
        # PnPUtil reports 259 when no device needs the supplied driver.
        $report.state = if (@($report.drivers | Where-Object { $_.exit_code -notin @(0, 259, 3010) }).Count) { 'partial' } else { 'done' }
    } catch {
        $report.state = 'failed'
        $report.error = $_.Exception.Message
    }
    $report | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $env:ProgramData 'Monet\hardware-setup.json') -Encoding UTF8
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

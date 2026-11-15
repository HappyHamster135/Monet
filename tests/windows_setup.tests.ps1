# Cross-platform behavioral tests. Windows commands are mocked; no real registry,
# driver, package, Wi-Fi or installer operation is allowed in these fixtures.
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$count = 0
function Assert($condition, [string]$message) {
    if (-not $condition) { throw $message }
    $script:count++
}
function MustFail([scriptblock]$action, [string]$message) {
    $failed = $false
    try { & $action } catch { $failed = $true }
    Assert $failed $message
}
foreach ($path in Get-ChildItem (Join-Path $root 'windows') -Filter '*.ps1') {
    $tokens = $null; $errors = $null
    [void][System.Management.Automation.Language.Parser]::ParseFile($path.FullName, [ref]$tokens, [ref]$errors)
    Assert (-not $errors) "Syntax error in $($path.Name): $errors"
}
. (Join-Path $root 'windows/Setup-Functions.ps1')
$installerAst = [System.Management.Automation.Language.Parser]::ParseFile(
    (Join-Path $root 'windows/Install-Monet.ps1'), [ref]$tokens, [ref]$errors)
$diskWrite = $installerAst.Find({ param($node)
    $node -is [System.Management.Automation.Language.CommandAst] -and
    $node.GetCommandName() -in ('Remove-Partition', 'Resize-Partition')
}, $true)
Assert (-not $diskWrite) 'First sign-in must leave the partition layout intact'
$updater = [System.Management.Automation.Language.Parser]::ParseFile(
    (Join-Path $root 'windows/Update-Monet.ps1'), [ref]$tokens, [ref]$errors)
foreach ($entry in $updater.FindAll({ param($node)
    $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -in ('ReleaseOrder', 'Newest')
}, $false)) {
    . ([scriptblock]::Create($entry.Extent.Text))
}
$Repository = 'fixture/Monet'
function Invoke-RestMethod {
    foreach ($tag in ('v0.9.8', 'v0.9.8-5', 'v0.9.8-12', 'v0.9.9', 'v0.9.9-preview', 'v0.9.8-99999999999')) {
        [pscustomobject]@{tag_name=$tag; draft=$tag -eq 'v0.9.9'; assets=@(
            [pscustomobject]@{name="Monet-$($tag.Substring(1))-Windows.zip"}, [pscustomobject]@{name='SHA256SUMS.txt'})}
    }
}
Assert ((ReleaseOrder '0.9.8-5') -gt (ReleaseOrder '0.9.8')) 'A numbered update follows the base release'
Assert ((ReleaseOrder '0.9.9') -gt (ReleaseOrder '0.9.8-12')) 'A later base release follows earlier updates'
Assert ($null -eq (ReleaseOrder '0.9.8-test')) 'Unrecognized suffixes must be skipped'
$latest = Newest
Assert ($latest.Version -eq '0.9.8-12' -and $latest.Package.name -eq 'Monet-0.9.8-12-Windows.zip') 'Select the newest published numeric update and its exact asset'
Remove-Item Function:Invoke-RestMethod
$update = [pscustomobject]@{Type=2;DriverClass='Display';DriverHardwareID='PCI\VEN_10DE&DEV_25BB';InstallationBehavior=[pscustomobject]@{CanRequestUserInput=$false}}
Assert (Test-MonetMissingDriver $update @('PCI\VEN_10DE&DEV_25BB')) 'Matching missing graphics driver must be eligible'
Assert (-not (Test-MonetMissingDriver $update @('PCI\VEN_8086&DEV_51F1'))) 'Working/unrelated graphics driver must not be replaced'
$update.DriverClass='Firmware'
Assert (-not (Test-MonetMissingDriver $update @($update.DriverHardwareID))) 'Firmware must not be installed'
$update.DriverClass='System';$update.Type=1
Assert (-not (Test-MonetMissingDriver $update @($update.DriverHardwareID))) 'Software updates must not enter hardware-only repair'
$update.Type=2;$update.InstallationBehavior.CanRequestUserInput=$true
Assert (-not (Test-MonetMissingDriver $update @($update.DriverHardwareID))) 'Interactive updates must not be installed silently'
$temp = Join-Path ([IO.Path]::GetTempPath()) ('monet-setup-tests-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $temp | Out-Null
try {
    $windowsRoot = New-Item -ItemType Directory (Join-Path $temp 'windows-disk')
    $setupRoot = New-Item -ItemType Directory (Join-Path $temp 'setup-disk')
    New-Item -ItemType Directory (Join-Path $setupRoot.FullName 'monet') | Out-Null
    $letters = @('Z', 'Y', 'X', 'W' | Where-Object { -not (Get-PSDrive -Name $_ -ErrorAction SilentlyContinue) })
    New-PSDrive -Name $letters[0] -PSProvider FileSystem -Root $windowsRoot.FullName | Out-Null
    New-PSDrive -Name $letters[1] -PSProvider FileSystem -Root $setupRoot.FullName | Out-Null
    try {
        $gptData = 'ebd0a0a2-b9e5-4433-87c0-68b6b72699c7'
        $disk = [pscustomobject]@{ Guid = [guid]::NewGuid(); PartitionStyle = 'GPT' }
        $windows = [pscustomobject]@{ DiskNumber = 1; Guid = [guid]::NewGuid(); Offset = 1MB; Size = 5MB; GptType = $gptData }
        $installer = [pscustomobject]@{ DiskNumber = 1; Guid = [guid]::NewGuid(); Offset = 6MB; Size = 2MB;
            GptType = $gptData; DriveLetter = $letters[1]; IsBoot = $false; IsSystem = $false }
        $volume = [pscustomobject]@{ FileSystemLabel = 'MONETSETUP'; FileSystem = 'FAT32' }
        function Get-Disk { param($Number) if ($Number -eq $windows.DiskNumber) { $disk } }
        function Get-Partition {
            param($DriveLetter, $DiskNumber)
            if ($DriveLetter -eq $letters[0]) { $windows }
            elseif ($DiskNumber -eq $installer.DiskNumber) { $windows; $installer }
        }
        function Get-Volume { param($Partition) if ($Partition -eq $installer) { $volume } }
        $drive = "$($letters[0]):"
        $jobFile = Join-Path $setupRoot.FullName 'monet/deployment.json'
        $job = @{ version = 1; id = [guid]::NewGuid(); partitions = @{ version = 1; disk_guid = $disk.Guid;
            windows = @{ guid = $windows.Guid; offset = $windows.Offset; length = $windows.Size };
            setup = @{ guid = $installer.Guid; offset = $installer.Offset; length = $installer.Size } } }
        Assert (-not (Get-MonetInstallerPartition $drive)) 'Without a completed receipt, keep a volume named MONETSETUP'
        $job | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $jobFile
        $receipt = @{ version = 1; phase = 'complete'; job_id = $job.id; manifest_sha256 = (Get-FileHash $jobFile).Hash }
        $checkpoint = Join-Path $windowsRoot.FullName '.monet-setup.json'
        $receipt | ConvertTo-Json | Set-Content -LiteralPath $checkpoint
        Assert ((Get-MonetInstallerPartition $drive) -eq $installer) 'Allow only the FAT32 installer from the completed job'
        $setupGuid = $installer.Guid
        $installer.Guid = [guid]::NewGuid()
        Assert (-not (Get-MonetInstallerPartition $drive)) 'Keep a replacement partition with the same label and files'
        $installer.Guid = $setupGuid
        $installer.DiskNumber = 2
        Assert (-not (Get-MonetInstallerPartition $drive)) 'Keep a matching volume on another disk'
        $installer.DiskNumber = 1
        $installer.IsSystem = $true
        Assert (-not (Get-MonetInstallerPartition $drive)) 'Keep partitions Windows identifies as system partitions'
        $installer.IsSystem = $false
        $receipt.phase = 'applied'
        $receipt | ConvertTo-Json | Set-Content -LiteralPath $checkpoint
        Assert (-not (Get-MonetInstallerPartition $drive)) 'Keep setup media while deployment is incomplete'
        $receipt.phase = 'complete'
        $receipt | ConvertTo-Json | Set-Content -LiteralPath $checkpoint
        Add-Content -LiteralPath $jobFile ' '
        Assert (-not (Get-MonetInstallerPartition $drive)) 'Keep setup media if the stored job has changed'
    } finally {
        Remove-Item Function:Get-Disk, Function:Get-Partition, Function:Get-Volume
        Remove-PSDrive -Name $letters[0], $letters[1]
    }

    function icacls.exe { $global:LASTEXITCODE = $script:aclExit }
    function netsh.exe { $global:LASTEXITCODE = $script:networkExit; $script:imports++ }
    $script:aclExit = 0; $script:networkExit = 1; $script:imports = 0
    $source = Join-Path $temp 'source'; $pending = Join-Path $temp 'pending'
    New-Item -ItemType Directory $source | Out-Null
    Set-Content (Join-Path $source 'profile.xml') 'synthetic profile - no password'
    $result = Import-MonetWifi $source $pending
    Assert ($result.Imported -eq 0 -and $result.Pending -eq 1) 'Missing drivers must preserve pending Wi-Fi'
    Assert (@(Get-ChildItem $source).Count -eq 0) 'Profile must move out of temporary setup before cleanup'
    Assert ((Get-Content (Get-ChildItem $pending).FullName) -eq 'synthetic profile - no password') 'Profile contents changed'
    $result = Import-MonetWifi $pending $pending
    Assert ($result.Pending -eq 1) 'Retry while offline must not remove a profile'
    $script:networkExit = 0
    $result = Import-MonetWifi $pending $pending
    Assert ($result.Imported -eq 1 -and $result.Pending -eq 0) 'Successful import must erase the plaintext staging copy'
    $script:aclExit = 5
    $before = $script:imports
    MustFail { Import-MonetWifi $source $pending } 'Unprotected profile directory must fail closed'
    Assert ($script:imports -eq $before) 'ACL failure must not run netsh'

    $driver = Join-Path $temp 'driver.inf'; $steam = Join-Path $temp 'SteamSetup.exe'
    Set-Content $driver 'synthetic driver'; Set-Content $steam 'synthetic installer'
    $file = [pscustomobject]@{path='driver.inf'; sha256=(Get-FileHash $driver).Hash}
    $manifest = [pscustomobject]@{
        version=1; vendor='LENOVO'; models=@('21HL'); drivers=@([pscustomobject]@{infs=@('driver.inf'); files=@($file)})
        steam=[pscustomobject]@{path='SteamSetup.exe'; sha256=(Get-FileHash $steam).Hash}
    }
    Test-MonetRepairBundle $temp $manifest LENOVO 21HLS24200
    Assert $true 'Valid model and files'
    MustFail { Test-MonetRepairBundle $temp $manifest LENOVO 21ZZ } 'Wrong model must not install'
    MustFail { Test-MonetRepairBundle $temp $manifest Other 21HL } 'Wrong manufacturer must not install'
    MustFail { Test-MonetRepairBundle $temp $manifest LENOVO '' } 'Missing model must not install'
    Set-Content $driver 'corrupt'
    MustFail { Test-MonetRepairBundle $temp $manifest LENOVO 21HL } 'Corrupt payload must not install'
    Set-Content $driver 'synthetic driver'
    $manifest.drivers[0].infs = @('absent.inf')
    MustFail { Test-MonetRepairBundle $temp $manifest LENOVO 21HL } 'Unhashed INF must not run'
    $manifest.drivers[0].infs = @('driver.inf')
    foreach ($unsafe in '../outside.inf', 'C:\Windows\driver.inf', 'driver.inf:stream', '/driver.inf', 'dir/../driver.inf') {
        MustFail { Resolve-MonetBundleFile $temp $unsafe } 'Unsafe manifest path accepted'
    }
    Remove-Item $steam
    MustFail { Test-MonetRepairBundle $temp $manifest LENOVO 21HL } 'Missing Steam payload must stop validation'
    Test-MonetRepairBundle $temp $manifest LENOVO 21HL -DriversOnly
    Assert $true 'Offline setup validates drivers without Steam'

    $env:ProgramData = $temp
    New-Item -ItemType Directory (Join-Path $temp 'Monet') | Out-Null
    $manifest | ConvertTo-Json -Depth 5 | Set-Content (Join-Path $temp 'repair-manifest.json')
    & {
        function Get-CimInstance { [pscustomobject]@{Manufacturer='LENOVO'; Model='21HL'} }
        function Install-MonetOfflineDrivers {
            foreach ($code in $driverCodes) { [pscustomobject]@{inf='driver.inf'; exit_code=$code} }
        }
        $receipt = Join-Path $env:ProgramData 'Monet/hardware-setup.json'
        $driverCodes = @(0, 259, 3010)
        Initialize-MonetHardware $temp
        $hardware = Get-Content $receipt -Raw | ConvertFrom-Json
        Assert ($hardware.state -eq 'done' -and $hardware.drivers[1].exit_code -eq 259) 'An inapplicable driver must not mark setup partial'
        $driverCodes = @(0, 5)
        Initialize-MonetHardware $temp
        $hardware = Get-Content $receipt -Raw | ConvertFrom-Json
        Assert ($hardware.state -eq 'partial') 'A driver installation error must still mark setup partial'
    }

    # Extract and exercise the actual signature validator, including Valve's
    # punctuation. This catches rejection of the real Valve Corp. certificate.
    $tokens = $null; $errors = $null
    $ast = [Management.Automation.Language.Parser]::ParseFile((Join-Path $root 'windows/Install-Launcher.ps1'), [ref]$tokens, [ref]$errors)
    $knownAssignment = $ast.Find({param($n) $n -is [Management.Automation.Language.AssignmentStatementAst] -and $n.Left.Extent.Text -eq '$known'}, $true)
    $Launcher = 'steam'; $x86 = $temp; $x64 = $temp
    $env:ProgramData = $temp; $env:LOCALAPPDATA = $temp
    Invoke-Expression $knownAssignment.Extent.Text
    $signedFunction = $ast.Find({param($n) $n -is [Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq 'Signed'}, $true)
    Invoke-Expression $signedFunction.Extent.Text
    function Get-AuthenticodeSignature { [pscustomobject]@{Status=$script:signatureStatus; SignerCertificate=[pscustomobject]@{Subject=$script:signer}} }
    Set-Content $steam 'fixture'
    $script:signatureStatus = 'Valid'; $script:signer = 'CN=Valve Corp., O=Valve Corp., L=Bellevue, C=US'
    Assert (Signed $steam) 'Real Valve publisher must match'
    $script:signer = 'O=Valve Corporation Evil, C=US'
    Assert (-not (Signed $steam)) 'Similar publisher must not match'
    $script:signer = 'O=Valve Corp., C=US'; $script:signatureStatus = 'HashMismatch'
    Assert (-not (Signed $steam)) 'Broken signature must not run'
    Assert (-not (Signed (Join-Path $temp 'missing.exe'))) 'Missing installer must not run'

    $profileAst = [Management.Automation.Language.Parser]::ParseFile((Join-Path $root 'windows/GameProfile.ps1'), [ref]$tokens, [ref]$errors)
    $removeFunction = $profileAst.Find({param($node)
        $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Remove-MonetOptionalApps'
    }, $true)
    Invoke-Expression $removeFunction.Extent.Text
    $script:removedApps = @()
    $script:deprovisionedApps = @()
    $script:appxQueries = @()
    function Get-AppxProvisionedPackage {
        param([switch]$Online)
        @(
            if ('outlook_provisioned' -notin $script:deprovisionedApps) {
                [pscustomobject]@{DisplayName='Microsoft.OutlookForWindows'; PackageName='outlook_provisioned'}
            }
            [pscustomobject]@{DisplayName='Microsoft.GamingApp'; PackageName='xbox_provisioned'}
        )
    }
    function Remove-AppxProvisionedPackage {
        param([switch]$Online, [string]$PackageName)
        $script:deprovisionedApps += $PackageName
    }
    function Get-AppxPackage {
        param([switch]$AllUsers, [string[]]$PackageTypeFilter)
        Assert $AllUsers 'Optional package cleanup must query every account'
        $script:appxQueries += ($PackageTypeFilter -join ',')
        if ('Bundle' -in $PackageTypeFilter -and 'outlook_bundle' -notin $script:removedApps) {
            [pscustomobject]@{Name='Microsoft.OutlookForWindows'; PackageFullName='outlook_bundle'}
        }
        if ('Main' -in $PackageTypeFilter -and 'weather_main' -notin $script:removedApps) {
            [pscustomobject]@{Name='Microsoft.BingWeather'; PackageFullName='weather_main'}
        }
        [pscustomobject]@{Name='Microsoft.GamingApp'; PackageFullName='xbox_main'}
    }
    function Remove-AppxPackage {
        param([switch]$AllUsers, [string]$Package)
        Assert $AllUsers 'Optional package cleanup must unregister all accounts'
        $script:removedApps += $Package
    }
    Assert (Remove-MonetOptionalApps) 'Optional package cleanup should succeed'
    Assert (($script:deprovisionedApps -join ',') -eq 'outlook_provisioned') 'Deprovision Outlook and retain the Xbox app'
    Assert (($script:removedApps -join ',') -eq 'outlook_bundle,weather_main') 'Remove app bundles before standalone packages and retain the Xbox app'
    Assert (($script:appxQueries -join ';') -eq 'Bundle;Main;Bundle,Main') 'Read the inventory once per package type, then verify the result'
    function Get-AppxPackage { [pscustomobject]@{Name='Microsoft.Copilot'; PackageFullName='copilot_main'} }
    Assert (-not (Remove-MonetOptionalApps)) 'App cleanup must report a package that Windows keeps registered'
} finally {
    Remove-Item -LiteralPath $temp -Recurse -Force
}
Write-Host "$count PowerShell setup checks passed"

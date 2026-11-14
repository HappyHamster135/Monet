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
    $bridgeUpdate = Join-Path $root 'windows/Update-Monet.ps1'
    $programFiles, $programData = $env:ProgramFiles, $env:ProgramData
    $env:ProgramFiles = $env:ProgramData = $temp
    $baseInstalled = '0.9.8'
    function Get-ItemProperty { [pscustomobject]@{ DisplayVersion = $baseInstalled } }
    function Invoke-RestMethod { $releases }
    function BridgeRelease([string]$label, [bool]$draft = $false, [bool]$withSums = $true) {
        $assets = @([pscustomobject]@{ name = "Monet-$label-Windows.zip" })
        if ($withSums) { $assets += [pscustomobject]@{ name = 'SHA256SUMS.txt' } }
        [pscustomobject]@{ tag_name = "v$label"; draft = $draft; assets = $assets }
    }
    $releases = @(
        (BridgeRelease '0.9.8'), (BridgeRelease '0.9.8-5'),
        (BridgeRelease '0.9.9' $true), (BridgeRelease '1.0.0' $false $false),
        (BridgeRelease '2.0.0-rc.1'), (BridgeRelease '2147483648.0.0')
    )
    Assert ((& $bridgeUpdate -CheckOnly) -eq 'Monet Bridge 0.9.8-5 is out (this is 0.9.8).') 'Revision must be newer than the base release'
    $baseInstalled = '0.9.8-5'
    Assert ((& $bridgeUpdate -CheckOnly) -eq 'Monet Bridge 0.9.8-5 is up to date.') 'Same revision must not be reinstalled'
    $releases += (BridgeRelease '0.9.8-10')
    Assert ((& $bridgeUpdate -CheckOnly) -eq 'Monet Bridge 0.9.8-10 is out (this is 0.9.8-5).') 'Revisions sort numerically'
    $releases += (BridgeRelease '0.9.9')
    Assert ((& $bridgeUpdate -CheckOnly) -eq 'Monet Bridge 0.9.9 is out (this is 0.9.8-5).') 'Next base release outranks the prior revision'
    $releases = @()
    Assert ((& $bridgeUpdate -CheckOnly) -eq 'No downloadable Monet Bridge releases were found.') 'Empty release list needs clear feedback'
    $baseInstalled = '0.9.8'
    $releases = @(BridgeRelease '0.9.8-5')
    $fixturePackage = Join-Path $temp 'fixture-package'
    $fixtureFiles = Join-Path $fixturePackage 'Monet for Windows'
    New-Item -ItemType Directory -Path $fixtureFiles -Force | Out-Null
    Set-Content (Join-Path $fixtureFiles 'Install-Monet.ps1') '# Synthetic installer'
    $fixtureZip = Join-Path $temp 'fixture.zip'
    Compress-Archive -Path $fixtureFiles -DestinationPath $fixtureZip
    $bridgeData = Join-Path $temp 'Monet'
    New-Item -ItemType Directory -Path $bridgeData | Out-Null
    $calls = @{ Requests = 0; Installs = 0; Restarts = 0; InterruptDownload = $false }
    function Invoke-WebRequest {
        param([switch]$UseBasicParsing, $TimeoutSec, $Uri, $OutFile)
        $calls.Requests++
        if ($OutFile -like '*.zip') { Copy-Item $fixtureZip $OutFile }
        elseif ($calls.InterruptDownload) { throw 'Connection lost before the checksums arrived' }
        else { Set-Content $OutFile "$( (Get-FileHash $fixtureZip).Hash )  Monet-0.9.8-5-Windows.zip" }
    }
    function powershell.exe { $calls.Installs++; $global:LASTEXITCODE = 0 }
    function shutdown.exe { $calls.Restarts++ }
    & $bridgeUpdate -Stage
    $stageLog = Get-Content (Join-Path $bridgeData 'update.log') -ErrorAction SilentlyContinue
    Assert ((Test-Path (Join-Path $bridgeData 'update-ready')) -and $calls.Requests -eq 2) "Stage must publish a complete verified package. $stageLog"
    Assert ($calls.Installs -eq 0 -and $calls.Restarts -eq 0) 'Stage must leave the active Windows session running'
    & $bridgeUpdate
    Assert ($calls.Installs -eq 0 -and $calls.Restarts -eq 0) 'An updater without a restart request must leave Windows running'
    Set-Content (Join-Path $bridgeData 'update-then-restart') 'fixture'
    & $bridgeUpdate
    Assert ($calls.Requests -eq 2 -and $calls.Installs -eq 1 -and $calls.Restarts -eq 1) 'Return must install from disk and restart without network traffic'
    Assert (-not (Test-Path (Join-Path $bridgeData 'update-ready'))) 'A consumed package must not be applied again'

    Remove-Item (Join-Path $bridgeData 'update-checked')
    $calls.InterruptDownload = $true
    & $bridgeUpdate -Stage
    Assert (-not (Test-Path (Join-Path $bridgeData 'update-ready'))) 'An interrupted download must never publish a ready package'
    Assert (-not (Test-Path (Join-Path $bridgeData 'Update'))) 'An interrupted download must discard the partial package'
    Assert (-not (Test-Path (Join-Path $bridgeData 'update-checked'))) 'An interrupted download must remain eligible for retry'
    Assert ($calls.Installs -eq 1 -and $calls.Restarts -eq 1) 'An interrupted background download must leave Windows running'
    $calls.InterruptDownload = $false
    & $bridgeUpdate -Stage
    Set-Content (Join-Path $bridgeData 'update-ready/Monet-0.9.8-5-Windows.zip') 'damaged after staging'
    Set-Content (Join-Path $bridgeData 'update-then-restart') 'fixture'
    & $bridgeUpdate
    Assert ($calls.Requests -eq 6 -and $calls.Installs -eq 1 -and $calls.Restarts -eq 2) 'Corrupted updates must be discarded and restart must still proceed offline'
    Assert (-not (Test-Path (Join-Path $bridgeData 'update-checked'))) 'A discarded update must be eligible for a fresh download'
    Assert ((Test-Path (Join-Path $bridgeData 'update-claimed'))) 'A fast failure must leave the restart receipt visible to Bridge'
    & $bridgeUpdate
    Assert ($calls.Restarts -eq 2) 'A restart receipt must not trigger another reboot'
    Remove-Item Function:Invoke-WebRequest, Function:powershell.exe, Function:shutdown.exe
    Remove-Item Function:Get-ItemProperty, Function:Invoke-RestMethod
    $env:ProgramFiles, $env:ProgramData = $programFiles, $programData

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
} finally {
    Remove-Item -LiteralPath $temp -Recurse -Force
}
Write-Host "$count PowerShell setup checks passed"

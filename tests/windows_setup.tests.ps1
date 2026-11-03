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
$temp = Join-Path ([IO.Path]::GetTempPath()) ('monet-setup-tests-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $temp | Out-Null
try {
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

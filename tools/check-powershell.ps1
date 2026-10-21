# Parses every PowerShell script in windows/ and reports syntax errors.
$failed = $false
foreach ($file in Get-ChildItem -Path (Join-Path $PSScriptRoot '..\windows'), (Join-Path $PSScriptRoot '../windows') -Filter *.ps1 -ErrorAction SilentlyContinue | Sort-Object FullName -Unique) {
    $tokens = $null; $errors = $null
    [System.Management.Automation.Language.Parser]::ParseFile($file.FullName, [ref]$tokens, [ref]$errors) | Out-Null
    if ($errors) {
        $failed = $true
        foreach ($e in $errors) { Write-Host "$($file.Name):$($e.Extent.StartLineNumber): $($e.Message)" }
    } else {
        Write-Host "ok  $($file.Name)"
    }
}
if ($failed) { exit 1 }

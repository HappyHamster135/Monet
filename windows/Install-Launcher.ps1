<#
.SYNOPSIS
    Installs a game launcher a game in the Games folder Monet shares needs: Epic Games',
    Ubisoft Connect, Battle.net or the EA app (monet-bridge runs it on the first trip for such
    a game); or Discord, for someone who uses it in Monet (on the trip to sign in to launchers).

.DESCRIPTION
    Uses the installer Monet fetched while you were in Monet (Games\.monet\installers), when
    it's signed by the launcher's maker, so nothing needs downloading here; else downloads it
    from the maker. Epic's and Ubisoft's install with no questions (as administrator);
    Battle.net's and the EA app's show their own small window (as you; each asks for an
    administrator itself). Discord installs for you alone, as you, with no questions.
    Nothing happens when the launcher is there already. Exits 0 when it's installed afterwards.

.PARAMETER Launcher
    epic, ubisoft, battlenet, ea or discord.

.PARAMETER Installer
    The installer Monet fetched, if there is one.
#>
param(
    [Parameter(Mandatory)][ValidateSet('epic', 'ubisoft', 'battlenet', 'ea', 'discord')][string]$Launcher,
    [string]$Installer
)

$ErrorActionPreference = 'Stop'
$x86 = ${env:ProgramFiles(x86)}
$x64 = $env:ProgramFiles
$known = @{
    epic      = @{ Installed = (Join-Path $env:ProgramData 'Epic\EpicGamesLauncher\Data');
                   Url = 'https://launcher-public-service-prod06.ol.epicgames.com/launcher/api/installer/download/EpicGamesLauncherInstaller.msi';
                   File = 'EpicGamesLauncherInstaller.msi'; Signer = 'O="?Epic Games' }
    ubisoft   = @{ Installed = (Join-Path $x86 'Ubisoft\Ubisoft Game Launcher\UbisoftConnect.exe');
                   Url = 'https://static3.cdn.ubi.com/orbit/launcher_installer/UbisoftConnectInstaller.exe';
                   File = 'UbisoftConnectInstaller.exe'; Signer = 'O="?Ubisoft' }
    battlenet = @{ Installed = (Join-Path $x86 'Battle.net\Battle.net.exe');
                   Url = 'https://downloader.battle.net/download/getInstallerForGame?os=win&gameProgram=BATTLENET_APP&version=Live';
                   File = 'Battle.net-Setup.exe'; Signer = 'O="?Blizzard Entertainment' }
    ea        = @{ Installed = (Join-Path $x64 'Electronic Arts\EA Desktop\EA Desktop\EALauncher.exe');
                   Url = 'https://origin-a.akamaihd.net/EA-Desktop-Client-Download/installer-releases/EAappInstaller.exe';
                   File = 'EAappInstaller.exe'; Signer = 'O="?Electronic Arts' }
    discord   = @{ Installed = (Join-Path $env:LOCALAPPDATA 'Discord\Update.exe');
                   Url = 'https://discord.com/api/downloads/distributions/app/installers/latest?channel=stable&platform=win&arch=x64';
                   File = 'DiscordSetup.exe'; Signer = 'O="?Discord' }
}[$Launcher]
if (Test-Path $known.Installed) { exit 0 }

# Only an installer its maker signed runs (the shared folder is one anyone can write in).
function Signed([string]$path) {
    if (-not $path -or -not (Test-Path $path)) { return $false }
    $signature = Get-AuthenticodeSignature -FilePath $path
    return $signature.Status -eq 'Valid' -and $signature.SignerCertificate.Subject -match $known.Signer
}

$setup = $Installer
$fetched = $false
if (-not (Signed $setup)) {
    $setup = Join-Path $env:TEMP $known.File
    for ($try = 1; $try -le 5 -and -not (Signed $setup); $try++) {
        try {
            Invoke-WebRequest -UseBasicParsing -Uri $known.Url -OutFile $setup -ErrorAction Stop
        } catch {
            Remove-Item -Force -ErrorAction SilentlyContinue $setup
            Start-Sleep -Seconds 10   # Wi-Fi may still be connecting
        }
    }
    if (-not (Signed $setup)) { exit 1 }
    $fetched = $true
}

switch ($Launcher) {
    'epic' {
        $install = Start-Process -FilePath 'msiexec.exe' -ArgumentList '/i', "`"$setup`"", '/qn', '/norestart' -Wait -PassThru
        # The launcher makes its data folder on its first start; it's installed when msiexec says so.
        if ($install.ExitCode -eq 0 -or $install.ExitCode -eq 3010) {
            New-Item -ItemType Directory -Force -Path (Join-Path $known.Installed 'Manifests') | Out-Null
        }
    }
    'ubisoft' { Start-Process -FilePath $setup -ArgumentList '/S' -Wait | Out-Null }
    'battlenet' {
        $language = (Get-Culture).Name -replace '-', ''
        Start-Process -FilePath $setup -ArgumentList "--lang=$language", "--installpath=`"$(Join-Path $x86 'Battle.net')`"" -Wait | Out-Null
    }
    'ea' { Start-Process -FilePath $setup -Wait | Out-Null }
    # Installs for this account without a question, then starts Discord to sign in: waits for
    # the installer alone (-Wait would wait for Discord too, which stays open).
    'discord' { (Start-Process -FilePath $setup -PassThru).WaitForExit() }
}
if ($fetched) { Remove-Item -Force -ErrorAction SilentlyContinue $setup }
if (Test-Path $known.Installed) { exit 0 }
exit 1

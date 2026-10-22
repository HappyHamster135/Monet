<#
  Makes a Hyper-V virtual machine for trying Monet on a Windows PC, set up the
  way a real PC is: UEFI with Secure Boot on (with Microsoft's keys for Linux,
  so Monet starts through its signed shim and shows the blue driver-key
  screen once), a TPM for the Windows half, 8 GB of memory, 4 processors, a
  128 GB disk, the internet through Hyper-V's Default Switch, and the USB
  stick's image in its DVD drive.

  In PowerShell as administrator, with Hyper-V turned on:

    .\tools\hyperv-vm.ps1 -Iso D:\VMs\Monet-0.7.0-Installer.iso

  Then Hyper-V Manager: select Monet, Connect, Start. Once Monet is
  installed, take a checkpoint, so it can go back to a fresh Monet at once.
#>
param(
    [Parameter(Mandatory)][string]$Iso,
    [string]$Name = "Monet",
    [string]$Folder = "D:\VMs",
    [int]$DiskGB = 128,
    [int]$MemoryGB = 8,
    [int]$Processors = 4
)
$ErrorActionPreference = "Stop"

if (-not (Get-Command New-VM -ErrorAction SilentlyContinue)) {
    throw "Hyper-V isn't turned on. In PowerShell as administrator: Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V-All, then restart."
}
if (Get-VM -Name $Name -ErrorAction SilentlyContinue) {
    throw "There's already a virtual machine called $Name. Remove it in Hyper-V Manager, or pick another -Name."
}
$image = (Resolve-Path $Iso).Path
New-Item -ItemType Directory -Force -Path $Folder | Out-Null

New-VM -Name $Name -Generation 2 -MemoryStartupBytes ($MemoryGB * 1GB) -Path $Folder `
    -NewVHDPath (Join-Path $Folder "$Name.vhdx") -NewVHDSizeBytes ($DiskGB * 1GB) -SwitchName "Default Switch" | Out-Null
Set-VMMemory -VMName $Name -DynamicMemoryEnabled $false
Set-VMProcessor -VMName $Name -Count $Processors
# Secure Boot with Microsoft's keys for Linux, like a PC that came with Windows.
Set-VMFirmware -VMName $Name -EnableSecureBoot On -SecureBootTemplate MicrosoftUEFICertificateAuthority
# Windows 11, which Monet installs for games, wants a TPM. Monet itself doesn't.
try {
    Set-VMKeyProtector -VMName $Name -NewLocalKeyProtector
    Enable-VMTPM -VMName $Name
} catch {
    Write-Warning "No TPM for this VM ($($_.Exception.Message)). Monet still installs; Windows 11 inside it won't."
}
$dvd = Add-VMDvdDrive -VMName $Name -Path $image -Passthru
Set-VMFirmware -VMName $Name -FirstBootDevice $dvd
# Checkpoints only when you take them.
Set-VM -VMName $Name -AutomaticCheckpointsEnabled $false

Write-Host "Made $Name in $Folder. In Hyper-V Manager: select $Name, Connect, then Start."

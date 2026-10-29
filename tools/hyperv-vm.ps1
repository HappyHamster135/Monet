<#
  Makes a Hyper-V virtual machine for trying Monet on a Windows PC, set up the
  way a real PC is: UEFI with Secure Boot on (with Microsoft's keys for Linux,
  so Monet starts through its signed shim and shows the blue driver-key
  screen once), a TPM for the Windows half, a 128 GB disk, the internet
  through Hyper-V's Default Switch, and the USB stick's image in its DVD drive.

  Hyper-V draws a Linux desktop with the processor, so Monet's VM gets plenty
  of them: all but four of this PC's (at most 12), 16 GB of memory, and a
  1920x1080 screen (-Width 1600 -Height 900 is smoother still). Checkpoints
  keep what's running, so going back to one takes seconds (tools/vm.py).

  In PowerShell as administrator, with Hyper-V turned on:

    .\tools\hyperv-vm.ps1 -Iso D:\VMs\Monet-0.9.4-Setup.iso

  A VM made before, switched off, gets the same with -Tune:

    .\tools\hyperv-vm.ps1 -Tune

  Then Hyper-V Manager: select Monet, Connect, Start (or python tools/vm.py start).
  Once Monet is installed, take a checkpoint (python tools/vm.py checkpoint fresh).
#>
param(
    [string]$Iso,
    [string]$Name = "Monet",
    [string]$Folder = "D:\VMs",
    [int]$DiskGB = 128,
    [int]$MemoryGB = 16,
    [int]$Processors = 0,
    [int]$Width = 1920,
    [int]$Height = 1080,
    [switch]$Tune
)
$ErrorActionPreference = "Stop"

if (-not (Get-Command New-VM -ErrorAction SilentlyContinue)) {
    throw "Hyper-V isn't turned on. In PowerShell as administrator: Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V-All, then restart."
}
if ($Processors -le 0) {
    $logical = (Get-CimInstance Win32_ComputerSystem).NumberOfLogicalProcessors
    $Processors = [math]::Max(4, [math]::Min(12, $logical - 4))
}

# How fast it is and how it keeps checkpoints: for a new VM and for -Tune.
function Set-Speed {
    Set-VMMemory -VMName $Name -DynamicMemoryEnabled $false -StartupBytes ($MemoryGB * 1GB)
    Set-VMProcessor -VMName $Name -Count $Processors
    Set-VMVideo -VMName $Name -ResolutionType Single -HorizontalResolution $Width -VerticalResolution $Height
    # Standard checkpoints keep memory too: restoring one is back where it was, running.
    Set-VM -VMName $Name -CheckpointType Standard -AutomaticCheckpointsEnabled $false
    Enable-VMIntegrationService -VMName $Name -Name "Guest Service Interface" -ErrorAction SilentlyContinue
}

if ($Tune) {
    $vm = Get-VM -Name $Name
    if ($vm.State -ne "Off") { throw "Switch $Name off first (python tools/vm.py stop), then run this again." }
    Set-Speed
    Write-Host "$Name now has $Processors processors, $MemoryGB GB and a ${Width}x$Height screen."
    return
}

if (-not $Iso) { throw "Give the USB stick's image: -Iso D:\VMs\Monet-Setup.iso (or -Tune for a VM made before)." }
if (Get-VM -Name $Name -ErrorAction SilentlyContinue) {
    throw "There's already a virtual machine called $Name. Remove it in Hyper-V Manager, pick another -Name, or use -Tune."
}
$image = (Resolve-Path $Iso).Path
New-Item -ItemType Directory -Force -Path $Folder | Out-Null

New-VM -Name $Name -Generation 2 -MemoryStartupBytes ($MemoryGB * 1GB) -Path $Folder `
    -NewVHDPath (Join-Path $Folder "$Name.vhdx") -NewVHDSizeBytes ($DiskGB * 1GB) -SwitchName "Default Switch" | Out-Null
Set-Speed
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

Write-Host "Made $Name in $Folder ($Processors processors, $MemoryGB GB). In Hyper-V Manager: select $Name, Connect, then Start."

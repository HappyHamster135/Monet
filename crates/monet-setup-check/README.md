# Windows Setup identity checker

This program verifies prepared partitions and, in its explicit `--deploy` mode,
installs Windows inside WinPE. The integration is on the local follow-up branch;
it is not in the prepared 0.9.5 candidate or installed on this laptop.
Remaining installation acceptance is tracked in backlog item 095-52. It adds no daemon or
background work to the installed desktop.

`monet-setup-check.exe preparation.json D` inspects native Windows storage and
prints a JSON selection only when the supplied preparation record matches. The
example `D` is the drive letter of the staged setup volume. A nonzero exit and
diagnostic mean the selection was not verified.

The Linux `deployment_manifest()` producer records GPT disk/partition GUIDs,
byte offsets and lengths, filesystem kinds and filesystem IDs. The checker
requires matching Windows, Setup and shared EFI partitions on one observed
physical disk. It rejects changed filesystems, read-only media, duplicate disk
or partition identities, ambiguous drive letters, overlapping geometry and
incomplete native records. Names and volume labels never select the target.

Windows queries use read-only device handles and the SDK's GPT and volume-extent
structures. NTFS identity uses its full 64-bit filesystem serial; FAT32 uses the
32-bit serial. A hidden shared EFI partition need not have a mounted volume:
its recorded GPT entry and FAT32 boot sector are read directly, without mounting
it. Only that recorded EFI partition is probed this way.

In the native WinPE fixture, an EFI partition remains absent from volume-GUID
enumeration even after DiskPart assigns it a drive letter. Discovery therefore
also checks unlisted drive-letter device handles, read-only, against the complete
GPT extent and filesystem identity. A conflicting observation stops selection;
the existence of a drive letter alone never establishes a match.

Relevant API definitions:

- [GPT drive layout](https://learn.microsoft.com/en-us/windows/win32/api/winioctl/ni-winioctl-ioctl_disk_get_drive_layout_ex)
- [Volume extents](https://learn.microsoft.com/en-us/windows/win32/api/winioctl/ni-winioctl-ioctl_volume_get_volume_disk_extents)
- [NTFS volume data](https://learn.microsoft.com/en-us/windows/win32/api/winioctl/ni-winioctl-fsctl_get_ntfs_volume_data)

## Recorded deployment

Linux embeds the program, deployment script and exact job manifest in boot.wim.
The WinPE launcher only calls that RAM-image copy. `--deploy deployment.json`
refuses to run outside WinPE, checks the recorded partitions and verifies every
payload's size and SHA-256 before the first target write. Verified input handles
stay open without write/delete sharing during image application and copies.

The target starts empty and receives a checkpoint bound to the exact manifest
hash and job ID before DISM runs. An interrupted `applying` phase reapplies the
same WIM without formatting; a successful application records `applied` before
boot configuration and will never run DISM again for that job. `complete` retries
do not rewrite Windows. Unknown data, changed payloads, changed identities or a
foreign/damaged receipt stop the job. Windows paths reject traversal, alternate
streams, reserved names and reparse points.

EFI assignment uses the verified physical disk and partition number and checks
the resulting drive letter again. BCDBoot gets an explicit shared EFI volume,
with no automatic-volume fallback. The original bootx64.efi fallback loader is
backed up and restored across retries. Linux checks the same saved payload and
NTFS checkpoint before restarting an existing job; it does not erase or restage
an installation that has begun.

WIM retry behavior follows [Microsoft's WIM documentation](https://learn.microsoft.com/en-us/windows-hardware/manufacture/desktop/wim-vs-ffu-image-file-formats?view=windows-11):
matching files are replaced and other files remain. This is not a general
reinstallation mechanism for a user's existing Windows.

## Checks and remaining acceptance

`cargo test -p monet-setup-check` tests identity selection. Linux additionally
checks the actual Python manifest producer and disposable `mkfs.fat`/`blkid`
images with 512- and 4096-byte logical sectors. Native Windows tests decode SDK
layout buffers and reject malformed, overlapping and duplicate records; CI
builds and tests the crate on Windows. Transaction tests inject application and
boot failures, changed identities, bad payloads, extra split images and redirected
paths; actual temporary directories prove preservation and retry behavior. Python
tests embed/extract a real disposable WIM and read checkpoints from a real NTFS
file image. None of these tests formats a block device.

The isolated WinPE 10.0.26100.1 fixture now passes 22 Windows tests, including
native SDK layouts and Windows payload-sharing locks. Real SATA GPT/NTFS/FAT32
queries accept the recorded partitions and reject a changed serial. Native DISM
applies a tiny non-bootable test image; BCDBoot then deliberately fails. The
helper keeps the `applied` checkpoint, preserves the original EFI fallback and
user files, and retries without reapplying the image. The EFI letter discovery
fix was found by this fixture, rather than by the simulated backend tests.

Run [the repeatable fixture](../../tools/test-winpe.py) with an independently
obtained amd64 ADK WinPE Media directory and winpe.wim, the release checker,
Windows executables from `cargo test -p monet-setup-check --target
x86_64-pc-windows-gnu --no-run`, and OVMF firmware. `--test-exe` is repeatable;
`--work` must name a new directory. `--help` lists dependencies and arguments.
Only ordinary files created inside that directory become VM disks. The VM has
no network interface and shuts down automatically; logs and images remain there
for inspection. Windows/ADK images are not bundled or downloaded by the tool.

[The full-image fixture](../../tools/test-windows-install.py) additionally checks
DISM and successful BCDBoot, a completed retry, the original EFI fallback and a
user file, then boots Windows and checks the automatic first-logon handoff. It
uses a fresh 64 GiB file-backed GPT disk, private OVMF variables and a virtual TPM.
Supply independently verified **en-US x64**, single-image installation and WinPE
WIMs, matching WinPE media, the release checker and OVMF firmware. `--help` lists
the required tools. No Microsoft images are downloaded or included in the repo.

The original ESP remains on the target. A boot entry in the fixture's OVMF file
selects `EFI/Microsoft/Boot/bootmgfw.efi`; the host firmware is never accessed.
The fixture records the actual account, computer, administrator token and four
first-logon flags instead of installing Bridge, the Game Profile or Steam. Its
test account deliberately matches Monet's usual computer name, exercising the
preparation helper's account-domain collision guard. It keeps the production
answer-file template and renders it through the production escaping helper.

The complete fixture passes with Microsoft's en-US x64 Windows 11 Enterprise
Evaluation, build 26300: successful BCDBoot, completed retry, preserved fallback
and user file, automatic account creation and elevated first-logon execution.
The result records `Monet-Games` on `MONET-PLAY`, the expected job/checkpoint and
all four handoff flags. Windows' setup log confirms membership in Users and
Administrators. An earlier account/computer-name collision had prevented those
group assignments and the first-logon task; the preparation helper now chooses
a different computer name while preserving the requested account name.

Locked/offline disks, alternate storage drivers, consumer Windows editions and
the complete return-to-Monet round trip still need acceptance. The checker cannot
prove that an offline, unenumerated clone is absent.

A successful identity match alone is **not permission to erase a volume**.
The program has no format operation. Do not infer ownership of legacy partitions
that have no Linux preparation receipt. Physical power-loss durability,
restoration of Monet's boot path across a full installation still need acceptance
before enabling this follow-up on a real install. Successful image application
and boot do not establish that a complete installation survives physical power
loss, or that a real Windows game/Bridge round trip works.

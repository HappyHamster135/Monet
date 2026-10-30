# Windows Setup identity checker

This program verifies prepared partitions and, in its explicit `--deploy` mode,
installs Windows inside WinPE. The integration is on the local follow-up branch;
it is not in the prepared 0.9.5 candidate or installed on this laptop. Actual
WinPE acceptance remains open in backlog item 095-52. It adds no daemon or
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

Actual WinPE storage discovery, locked/offline disks, driver behavior and the
complete Windows installation/retry round trip still need VM acceptance. The
checker cannot prove that an offline, unenumerated clone is absent.

A successful identity match alone is **not permission to erase a volume**.
The program has no format operation. Do not infer ownership of legacy partitions
that have no Linux preparation receipt. Physical power-loss durability, native
Windows file-sharing/rename semantics, DISM retries, hidden-ESP assignment,
BCDBoot's exact changes and restoration of Monet's boot path need actual WinPE
VM tests before enabling this follow-up on a real install.

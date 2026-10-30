# Windows Setup identity checker

This is a **read-only foundation**, not yet connected to Monet's Windows
deployment script or shipped in its setup image. It adds no daemon or background
work to the installed desktop. The existing deployment flow still needs the
integration and acceptance work recorded in backlog item 095-52.

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

## Checks and remaining integration

`cargo test -p monet-setup-check` tests identity selection. Linux additionally
checks the actual Python manifest producer and disposable `mkfs.fat`/`blkid`
images with 512- and 4096-byte logical sectors. Native Windows tests decode SDK
layout buffers and reject malformed, overlapping and duplicate records; CI
builds and tests the crate on Windows. None of these tests formats a block device.

Actual WinPE storage discovery, locked/offline disks, driver behavior and the
complete Windows installation/retry round trip still need VM acceptance. The
checker cannot prove that an offline, unenumerated clone is absent.

A successful match is **not permission to erase a volume**. Integration must
embed the trusted manifest and program in the boot image, verify the staged
content, recheck identities immediately before mutation, and persist deployment
phases so a retry cannot erase a completed Windows installation. The present
label-based `deploy.cmd` remains unchanged pending that work. Do not use this
checker alone to authorize formatting, or infer ownership of legacy partitions
that have no Linux preparation receipt.

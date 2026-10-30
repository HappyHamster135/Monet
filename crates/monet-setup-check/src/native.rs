//! Windows storage queries. Every device handle is read-only; no control code here writes media.
use monet_setup_check::Volume;
use std::collections::{HashMap, HashSet};
use std::ffi::c_void;
use std::io;
use std::mem::{offset_of, size_of};
use std::ptr::{null, null_mut};
use windows_sys::core::GUID;
use windows_sys::Win32::Foundation::{
    CloseHandle, ERROR_INSUFFICIENT_BUFFER, ERROR_MORE_DATA, ERROR_NO_MORE_FILES, GENERIC_READ,
    HANDLE, INVALID_HANDLE_VALUE,
};
use windows_sys::Win32::Storage::FileSystem::{
    CreateFileW, FindFirstVolumeW, FindNextVolumeW, FindVolumeClose, GetLogicalDrives,
    GetVolumeInformationByHandleW, GetVolumePathNamesForVolumeNameW, ReadFile, SetFilePointerEx,
    FILE_BEGIN, FILE_SHARE_READ, FILE_SHARE_WRITE, IOCTL_VOLUME_GET_VOLUME_DISK_EXTENTS,
    OPEN_EXISTING,
};
use windows_sys::Win32::System::Ioctl::{
    DRIVE_LAYOUT_INFORMATION_EX, FSCTL_GET_NTFS_VOLUME_DATA, GPT_BASIC_DATA_ATTRIBUTE_READ_ONLY,
    IOCTL_DISK_GET_DRIVE_LAYOUT_EX, IOCTL_DISK_IS_WRITABLE, NTFS_VOLUME_DATA_BUFFER,
    PARTITION_INFORMATION_EX, PARTITION_STYLE_GPT, VOLUME_DISK_EXTENTS,
};
use windows_sys::Win32::System::IO::DeviceIoControl;

fn bad(message: &str) -> io::Error {
    io::Error::other(message)
}
fn wide(text: &str) -> Vec<u16> {
    text.encode_utf16().chain(Some(0)).collect()
}
fn from_wide(text: &[u16]) -> String {
    String::from_utf16_lossy(&text[..text.iter().position(|c| *c == 0).unwrap_or(text.len())])
}
fn guid(id: GUID) -> String {
    format!(
        "{:08x}-{:04x}-{:04x}-{:02x}{:02x}-{:02x}{:02x}{:02x}{:02x}{:02x}{:02x}",
        id.data1,
        id.data2,
        id.data3,
        id.data4[0],
        id.data4[1],
        id.data4[2],
        id.data4[3],
        id.data4[4],
        id.data4[5],
        id.data4[6],
        id.data4[7]
    )
}

struct Handle(HANDLE);
impl Drop for Handle {
    fn drop(&mut self) {
        unsafe {
            CloseHandle(self.0);
        }
    }
}
struct Search(HANDLE);
impl Drop for Search {
    fn drop(&mut self) {
        unsafe {
            FindVolumeClose(self.0);
        }
    }
}

fn open(path: &str) -> io::Result<Handle> {
    let path = wide(path);
    // SAFETY: path is terminated, security/template arguments are null, handle ownership is retained.
    let handle = unsafe {
        CreateFileW(
            path.as_ptr(),
            GENERIC_READ,
            FILE_SHARE_READ | FILE_SHARE_WRITE,
            null(),
            OPEN_EXISTING,
            0,
            null_mut(),
        )
    };
    if handle == INVALID_HANDLE_VALUE {
        Err(io::Error::last_os_error())
    } else {
        Ok(Handle(handle))
    }
}

fn query(handle: &Handle, code: u32, output: *mut c_void, bytes: usize) -> io::Result<usize> {
    let mut read = 0;
    // SAFETY: callers supply a live, writable buffer of the stated size (or null and zero).
    if unsafe {
        DeviceIoControl(
            handle.0,
            code,
            null(),
            0,
            output,
            bytes as u32,
            &mut read,
            null_mut(),
        )
    } == 0
    {
        Err(io::Error::last_os_error())
    } else if read as usize > bytes {
        Err(bad("Storage query returned an invalid byte count."))
    } else {
        Ok(read as usize)
    }
}

#[derive(Clone, Debug)]
struct Part {
    number: u32,
    guid: String,
    kind: String,
    offset: u64,
    length: u64,
    read_only: bool,
}
struct Disk {
    guid: String,
    parts: Vec<Part>,
    read_only: bool,
}

fn parse_layout(data: &[u64], bytes: usize) -> io::Result<(String, Vec<Part>)> {
    let header = offset_of!(DRIVE_LAYOUT_INFORMATION_EX, PartitionEntry);
    if bytes > std::mem::size_of_val(data) || bytes < header {
        return Err(bad("Incomplete GPT layout header."));
    }
    let raw = data.as_ptr().cast::<DRIVE_LAYOUT_INFORMATION_EX>();
    // SAFETY: the u64 buffer has the SDK structures' alignment. The header is fully within bytes.
    let (style, count, disk_guid) = unsafe {
        (
            (*raw).PartitionStyle,
            (*raw).PartitionCount,
            (*raw).Anonymous.Gpt.DiskId,
        )
    };
    if style != PARTITION_STYLE_GPT as u32 {
        return Err(bad("The volume's physical disk is not GPT."));
    }
    let needed = (count as usize)
        .checked_mul(size_of::<PARTITION_INFORMATION_EX>())
        .and_then(|size| size.checked_add(header))
        .ok_or_else(|| bad("Invalid GPT partition count."))?;
    if needed > bytes {
        return Err(bad("Incomplete GPT partition entries."));
    }
    if monet_setup_check::guid(&guid(disk_guid)).is_none() {
        return Err(bad("Invalid GPT disk identity."));
    }
    let mut parts: Vec<Part> = Vec::new();
    let mut numbers = HashSet::new();
    let mut identities = HashSet::new();
    for index in 0..count as usize {
        // SAFETY: needed bounds every selected entry. Only scalar/GUID fields are read; no bool is materialized.
        let p = unsafe {
            data.as_ptr()
                .cast::<u8>()
                .add(header + index * size_of::<PARTITION_INFORMATION_EX>())
                .cast::<PARTITION_INFORMATION_EX>()
        };
        let (style, number, offset, length) = unsafe {
            (
                (*p).PartitionStyle,
                (*p).PartitionNumber,
                (*p).StartingOffset,
                (*p).PartitionLength,
            )
        };
        if number == 0 {
            continue;
        }
        if style != PARTITION_STYLE_GPT
            || offset <= 0
            || length <= 0
            || offset % 512 != 0
            || length % 512 != 0
            || offset.checked_add(length).is_none()
        {
            return Err(bad("Invalid GPT partition geometry."));
        }
        let (id, kind, attributes) = unsafe {
            (
                (*p).Anonymous.Gpt.PartitionId,
                (*p).Anonymous.Gpt.PartitionType,
                (*p).Anonymous.Gpt.Attributes,
            )
        };
        if monet_setup_check::guid(&guid(id)).is_none()
            || monet_setup_check::guid(&guid(kind)).is_none()
            || !numbers.insert(number)
            || !identities.insert(guid(id))
            || parts.iter().any(|p| {
                (offset as u64) < p.offset + p.length && p.offset < (offset + length) as u64
            })
        {
            return Err(bad("Ambiguous GPT partition identities or boundaries."));
        }
        parts.push(Part {
            number,
            guid: guid(id),
            kind: guid(kind),
            offset: offset as u64,
            length: length as u64,
            read_only: attributes & GPT_BASIC_DATA_ATTRIBUTE_READ_ONLY != 0,
        });
    }
    Ok((guid(disk_guid), parts))
}

fn disk(number: u32) -> io::Result<Disk> {
    let handle = open(&format!(r"\\.\PhysicalDrive{number}"))?;
    let mut size = 4096;
    loop {
        let mut storage = vec![0u64; size / 8];
        match query(
            &handle,
            IOCTL_DISK_GET_DRIVE_LAYOUT_EX,
            storage.as_mut_ptr().cast(),
            size,
        ) {
            Ok(bytes) => {
                let (guid, parts) = parse_layout(&storage, bytes)?;
                let read_only = query(&handle, IOCTL_DISK_IS_WRITABLE, null_mut(), 0).is_err();
                return Ok(Disk {
                    guid,
                    parts,
                    read_only,
                });
            }
            Err(error)
                if matches!(error.raw_os_error(), Some(n) if n == ERROR_INSUFFICIENT_BUFFER as i32 || n == ERROR_MORE_DATA as i32)
                    && size < 1024 * 1024 =>
            {
                size *= 2;
            }
            Err(error) => return Err(error),
        }
    }
}

fn letters(path: &str) -> io::Result<Vec<char>> {
    let name = wide(path);
    let mut paths = vec![0u16; 32768];
    let mut needed = 0;
    if unsafe {
        GetVolumePathNamesForVolumeNameW(
            name.as_ptr(),
            paths.as_mut_ptr(),
            paths.len() as u32,
            &mut needed,
        )
    } == 0
    {
        return Err(io::Error::last_os_error());
    }
    if needed as usize > paths.len() {
        return Err(bad("Invalid volume mount-point length."));
    }
    Ok(paths[..needed as usize]
        .split(|c| *c == 0)
        .filter_map(|s| {
            if s.len() == 3
                && s[1] == b':' as u16
                && s[2] == b'\\' as u16
                && (65..=90).contains(&s[0])
            {
                Some(s[0] as u8 as char)
            } else {
                None
            }
        })
        .collect())
}

fn filesystem(handle: &Handle) -> (String, String) {
    let mut name = [0u16; 64];
    let mut serial = 0;
    if unsafe {
        GetVolumeInformationByHandleW(
            handle.0,
            null_mut(),
            0,
            &mut serial,
            null_mut(),
            null_mut(),
            name.as_mut_ptr(),
            name.len() as u32,
        )
    } == 0
    {
        return (String::new(), String::new());
    }
    match from_wide(&name).as_str() {
        "FAT32" => ("vfat".into(), format!("{serial:08X}")),
        "NTFS" => {
            let mut data = NTFS_VOLUME_DATA_BUFFER::default();
            if query(
                handle,
                FSCTL_GET_NTFS_VOLUME_DATA,
                (&mut data as *mut NTFS_VOLUME_DATA_BUFFER).cast(),
                size_of::<NTFS_VOLUME_DATA_BUFFER>(),
            )
            .is_ok_and(|bytes| bytes >= size_of::<NTFS_VOLUME_DATA_BUFFER>())
            {
                (
                    "ntfs".into(),
                    format!("{:016X}", data.VolumeSerialNumber as u64),
                )
            } else {
                ("ntfs".into(), String::new())
            }
        }
        other => (other.to_ascii_lowercase(), String::new()),
    }
}

fn volume(path: &str, letter: Option<char>, disks: &mut HashMap<u32, Disk>) -> io::Result<Volume> {
    let handle = open(path.trim_end_matches('\\'))?;
    let mut extents = VOLUME_DISK_EXTENTS::default();
    let bytes = query(
        &handle,
        IOCTL_VOLUME_GET_VOLUME_DISK_EXTENTS,
        (&mut extents as *mut VOLUME_DISK_EXTENTS).cast(),
        size_of::<VOLUME_DISK_EXTENTS>(),
    )?;
    if bytes < size_of::<VOLUME_DISK_EXTENTS>() || extents.NumberOfDiskExtents != 1 {
        return Err(bad(
            "Setup requires a single basic partition, not a spanned/dynamic volume.",
        ));
    }
    let extent = extents.Extents[0];
    if extent.StartingOffset <= 0 || extent.ExtentLength <= 0 {
        return Err(bad("Invalid volume extent."));
    }
    if let std::collections::hash_map::Entry::Vacant(entry) = disks.entry(extent.DiskNumber) {
        entry.insert(disk(extent.DiskNumber)?);
    }
    let disk = &disks[&extent.DiskNumber];
    let parts: Vec<_> = disk
        .parts
        .iter()
        .filter(|p| {
            p.offset == extent.StartingOffset as u64 && p.length == extent.ExtentLength as u64
        })
        .collect();
    if parts.len() != 1 {
        return Err(bad(
            "The volume does not map to one complete GPT partition.",
        ));
    }
    let part = parts[0];
    let (filesystem, filesystem_id) = filesystem(&handle);
    Ok(Volume {
        volume_path: path.into(),
        letters: match letter {
            Some(letter) => vec![letter],
            None => letters(path)?,
        },
        disk_number: extent.DiskNumber,
        partition_number: part.number,
        disk_guid: disk.guid.clone(),
        partition_guid: part.guid.clone(),
        partition_type: part.kind.clone(),
        offset: part.offset,
        length: part.length,
        filesystem,
        filesystem_id,
        read_only: disk.read_only || part.read_only,
    })
}

fn hidden_efi(number: u32, disk: &Disk, part: &Part) -> io::Result<Volume> {
    let handle = open(&format!(r"\\.\PhysicalDrive{number}"))?;
    // Hidden EFI partitions need not have a volume GUID/mount-manager entry.
    // Read only their boot sector at the already-checked GPT offset.
    if unsafe { SetFilePointerEx(handle.0, part.offset as i64, null_mut(), FILE_BEGIN) } == 0 {
        return Err(io::Error::last_os_error());
    }
    let mut boot = [0u8; 4096];
    let mut read = 0;
    if unsafe {
        ReadFile(
            handle.0,
            boot.as_mut_ptr(),
            boot.len() as u32,
            &mut read,
            null_mut(),
        )
    } == 0
    {
        return Err(io::Error::last_os_error());
    }
    if read as usize != boot.len() {
        return Err(bad("Incomplete EFI boot sector read."));
    }
    let filesystem_id = monet_setup_check::fat32_id(&boot, part.length)
        .ok_or_else(|| bad("The EFI partition has no verified FAT32 identity."))?;
    Ok(Volume {
        volume_path: String::new(),
        letters: Vec::new(),
        disk_number: number,
        partition_number: part.number,
        disk_guid: disk.guid.clone(),
        partition_guid: part.guid.clone(),
        partition_type: part.kind.clone(),
        offset: part.offset,
        length: part.length,
        filesystem: "vfat".into(),
        filesystem_id,
        read_only: disk.read_only || part.read_only,
    })
}

fn check_disk_identities(disks: &HashMap<u32, Disk>) -> io::Result<()> {
    let mut identities = HashSet::new();
    for disk in disks.values() {
        if !identities.insert(disk.guid.to_ascii_lowercase()) {
            return Err(bad("Two physical disks have the same GPT identity. Disconnect the duplicate before setup."));
        }
    }
    Ok(())
}

fn add_hidden_efi(
    found: &mut Vec<Volume>,
    disks: &HashMap<u32, Disk>,
    expected_disk: &str,
    expected_efi: &str,
) -> io::Result<()> {
    for (number, disk) in disks {
        if !disk.guid.eq_ignore_ascii_case(expected_disk) {
            continue;
        }
        for part in disk.parts.iter().filter(|p| {
            p.kind == monet_setup_check::EFI_SYSTEM && p.guid.eq_ignore_ascii_case(expected_efi)
        }) {
            if !found
                .iter()
                .any(|v| v.disk_number == *number && v.partition_guid == part.guid)
            {
                found.push(hidden_efi(*number, disk, part)?);
            }
        }
    }
    Ok(())
}

fn merge_efi_letter(found: &mut Vec<Volume>, mounted: Volume) -> io::Result<()> {
    if let Some(existing) = found.iter_mut().find(|v| {
        v.disk_number == mounted.disk_number && v.partition_guid == mounted.partition_guid
    }) {
        let mut comparable = mounted.clone();
        comparable.volume_path = existing.volume_path.clone();
        comparable.letters = existing.letters.clone();
        if *existing != comparable {
            return Err(bad(
                "The EFI identity changed while inspecting its drive letter.",
            ));
        }
        for letter in mounted.letters {
            if !existing.letters.contains(&letter) {
                existing.letters.push(letter);
            }
        }
    } else {
        found.push(mounted);
    }
    Ok(())
}

fn add_lettered_efi(
    found: &mut Vec<Volume>,
    disks: &mut HashMap<u32, Disk>,
    expected_disk: &str,
    expected_efi: &str,
) -> io::Result<()> {
    // FindFirstVolume omits a WinPE EFI mount even after DiskPart assigns its letter.
    // Probe DOS volume handles read-only and require the same complete GPT identity.
    let mask = unsafe { GetLogicalDrives() };
    if mask == 0 {
        return Err(io::Error::last_os_error());
    }
    for letter in 'A'..='Z' {
        if letter == 'X'
            || mask & (1 << (letter as u8 - b'A')) == 0
            || found.iter().any(|v| v.letters.contains(&letter))
        {
            continue;
        }
        if let Ok(mounted) = volume(&format!(r"\\.\{letter}:"), Some(letter), disks) {
            if mounted.partition_type == monet_setup_check::EFI_SYSTEM
                && mounted.disk_guid.eq_ignore_ascii_case(expected_disk)
                && mounted.partition_guid.eq_ignore_ascii_case(expected_efi)
            {
                merge_efi_letter(found, mounted)?;
            }
        }
    }
    Ok(())
}

pub fn volumes(expected_disk: &str, expected_efi: &str) -> io::Result<Vec<Volume>> {
    let mut buffer = [0u16; 1024];
    let handle = unsafe { FindFirstVolumeW(buffer.as_mut_ptr(), buffer.len() as u32) };
    if handle == INVALID_HANDLE_VALUE {
        return Err(io::Error::last_os_error());
    }
    let search = Search(handle);
    let mut found = Vec::new();
    let mut disks = HashMap::new();
    for _ in 0..1024 {
        let path = from_wide(&buffer);
        if !monet_setup_check::volume_path(&path) {
            return Err(bad("Invalid Windows volume enumeration."));
        }
        // Windows also lists optical media, RAM disks and unsupported/locked filesystems.
        // They cannot satisfy a required identity. A missing required volume fails selection.
        if let Ok(volume) = volume(&path, None, &mut disks) {
            found.push(volume);
        }
        if unsafe { FindNextVolumeW(search.0, buffer.as_mut_ptr(), buffer.len() as u32) } == 0 {
            let error = io::Error::last_os_error();
            if error.raw_os_error() == Some(ERROR_NO_MORE_FILES as i32) {
                add_lettered_efi(&mut found, &mut disks, expected_disk, expected_efi)?;
                check_disk_identities(&disks)?;
                add_hidden_efi(&mut found, &disks, expected_disk, expected_efi)?;
                return Ok(found);
            }
            return Err(error);
        }
    }
    Err(bad("Too many volumes to inspect safely."))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn merges_efi_letter_only_when_every_observed_identity_field_matches() {
        let mounted = Volume {
            volume_path: r"\\.\Z:".into(),
            letters: vec!['Z'],
            disk_number: 0,
            partition_number: 1,
            disk_guid: "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee".into(),
            partition_guid: "11111111-2222-3333-4444-555555555555".into(),
            partition_type: monet_setup_check::EFI_SYSTEM.into(),
            offset: 1024 * 1024,
            length: 128 * 1024 * 1024,
            filesystem: "vfat".into(),
            filesystem_id: "1234ABCD".into(),
            read_only: false,
        };
        let mut existing = mounted.clone();
        existing.volume_path = r"\\?\Volume{22222222-3333-4444-5555-666666666666}\".into();
        existing.letters.clear();
        let mut found = vec![existing.clone()];
        merge_efi_letter(&mut found, mounted.clone()).unwrap();
        assert_eq!(found.len(), 1);
        assert_eq!(found[0].letters, ['Z']);
        assert_eq!(found[0].volume_path, existing.volume_path);
        for field in 0..4 {
            let mut changed = mounted.clone();
            match field {
                0 => changed.filesystem_id = "FFFFFFFF".into(),
                1 => changed.offset += 512,
                2 => changed.read_only = true,
                _ => changed.disk_guid = "bbbbbbbb-bbbb-cccc-dddd-eeeeeeeeeeee".into(),
            }
            assert!(merge_efi_letter(&mut found, changed).is_err());
        }
    }

    fn layout() -> (Vec<u64>, usize) {
        let header = offset_of!(DRIVE_LAYOUT_INFORMATION_EX, PartitionEntry);
        let bytes = header + 2 * size_of::<PARTITION_INFORMATION_EX>();
        let mut data = vec![0u64; bytes.div_ceil(8)];
        let raw = data.as_mut_ptr().cast::<DRIVE_LAYOUT_INFORMATION_EX>();
        let id = GUID {
            data1: 0x12345678,
            data2: 0x9abc,
            data3: 0xdef0,
            data4: [1, 2, 3, 4, 5, 6, 7, 8],
        };
        // SAFETY: the aligned, initialized allocation covers the SDK header and both entries.
        unsafe {
            (*raw).PartitionStyle = PARTITION_STYLE_GPT as u32;
            (*raw).PartitionCount = 2;
            (*raw).Anonymous.Gpt.DiskId = id;
            for i in 0..2 {
                let part = data
                    .as_mut_ptr()
                    .cast::<u8>()
                    .add(header + i * size_of::<PARTITION_INFORMATION_EX>())
                    .cast::<PARTITION_INFORMATION_EX>();
                (*part).PartitionStyle = PARTITION_STYLE_GPT;
                (*part).PartitionNumber = i as u32 + 1;
                (*part).StartingOffset = (i as i64 + 1) * 1024 * 1024;
                (*part).PartitionLength = 1024 * 1024;
                (*part).Anonymous.Gpt.PartitionId = GUID {
                    data1: i as u32 + 1,
                    ..id
                };
                (*part).Anonymous.Gpt.PartitionType = GUID {
                    data1: 0xc12a7328,
                    data2: 0xf81f,
                    data3: 0x11d2,
                    data4: [0xba, 0x4b, 0, 0xa0, 0xc9, 0x3e, 0xc9, 0x3b],
                };
                (*part).Anonymous.Gpt.Attributes = if i == 1 {
                    GPT_BASIC_DATA_ATTRIBUTE_READ_ONLY
                } else {
                    0
                };
            }
        }
        (data, bytes)
    }

    #[test]
    fn decodes_real_sdk_offsets_geometry_and_read_only_attributes() {
        let (data, bytes) = layout();
        let (disk, parts) = parse_layout(&data, bytes).unwrap();
        assert_eq!(disk, "12345678-9abc-def0-0102-030405060708");
        assert_eq!(parts.len(), 2);
        assert_eq!(parts[0].number, 1);
        assert_eq!(parts[1].offset, 2 * 1024 * 1024);
        assert_eq!(parts[1].length, 1024 * 1024);
        assert_eq!(parts[0].kind, monet_setup_check::EFI_SYSTEM);
        assert!(!parts[0].read_only);
        assert!(parts[1].read_only);
        assert!(parse_layout(&data, bytes - 1).is_err());
    }

    #[test]
    fn rejects_overlapping_or_duplicate_native_partitions() {
        let (mut data, bytes) = layout();
        let header = offset_of!(DRIVE_LAYOUT_INFORMATION_EX, PartitionEntry);
        let second = unsafe {
            data.as_mut_ptr()
                .cast::<u8>()
                .add(header + size_of::<PARTITION_INFORMATION_EX>())
                .cast::<PARTITION_INFORMATION_EX>()
        };
        unsafe {
            (*second).StartingOffset = 1024 * 1024;
        }
        assert!(parse_layout(&data, bytes).is_err());
        unsafe {
            (*second).StartingOffset = 2 * 1024 * 1024;
            (*second).PartitionNumber = 1;
        }
        assert!(parse_layout(&data, bytes).is_err());
        unsafe {
            (*second).PartitionNumber = 2;
            (*second).Anonymous.Gpt.PartitionId.data1 = 1;
        }
        assert!(parse_layout(&data, bytes).is_err());
    }

    #[test]
    fn rejects_duplicate_disks_even_when_the_clone_has_no_readable_volume() {
        let disks = [
            (
                1,
                Disk {
                    guid: "ABC".into(),
                    parts: vec![],
                    read_only: false,
                },
            ),
            (
                2,
                Disk {
                    guid: "abc".into(),
                    parts: vec![],
                    read_only: false,
                },
            ),
        ]
        .into_iter()
        .collect();
        assert!(check_disk_identities(&disks).is_err());
    }

    #[test]
    fn rejects_short_layouts_and_overflowing_counts() {
        let mut data = vec![0u64; 128];
        assert!(parse_layout(&data, 1).is_err());
        let raw = data.as_mut_ptr().cast::<DRIVE_LAYOUT_INFORMATION_EX>();
        unsafe {
            (*raw).PartitionStyle = PARTITION_STYLE_GPT as u32;
            (*raw).PartitionCount = u32::MAX;
        }
        assert!(parse_layout(&data, 1024).is_err());
    }
    #[test]
    fn sdk_guid_format_preserves_gpt_byte_order() {
        let id = GUID {
            data1: 0x12345678,
            data2: 0x9abc,
            data3: 0xdef0,
            data4: [1, 2, 3, 4, 5, 6, 7, 8],
        };
        assert_eq!(guid(id), "12345678-9abc-def0-0102-030405060708");
    }
}

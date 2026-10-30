//! Match the recorded Linux preparation to native Windows volume identities.
//! Identity selection is read-only. Explicit deployment uses a verified job and durable phases.
use serde::{Deserialize, Serialize};
use std::collections::{HashMap, HashSet};

pub mod deployment;

pub const BASIC_DATA: &str = "ebd0a0a2-b9e5-4433-87c0-68b6b72699c7";
pub const EFI_SYSTEM: &str = "c12a7328-f81f-11d2-ba4b-00a0c93ec93b";

#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Partition {
    pub guid: String,
    pub offset: u64,
    pub length: u64,
    pub filesystem: String,
    pub filesystem_id: String,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Manifest {
    pub version: u32,
    pub disk_guid: String,
    pub windows: Partition,
    pub setup: Partition,
    pub efi: Partition,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct Volume {
    pub volume_path: String,
    pub letters: Vec<char>,
    pub disk_number: u32,
    pub partition_number: u32,
    pub disk_guid: String,
    pub partition_guid: String,
    pub partition_type: String,
    pub offset: u64,
    pub length: u64,
    pub filesystem: String,
    pub filesystem_id: String,
    pub read_only: bool,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct Selection {
    pub setup: char,
    pub windows: char,
    pub efi_disk: u32,
    pub efi_partition: u32,
}

pub fn guid(value: &str) -> Option<String> {
    let bytes = value.as_bytes();
    if bytes.len() != 36 || value == "00000000-0000-0000-0000-000000000000" {
        return None;
    }
    for (index, byte) in bytes.iter().enumerate() {
        if matches!(index, 8 | 13 | 18 | 23) {
            if *byte != b'-' {
                return None;
            }
        } else if !byte.is_ascii_hexdigit() {
            return None;
        }
    }
    Some(value.to_ascii_lowercase())
}

pub fn volume_path(value: &str) -> bool {
    value
        .strip_prefix(r"\\?\Volume{")
        .and_then(|s| s.strip_suffix("}\\"))
        .and_then(guid)
        .is_some()
}

/// FAT32's BPB/extended BPB, read without mounting the hidden EFI partition.
/// Layout follows Microsoft's FAT specification and dosfstools' boot_sector.
pub fn fat32_id(boot: &[u8], partition_length: u64) -> Option<String> {
    if boot.len() < 512
        || boot[510..512] != [0x55, 0xaa]
        || &boot[82..90] != b"FAT32   "
        || boot[66] != 0x29
        || boot[17..19] != [0, 0]
        || boot[22..24] != [0, 0]
    {
        return None;
    }
    let sector = u16::from_le_bytes(boot[11..13].try_into().ok()?) as u64;
    let sectors = u32::from_le_bytes(boot[32..36].try_into().ok()?) as u64;
    let fat_sectors = u32::from_le_bytes(boot[36..40].try_into().ok()?) as u64;
    if !matches!(sector, 512 | 1024 | 2048 | 4096)
        || sectors == 0
        || sectors * sector > partition_length
        || fat_sectors == 0
        || fat_sectors >= sectors
        || boot[13] == 0
        || !boot[13].is_power_of_two()
        || u16::from_le_bytes(boot[14..16].try_into().ok()?) == 0
        || !matches!(boot[16], 1 | 2)
    {
        return None;
    }
    Some(format!(
        "{:08X}",
        u32::from_le_bytes(boot[67..71].try_into().ok()?)
    ))
}

fn fs_id(value: &str, filesystem: &str) -> Option<String> {
    let normalized = value.replace('-', "");
    let len = match filesystem {
        "ntfs" => 16,
        "vfat" => 8,
        _ => return None,
    };
    (normalized.len() == len && normalized.bytes().all(|c| c.is_ascii_hexdigit()))
        .then(|| normalized.to_ascii_uppercase())
}

impl Manifest {
    pub fn validate(&self) -> Result<(), String> {
        if self.version != 1 || guid(&self.disk_guid).is_none() {
            return Err(
                "The Windows preparation record has an unsupported version or disk ID.".into(),
            );
        }
        let mut ids = HashSet::new();
        for (part, fs) in [
            (&self.windows, "ntfs"),
            (&self.setup, "vfat"),
            (&self.efi, "vfat"),
        ] {
            let id =
                guid(&part.guid).ok_or("The preparation record has an invalid partition ID.")?;
            if !ids.insert(id)
                || part.filesystem != fs
                || fs_id(&part.filesystem_id, fs).is_none()
                || part.offset == 0
                || part.length == 0
                || part.offset % 512 != 0
                || part.length % 512 != 0
                || part.offset.checked_add(part.length).is_none()
            {
                return Err(
                    "The preparation record has conflicting or invalid partition details.".into(),
                );
            }
        }
        let parts = [&self.windows, &self.setup, &self.efi];
        for (i, a) in parts.iter().enumerate() {
            for b in parts.iter().skip(i + 1) {
                if a.offset < b.offset + b.length && b.offset < a.offset + a.length {
                    return Err("The recorded Windows partitions overlap.".into());
                }
            }
        }
        Ok(())
    }
}

fn matches(part: &Partition, volume: &Volume, partition_type: &str, disk: &str) -> bool {
    guid(&volume.disk_guid).as_deref() == Some(disk)
        && guid(&volume.partition_guid) == guid(&part.guid)
        && guid(&volume.partition_type).as_deref() == Some(partition_type)
        && part.offset == volume.offset
        && part.length == volume.length
        && volume.filesystem == part.filesystem
        && fs_id(&volume.filesystem_id, &volume.filesystem)
            == fs_id(&part.filesystem_id, &part.filesystem)
        && !volume.read_only
}

pub fn select(
    manifest: &Manifest,
    setup_letter: char,
    volumes: &[Volume],
) -> Result<Selection, String> {
    manifest.validate()?;
    if !setup_letter.is_ascii_uppercase() || setup_letter == 'X' {
        return Err("The setup drive letter is invalid.".into());
    }
    let disk = guid(&manifest.disk_guid).unwrap();
    let mut physical = HashMap::new();
    let mut partitions = HashSet::new();
    let mut letters = HashSet::new();
    for volume in volumes {
        let hidden_efi = volume.partition_type.eq_ignore_ascii_case(EFI_SYSTEM)
            && volume.volume_path.is_empty()
            && volume.letters.is_empty()
            && volume.partition_number > 0;
        if !volume_path(&volume.volume_path) && !hidden_efi {
            return Err("Windows returned an invalid volume path.".into());
        }
        for letter in &volume.letters {
            if !letter.is_ascii_uppercase() || !letters.insert(*letter) {
                return Err("Windows returned ambiguous drive letters.".into());
            }
        }
        let Some(disk_id) = guid(&volume.disk_guid) else {
            continue;
        };
        if let Some(number) = physical.insert(disk_id.clone(), volume.disk_number) {
            if number != volume.disk_number {
                return Err("Two physical disks have the same GPT identity. Disconnect the duplicate before setup.".into());
            }
        }
        if let Some(part_id) = guid(&volume.partition_guid) {
            if !partitions.insert(part_id) {
                return Err(
                    "Two volumes have the same partition identity. Setup cannot choose safely."
                        .into(),
                );
            }
        }
    }
    let find = |part: &Partition, kind| -> Result<&Volume, String> {
        let found: Vec<_> = volumes
            .iter()
            .filter(|v| matches(part, v, kind, &disk))
            .collect();
        if found.len() != 1 {
            return Err("A prepared partition is missing, changed, read-only or ambiguous.".into());
        }
        Ok(found[0])
    };
    let setup = find(&manifest.setup, BASIC_DATA)?;
    let windows = find(&manifest.windows, BASIC_DATA)?;
    let efi = find(&manifest.efi, EFI_SYSTEM)?;
    if !setup.letters.contains(&setup_letter)
        || setup.disk_number != windows.disk_number
        || setup.disk_number != efi.disk_number
    {
        return Err(
            "Setup, Windows and the shared EFI partition are not on the recorded physical disk."
                .into(),
        );
    }
    let target = windows
        .letters
        .iter()
        .copied()
        .find(|letter| *letter != 'X')
        .ok_or("The prepared Windows partition has no usable drive letter.")?;
    if target == setup_letter {
        return Err("Setup and Windows cannot use the same drive letter.".into());
    }
    if efi.partition_number == 0 {
        return Err("The EFI partition number is invalid.".into());
    }
    Ok(Selection {
        setup: setup_letter,
        windows: target,
        efi_disk: efi.disk_number,
        efi_partition: efi.partition_number,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    fn fixture() -> (Manifest, Vec<Volume>) {
        let part = |n, offset, fs: &str, id: &str| Partition {
            guid: format!("11111111-1111-1111-1111-{n:012}"),
            offset,
            length: 1024 * 1024,
            filesystem: fs.into(),
            filesystem_id: id.into(),
        };
        let manifest = Manifest {
            version: 1,
            disk_guid: "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee".into(),
            windows: part(1, 2 * 1024 * 1024, "ntfs", "0123456789ABCDEF"),
            setup: part(2, 3 * 1024 * 1024, "vfat", "1234-ABCD"),
            efi: part(3, 1024 * 1024, "vfat", "5678-DCBA"),
        };
        let volumes = [&manifest.windows, &manifest.setup, &manifest.efi]
            .into_iter()
            .enumerate()
            .map(|(i, p)| Volume {
                volume_path: format!("\\\\?\\Volume{{22222222-2222-2222-2222-{:012}}}\\", i + 1),
                letters: match i {
                    0 => vec!['C'],
                    1 => vec!['D'],
                    _ => vec![],
                },
                disk_number: 7,
                partition_number: i as u32 + 1,
                disk_guid: manifest.disk_guid.clone(),
                partition_guid: p.guid.clone(),
                partition_type: if i == 2 { EFI_SYSTEM } else { BASIC_DATA }.into(),
                offset: p.offset,
                length: p.length,
                filesystem: p.filesystem.clone(),
                filesystem_id: p.filesystem_id.clone(),
                read_only: false,
            })
            .collect();
        (manifest, volumes)
    }

    #[test]
    fn selects_ids_geometry_and_filesystems_without_volume_labels() {
        let (m, mut v) = fixture();
        v[0].partition_guid = v[0].partition_guid.to_uppercase();
        v[1].filesystem_id = "1234abcd".into();
        let selected = select(&m, 'D', &v).unwrap();
        assert_eq!(selected.windows, 'C');
        assert_eq!(selected.setup, 'D');
        assert_eq!(selected.efi_disk, 7);
        assert_eq!(selected.efi_partition, 3);
        v[2].volume_path.clear();
        assert!(select(&m, 'D', &v).is_ok());
    }

    #[test]
    fn rejects_reformatted_resized_moved_and_wrong_type_targets() {
        let (m, v) = fixture();
        let mut cases = Vec::new();
        let mut changed = v.clone();
        changed[0].filesystem_id = "FFFFFFFFFFFFFFFF".into();
        cases.push(changed);
        let mut changed = v.clone();
        changed[0].offset += 512;
        cases.push(changed);
        let mut changed = v.clone();
        changed[0].length -= 512;
        cases.push(changed);
        let mut changed = v.clone();
        changed[0].partition_type = EFI_SYSTEM.into();
        cases.push(changed);
        let mut changed = v.clone();
        changed[0].read_only = true;
        cases.push(changed);
        let mut changed = v.clone();
        changed[2].disk_guid = "33333333-3333-3333-3333-333333333333".into();
        cases.push(changed);
        for changed in cases {
            assert!(select(&m, 'D', &changed).is_err());
        }
    }

    #[test]
    fn rejects_cloned_disks_and_duplicate_partitions_even_without_drive_letters() {
        let (m, mut v) = fixture();
        let mut clone = v[0].clone();
        clone.disk_number = 8;
        clone.letters.clear();
        v.push(clone);
        assert!(select(&m, 'D', &v).unwrap_err().contains("physical disks"));
        v[3].disk_number = 7;
        assert!(select(&m, 'D', &v)
            .unwrap_err()
            .contains("partition identity"));
    }

    #[test]
    fn rejects_bad_manifest_geometry_ids_or_filesystem_serials() {
        let (m, v) = fixture();
        let mut changed = m.clone();
        changed.setup.guid = changed.windows.guid.clone();
        assert!(select(&changed, 'D', &v).is_err());
        let mut changed = m.clone();
        changed.setup.offset = changed.windows.offset;
        assert!(select(&changed, 'D', &v).is_err());
        let mut changed = m.clone();
        changed.windows.length = u64::MAX;
        assert!(select(&changed, 'D', &v).is_err());
        let mut changed = m.clone();
        changed.windows.filesystem_id = "89ABCDEF".into();
        assert!(select(&changed, 'D', &v).is_err());
        let mut changed = m.clone();
        changed.version = 2;
        assert!(select(&changed, 'D', &v).is_err());
    }

    #[test]
    fn rejects_untrusted_drive_letters_and_paths() {
        let (m, mut v) = fixture();
        for letter in ['X', '&', 'd', 'é'] {
            assert!(select(&m, letter, &v).is_err());
        }
        v[0].letters = vec!['D'];
        assert!(select(&m, 'D', &v).is_err());
        v[0].letters = vec!['C'];
        v[2].volume_path = r"C:\&erase".into();
        assert!(select(&m, 'D', &v).is_err());
        assert!(!volume_path(
            r"\\?\Volume{00000000-0000-0000-0000-000000000000}\"
        ));
    }

    #[test]
    fn rejects_missing_target_or_staging_on_an_unrelated_drive() {
        let (m, mut v) = fixture();
        assert!(select(&m, 'E', &v).is_err());
        v.remove(0);
        assert!(select(&m, 'D', &v).is_err());
    }

    #[test]
    fn checks_fat32_serial_without_mounting_and_rejects_truncation_or_bad_geometry() {
        let mut boot = vec![0; 512];
        boot[510..512].copy_from_slice(&[0x55, 0xaa]);
        boot[82..90].copy_from_slice(b"FAT32   ");
        boot[11..13].copy_from_slice(&512u16.to_le_bytes());
        boot[13] = 1;
        boot[14] = 32;
        boot[16] = 2;
        boot[32..36].copy_from_slice(&131072u32.to_le_bytes());
        boot[36..40].copy_from_slice(&1009u32.to_le_bytes());
        boot[66] = 0x29;
        boot[67..71].copy_from_slice(&0x1234abcdu32.to_le_bytes());
        assert_eq!(
            fat32_id(&boot, 64 * 1024 * 1024).as_deref(),
            Some("1234ABCD")
        );
        assert!(fat32_id(&boot[..500], 64 * 1024 * 1024).is_none());
        assert!(fat32_id(&boot, 1024).is_none());
        boot[66] = 0;
        assert!(fat32_id(&boot, 64 * 1024 * 1024).is_none());
    }
}

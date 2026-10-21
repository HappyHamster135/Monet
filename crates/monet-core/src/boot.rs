//! Finding boot entries and choosing what starts next.

use crate::efi::{self, EfiError, EfiVars, Result, ATTR_DEFAULT, GLOBAL_GUID};
use crate::load_option::LoadOption;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct BootEntry {
    pub number: u16,
    pub option: LoadOption,
}

impl BootEntry {
    pub fn is_windows(&self) -> bool {
        let desc = self.option.description.to_ascii_lowercase();
        let path = self.option.file_path.as_deref().unwrap_or("").to_ascii_lowercase();
        desc.contains("windows boot manager") || path.ends_with("\\microsoft\\boot\\bootmgfw.efi")
    }

    /// An entry that loads a non-Windows loader from disk (shim, GRUB,
    /// systemd-boot, ...). Firmware entries such as USB or network boot have
    /// no file path, and the removable-media fallback path
    /// (`\EFI\BOOT\BOOTX64.EFI`, used by USB sticks and Monet's Windows
    /// setup partition) is skipped too.
    pub fn is_other_os(&self) -> bool {
        match self.option.file_path.as_deref() {
            Some(path) => {
                let path = path.to_ascii_lowercase();
                !self.is_windows()
                    && path.ends_with(".efi")
                    && !path.contains("\\microsoft\\")
                    && !path.ends_with("\\efi\\boot\\bootx64.efi")
            }
            None => false,
        }
    }
}

/// All boot entries, in `BootOrder` order first, then any others.
pub fn list_entries(efi: &dyn EfiVars) -> Result<Vec<BootEntry>> {
    let order = boot_order(efi).unwrap_or_default();
    let mut numbers = order.clone();
    let mut extra = efi.boot_entry_numbers().unwrap_or_default();
    extra.sort_unstable();
    for n in extra {
        if !numbers.contains(&n) {
            numbers.push(n);
        }
    }

    let mut entries = Vec::new();
    for number in numbers {
        match efi.get(GLOBAL_GUID, &efi::boot_var_name(number)) {
            Ok(data) => {
                if let Ok(option) = LoadOption::parse(&data) {
                    entries.push(BootEntry { number, option });
                }
            }
            Err(EfiError::NotFound) => {}
            Err(e) => return Err(e),
        }
    }
    Ok(entries)
}

pub fn boot_order(efi: &dyn EfiVars) -> Result<Vec<u16>> {
    efi::read_u16_list(&efi.get(GLOBAL_GUID, "BootOrder")?)
}

/// The entry the running system was started from.
pub fn boot_current(efi: &dyn EfiVars) -> Result<u16> {
    efi::read_u16(&efi.get(GLOBAL_GUID, "BootCurrent")?)
}

pub fn boot_next(efi: &dyn EfiVars) -> Result<Option<u16>> {
    match efi.get(GLOBAL_GUID, "BootNext") {
        Ok(data) => Ok(Some(efi::read_u16(&data)?)),
        Err(EfiError::NotFound) => Ok(None),
        Err(e) => Err(e),
    }
}

/// Starts `number` on the next boot only. The normal boot order is untouched.
pub fn set_boot_next(efi: &mut dyn EfiVars, number: u16) -> Result<()> {
    efi.set(GLOBAL_GUID, "BootNext", &number.to_le_bytes(), ATTR_DEFAULT)
}

/// The Windows Boot Manager entry, preferring active entries.
pub fn find_windows(entries: &[BootEntry]) -> Option<&BootEntry> {
    entries
        .iter()
        .filter(|e| e.is_windows())
        .max_by_key(|e| e.option.is_active())
}

/// Puts `number` first in `BootOrder`. Returns true if anything changed.
pub fn move_to_front(efi: &mut dyn EfiVars, number: u16) -> Result<bool> {
    let mut order = boot_order(efi)?;
    if order.first() == Some(&number) {
        return Ok(false);
    }
    if !order.contains(&number) {
        return Err(EfiError::Invalid(format!("Boot{number:04X} is not in the boot order")));
    }
    order.retain(|n| *n != number);
    order.insert(0, number);
    efi.set(GLOBAL_GUID, "BootOrder", &efi::write_u16_list(&order), ATTR_DEFAULT)?;
    Ok(true)
}

#[cfg(test)]
pub mod testing {
    use super::*;
    use crate::efi::MemoryEfi;
    use crate::load_option::LOAD_OPTION_ACTIVE;

    pub fn add_entry(efi: &mut MemoryEfi, number: u16, description: &str, path: Option<&str>) {
        let option = LoadOption {
            attributes: LOAD_OPTION_ACTIVE,
            description: description.into(),
            file_path: path.map(Into::into),
            partition_guid: None,
        };
        efi.set(GLOBAL_GUID, &efi::boot_var_name(number), &option.encode(), ATTR_DEFAULT)
            .unwrap();
    }

    /// A typical dual-boot laptop: Linux first, Windows second, plus USB/PXE.
    pub fn dual_boot() -> MemoryEfi {
        let mut efi = MemoryEfi::default();
        add_entry(&mut efi, 0x0000, "Windows Boot Manager", Some("\\EFI\\Microsoft\\Boot\\bootmgfw.efi"));
        add_entry(&mut efi, 0x0003, "Fedora", Some("\\EFI\\fedora\\shimx64.efi"));
        add_entry(&mut efi, 0x0010, "UEFI: PXE IPv4", None);
        add_entry(&mut efi, 0x0011, "Linux Firmware Updater", Some("\\EFI\\fedora\\fwupdx64.efi"));
        add_entry(&mut efi, 0x0012, "Monet Windows Setup", Some("\\EFI\\BOOT\\BOOTX64.EFI"));
        efi.set(GLOBAL_GUID, "BootOrder", &efi::write_u16_list(&[3, 0, 0x10]), ATTR_DEFAULT)
            .unwrap();
        efi.set(GLOBAL_GUID, "BootCurrent", &3u16.to_le_bytes(), ATTR_DEFAULT).unwrap();
        efi
    }
}

#[cfg(test)]
mod tests {
    use super::testing::dual_boot;
    use super::*;

    #[test]
    fn finds_windows_and_current() {
        let efi = dual_boot();
        let entries = list_entries(&efi).unwrap();
        assert_eq!(entries.iter().map(|e| e.number).collect::<Vec<_>>(), vec![3, 0, 0x10, 0x11, 0x12]);
        assert_eq!(find_windows(&entries).unwrap().number, 0);
        assert_eq!(boot_current(&efi).unwrap(), 3);
        assert!(entries[0].is_other_os());
        assert!(!entries[1].is_other_os());
        assert!(!entries[2].is_other_os());
        assert!(!entries[4].is_other_os(), "the setup partition is never Monet");
    }

    #[test]
    fn boot_next_and_order() {
        let mut efi = dual_boot();
        assert_eq!(boot_next(&efi).unwrap(), None);
        set_boot_next(&mut efi, 0).unwrap();
        assert_eq!(boot_next(&efi).unwrap(), Some(0));

        // Windows updates like to put themselves first; Monet moves Linux back.
        efi.set(GLOBAL_GUID, "BootOrder", &efi::write_u16_list(&[0, 3, 0x10]), ATTR_DEFAULT)
            .unwrap();
        assert!(move_to_front(&mut efi, 3).unwrap());
        assert_eq!(boot_order(&efi).unwrap(), vec![3, 0, 0x10]);
        assert!(!move_to_front(&mut efi, 3).unwrap());
        assert!(move_to_front(&mut efi, 0x42).is_err());
    }
}

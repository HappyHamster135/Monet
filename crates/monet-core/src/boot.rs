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

/// Whether the firmware can start an entry, as far as Monet can tell.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Reach {
    /// Its partition is there.
    Yes,
    /// Its partition is gone (the disk was wiped or replaced), or starting
    /// it failed before. The firmware skips it and starts Monet instead.
    No,
    /// The entry doesn't say which partition it's on.
    Unknown,
}

/// The Windows Boot Manager entry to start. Many PCs keep old entries after
/// a disk is wiped; those can't start, so they're skipped. Of the rest, a
/// checked entry beats an unchecked one, an active one an inactive one, and
/// then the earliest in `BootOrder` wins.
pub fn find_windows<'a>(
    entries: &'a [BootEntry],
    order: &[u16],
    reach: impl Fn(&BootEntry) -> Reach,
) -> Option<&'a BootEntry> {
    entries
        .iter()
        .filter(|e| e.is_windows())
        .map(|e| (e, reach(e)))
        .filter(|(_, r)| *r != Reach::No)
        .min_by_key(|(e, r)| {
            let position = order.iter().position(|n| *n == e.number).unwrap_or(usize::MAX);
            (*r != Reach::Yes, !e.option.is_active(), position)
        })
        .map(|(e, _)| e)
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
        assert_eq!(find_windows(&entries, &[3, 0, 0x10], |_| Reach::Unknown).unwrap().number, 0);
        assert_eq!(boot_current(&efi).unwrap(), 3);
        assert!(entries[0].is_other_os());
        assert!(!entries[1].is_other_os());
        assert!(!entries[2].is_other_os());
        assert!(!entries[4].is_other_os(), "the setup partition is never Monet");
    }

    /// A PC that came with Windows, wiped by Monet's installer: the factory
    /// entry (Boot0000) still exists, but its partition is gone.
    fn wiped() -> (Vec<BootEntry>, Vec<u16>) {
        use crate::load_option::LOAD_OPTION_ACTIVE;
        let entry = |number, active: bool, guid: &str| BootEntry {
            number,
            option: LoadOption {
                attributes: if active { LOAD_OPTION_ACTIVE } else { 0 },
                description: "Windows Boot Manager".into(),
                file_path: Some("\\EFI\\Microsoft\\Boot\\bootmgfw.efi".into()),
                partition_guid: Some(guid.into()),
            },
        };
        let entries = vec![entry(0x0000, true, "old"), entry(0x0004, true, "new"), entry(0x0007, false, "new")];
        (entries, vec![1, 4, 0])
    }

    #[test]
    fn skips_windows_entries_that_cant_start() {
        let (entries, order) = wiped();
        let reach = |e: &BootEntry| {
            if e.option.partition_guid.as_deref() == Some("new") { Reach::Yes } else { Reach::No }
        };
        assert_eq!(find_windows(&entries, &order, reach).unwrap().number, 4);
        // Even when the stale entry is first in the boot order.
        assert_eq!(find_windows(&entries, &[0, 1, 4], reach).unwrap().number, 4);
        // Or not in it at all.
        assert_eq!(find_windows(&entries, &[1, 4], reach).unwrap().number, 4);
        // Nothing that can start: no Windows at all, rather than a dead one.
        assert!(find_windows(&entries, &order, |_| Reach::No).is_none());
    }

    #[test]
    fn prefers_checked_active_and_early_entries() {
        let (entries, _) = wiped();
        // Unchecked entries lose to a checked one.
        let reach = |e: &BootEntry| if e.number == 7 { Reach::Yes } else { Reach::Unknown };
        assert_eq!(find_windows(&entries, &[0, 4, 7], reach).unwrap().number, 7);
        // All unchecked: the first active one in the boot order.
        assert_eq!(find_windows(&entries, &[7, 4, 0], |_| Reach::Unknown).unwrap().number, 4);
        assert_eq!(find_windows(&entries, &[0, 4, 7], |_| Reach::Unknown).unwrap().number, 0);
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

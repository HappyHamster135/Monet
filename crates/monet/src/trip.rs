//! Getting to Windows reliably: which boot entry to start, how, a log of
//! every trip, and, at Monet's next start, what happened.

use std::fs::{self, OpenOptions};
use std::io::Write;
use std::path::{Path, PathBuf};
use std::process::Command;

use serde::{Deserialize, Serialize};

use monet_core::boot::{self, BootEntry, Reach};
use monet_core::efi::{EfiVars, GLOBAL_GUID, LAUNCH_VAR, MONET_GUID};

use crate::esp;

/// How a trip to Windows was set up.
#[derive(Serialize, Deserialize, Debug, Clone, Copy, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum Method {
    /// BootNext: Windows for one start, then Monet again.
    Once,
    /// BootNext, and Windows first in BootOrder too: for firmware that
    /// ignores BootNext, and for a Windows still finishing its own setup
    /// (it restarts itself on the way). Monet Bridge, or Monet's next
    /// start, puts Monet back first.
    First,
}

/// One trip to Windows, saved just before the restart.
#[derive(Serialize, Deserialize, Debug, Clone, PartialEq, Eq)]
pub struct Trip {
    pub created: u64,
    /// The Windows entry.
    pub entry: u16,
    /// The entry Monet started from.
    pub monet: u16,
    pub method: Method,
}

/// What happened on a trip, read at Monet's next start.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Arrival {
    /// Windows started and Monet Bridge took the request.
    Arrived,
    /// The firmware never used BootNext (or the restart skipped the firmware).
    Skipped,
    /// The firmware used BootNext, but Windows never took the request: the
    /// entry couldn't start, or Windows stopped before Monet Bridge ran.
    Failed,
}

/// Monet Bridge takes the request as soon as Windows is up; the firmware
/// clears BootNext as soon as it uses it.
pub fn classify(boot_next_left: bool, request_left: bool) -> Arrival {
    match (request_left, boot_next_left) {
        (false, _) => Arrival::Arrived,
        (true, true) => Arrival::Skipped,
        (true, false) => Arrival::Failed,
    }
}

/// A trip older than this didn't just happen; it's only tidied up.
const RECENT_SECS: u64 = 2 * 60 * 60;

pub struct Paths {
    dir: PathBuf,
}

impl Paths {
    pub fn new(dir: PathBuf) -> Paths {
        Paths { dir }
    }
    fn trip(&self) -> PathBuf {
        self.dir.join("trip.json")
    }
    fn log(&self) -> PathBuf {
        self.dir.join("switch.log")
    }
    /// Set once the firmware ignored BootNext: trips then use Method::First.
    fn skips_boot_next(&self) -> PathBuf {
        self.dir.join("firmware-skips-bootnext")
    }
    /// Windows entries that failed to start.
    fn bad(&self) -> PathBuf {
        self.dir.join("bad-entries")
    }
    pub fn notice(&self) -> PathBuf {
        self.dir.join("switch-notice")
    }
}

pub fn bad_entries(paths: &Paths) -> Vec<u16> {
    fs::read_to_string(paths.bad())
        .unwrap_or_default()
        .split_whitespace()
        .filter_map(|w| u16::from_str_radix(w, 16).ok())
        .collect()
}

fn save_bad_entries(paths: &Paths, entries: &[u16]) {
    let text: Vec<String> = entries.iter().map(|n| format!("{n:04X}")).collect();
    let _ = fs::write(paths.bad(), text.join("\n"));
}

pub fn firmware_skips_boot_next(paths: &Paths) -> bool {
    paths.skips_boot_next().exists()
}

/// Whether the firmware can start `entry`: its partition must exist, and it
/// mustn't have failed before.
pub fn reach(entry: &BootEntry, bad: &[u16], partuuids: &Path) -> Reach {
    if bad.contains(&entry.number) {
        return Reach::No;
    }
    let Some(guid) = entry.option.partition_guid.as_deref() else {
        return Reach::Unknown;
    };
    if !partuuids.is_dir() {
        return Reach::Unknown;
    }
    if partuuids.join(guid.to_ascii_lowercase()).exists() {
        Reach::Yes
    } else {
        Reach::No
    }
}

pub const PARTUUIDS: &str = "/dev/disk/by-partuuid";

/// The Windows entry to start, if one can.
pub fn choose(efi: &dyn EfiVars, paths: &Paths) -> Option<BootEntry> {
    let entries = boot::list_entries(efi).ok()?;
    let order = boot::boot_order(efi).unwrap_or_default();
    let bad = bad_entries(paths);
    boot::find_windows(&entries, &order, |e| reach(e, &bad, Path::new(PARTUUIDS))).cloned()
}

/// Every Windows entry and whether it can start, for `monet doctor`.
pub fn describe(efi: &dyn EfiVars, paths: &Paths) -> Vec<(BootEntry, Reach)> {
    let bad = bad_entries(paths);
    boot::list_entries(efi)
        .unwrap_or_default()
        .into_iter()
        .filter(|e| e.is_windows())
        .map(|e| {
            let r = reach(&e, &bad, Path::new(PARTUUIDS));
            (e, r)
        })
        .collect()
}

/// Adds a "Windows Boot Manager" entry when none can start but Windows' boot
/// manager is on an EFI partition: bcdboot doesn't always add one, and a
/// wiped disk leaves only dead ones. Monet stays first in the boot order.
pub fn add_windows_entry(efi: &mut dyn EfiVars, monet: u16) -> Result<bool, String> {
    let Some(device) = esp::find_windows_loader() else { return Ok(false) };
    let (disk, part) = esp::disk_and_partition(&device).ok_or_else(|| format!("couldn't tell which disk {device} is on"))?;
    let out = Command::new("efibootmgr")
        .args(["--create", "--disk", &disk, "--part", &part.to_string(), "--label", "Windows Boot Manager", "--loader"])
        .arg("\\EFI\\Microsoft\\Boot\\bootmgfw.efi")
        .output()
        .map_err(|e| format!("couldn't run efibootmgr: {e}"))?;
    if !out.status.success() {
        return Err(format!("efibootmgr: {}", String::from_utf8_lossy(&out.stderr).trim()));
    }
    // efibootmgr puts the new entry first; Monet stays the default.
    let _ = boot::move_to_front(efi, monet);
    Ok(true)
}

/// Appends to /var/lib/monet/switch.log, so a trip that went wrong can be
/// looked into afterwards.
pub fn log(paths: &Paths, now: u64, line: &str) {
    let _ = fs::create_dir_all(&paths.dir);
    if let Ok(mut f) = OpenOptions::new().create(true).append(true).open(paths.log()) {
        let _ = writeln!(f, "{now} {line}");
    }
}

/// The boot variables as they are, for the log.
pub fn snapshot(efi: &dyn EfiVars) -> String {
    let current = boot::boot_current(efi).map(|n| format!("{n:04X}")).unwrap_or_else(|_| "?".into());
    let next = match boot::boot_next(efi) {
        Ok(Some(n)) => format!("{n:04X}"),
        Ok(None) => "none".into(),
        Err(_) => "?".into(),
    };
    let order: Vec<String> = boot::boot_order(efi).unwrap_or_default().iter().map(|n| format!("{n:04X}")).collect();
    let request = if efi.get(MONET_GUID, LAUNCH_VAR).is_ok() { "waiting" } else { "none" };
    format!("current={current} next={next} order={} request={request}", order.join(","))
}

pub fn save(paths: &Paths, trip: &Trip) -> Result<(), String> {
    fs::create_dir_all(&paths.dir).map_err(|e| e.to_string())?;
    let json = serde_json::to_vec(trip).map_err(|e| e.to_string())?;
    fs::write(paths.trip(), json).map_err(|e| e.to_string())
}

/// Puts Windows first in BootOrder for a Method::First trip.
pub fn put_windows_first(efi: &mut dyn EfiVars, entry: u16) -> Result<(), String> {
    let mut order = boot::boot_order(efi).unwrap_or_default();
    order.retain(|n| *n != entry);
    order.insert(0, entry);
    efi.set(GLOBAL_GUID, "BootOrder", &monet_core::efi::write_u16_list(&order), monet_core::efi::ATTR_DEFAULT)
        .map_err(|e| e.to_string())
}

/// At Monet's start: if a trip to Windows just happened and Monet is back,
/// find out why, tidy up, and remember what to do differently. Returns a
/// sentence for the person when something went wrong.
pub fn check_after_boot(efi: &mut dyn EfiVars, paths: &Paths, now: u64, setup_done: bool) -> Option<String> {
    let trip: Trip = serde_json::from_slice(&fs::read(paths.trip()).ok()?).ok()?;
    let _ = fs::remove_file(paths.trip());
    let before = snapshot(efi);

    // Monet is running again: it goes back to being the default.
    if trip.method == Method::First {
        if let Ok(current) = boot::boot_current(efi) {
            let _ = boot::move_to_front(efi, current);
        }
    }

    let next_left = matches!(boot::boot_next(efi), Ok(Some(n)) if n == trip.entry);
    let request_left = efi.get(MONET_GUID, LAUNCH_VAR).is_ok();
    let arrival = classify(next_left, request_left);
    let recent = now.saturating_sub(trip.created) < RECENT_SECS;
    log(paths, now, &format!("back in Monet after a trip to Boot{:04X} ({:?}): {arrival:?}; {before}", trip.entry, trip.method));

    if arrival == Arrival::Arrived {
        let mut bad = bad_entries(paths);
        if bad.contains(&trip.entry) {
            bad.retain(|n| *n != trip.entry);
            save_bad_entries(paths, &bad);
        }
        let _ = fs::remove_file(paths.notice());
        return None;
    }

    // Nobody in Windows will use these now.
    let _ = monet_core::request::clear(efi);
    if next_left {
        let _ = efi.delete(GLOBAL_GUID, "BootNext");
    }
    if !recent {
        return None;
    }

    let notice = match arrival {
        Arrival::Skipped => {
            // Next time, Windows goes first in the boot order as well.
            let _ = fs::write(paths.skips_boot_next(), "");
            "Windows didn't start: this PC skipped Monet's one-time start. Next time, Monet asks it a different way."
                .to_string()
        }
        Arrival::Failed if setup_done && trip.method == Method::Once => {
            // That entry can't start; Monet uses another one, or makes one.
            let mut bad = bad_entries(paths);
            if !bad.contains(&trip.entry) {
                bad.push(trip.entry);
                save_bad_entries(paths, &bad);
            }
            format!(
                "Windows didn't start: this PC couldn't open its boot entry (Boot{:04X}). Next time, Monet uses another one.",
                trip.entry
            )
        }
        _ => "Windows didn't finish starting. Choose Play again to continue; if it happens again, run `monet doctor`.".to_string(),
    };
    let _ = fs::write(paths.notice(), &notice);
    Some(notice)
}

#[cfg(test)]
mod tests {
    use super::*;
    use monet_core::efi::{MemoryEfi, ATTR_DEFAULT};
    use monet_core::load_option::{LoadOption, LOAD_OPTION_ACTIVE};

    fn temp() -> PathBuf {
        let dir = std::env::temp_dir().join(format!("monet-trip-{}-{:?}", std::process::id(), std::thread::current().id()));
        let _ = fs::remove_dir_all(&dir);
        fs::create_dir_all(&dir).unwrap();
        dir
    }

    fn pc(next: Option<u16>, request: bool) -> MemoryEfi {
        let mut efi = MemoryEfi::default();
        for (n, name) in [(1u16, "Monet"), (4, "Windows Boot Manager")] {
            let option = LoadOption {
                attributes: LOAD_OPTION_ACTIVE,
                description: name.into(),
                file_path: Some(if n == 4 { "\\EFI\\Microsoft\\Boot\\bootmgfw.efi" } else { "\\EFI\\fedora\\shimx64.efi" }.into()),
                partition_guid: None,
            };
            efi.set(GLOBAL_GUID, &monet_core::efi::boot_var_name(n), &option.encode(), ATTR_DEFAULT).unwrap();
        }
        efi.set(GLOBAL_GUID, "BootOrder", &monet_core::efi::write_u16_list(&[4, 1]), ATTR_DEFAULT).unwrap();
        efi.set(GLOBAL_GUID, "BootCurrent", &1u16.to_le_bytes(), ATTR_DEFAULT).unwrap();
        if let Some(n) = next {
            efi.set(GLOBAL_GUID, "BootNext", &n.to_le_bytes(), ATTR_DEFAULT).unwrap();
        }
        if request {
            efi.set(MONET_GUID, LAUNCH_VAR, b"{}", ATTR_DEFAULT).unwrap();
        }
        efi
    }

    #[test]
    fn tells_what_happened() {
        assert_eq!(classify(false, false), Arrival::Arrived);
        assert_eq!(classify(true, false), Arrival::Arrived);
        assert_eq!(classify(true, true), Arrival::Skipped);
        assert_eq!(classify(false, true), Arrival::Failed);
    }

    #[test]
    fn firmware_that_skips_boot_next_gets_the_other_way() {
        let paths = Paths::new(temp());
        save(&paths, &Trip { created: 1000, entry: 4, monet: 1, method: Method::Once }).unwrap();
        let mut efi = pc(Some(4), true);
        let notice = check_after_boot(&mut efi, &paths, 1060, true).unwrap();
        assert!(notice.contains("skipped"));
        assert!(firmware_skips_boot_next(&paths));
        assert!(boot::boot_next(&efi).unwrap().is_none(), "BootNext is cleared");
        assert!(efi.get(MONET_GUID, LAUNCH_VAR).is_err(), "the request is cleared");
        // Handled once.
        assert!(check_after_boot(&mut efi, &paths, 1070, true).is_none());
    }

    #[test]
    fn an_entry_that_cant_start_is_not_used_again() {
        let paths = Paths::new(temp());
        save(&paths, &Trip { created: 1000, entry: 4, monet: 1, method: Method::Once }).unwrap();
        let mut efi = pc(None, true);
        assert!(check_after_boot(&mut efi, &paths, 1060, true).unwrap().contains("Boot0004"));
        assert_eq!(bad_entries(&paths), vec![4]);
        // Once a trip works, the entry is trusted again.
        save(&paths, &Trip { created: 2000, entry: 4, monet: 1, method: Method::Once }).unwrap();
        let mut efi = pc(None, false);
        assert!(check_after_boot(&mut efi, &paths, 2060, true).is_none());
        assert!(bad_entries(&paths).is_empty());
    }

    #[test]
    fn a_windows_still_setting_up_is_not_blamed_and_monet_goes_first_again() {
        let paths = Paths::new(temp());
        save(&paths, &Trip { created: 1000, entry: 4, monet: 1, method: Method::First }).unwrap();
        let mut efi = pc(None, true);
        let notice = check_after_boot(&mut efi, &paths, 1060, false).unwrap();
        assert!(notice.contains("didn't finish"));
        assert!(bad_entries(&paths).is_empty());
        assert_eq!(boot::boot_order(&efi).unwrap(), vec![1, 4]);
    }

    #[test]
    fn dead_partitions_cant_start() {
        let dir = temp();
        fs::write(dir.join("0f0e0d0c-0b0a-0908-0706-050403020100"), "").unwrap();
        let entry = |guid: Option<&str>| BootEntry {
            number: 4,
            option: LoadOption {
                attributes: LOAD_OPTION_ACTIVE,
                description: "Windows Boot Manager".into(),
                file_path: None,
                partition_guid: guid.map(Into::into),
            },
        };
        assert_eq!(reach(&entry(Some("0F0E0D0C-0B0A-0908-0706-050403020100")), &[], &dir), Reach::Yes);
        assert_eq!(reach(&entry(Some("11111111-0000-0000-0000-000000000000")), &[], &dir), Reach::No);
        assert_eq!(reach(&entry(None), &[], &dir), Reach::Unknown);
        assert_eq!(reach(&entry(Some("0f0e0d0c-0b0a-0908-0706-050403020100")), &[4], &dir), Reach::No);
    }
}

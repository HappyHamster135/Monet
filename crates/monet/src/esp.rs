//! Reading the games list that Monet Bridge leaves on the EFI system partition.

use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;

use monet_core::games::{GameList, ESP_PATH};

const ESP_TYPE_GUID: &str = "c12a7328-f81f-11d2-ba4b-00a0c93ec93b";
const MOUNT_BASE: &str = "/run/monet";

/// Mount points of EFI partitions that are already mounted (for example
/// `/boot/efi`). Read straight from there instead of mounting again.
fn mounted_esps() -> Vec<(PathBuf, String)> {
    let Ok(info) = fs::read_to_string("/proc/self/mountinfo") else {
        return Vec::new();
    };
    let mut out = Vec::new();
    for line in info.lines() {
        // id parent major:minor root mount-point options ... - fstype source options
        let Some((left, right)) = line.split_once(" - ") else { continue };
        let mount_point = PathBuf::from(unescape_mount(left.split(' ').nth(4).unwrap_or("")));
        let mut right = right.split(' ');
        let fstype = right.next().unwrap_or("");
        let source = right.next().unwrap_or("");
        if fstype == "vfat" && mount_point.join("EFI").is_dir() {
            out.push((mount_point, unescape_mount(source)));
        }
    }
    out
}

/// mountinfo escapes spaces and a few other characters as octal (`\040`).
fn unescape_mount(s: &str) -> String {
    let bytes = s.as_bytes();
    let mut out = Vec::with_capacity(bytes.len());
    let mut i = 0;
    while i < bytes.len() {
        if bytes[i] == b'\\' && i + 3 < bytes.len() {
            if let Ok(v) = u8::from_str_radix(&s[i + 1..i + 4], 8) {
                out.push(v);
                i += 4;
                continue;
            }
        }
        out.push(bytes[i]);
        i += 1;
    }
    String::from_utf8_lossy(&out).into_owned()
}

/// Device paths of all EFI partitions, from lsblk.
fn esp_devices() -> Vec<String> {
    let Ok(out) = Command::new("lsblk").args(["-nrp", "-o", "PATH,PARTTYPE"]).output() else {
        return Vec::new();
    };
    String::from_utf8_lossy(&out.stdout)
        .lines()
        .filter_map(|line| {
            let (path, parttype) = line.split_once(' ')?;
            parttype.trim().eq_ignore_ascii_case(ESP_TYPE_GUID).then(|| path.to_string())
        })
        .collect()
}

fn read_list(root: &Path) -> Option<GameList> {
    let data = fs::read(root.join(ESP_PATH)).ok()?;
    GameList::parse(&data).ok()
}

/// Calls `visit` with the root folder and device of every EFI partition:
/// mounted ones where they are, the others mounted read-only for the call
/// and unmounted right after (that needs root).
fn each_esp(mut visit: impl FnMut(&Path, &str)) {
    let mounted = mounted_esps();
    for (mount_point, device) in &mounted {
        visit(mount_point, device);
    }

    for (i, device) in esp_devices().iter().enumerate() {
        if mounted.iter().any(|(_, source)| source == device) {
            continue;
        }
        let target = PathBuf::from(format!("{MOUNT_BASE}/esp{i}"));
        if fs::create_dir_all(&target).is_err() {
            continue;
        }
        let mounted_ok = Command::new("mount")
            .args(["-t", "vfat", "-o", "ro,nosuid,nodev,noexec"])
            .arg(device)
            .arg(&target)
            .status()
            .map(|s| s.success())
            .unwrap_or(false);
        if mounted_ok {
            visit(&target, device);
            let _ = Command::new("umount").arg(&target).status();
        }
        let _ = fs::remove_dir(&target);
    }
}

/// Finds the newest games list on any EFI partition.
pub fn find_games_list() -> Option<GameList> {
    let mut best: Option<GameList> = None;
    each_esp(|root, _| {
        if let Some(list) = read_list(root) {
            if best.as_ref().is_none_or(|b| list.updated > b.updated) {
                best = Some(list);
            }
        }
    });
    best
}

/// Windows' boot manager on an EFI partition (FAT doesn't care about case).
pub const WINDOWS_LOADER: &str = "EFI/Microsoft/Boot/bootmgfw.efi";

/// The device of an EFI partition that has Windows' boot manager on it.
pub fn find_windows_loader() -> Option<String> {
    let mut found = None;
    each_esp(|root, device| {
        if found.is_none() && root.join(WINDOWS_LOADER).is_file() {
            found = Some(device.to_string());
        }
    });
    found
}

/// The disk and partition number of a partition device, from sysfs:
/// `/dev/nvme0n1p1` is partition 1 of `/dev/nvme0n1`.
pub fn disk_and_partition(device: &str) -> Option<(String, u32)> {
    let name = Path::new(device).file_name()?.to_str()?;
    let sys = fs::canonicalize(format!("/sys/class/block/{name}")).ok()?;
    let number = fs::read_to_string(sys.join("partition")).ok()?.trim().parse().ok()?;
    let disk = sys.parent()?.file_name()?.to_str()?;
    Some((format!("/dev/{disk}"), number))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn unescapes_mountinfo() {
        assert_eq!(unescape_mount("/boot/efi"), "/boot/efi");
        assert_eq!(unescape_mount("/media/my\\040disk"), "/media/my disk");
    }
}

//! Prepares Windows from Monet, so Monet Bridge installs itself the first time
//! Windows starts. No download or installer needed in Windows.
//!
//! Monet copies the Bridge files to `C:\ProgramData\Monet\Setup` and puts a
//! small script in the all-users Startup folder. At the next sign-in, Windows
//! asks once for permission, installs Bridge, removes the script, and returns
//! to Monet.
//!
//! Windows' drive is only written when it is safely shut down: never when it
//! is hibernated, and never when it is encrypted with BitLocker.

use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;

pub const STATUS_FILE: &str = "windows-setup";

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Outcome {
    /// Setup files are in place; Bridge installs at the next Windows sign-in.
    Staged,
    /// Monet Bridge is already installed in Windows.
    Installed,
    /// No Windows installation was found.
    NotFound,
    /// Windows is encrypted with BitLocker, so Monet can't write to it.
    BitLocker,
    /// Windows is hibernated (or uses Fast Startup); writing could damage it.
    Hibernated,
    /// This copy of Monet doesn't include the Windows files.
    NoPayload,
    /// "Monet and Windows": Windows downloads after the first sign-in.
    Waiting,
    /// "Monet and Windows": Windows is downloading and getting ready.
    Preparing,
    /// "Monet and Windows": Windows installs itself at the next restart.
    Pending,
    /// "Monet and Windows": Microsoft's download didn't work.
    DownloadFailed,
    /// "Monet and Windows": there wasn't room on the disk.
    NoSpace,
    /// "Monet and Windows": something else went wrong; see the log.
    Failed,
}

impl Outcome {
    pub fn code(self) -> &'static str {
        match self {
            Outcome::Staged => "staged",
            Outcome::Installed => "installed",
            Outcome::NotFound => "not-found",
            Outcome::BitLocker => "bitlocker",
            Outcome::Hibernated => "hibernated",
            Outcome::NoPayload => "no-payload",
            Outcome::Waiting => "waiting",
            Outcome::Preparing => "preparing",
            Outcome::Pending => "pending",
            Outcome::DownloadFailed => "download-failed",
            Outcome::NoSpace => "no-space",
            Outcome::Failed => "failed",
        }
    }

    pub fn from_code(code: &str) -> Option<Outcome> {
        [
            Outcome::Staged,
            Outcome::Installed,
            Outcome::NotFound,
            Outcome::BitLocker,
            Outcome::Hibernated,
            Outcome::NoPayload,
            Outcome::Waiting,
            Outcome::Preparing,
            Outcome::Pending,
            Outcome::DownloadFailed,
            Outcome::NoSpace,
            Outcome::Failed,
        ]
        .into_iter()
        .find(|o| o.code() == code.trim())
    }

    /// True when nothing more needs to happen on the Linux side.
    pub fn is_done(self) -> bool {
        matches!(self, Outcome::Staged | Outcome::Installed)
    }

    /// True for the "Monet and Windows" states, where Monet installs Windows
    /// itself instead of preparing an existing one.
    pub fn is_fresh_install(self) -> bool {
        matches!(
            self,
            Outcome::Waiting | Outcome::Preparing | Outcome::Pending | Outcome::DownloadFailed | Outcome::NoSpace | Outcome::Failed
        )
    }
}

const STARTUP_SCRIPT: &str = "Finish Monet setup.cmd";

/// Files that make up the Windows payload.
const PAYLOAD: &[&str] = &[
    "monet-bridge.exe",
    "Install-Monet.ps1",
    "Uninstall-Monet.ps1",
    "GameProfile.ps1",
    "Update-Monet.ps1",
    "Update-Windows.ps1",
    "Install-Launcher.ps1",
    "monet.ico",
    // The cover Monet Bridge puts over Windows on a trip. (Not the desktop's painting: a
    // Windows kept from before keeps its own.)
    "cover.jpg",
    "monet-mark.png",
    "Fraunces-Light.ttf",
    "Fraunces-Regular.ttf",
    "OFL-Fraunces.txt",
];

/// Where this copy of Monet keeps its helper scripts.
pub fn libexec_dir() -> Option<PathBuf> {
    let exe = std::env::current_exe().ok()?;
    let from_exe = exe.parent()?.parent()?.join("libexec");
    [from_exe, PathBuf::from("/usr/libexec"), PathBuf::from("/usr/local/libexec")]
        .into_iter()
        .find(|d| d.join("monet-prepare-windows").is_file())
}

/// Monet's shared data folder (`share/monet`).
pub fn share_dir() -> Option<PathBuf> {
    let exe = std::env::current_exe().ok()?;
    let from_exe = exe.parent()?.parent()?.join("share/monet");
    [from_exe, PathBuf::from("/usr/share/monet"), PathBuf::from("/usr/local/share/monet")]
        .into_iter()
        .find(|d| d.is_dir())
}

/// Where this copy of Monet keeps the Windows files.
pub fn payload_dir() -> Option<PathBuf> {
    let exe = std::env::current_exe().ok()?;
    let from_exe = exe.parent()?.parent()?.join("share/monet/windows");
    [from_exe, PathBuf::from("/usr/share/monet/windows"), PathBuf::from("/usr/local/share/monet/windows")]
        .into_iter()
        .find(|d| d.join("monet-bridge.exe").is_file())
}

/// Finds `rel` under `root` ignoring letter case, as Windows does. With
/// `create`, missing folders are created (with the given spelling).
pub fn resolve(root: &Path, rel: &[&str], create: bool) -> Option<PathBuf> {
    let mut path = root.to_path_buf();
    for part in rel {
        let found = fs::read_dir(&path).ok().and_then(|entries| {
            entries
                .flatten()
                .find(|e| e.file_name().to_string_lossy().eq_ignore_ascii_case(part))
                .map(|e| e.path())
        });
        path = match found {
            Some(p) => p,
            None if create => {
                let p = path.join(part);
                fs::create_dir(&p).ok()?;
                p
            }
            None => return None,
        };
    }
    Some(path)
}

pub fn is_windows_root(root: &Path) -> bool {
    resolve(root, &["Windows", "System32"], false).is_some_and(|p| p.is_dir())
}

/// Windows writes "hibr" at the start of hiberfil.sys while it is hibernated,
/// including the hybrid shutdown that Fast Startup uses.
pub fn is_hibernated(root: &Path) -> bool {
    let Some(file) = resolve(root, &["hiberfil.sys"], false) else { return false };
    let mut magic = [0u8; 4];
    match fs::File::open(file).and_then(|mut f| std::io::Read::read_exact(&mut f, &mut magic)) {
        Ok(()) => magic.eq_ignore_ascii_case(b"hibr"),
        Err(_) => false,
    }
}

pub fn bridge_installed(root: &Path) -> bool {
    resolve(root, &["Program Files", "Monet", "monet-bridge.exe"], false).is_some()
}

/// Copies the payload into a mounted, writable Windows drive.
pub fn stage_into(root: &Path, payload: &Path) -> Result<Outcome, String> {
    if bridge_installed(root) {
        return Ok(Outcome::Installed);
    }
    let setup = resolve(root, &["ProgramData", "Monet", "Setup"], true).ok_or("couldn't create the setup folder")?;
    for name in PAYLOAD {
        let from = payload.join(name);
        if from.is_file() {
            fs::copy(&from, setup.join(name)).map_err(|e| format!("couldn't copy {name}: {e}"))?;
        }
    }
    let startup = resolve(
        root,
        &["ProgramData", "Microsoft", "Windows", "Start Menu", "Programs", "StartUp"],
        true,
    )
    .ok_or("couldn't find the Windows Startup folder")?;
    let script = "@echo off\r\n\
        rem Added by Monet. Installs Monet Bridge once, then removes itself.\r\n\
        start \"\" /min powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden \
        -File \"%ProgramData%\\Monet\\Setup\\Install-Monet.ps1\" -FromMonet\r\n";
    fs::write(startup.join(STARTUP_SCRIPT), script).map_err(|e| format!("couldn't add the setup script: {e}"))?;
    Ok(Outcome::Staged)
}

// ------------------------------------------------------------- finding Windows

struct Volume {
    device: String,
    fstype: String,
}

fn volumes() -> Vec<Volume> {
    let Ok(out) = Command::new("lsblk").args(["-nrp", "-o", "PATH,FSTYPE"]).output() else {
        return Vec::new();
    };
    String::from_utf8_lossy(&out.stdout)
        .lines()
        .filter_map(|line| {
            let (device, fstype) = line.split_once(' ')?;
            Some(Volume { device: device.to_string(), fstype: fstype.trim().to_lowercase() })
        })
        .collect()
}

const MOUNT_POINT: &str = "/run/monet/windows";

fn mount(device: &str, writable: bool) -> bool {
    let _ = fs::create_dir_all(MOUNT_POINT);
    let options = if writable { "rw,nosuid,nodev,noexec" } else { "ro,nosuid,nodev,noexec" };
    ["ntfs3", "ntfs-3g", "ntfs"].iter().any(|fstype| {
        Command::new("mount")
            .args(["-t", fstype, "-o", options, device, MOUNT_POINT])
            .stderr(std::process::Stdio::null())
            .status()
            .map(|s| s.success())
            .unwrap_or(false)
    })
}

fn unmount() {
    let _ = Command::new("sync").status();
    let _ = Command::new("umount").arg(MOUNT_POINT).status();
}

/// Finds Windows and prepares it. Needs root.
pub fn stage(payload: Option<&Path>) -> Result<Outcome, String> {
    let Some(payload) = payload else { return Ok(Outcome::NoPayload) };
    let vols = volumes();
    let mut saw_bitlocker = false;
    let mut result = Ok(Outcome::NotFound);

    for vol in &vols {
        if vol.fstype == "bitlocker" {
            saw_bitlocker = true;
            continue;
        }
        if vol.fstype != "ntfs" || !mount(&vol.device, false) {
            continue;
        }
        let root = Path::new(MOUNT_POINT);
        if !is_windows_root(root) {
            unmount();
            continue;
        }
        if bridge_installed(root) {
            unmount();
            return Ok(Outcome::Installed);
        }
        if is_hibernated(root) {
            unmount();
            result = Ok(Outcome::Hibernated);
            continue;
        }
        unmount();
        if !mount(&vol.device, true) {
            result = Err("Windows' drive couldn't be opened for writing".into());
            continue;
        }
        let staged = stage_into(Path::new(MOUNT_POINT), payload);
        unmount();
        return staged;
    }

    match result {
        Ok(Outcome::NotFound) if saw_bitlocker => Ok(Outcome::BitLocker),
        other => other,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn temp(name: &str) -> PathBuf {
        let dir = std::env::temp_dir().join(format!("monet-test-{name}-{}", std::process::id()));
        let _ = fs::remove_dir_all(&dir);
        fs::create_dir_all(&dir).unwrap();
        dir
    }

    fn fake_windows(name: &str) -> PathBuf {
        let root = temp(name);
        fs::create_dir_all(root.join("Windows/System32")).unwrap();
        fs::create_dir_all(root.join("ProgramData/Microsoft/Windows/Start Menu/Programs/StartUp")).unwrap();
        root
    }

    fn fake_payload(name: &str) -> PathBuf {
        let dir = temp(name);
        for f in PAYLOAD {
            fs::write(dir.join(f), f.as_bytes()).unwrap();
        }
        dir
    }

    #[test]
    fn resolves_ignoring_case() {
        let root = fake_windows("case");
        assert!(resolve(&root, &["WINDOWS", "system32"], false).is_some());
        assert!(resolve(&root, &["nope"], false).is_none());
        let made = resolve(&root, &["programdata", "Monet", "Setup"], true).unwrap();
        assert_eq!(made, root.join("ProgramData/Monet/Setup"));
        assert!(is_windows_root(&root));
    }

    #[test]
    fn detects_hibernation() {
        let root = fake_windows("hiber");
        assert!(!is_hibernated(&root));
        fs::write(root.join("hiberfil.sys"), b"\0\0\0\0rest").unwrap();
        assert!(!is_hibernated(&root));
        fs::write(root.join("hiberfil.sys"), b"HIBRrest").unwrap();
        assert!(is_hibernated(&root));
    }

    #[test]
    fn stages_payload_and_startup_script() {
        let root = fake_windows("stage");
        let payload = fake_payload("payload");
        assert_eq!(stage_into(&root, &payload).unwrap(), Outcome::Staged);
        assert!(root.join("ProgramData/Monet/Setup/monet-bridge.exe").is_file());
        let script = fs::read_to_string(
            root.join("ProgramData/Microsoft/Windows/Start Menu/Programs/StartUp").join(STARTUP_SCRIPT),
        )
        .unwrap();
        assert!(script.contains("Install-Monet.ps1\" -FromMonet\r\n"));

        fs::create_dir_all(root.join("Program Files/Monet")).unwrap();
        fs::write(root.join("Program Files/Monet/monet-bridge.exe"), b"x").unwrap();
        assert_eq!(stage_into(&root, &payload).unwrap(), Outcome::Installed);
    }

    #[test]
    fn status_codes_round_trip() {
        for o in [Outcome::Staged, Outcome::BitLocker, Outcome::Hibernated, Outcome::NoPayload, Outcome::Waiting, Outcome::DownloadFailed] {
            assert_eq!(Outcome::from_code(o.code()), Some(o));
        }
        assert_eq!(Outcome::from_code("staged\n"), Some(Outcome::Staged));
    }
}

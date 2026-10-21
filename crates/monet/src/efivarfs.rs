//! UEFI variables through Linux efivarfs (`/sys/firmware/efi/efivars`).
//!
//! Each variable is a file named `Name-guid` holding 4 bytes of attributes
//! followed by the data. Most files are marked immutable by the kernel, so
//! that flag is cleared before writing or deleting, the same way efivar and
//! efibootmgr do it.

use std::fs::{self, File, OpenOptions};
use std::io::{ErrorKind, Read, Write};
use std::os::unix::io::AsRawFd;
use std::path::{Path, PathBuf};

use monet_core::efi::{self, EfiError, EfiVars, Result, GLOBAL_GUID};

pub const DEFAULT_DIR: &str = "/sys/firmware/efi/efivars";

const FS_IMMUTABLE_FL: libc::c_long = 0x10;
const FS_IOC_GETFLAGS: libc::c_ulong = 0x8008_6601;
const FS_IOC_SETFLAGS: libc::c_ulong = 0x4008_6602;

pub struct EfiVarFs {
    dir: PathBuf,
    /// False when pointed at a plain directory for testing.
    real: bool,
}

impl EfiVarFs {
    /// Uses `MONET_EFIVARS_DIR` if set (for tests), else the real efivarfs.
    pub fn open() -> Result<Self> {
        let (dir, real) = match std::env::var_os("MONET_EFIVARS_DIR") {
            Some(dir) => (PathBuf::from(dir), false),
            None => (PathBuf::from(DEFAULT_DIR), true),
        };
        if !dir.is_dir() {
            return Err(EfiError::Unsupported);
        }
        Ok(EfiVarFs { dir, real })
    }

    fn path(&self, guid: &str, name: &str) -> PathBuf {
        self.dir.join(format!("{name}-{guid}"))
    }
}

fn map_io(e: std::io::Error) -> EfiError {
    match e.kind() {
        ErrorKind::NotFound => EfiError::NotFound,
        ErrorKind::PermissionDenied => EfiError::PermissionDenied,
        _ => EfiError::Io(e.to_string()),
    }
}

/// Clears the immutable flag. Ignored on file systems without flags (tests).
fn make_mutable(file: &File) -> Result<()> {
    let fd = file.as_raw_fd();
    let mut flags: libc::c_long = 0;
    // SAFETY: plain ioctls on a valid fd with a pointer to a local integer.
    unsafe {
        if libc::ioctl(fd, FS_IOC_GETFLAGS as _, &mut flags) != 0 {
            return Ok(());
        }
        if flags & FS_IMMUTABLE_FL == 0 {
            return Ok(());
        }
        flags &= !FS_IMMUTABLE_FL;
        if libc::ioctl(fd, FS_IOC_SETFLAGS as _, &flags) != 0 {
            return Err(map_io(std::io::Error::last_os_error()));
        }
    }
    Ok(())
}

fn make_path_mutable(path: &Path) -> Result<()> {
    match File::open(path) {
        Ok(file) => make_mutable(&file),
        Err(e) if e.kind() == ErrorKind::NotFound => Ok(()),
        Err(e) => Err(map_io(e)),
    }
}

impl EfiVars for EfiVarFs {
    fn get(&self, guid: &str, name: &str) -> Result<Vec<u8>> {
        let mut data = Vec::new();
        File::open(self.path(guid, name))
            .and_then(|mut f| f.read_to_end(&mut data))
            .map_err(map_io)?;
        if data.len() < 4 {
            return Err(EfiError::Invalid(format!("{name} is too short")));
        }
        Ok(data.split_off(4))
    }

    fn set(&mut self, guid: &str, name: &str, data: &[u8], attributes: u32) -> Result<()> {
        let path = self.path(guid, name);
        make_path_mutable(&path)?;
        if !self.real {
            // efivarfs replaces the whole value on write; a plain file needs truncating.
            let _ = fs::remove_file(&path);
        }
        let mut file = OpenOptions::new()
            .write(true)
            .create(true)
            .truncate(false)
            .open(&path)
            .map_err(map_io)?;
        // New variables in a vendor namespace are created immutable too.
        make_mutable(&file)?;
        let mut buf = attributes.to_le_bytes().to_vec();
        buf.extend_from_slice(data);
        // efivarfs needs the whole variable in one write call.
        let written = file.write(&buf).map_err(map_io)?;
        if written != buf.len() {
            return Err(EfiError::Io(format!("short write to {name}")));
        }
        Ok(())
    }

    fn delete(&mut self, guid: &str, name: &str) -> Result<()> {
        let path = self.path(guid, name);
        make_path_mutable(&path)?;
        fs::remove_file(path).map_err(map_io)
    }

    fn boot_entry_numbers(&self) -> Result<Vec<u16>> {
        let suffix = format!("-{GLOBAL_GUID}");
        let mut numbers: Vec<u16> = fs::read_dir(&self.dir)
            .map_err(map_io)?
            .filter_map(|e| e.ok())
            .filter_map(|e| {
                let name = e.file_name().into_string().ok()?;
                efi::parse_boot_var_name(name.strip_suffix(&suffix)?)
            })
            .collect();
        numbers.sort_unstable();
        Ok(numbers)
    }
}

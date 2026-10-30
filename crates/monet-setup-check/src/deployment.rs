//! A recorded, monotonic installation. Formatting is deliberately not an operation here.
use crate::{guid, Manifest};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::HashSet;
use std::fs::{self, File, OpenOptions};
use std::io::{Read, Seek, Write};
use std::path::{Path, PathBuf};

pub const CHECKPOINT: &str = ".monet-setup.json";
pub const MAX_JOB_BYTES: u64 = 1024 * 1024;

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Payload {
    pub path: String,
    pub size: u64,
    pub sha256: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Job {
    pub version: u32,
    pub id: String,
    pub partitions: Manifest,
    pub files: Vec<Payload>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Phase {
    Applying,
    Applied,
    Complete,
}

#[derive(Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Checkpoint {
    pub version: u32,
    pub job_id: String,
    pub manifest_sha256: String,
    pub phase: Phase,
}

pub fn digest(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
}

fn relative(name: &str) -> bool {
    !name.is_empty()
        && name.len() < 240
        && name.is_ascii()
        && name.split('/').all(|part| {
            !part.is_empty()
                && part != "."
                && part != ".."
                && !part.ends_with(['.', ' '])
                && part
                    .bytes()
                    .all(|b| b.is_ascii_alphanumeric() || b"._- ()".contains(&b))
                && ![
                    "CON", "PRN", "AUX", "NUL", "COM1", "COM2", "COM3", "COM4", "COM5", "COM6",
                    "COM7", "COM8", "COM9", "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7",
                    "LPT8", "LPT9",
                ]
                .contains(
                    &part
                        .split('.')
                        .next()
                        .unwrap_or("")
                        .to_ascii_uppercase()
                        .as_str(),
                )
        })
}

pub fn read_small(path: &Path, limit: u64) -> Result<Vec<u8>, String> {
    let mut data = Vec::new();
    File::open(path)
        .map_err(|e| e.to_string())?
        .take(limit + 1)
        .read_to_end(&mut data)
        .map_err(|e| e.to_string())?;
    if data.len() as u64 > limit {
        return Err("The installation record is too large.".into());
    }
    Ok(data)
}

impl Job {
    pub fn parse(data: &[u8]) -> Result<Self, String> {
        if data.len() as u64 > MAX_JOB_BYTES {
            return Err("The installation record is too large.".into());
        }
        let job: Self = serde_json::from_slice(data)
            .map_err(|e| format!("Invalid installation record: {e}"))?;
        job.validate()?;
        Ok(job)
    }

    pub fn validate(&self) -> Result<(), String> {
        self.partitions.validate()?;
        if self.version != 1
            || guid(&self.id).is_none()
            || self.files.is_empty()
            || self.files.len() > 1024
        {
            return Err("Invalid installation job identity or file list.".into());
        }
        let mut names = HashSet::new();
        for file in &self.files {
            let name = file.path.to_ascii_lowercase();
            if !relative(&file.path)
                || !names.insert(name)
                || file.size > u32::MAX as u64
                || file.sha256.len() != 64
                || !file.sha256.bytes().all(|b| b.is_ascii_hexdigit())
            {
                return Err("Invalid or ambiguous installation payload.".into());
            }
        }
        for required in [
            "sources/install.swm",
            "monet/unattend.xml",
            "monet/bridge/monet-bridge.exe",
            "monet/bridge/install-monet.ps1",
        ] {
            if !names.contains(required) {
                return Err(format!("Missing installation file: {required}"));
            }
        }
        Ok(())
    }
}

fn no_redirect(path: &Path) -> Result<(), String> {
    match fs::symlink_metadata(path) {
        Err(error) if error.kind() != std::io::ErrorKind::NotFound => return Err(error.to_string()),
        _ => {}
    }
    if let Ok(info) = fs::symlink_metadata(path) {
        #[cfg(windows)]
        {
            use std::os::windows::fs::MetadataExt;
            if info.file_attributes() & 0x400 != 0 {
                return Err("An installation path is a reparse point.".into());
            }
        }
        if info.file_type().is_symlink() {
            return Err("An installation path is a symbolic link.".into());
        }
    }
    Ok(())
}

pub fn checked_path(root: &Path, rel: &str) -> Result<PathBuf, String> {
    if !relative(rel) {
        return Err("Unsafe installation path.".into());
    }
    let mut path = root.to_owned();
    no_redirect(&path)?;
    for part in rel.split('/') {
        path.push(part);
        no_redirect(&path)?;
    }
    Ok(path)
}

struct Verified {
    path: String,
    file: File,
}

fn payload(job: &Job, setup: &Path) -> Result<Vec<Verified>, String> {
    let mut held = Vec::new();
    for item in &job.files {
        let path = checked_path(setup, &item.path)?;
        let mut options = OpenOptions::new();
        options.read(true);
        // Keep every verified input open without write/delete sharing until DISM and copies finish.
        #[cfg(windows)]
        {
            use std::os::windows::fs::OpenOptionsExt;
            options.share_mode(windows_sys::Win32::Storage::FileSystem::FILE_SHARE_READ);
        }
        let mut file = options
            .open(path)
            .map_err(|e| format!("Cannot read {}: {e}", item.path))?;
        if !file.metadata().map_err(|e| e.to_string())?.is_file()
            || file.metadata().map_err(|e| e.to_string())?.len() != item.size
        {
            return Err(format!("The size of {} changed.", item.path));
        }
        let mut hash = Sha256::new();
        let mut buffer = vec![0u8; 1024 * 1024];
        loop {
            let count = file.read(&mut buffer).map_err(|e| e.to_string())?;
            if count == 0 {
                break;
            }
            hash.update(&buffer[..count]);
        }
        if format!("{:x}", hash.finalize()) != item.sha256.to_ascii_lowercase() {
            return Err(format!("The checksum of {} changed.", item.path));
        }
        file.rewind().map_err(|e| e.to_string())?;
        held.push(Verified {
            path: item.path.clone(),
            file,
        });
    }
    // DISM expands install*.swm itself. Never let an unverified extra split join that set.
    for entry in fs::read_dir(setup.join("sources")).map_err(|e| e.to_string())? {
        let name = entry
            .map_err(|e| e.to_string())?
            .file_name()
            .to_string_lossy()
            .to_ascii_lowercase();
        if name.starts_with("install")
            && name.ends_with(".swm")
            && !job
                .files
                .iter()
                .any(|p| p.path.eq_ignore_ascii_case(&format!("sources/{name}")))
        {
            return Err("An unverified split image was added to Windows Setup.".into());
        }
    }
    Ok(held)
}

pub fn save_checkpoint(root: &Path, value: &Checkpoint) -> Result<(), String> {
    let bytes = serde_json::to_vec(value).map_err(|e| e.to_string())?;
    write_atomic(root, CHECKPOINT, &bytes)
}

pub fn write_atomic(root: &Path, name: &str, bytes: &[u8]) -> Result<(), String> {
    let final_path = checked_path(root, name)?;
    let temporary_name = if name == CHECKPOINT {
        ".monet-setup.next".to_owned()
    } else {
        format!("{name}.next")
    };
    let temporary = checked_path(root, &temporary_name)?;
    let mut file = OpenOptions::new()
        .write(true)
        .create(true)
        .truncate(true)
        .open(&temporary)
        .map_err(|e| e.to_string())?;
    file.write_all(bytes)
        .and_then(|_| file.sync_all())
        .map_err(|e| e.to_string())?;
    drop(file);
    #[cfg(windows)]
    {
        use std::os::windows::ffi::OsStrExt;
        use windows_sys::Win32::Storage::FileSystem::{
            MoveFileExW, MOVEFILE_REPLACE_EXISTING, MOVEFILE_WRITE_THROUGH,
        };
        let from: Vec<_> = temporary.as_os_str().encode_wide().chain(Some(0)).collect();
        let to: Vec<_> = final_path
            .as_os_str()
            .encode_wide()
            .chain(Some(0))
            .collect();
        if unsafe {
            MoveFileExW(
                from.as_ptr(),
                to.as_ptr(),
                MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH,
            )
        } == 0
        {
            return Err(std::io::Error::last_os_error().to_string());
        }
    }
    #[cfg(not(windows))]
    {
        fs::rename(&temporary, &final_path)
            .and_then(|_| File::open(root)?.sync_all())
            .map_err(|e| e.to_string())?;
    }
    Ok(())
}

fn checkpoint(job: &Job, hash: &str, root: &Path) -> Result<Option<Phase>, String> {
    let path = checked_path(root, CHECKPOINT)?;
    if !path.try_exists().map_err(|e| e.to_string())? {
        return Ok(None);
    }
    let saved: Checkpoint = serde_json::from_slice(&read_small(&path, 4096)?)
        .map_err(|e| format!("Damaged installation checkpoint: {e}"))?;
    if saved.version != 1 || saved.job_id != job.id || saved.manifest_sha256 != hash {
        return Err(
            "The Windows installation checkpoint belongs to a different preparation.".into(),
        );
    }
    Ok(Some(saved.phase))
}

pub trait Backend {
    /// Check current native identities and letters before each mutation, never cached discovery.
    fn recheck(&mut self) -> Result<(), String>;
    fn apply(&mut self, setup: &Path, target: &Path) -> Result<(), String>;
    fn boot(&mut self, target: &Path) -> Result<(), String>;
}

pub fn deploy(
    data: &[u8],
    setup: &Path,
    target: &Path,
    backend: &mut impl Backend,
) -> Result<(), String> {
    let job = Job::parse(data)?;
    let hash = digest(data);
    backend.recheck()?;
    let mut phase = checkpoint(&job, &hash, target)?;
    if phase == Some(Phase::Complete) {
        if !checked_path(target, "Windows/System32/winload.efi")?.is_file() {
            return Err("The completed Windows installation is missing its boot loader.".into());
        }
        return Ok(());
    }
    let mut held = payload(&job, setup)?;
    if phase.is_none() {
        for entry in fs::read_dir(target).map_err(|e| e.to_string())? {
            let name = entry
                .map_err(|e| e.to_string())?
                .file_name()
                .to_string_lossy()
                .to_ascii_lowercase();
            if ![
                "system volume information",
                "$recycle.bin",
                ".monet-setup.next",
            ]
            .contains(&name.as_str())
            {
                return Err(
                    "The Windows target is not empty and has no matching installation checkpoint."
                        .into(),
                );
            }
        }
        backend.recheck()?;
        save_checkpoint(
            target,
            &Checkpoint {
                version: 1,
                job_id: job.id.clone(),
                manifest_sha256: hash.clone(),
                phase: Phase::Applying,
            },
        )?;
        phase = Some(Phase::Applying);
    }
    if phase == Some(Phase::Applying) {
        backend.recheck()?;
        backend.apply(setup, target)?;
        backend.recheck()?;
        if !checked_path(target, "Windows/System32/winload.efi")?.is_file() {
            return Err("Windows image application did not produce its boot loader.".into());
        }
        // This durable phase is written BEFORE enabling any boot path. All retries after it skip DISM.
        save_checkpoint(
            target,
            &Checkpoint {
                version: 1,
                job_id: job.id.clone(),
                manifest_sha256: hash.clone(),
                phase: Phase::Applied,
            },
        )?;
    }
    backend.recheck()?;
    for item in &mut held {
        let rel = if item.path.eq_ignore_ascii_case("monet/unattend.xml") {
            "Windows/Panther/unattend.xml".to_owned()
        } else if item.path.to_ascii_lowercase().starts_with("monet/bridge/") {
            format!("ProgramData/Monet/Setup/{}", &item.path[13..])
        } else {
            continue;
        };
        let dest = checked_path(target, &rel)?;
        fs::create_dir_all(dest.parent().unwrap()).map_err(|e| e.to_string())?;
        let mut output = File::create(dest).map_err(|e| e.to_string())?;
        std::io::copy(&mut item.file, &mut output)
            .and_then(|_| output.sync_all())
            .map_err(|e| e.to_string())?;
    }
    backend.recheck()?;
    backend.boot(target)?;
    backend.recheck()?;
    save_checkpoint(
        target,
        &Checkpoint {
            version: 1,
            job_id: job.id,
            manifest_sha256: hash,
            phase: Phase::Complete,
        },
    )
}

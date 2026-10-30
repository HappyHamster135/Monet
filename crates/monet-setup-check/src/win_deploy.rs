//! WinPE adapter. Disk selection is always delegated to the read-only native inventory.
use crate::native;
use monet_setup_check::{
    deployment::{self, Backend, Job},
    select, Selection,
};
use std::fs::{self, OpenOptions};
use std::io::Write;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use windows_sys::Win32::Storage::FileSystem::GetLogicalDrives;
use windows_sys::Win32::System::Registry::{
    RegCloseKey, RegOpenKeyExW, HKEY_LOCAL_MACHINE, KEY_READ,
};
use windows_sys::Win32::System::SystemInformation::GetSystemDirectoryW;

fn system_dir() -> Result<PathBuf, String> {
    let mut buffer = vec![0u16; 32768];
    let len = unsafe { GetSystemDirectoryW(buffer.as_mut_ptr(), buffer.len() as u32) } as usize;
    if len == 0 || len >= buffer.len() {
        return Err("Windows' system directory is unavailable.".into());
    }
    Ok(PathBuf::from(
        String::from_utf16(&buffer[..len]).map_err(|e| e.to_string())?,
    ))
}

fn winpe_only() -> Result<(), String> {
    let key: Vec<_> = r"SYSTEM\CurrentControlSet\Control\MiniNT"
        .encode_utf16()
        .chain(Some(0))
        .collect();
    let mut handle = std::ptr::null_mut();
    let status =
        unsafe { RegOpenKeyExW(HKEY_LOCAL_MACHINE, key.as_ptr(), 0, KEY_READ, &mut handle) };
    if status != 0 {
        return Err("Deployment can only run inside Windows PE.".into());
    }
    unsafe {
        RegCloseKey(handle);
    }
    Ok(())
}

fn discover(job: &Job) -> Result<Selection, String> {
    let m = &job.partitions;
    let volumes = native::volumes(&m.disk_guid, &m.efi.guid).map_err(|e| e.to_string())?;
    let setup = volumes
        .iter()
        .find(|v| {
            v.disk_guid.eq_ignore_ascii_case(&m.disk_guid)
                && v.partition_guid.eq_ignore_ascii_case(&m.setup.guid)
        })
        .and_then(|v| v.letters.iter().copied().find(|c| *c != 'X'))
        .ok_or("The recorded setup volume has no usable drive letter.")?;
    select(m, setup, &volumes)
}

struct WinPe {
    job: Job,
    chosen: Selection,
    system: PathBuf,
}
impl WinPe {
    fn command(&self, name: &str, args: &[String]) -> Result<(), String> {
        let status = Command::new(self.system.join(name))
            .args(args)
            .stdin(Stdio::null())
            .status()
            .map_err(|e| e.to_string())?;
        if !status.success() {
            return Err(format!(
                "{name} stopped with {status}. Setup can be retried from Monet."
            ));
        }
        Ok(())
    }

    fn efi_letter(&self) -> Result<Option<char>, String> {
        let m = &self.job.partitions;
        let volumes = native::volumes(&m.disk_guid, &m.efi.guid).map_err(|e| e.to_string())?;
        select(m, self.chosen.setup, &volumes)?;
        Ok(volumes
            .iter()
            .find(|v| {
                v.disk_guid.eq_ignore_ascii_case(&m.disk_guid)
                    && v.partition_guid.eq_ignore_ascii_case(&m.efi.guid)
            })
            .and_then(|v| v.letters.iter().copied().find(|c| *c != 'X')))
    }

    fn mount_efi(&mut self) -> Result<char, String> {
        self.recheck()?;
        if let Some(letter) = self.efi_letter()? {
            return Ok(letter);
        }
        let mask = unsafe { GetLogicalDrives() };
        if mask == 0 {
            return Err("Cannot establish an unused drive letter for EFI.".into());
        }
        let letter = ('D'..='Z')
            .rev()
            .find(|c| *c != 'X' && mask & (1 << (*c as u8 - b'A')) == 0)
            .ok_or("No free drive letter is available for the shared EFI partition.")?;
        let script = std::env::current_exe()
            .map_err(|e| e.to_string())?
            .with_file_name(format!("efi-{}.txt", std::process::id()));
        let mut file = OpenOptions::new()
            .write(true)
            .create_new(true)
            .open(&script)
            .map_err(|e| e.to_string())?;
        write!(
            file,
            "select disk {}\r\nselect partition {}\r\nassign letter={}\r\nexit\r\n",
            self.chosen.efi_disk, self.chosen.efi_partition, letter
        )
        .and_then(|_| file.sync_all())
        .map_err(|e| e.to_string())?;
        drop(file);
        let result = self.command(
            "diskpart.exe",
            &["/s".into(), script.to_string_lossy().into_owned()],
        );
        let _ = fs::remove_file(script);
        result?;
        self.recheck()?;
        if self.efi_letter()? != Some(letter) {
            return Err("The assigned EFI letter does not match the recorded partition.".into());
        }
        Ok(letter)
    }
}

impl Backend for WinPe {
    fn recheck(&mut self) -> Result<(), String> {
        if discover(&self.job)? != self.chosen {
            return Err("Disk identities or drive letters changed during setup; restart to inspect them again.".into());
        }
        Ok(())
    }
    fn apply(&mut self, setup: &Path, target: &Path) -> Result<(), String> {
        println!("Applying the verified Windows image...");
        self.command(
            "dism.exe",
            &[
                "/Apply-Image".into(),
                format!("/ImageFile:{}", setup.join("sources/install.swm").display()),
                format!("/SWMFile:{}", setup.join("sources/install*.swm").display()),
                "/Index:1".into(),
                format!("/ApplyDir:{}", target.display()),
                "/CheckIntegrity".into(),
                "/Verify".into(),
            ],
        )
    }
    fn boot(&mut self, target: &Path) -> Result<(), String> {
        let letter = self.mount_efi()?;
        let efi = PathBuf::from(format!("{letter}:\\"));
        let fallback = deployment::checked_path(&efi, "EFI/Boot/bootx64.efi")?;
        // BCDBoot /s can replace the fallback loader. Preserve Monet's existing one across retries.
        let backup = deployment::checked_path(target, &format!(".monet-boot-{}.efi", self.job.id))?;
        let record_name = format!(".monet-boot-{}.json", self.job.id);
        let record = deployment::checked_path(target, &record_name)?;
        let saved: Option<String> = if record.try_exists().map_err(|e| e.to_string())? {
            serde_json::from_slice(&deployment::read_small(&record, 4096)?)
                .map_err(|e| e.to_string())?
        } else {
            let saved = if fallback.try_exists().map_err(|e| e.to_string())? {
                fs::copy(&fallback, &backup).map_err(|e| e.to_string())?;
                OpenOptions::new()
                    .write(true)
                    .open(&backup)
                    .and_then(|f| f.sync_all())
                    .map_err(|e| e.to_string())?;
                Some(deployment::digest(&deployment::read_small(
                    &backup,
                    32 * 1024 * 1024,
                )?))
            } else {
                None
            };
            deployment::write_atomic(
                target,
                &record_name,
                &serde_json::to_vec(&saved).map_err(|e| e.to_string())?,
            )?;
            saved
        };
        if let Some(hash) = &saved {
            if deployment::digest(&deployment::read_small(&backup, 32 * 1024 * 1024)?) != *hash {
                return Err(
                    "The original EFI fallback backup changed; refusing to overwrite it.".into(),
                );
            }
        }
        self.recheck()?;
        let boot = self.command(
            "bcdboot.exe",
            &[
                target.join("Windows").to_string_lossy().into_owned(),
                "/s".into(),
                format!("{letter}:"),
                "/f".into(),
                "UEFI".into(),
            ],
        );
        self.recheck()?;
        if saved.is_some() {
            fs::copy(backup, &fallback).map_err(|e| e.to_string())?;
            OpenOptions::new()
                .write(true)
                .open(&fallback)
                .and_then(|f| f.sync_all())
                .map_err(|e| e.to_string())?;
        }
        boot?;
        if !efi.join("EFI/Microsoft/Boot/bootmgfw.efi").is_file() {
            return Err(
                "Windows' EFI boot loader was not installed on the recorded partition.".into(),
            );
        }
        Ok(())
    }
}

pub fn run(path: &Path) -> Result<(), String> {
    winpe_only()?;
    let data = deployment::read_small(path, deployment::MAX_JOB_BYTES)?;
    let job = Job::parse(&data)?;
    let chosen = discover(&job)?;
    let setup = PathBuf::from(format!("{}:\\", chosen.setup));
    let target = PathBuf::from(format!("{}:\\", chosen.windows));
    let mut host = WinPe {
        job,
        chosen,
        system: system_dir()?,
    };
    deployment::deploy(&data, &setup, &target, &mut host)
}

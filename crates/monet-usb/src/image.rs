//! Keep one read-only image handle from validation through verification.
use std::fs::{File, OpenOptions};
use std::io::{Read, Seek};
use std::os::windows::fs::OpenOptionsExt;
use std::ptr::{null, null_mut};
use windows_sys::Win32::Security::Cryptography::*;
use windows_sys::Win32::Storage::FileSystem::FILE_SHARE_READ;

struct Hash {
    algorithm: BCRYPT_ALG_HANDLE,
    hash: BCRYPT_HASH_HANDLE,
}
impl Drop for Hash {
    fn drop(&mut self) {
        unsafe {
            if !self.hash.is_null() {
                BCryptDestroyHash(self.hash);
            }
            if !self.algorithm.is_null() {
                BCryptCloseAlgorithmProvider(self.algorithm, 0);
            }
        }
    }
}
fn checked(status: i32) -> Result<(), String> {
    if status < 0 {
        Err(format!(
            "{} ({status:#x})",
            t!("Windows could not check the installer checksum. Nothing was written.")
        ))
    } else {
        Ok(())
    }
}
fn sha256(file: &mut File) -> Result<String, String> {
    let mut hash = Hash {
        algorithm: null_mut(),
        hash: null_mut(),
    };
    unsafe {
        checked(BCryptOpenAlgorithmProvider(
            &mut hash.algorithm,
            BCRYPT_SHA256_ALGORITHM,
            null(),
            0,
        ))?;
        checked(BCryptCreateHash(
            hash.algorithm,
            &mut hash.hash,
            null_mut(),
            0,
            null(),
            0,
            0,
        ))?;
    }
    file.rewind().map_err(|e| e.to_string())?;
    let mut buf = vec![0; crate::writer::CHUNK];
    loop {
        let n = file.read(&mut buf).map_err(|e| e.to_string())?;
        if n == 0 {
            break;
        }
        checked(unsafe { BCryptHashData(hash.hash, buf.as_ptr(), n as u32, 0) })?;
    }
    let mut digest = [0u8; 32];
    checked(unsafe { BCryptFinishHash(hash.hash, digest.as_mut_ptr(), 32, 0) })?;
    Ok(digest.iter().map(|b| format!("{b:02x}")).collect())
}

#[derive(Debug)]
pub enum OpenError {
    Read(String),
    Invalid(&'static str),
}

impl From<std::io::Error> for OpenError {
    fn from(error: std::io::Error) -> Self {
        Self::Read(error.to_string())
    }
}

pub fn open(path: &str, expected: Option<&str>) -> Result<File, OpenError> {
    // Deny writes/deletion so validation and writing cannot see different source contents.
    let mut file = OpenOptions::new()
        .read(true)
        .share_mode(FILE_SHARE_READ)
        .open(path)?;
    let info = file.metadata()?;
    let invalid_iso = OpenError::Invalid(t!("This is not a complete bootable ISO image. Nothing was written."));
    if !info.is_file() || !crate::plan::bootable_iso(&mut file, info.len())? {
        return Err(invalid_iso);
    }
    if let Some(expected) = expected {
        if sha256(&mut file).map_err(OpenError::Read)? != expected {
            return Err(OpenError::Invalid(t!("The installer checksum does not match. Nothing was written.")));
        }
    }
    file.rewind()?;
    Ok(file)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Write;
    #[test]
    fn windows_hash_and_source_lock_use_only_a_temporary_file() {
        let path = std::env::temp_dir().join(format!(
            "monet-image-test-{}-{}.iso",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        {
            let mut file = OpenOptions::new()
                .read(true)
                .write(true)
                .create_new(true)
                .open(&path)
                .unwrap();
            file.write_all(b"abc").unwrap();
            assert_eq!(
                sha256(&mut file).unwrap(),
                "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
            );
        }
        let name = path.to_str().unwrap();
        assert!(matches!(open(name, None), Err(OpenError::Invalid(_))));
        std::fs::write(&path, crate::plan::test_iso(512)).unwrap();
        assert!(matches!(open(name, None), Err(OpenError::Invalid(_))));
        std::fs::write(&path, crate::plan::test_iso(32)).unwrap();
        assert!(matches!(open(name, Some(&"0".repeat(64))), Err(OpenError::Invalid(_))));
        let file = open(name, None).unwrap();
        assert!(OpenOptions::new().write(true).open(&path).is_err());
        assert!(std::fs::remove_file(&path).is_err());
        drop(file);
        std::fs::remove_file(path).unwrap();
    }
}

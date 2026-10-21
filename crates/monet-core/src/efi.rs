//! A small, platform-neutral view of UEFI variables.

use std::collections::BTreeMap;
use std::fmt;

/// Standard UEFI global variable namespace (`BootNext`, `BootOrder`, `Boot####`, ...).
pub const GLOBAL_GUID: &str = "8be4df61-93ca-11d2-aa0d-00e098032b8c";

/// Monet's own variable namespace.
pub const MONET_GUID: &str = "d7210c5b-b07a-45d5-961f-de0a89ac4bf5";

/// Name of the variable that carries a [`crate::request::LaunchRequest`].
pub const LAUNCH_VAR: &str = "MonetLaunch";

pub const ATTR_NON_VOLATILE: u32 = 0x1;
pub const ATTR_BOOTSERVICE_ACCESS: u32 = 0x2;
pub const ATTR_RUNTIME_ACCESS: u32 = 0x4;

/// Attributes used for every variable Monet writes.
pub const ATTR_DEFAULT: u32 = ATTR_NON_VOLATILE | ATTR_BOOTSERVICE_ACCESS | ATTR_RUNTIME_ACCESS;

#[derive(Debug)]
pub enum EfiError {
    /// The variable does not exist.
    NotFound,
    /// The system was not booted in UEFI mode, or variables are not exposed.
    Unsupported,
    /// Writing needs administrator / root rights.
    PermissionDenied,
    Io(String),
    Invalid(String),
}

impl fmt::Display for EfiError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            EfiError::NotFound => write!(f, "variable not found"),
            EfiError::Unsupported => write!(f, "UEFI variables are not available on this system"),
            EfiError::PermissionDenied => write!(f, "permission denied (needs administrator rights)"),
            EfiError::Io(e) => write!(f, "{e}"),
            EfiError::Invalid(e) => write!(f, "invalid data: {e}"),
        }
    }
}

impl std::error::Error for EfiError {}

pub type Result<T> = std::result::Result<T, EfiError>;

/// Read and write UEFI variables. Implemented by efivarfs on Linux, by the
/// firmware environment API on Windows, and by [`MemoryEfi`] in tests.
pub trait EfiVars {
    fn get(&self, guid: &str, name: &str) -> Result<Vec<u8>>;
    fn set(&mut self, guid: &str, name: &str, data: &[u8], attributes: u32) -> Result<()>;
    fn delete(&mut self, guid: &str, name: &str) -> Result<()>;

    /// Boot entry numbers that exist, as far as the platform can tell.
    /// The default falls back to `BootOrder`, which every platform can read.
    fn boot_entry_numbers(&self) -> Result<Vec<u16>> {
        read_u16_list(&self.get(GLOBAL_GUID, "BootOrder")?)
    }
}

pub fn read_u16(data: &[u8]) -> Result<u16> {
    match data {
        [a, b, ..] => Ok(u16::from_le_bytes([*a, *b])),
        _ => Err(EfiError::Invalid("expected a 16-bit value".into())),
    }
}

pub fn read_u16_list(data: &[u8]) -> Result<Vec<u16>> {
    if !data.len().is_multiple_of(2) {
        return Err(EfiError::Invalid("odd-length list of 16-bit values".into()));
    }
    Ok(data.as_chunks::<2>().0.iter().map(|c| u16::from_le_bytes(*c)).collect())
}

pub fn write_u16_list(values: &[u16]) -> Vec<u8> {
    values.iter().flat_map(|v| v.to_le_bytes()).collect()
}

/// `Boot0003` style name for a boot entry number.
pub fn boot_var_name(number: u16) -> String {
    format!("Boot{number:04X}")
}

/// Parses `Boot0003` into `3`. Rejects `BootOrder`, `BootNext`, etc.
pub fn parse_boot_var_name(name: &str) -> Option<u16> {
    let hex = name.strip_prefix("Boot")?;
    if hex.len() == 4 && hex.chars().all(|c| c.is_ascii_hexdigit()) {
        u16::from_str_radix(hex, 16).ok()
    } else {
        None
    }
}

/// In-memory variable store, used by tests and dry runs.
#[derive(Default, Debug, Clone)]
pub struct MemoryEfi {
    pub vars: BTreeMap<(String, String), (u32, Vec<u8>)>,
}

impl EfiVars for MemoryEfi {
    fn get(&self, guid: &str, name: &str) -> Result<Vec<u8>> {
        self.vars
            .get(&(guid.to_string(), name.to_string()))
            .map(|(_, d)| d.clone())
            .ok_or(EfiError::NotFound)
    }

    fn set(&mut self, guid: &str, name: &str, data: &[u8], attributes: u32) -> Result<()> {
        self.vars.insert((guid.to_string(), name.to_string()), (attributes, data.to_vec()));
        Ok(())
    }

    fn delete(&mut self, guid: &str, name: &str) -> Result<()> {
        self.vars
            .remove(&(guid.to_string(), name.to_string()))
            .map(|_| ())
            .ok_or(EfiError::NotFound)
    }

    fn boot_entry_numbers(&self) -> Result<Vec<u16>> {
        Ok(self
            .vars
            .keys()
            .filter(|(g, _)| g == GLOBAL_GUID)
            .filter_map(|(_, n)| parse_boot_var_name(n))
            .collect())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn boot_names_round_trip() {
        assert_eq!(boot_var_name(3), "Boot0003");
        assert_eq!(boot_var_name(0x1A2B), "Boot1A2B");
        assert_eq!(parse_boot_var_name("Boot1A2B"), Some(0x1A2B));
        assert_eq!(parse_boot_var_name("BootOrder"), None);
        assert_eq!(parse_boot_var_name("BootNext"), None);
        assert_eq!(parse_boot_var_name("Boot12"), None);
    }

    #[test]
    fn u16_lists() {
        let data = write_u16_list(&[3, 1, 0x2001]);
        assert_eq!(data, vec![3, 0, 1, 0, 1, 0x20]);
        assert_eq!(read_u16_list(&data).unwrap(), vec![3, 1, 0x2001]);
        assert!(read_u16_list(&[1, 2, 3]).is_err());
    }
}

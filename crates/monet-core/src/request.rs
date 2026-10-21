//! The message Monet leaves for Windows: "start this game, then come back".

use serde::{Deserialize, Serialize};

use crate::efi::{EfiError, EfiVars, Result, ATTR_DEFAULT, LAUNCH_VAR, MONET_GUID};
use crate::games;

/// Requests older than this are ignored, so a forgotten request never starts a
/// game days later. Generous, because Windows and Linux may disagree about the
/// hardware clock's time zone until Windows syncs its clock.
pub const MAX_AGE_SECS: u64 = 6 * 60 * 60;

/// Firmware storage is small; keep requests far below any firmware limit.
const MAX_SIZE: usize = 512;

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct LaunchRequest {
    /// Format version.
    pub v: u32,
    /// Game id such as `steam:1172470`, or none to just open Windows.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub game: Option<String>,
    /// Boot entry to return to afterwards (the Monet entry).
    pub return_to: u16,
    /// Unix time the request was made.
    pub created: u64,
}

impl LaunchRequest {
    pub fn new(game: Option<String>, return_to: u16, now: u64) -> Result<Self> {
        if let Some(id) = &game {
            if !games::is_valid_id(id) {
                return Err(EfiError::Invalid(format!("not a valid game id: {id}")));
            }
        }
        Ok(LaunchRequest { v: 1, game, return_to, created: now })
    }

    pub fn encode(&self) -> Vec<u8> {
        serde_json::to_vec(self).expect("request always serializes")
    }

    pub fn decode(data: &[u8]) -> Result<Self> {
        if data.len() > MAX_SIZE {
            return Err(EfiError::Invalid("request too large".into()));
        }
        let req: LaunchRequest =
            serde_json::from_slice(data).map_err(|e| EfiError::Invalid(e.to_string()))?;
        if req.v != 1 {
            return Err(EfiError::Invalid(format!("unknown request version {}", req.v)));
        }
        if let Some(id) = &req.game {
            if !games::is_valid_id(id) {
                return Err(EfiError::Invalid(format!("not a valid game id: {id}")));
            }
        }
        Ok(req)
    }

    pub fn is_fresh(&self, now: u64) -> bool {
        now.abs_diff(self.created) <= MAX_AGE_SECS
    }
}

pub fn write(efi: &mut dyn EfiVars, request: &LaunchRequest) -> Result<()> {
    efi.set(MONET_GUID, LAUNCH_VAR, &request.encode(), ATTR_DEFAULT)
}

/// Reads and removes the pending request, if there is one.
pub fn take(efi: &mut dyn EfiVars) -> Result<Option<LaunchRequest>> {
    let data = match efi.get(MONET_GUID, LAUNCH_VAR) {
        Ok(data) => data,
        Err(EfiError::NotFound) => return Ok(None),
        Err(e) => return Err(e),
    };
    // Always remove it, even if it is unreadable, so it can't get stuck.
    match efi.delete(MONET_GUID, LAUNCH_VAR) {
        Ok(()) | Err(EfiError::NotFound) => {}
        Err(e) => return Err(e),
    }
    LaunchRequest::decode(&data).map(Some)
}

pub fn clear(efi: &mut dyn EfiVars) -> Result<()> {
    match efi.delete(MONET_GUID, LAUNCH_VAR) {
        Ok(()) | Err(EfiError::NotFound) => Ok(()),
        Err(e) => Err(e),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::efi::MemoryEfi;

    #[test]
    fn write_then_take() {
        let mut efi = MemoryEfi::default();
        let req = LaunchRequest::new(Some("steam:730".into()), 3, 1000).unwrap();
        write(&mut efi, &req).unwrap();
        assert!(req.encode().len() < 100);
        assert_eq!(take(&mut efi).unwrap(), Some(req));
        assert_eq!(take(&mut efi).unwrap(), None);
    }

    #[test]
    fn open_windows_without_game() {
        let req = LaunchRequest::new(None, 3, 1000).unwrap();
        assert_eq!(String::from_utf8(req.encode()).unwrap(), r#"{"v":1,"return_to":3,"created":1000}"#);
    }

    #[test]
    fn rejects_bad_ids_and_garbage() {
        assert!(LaunchRequest::new(Some("steam:730; rm -rf /".into()), 3, 0).is_err());
        assert!(LaunchRequest::decode(br#"{"v":1,"game":"../x","return_to":3,"created":0}"#).is_err());
        assert!(LaunchRequest::decode(br#"{"v":2,"return_to":3,"created":0}"#).is_err());

        let mut efi = MemoryEfi::default();
        efi.set(MONET_GUID, LAUNCH_VAR, b"not json", ATTR_DEFAULT).unwrap();
        assert!(take(&mut efi).is_err());
        // The broken request is gone afterwards.
        assert_eq!(take(&mut efi).unwrap(), None);
    }

    #[test]
    fn freshness() {
        let req = LaunchRequest::new(None, 3, 10_000).unwrap();
        assert!(req.is_fresh(10_000 + 60));
        assert!(req.is_fresh(10_000 - 3600)); // clock behind by a time zone
        assert!(!req.is_fresh(10_000 + MAX_AGE_SECS + 1));
    }
}

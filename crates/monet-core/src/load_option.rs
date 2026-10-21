//! Parsing of `EFI_LOAD_OPTION`, the content of `Boot####` variables.
//!
//! ```text
//! u32     Attributes
//! u16     FilePathListLength
//! CHAR16  Description[]        (UCS-2, NUL-terminated)
//! u8      FilePathList[FilePathListLength]   (device path nodes)
//! u8      OptionalData[]
//! ```

use crate::efi::{EfiError, Result};

pub const LOAD_OPTION_ACTIVE: u32 = 0x1;

const DP_TYPE_MEDIA: u8 = 0x04;
const DP_SUBTYPE_HARD_DRIVE: u8 = 0x01;
const DP_SUBTYPE_FILE_PATH: u8 = 0x04;
const DP_TYPE_END: u8 = 0x7f;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct LoadOption {
    pub attributes: u32,
    pub description: String,
    /// The loader path, e.g. `\EFI\Microsoft\Boot\bootmgfw.efi`, if the entry
    /// points at a file on a disk. Firmware entries (USB, network) have none.
    pub file_path: Option<String>,
    /// GPT partition GUID of the disk partition the loader lives on.
    pub partition_guid: Option<String>,
}

impl LoadOption {
    pub fn is_active(&self) -> bool {
        self.attributes & LOAD_OPTION_ACTIVE != 0
    }

    pub fn parse(data: &[u8]) -> Result<LoadOption> {
        if data.len() < 6 {
            return Err(EfiError::Invalid("load option too short".into()));
        }
        let attributes = u32::from_le_bytes([data[0], data[1], data[2], data[3]]);
        let path_len = u16::from_le_bytes([data[4], data[5]]) as usize;

        let mut units = Vec::new();
        let mut pos = 6;
        loop {
            if pos + 1 >= data.len() {
                return Err(EfiError::Invalid("unterminated description".into()));
            }
            let unit = u16::from_le_bytes([data[pos], data[pos + 1]]);
            pos += 2;
            if unit == 0 {
                break;
            }
            units.push(unit);
        }
        let description = String::from_utf16_lossy(&units);

        let end = pos.checked_add(path_len).filter(|e| *e <= data.len());
        let device_path = match end {
            Some(end) => &data[pos..end],
            None => return Err(EfiError::Invalid("device path runs past the end".into())),
        };
        let (file_path, partition_guid) = parse_device_path(device_path);

        Ok(LoadOption { attributes, description, file_path, partition_guid })
    }

    /// Builds the binary form. Only used by tests and tools, Monet never
    /// creates boot entries on a real machine.
    pub fn encode(&self) -> Vec<u8> {
        let mut path = Vec::new();
        if let Some(file) = &self.file_path {
            let text: Vec<u8> = file
                .encode_utf16()
                .chain(std::iter::once(0))
                .flat_map(|u| u.to_le_bytes())
                .collect();
            path.push(DP_TYPE_MEDIA);
            path.push(DP_SUBTYPE_FILE_PATH);
            path.extend_from_slice(&((4 + text.len()) as u16).to_le_bytes());
            path.extend_from_slice(&text);
        }
        path.extend_from_slice(&[DP_TYPE_END, 0xff, 4, 0]);

        let mut out = Vec::new();
        out.extend_from_slice(&self.attributes.to_le_bytes());
        out.extend_from_slice(&(path.len() as u16).to_le_bytes());
        for unit in self.description.encode_utf16().chain(std::iter::once(0)) {
            out.extend_from_slice(&unit.to_le_bytes());
        }
        out.extend_from_slice(&path);
        out
    }
}

fn parse_device_path(mut data: &[u8]) -> (Option<String>, Option<String>) {
    let mut file_path: Option<String> = None;
    let mut partition_guid = None;

    while data.len() >= 4 {
        let node_type = data[0];
        let sub_type = data[1];
        let len = u16::from_le_bytes([data[2], data[3]]) as usize;
        if len < 4 || len > data.len() {
            break;
        }
        let body = &data[4..len];
        match (node_type, sub_type) {
            (DP_TYPE_END, _) => break,
            (DP_TYPE_MEDIA, DP_SUBTYPE_FILE_PATH) => {
                let units: Vec<u16> = body
                    .as_chunks::<2>()
                    .0
                    .iter()
                    .map(|c| u16::from_le_bytes(*c))
                    .take_while(|u| *u != 0)
                    .collect();
                let part = String::from_utf16_lossy(&units);
                // A path may be split over several nodes.
                file_path = Some(match file_path {
                    Some(prev) => format!("{}\\{}", prev.trim_end_matches('\\'), part.trim_start_matches('\\')),
                    None => part,
                });
            }
            (DP_TYPE_MEDIA, DP_SUBTYPE_HARD_DRIVE) if body.len() >= 38 => {
                // partition number (4) + start (8) + size (8) + signature (16) + mbr type (1) + sig type (1)
                let signature = &body[20..36];
                let sig_type = body[37];
                if sig_type == 0x02 {
                    partition_guid = Some(format_guid(signature));
                }
            }
            _ => {}
        }
        data = &data[len..];
    }
    (file_path, partition_guid)
}

/// Formats a GUID stored in the mixed-endian EFI layout.
pub fn format_guid(b: &[u8]) -> String {
    format!(
        "{:02x}{:02x}{:02x}{:02x}-{:02x}{:02x}-{:02x}{:02x}-{:02x}{:02x}-{:02x}{:02x}{:02x}{:02x}{:02x}{:02x}",
        b[3], b[2], b[1], b[0], b[5], b[4], b[7], b[6], b[8], b[9], b[10], b[11], b[12], b[13], b[14], b[15]
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn round_trip() {
        let opt = LoadOption {
            attributes: LOAD_OPTION_ACTIVE,
            description: "Windows Boot Manager".into(),
            file_path: Some("\\EFI\\Microsoft\\Boot\\bootmgfw.efi".into()),
            partition_guid: None,
        };
        let parsed = LoadOption::parse(&opt.encode()).unwrap();
        assert_eq!(parsed, opt);
        assert!(parsed.is_active());
    }

    #[test]
    fn hard_drive_node_and_optional_data() {
        // Hard drive node (42 bytes) followed by a file path node and end node.
        let mut hd = vec![DP_TYPE_MEDIA, DP_SUBTYPE_HARD_DRIVE, 42, 0];
        hd.extend_from_slice(&1u32.to_le_bytes());
        hd.extend_from_slice(&2048u64.to_le_bytes());
        hd.extend_from_slice(&1_000_000u64.to_le_bytes());
        hd.extend_from_slice(&[
            0x33, 0x22, 0x11, 0x00, 0x55, 0x44, 0x77, 0x66, 0x88, 0x99, 0xaa, 0xbb, 0xcc, 0xdd, 0xee, 0xff,
        ]);
        hd.push(0x02);
        hd.push(0x02);

        let file = LoadOption {
            attributes: 1,
            description: "Fedora".into(),
            file_path: Some("\\EFI\\fedora\\shimx64.efi".into()),
            partition_guid: None,
        }
        .encode();
        // Splice the hard drive node in front of the file path node.
        let desc_end = 6 + ("Fedora".len() + 1) * 2;
        let old_path = &file[desc_end..];
        let mut path = hd.clone();
        path.extend_from_slice(old_path);

        let mut data = file[..4].to_vec();
        data.extend_from_slice(&(path.len() as u16).to_le_bytes());
        data.extend_from_slice(&file[6..desc_end]);
        data.extend_from_slice(&path);
        data.extend_from_slice(b"optional-data");

        let parsed = LoadOption::parse(&data).unwrap();
        assert_eq!(parsed.description, "Fedora");
        assert_eq!(parsed.file_path.as_deref(), Some("\\EFI\\fedora\\shimx64.efi"));
        assert_eq!(parsed.partition_guid.as_deref(), Some("00112233-4455-6677-8899-aabbccddeeff"));
    }

    #[test]
    fn rejects_garbage() {
        assert!(LoadOption::parse(&[1, 2, 3]).is_err());
        assert!(LoadOption::parse(&[1, 0, 0, 0, 0xff, 0xff, b'A', 0, 0, 0]).is_err());
    }
}

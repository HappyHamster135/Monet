//! The parts of making a USB stick that don't touch Windows: what to download,
//! how to name a stick, how to cut the image into writes.

use std::io::{self, Read, Seek, SeekFrom};

/// Where one of this version's files is: the release this program came with.
pub fn release_url(version: &str, name: &str) -> String {
    format!("https://github.com/HappyHamster135/Monet/releases/download/v{version}/{name}")
}

/// A refreshed release must never resume bytes from the previous installer.
pub fn cache_name(name: &str, checksum: &str) -> String {
    format!("{checksum}-{name}")
}

/// This version's installers, best first: Monet Setup, Monet's own (in a
/// release only once it has installed Monet in a test PC), then Fedora's
/// installer dressed as Monet.
pub fn installer_names(version: &str) -> [String; 2] {
    [
        format!("Monet-{version}-Setup.iso"),
        format!("Monet-{version}-Installer.iso"),
    ]
}

/// Whether `curl -sIL` found the file: the last answer, after redirects, is a 2xx.
pub fn found(headers: &str) -> bool {
    headers
        .lines()
        .rev()
        .find(|line| line.starts_with("HTTP/"))
        .and_then(|line| line.split_whitespace().nth(1))
        .is_some_and(|code| code.starts_with('2'))
}

/// "SanDisk Ultra · 32 GB": what's printed on the stick, roughly.
pub fn label(vendor: &str, product: &str, size: u64) -> String {
    let name: Vec<&str> = vendor.split_whitespace().chain(product.split_whitespace()).collect();
    let name = if name.is_empty() {
        "USB stick".to_string()
    } else {
        name.join(" ")
    };
    format!("{name} · {}", size_text(size))
}

/// Sizes as sticks are sold: decimal GB, rounded.
pub fn size_text(size: u64) -> String {
    let gb = size as f64 / 1e9;
    if gb >= 10.0 {
        format!("{} GB", gb.round() as u64)
    } else {
        format!("{gb:.1} GB")
    }
}

/// Smallest stick that holds the installer, with room to spare.
pub const MIN_STICK: u64 = 2_000_000_000;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Target {
    pub number: u32,
    pub id: u128,
    pub bytes: u64,
    pub sector: u32,
    pub usb: bool,
}

pub fn check_sector_size(logical: u32) -> Result<(), &'static str> {
    // The hybrid ISO's partition table addresses 512-byte logical sectors.
    if logical != 512 {
        return Err(t!("Monet needs a USB stick with 512-byte logical sectors. Nothing was written."));
    }
    Ok(())
}

/// Recheck the opened device, never trust a disk number saved before downloading.
pub fn check_target(selected: Target, current: Target, system: Option<u32>, image: u64) -> Result<(), &'static str> {
    if system.is_none() || system == Some(current.number) {
        return Err(t!("Windows' system disk could not be excluded. Nothing was written."));
    }
    if !current.usb || current.id == 0 || current != selected {
        return Err(t!(
            "The selected USB device changed. Select it again. Nothing was written."
        ));
    }
    check_sector_size(current.sector)?;
    let padded = image.checked_add(4095).map(|n| n / 4096 * 4096);
    if image == 0 || padded.is_none_or(|n| n > current.bytes) {
        return Err(t!(
            "The installer does not fit on this USB device. Nothing was written."
        ));
    }
    Ok(())
}

/// Only the exact release asset is accepted; duplicate or malformed entries fail closed.
pub fn checksum(manifest: &str, name: &str) -> Option<String> {
    let mut found = None;
    for line in manifest.lines() {
        let Some((hash, file)) = line.split_once(char::is_whitespace) else {
            continue;
        };
        if file.trim_start().strip_prefix('*').unwrap_or(file.trim_start()) == name {
            if found.is_some() || hash.len() != 64 || !hash.bytes().all(|b| b.is_ascii_hexdigit()) {
                return None;
            }
            found = Some(hash.to_ascii_lowercase());
        }
    }
    found
}

const ISO_SECTOR: usize = 2048;
const FIRST_DESCRIPTOR: u64 = 16;

pub fn bootable_iso(image: &mut (impl Read + Seek), total: u64) -> io::Result<bool> {
    let sectors = total / ISO_SECTOR as u64;
    if sectors <= FIRST_DESCRIPTOR || !total.is_multiple_of(ISO_SECTOR as u64) {
        return Ok(false);
    }
    image.rewind()?;
    let mut sector = [0; ISO_SECTOR];
    image.read_exact(&mut sector)?;
    if sector[510..512] != *b"\x55\xaa" {
        return Ok(false);
    }
    if sector[512..520] == *b"EFI PART" {
        // A hybrid image can describe disk data beyond its ISO filesystem.
        let backup_lba = u64::from_le_bytes(sector[544..552].try_into().unwrap());
        if !(2..total / 512).contains(&backup_lba) {
            return Ok(false);
        }
    } else if sector[450..512].iter().step_by(16).any(|&kind| kind == 0xee) {
        return Ok(false);
    }
    image.seek(SeekFrom::Start(FIRST_DESCRIPTOR * ISO_SECTOR as u64))?;
    for descriptor in FIRST_DESCRIPTOR..sectors {
        image.read_exact(&mut sector)?;
        if sector[1..6] != *b"CD001" || sector[0] == 255 {
            return Ok(false);
        }
        if sector[0] == 1 {
            // ISO 9660 records both byte orders in its primary volume descriptor.
            let blocks = u32::from_le_bytes(sector[80..84].try_into().unwrap());
            let block_size = u16::from_le_bytes(sector[128..130].try_into().unwrap());
            let volume = u64::from(blocks) * u64::from(block_size);
            return Ok(sector[6] == 1
                && sector[84..88] == blocks.to_be_bytes()
                && sector[130..132] == block_size.to_be_bytes()
                && matches!(block_size, 512 | 1024 | 2048)
                && ((descriptor + 1) * ISO_SECTOR as u64..=total).contains(&volume));
        }
    }
    Ok(false)
}

#[cfg(test)]
pub(crate) fn test_iso(blocks: u32) -> Vec<u8> {
    let mut iso = vec![0; 32 * ISO_SECTOR];
    iso[510..512].copy_from_slice(b"\x55\xaa");
    let descriptor = &mut iso[FIRST_DESCRIPTOR as usize * ISO_SECTOR..];
    descriptor[..7].copy_from_slice(b"\x01CD001\x01");
    descriptor[80..84].copy_from_slice(&blocks.to_le_bytes());
    descriptor[84..88].copy_from_slice(&blocks.to_be_bytes());
    descriptor[128..130].copy_from_slice(&(ISO_SECTOR as u16).to_le_bytes());
    descriptor[130..132].copy_from_slice(&(ISO_SECTOR as u16).to_be_bytes());
    iso
}

/// Round the transfer up to match the 4 KiB-aligned I/O buffer.
/// The ISO is 2 KiB-aligned, so the padding is at most 2 KiB.
pub fn padded(len: usize) -> usize {
    len.div_ceil(4096) * 4096
}

/// The last `content-length` in `curl -sIL` output (after redirects).
pub fn content_length(headers: &str) -> Option<u64> {
    headers.lines().rev().find_map(|line| {
        let (name, value) = line.split_once(':')?;
        name.trim()
            .eq_ignore_ascii_case("content-length")
            .then(|| value.trim().parse().ok())?
    })
}

/// The minutes left, rounded, at least one: "about 3 min left" says it.
pub fn minutes_left(seconds: f64) -> u64 {
    (seconds / 60.0).round().max(1.0) as u64
}

/// A NUL-terminated ASCII string inside a storage descriptor, at `offset`.
pub fn descriptor_text(buf: &[u8], offset: u32) -> String {
    let start = offset as usize;
    if start == 0 || start >= buf.len() {
        return String::new();
    }
    let end = buf[start..]
        .iter()
        .position(|&b| b == 0)
        .map_or(buf.len(), |n| start + n);
    String::from_utf8_lossy(&buf[start..end]).trim().to_string()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn target() -> Target {
        Target {
            number: 2,
            id: 123,
            bytes: 4_000_000_000,
            sector: 512,
            usb: true,
        }
    }

    #[test]
    fn only_the_same_usb_with_a_known_system_disk_can_be_written() {
        let selected = target();
        assert!(check_target(selected, selected, Some(0), 2_000_000_000).is_ok());
        for current in [
            Target { id: 456, ..selected },
            Target { id: 0, ..selected },
            Target { number: 3, ..selected },
            Target { usb: false, ..selected },
            Target {
                bytes: 3_000_000_000,
                ..selected
            },
            Target {
                sector: 1024,
                ..selected
            },
        ] {
            assert!(check_target(selected, current, Some(0), 2048).is_err(), "{current:?}");
        }
        assert!(check_target(selected, selected, None, 2048).is_err());
        assert!(check_target(selected, selected, Some(2), 2048).is_err());
    }

    #[test]
    fn native_4k_target_is_rejected_before_the_write() {
        let native_4k = Target { sector: 4096, ..target() };
        let message = check_sector_size(4096).unwrap_err();
        assert_eq!(check_target(native_4k, native_4k, Some(0), 2048), Err(message));
    }

    #[test]
    fn image_must_fit_including_sector_padding() {
        let selected = Target {
            bytes: 8704,
            ..target()
        };
        for size in [0, 8193, u64::MAX] {
            assert!(check_target(selected, selected, Some(0), size).is_err());
        }
        for size in [2048, 8192] {
            assert!(check_target(selected, selected, Some(0), size).is_ok());
        }
    }

    #[test]
    fn checksum_is_for_one_exact_asset() {
        let hash = "a".repeat(64);
        let line = format!("{hash}  Monet.iso\n");
        assert_eq!(checksum(&line, "Monet.iso"), Some(hash.clone()));
        assert_eq!(checksum(&format!("{hash} *Monet.iso"), "Monet.iso"), Some(hash));
        for manifest in [
            "wrong  Monet.iso".into(),
            line.repeat(2),
            line.replace("Monet.iso", "OldMonet.iso"),
            String::new(),
        ] {
            assert_eq!(checksum(&manifest, "Monet.iso"), None);
        }
    }

    #[test]
    fn replaced_release_assets_get_separate_downloads() {
        let name = "Monet-0.9.4-Setup.iso";
        let old = cache_name(name, &"a".repeat(64));
        let new = cache_name(name, &"b".repeat(64));
        assert_ne!(old, new);
        assert_ne!(old, name);
        assert_eq!(new, cache_name(name, &"b".repeat(64)));
    }

    #[test]
    fn reject_empty_truncated_or_non_bootable_images() {
        let valid = |data: &[u8]| bootable_iso(&mut io::Cursor::new(data), data.len() as u64).unwrap();
        assert!(!valid(&[]));
        assert!(!valid(&[0; 65536]));
        assert!(!valid(&test_iso(512))); // Real ISO header with its payload missing.
        let mut iso = test_iso(32);
        assert!(valid(&iso));
        assert!(!valid(&iso[..65535]));
        assert!(!valid(&iso[..512]));
        iso[16 * ISO_SECTOR + 87] ^= 1;
        assert!(!valid(&iso));
    }

    #[test]
    fn hybrid_backup_gpt_must_fit_even_when_the_iso_volume_fits() {
        let mut iso = test_iso(24);
        iso[450] = 0xee;
        let fits = |data: &[u8]| bootable_iso(&mut io::Cursor::new(data), data.len() as u64).unwrap();
        assert!(!fits(&iso));
        iso[512..520].copy_from_slice(b"EFI PART");
        iso[544..552].copy_from_slice(&127u64.to_le_bytes());
        assert!(fits(&iso));
        assert!(!fits(&iso[..31 * ISO_SECTOR]));
    }

    #[test]
    fn the_boot_record_may_precede_the_primary_volume_descriptor() {
        let mut iso = test_iso(32);
        let first = 16 * ISO_SECTOR;
        iso.copy_within(first..first + ISO_SECTOR, first + ISO_SECTOR);
        iso[first] = 0;
        assert!(bootable_iso(&mut io::Cursor::new(&iso), iso.len() as u64).unwrap());
    }

    #[test]
    fn url_names_the_release_and_its_installer() {
        assert_eq!(
            release_url("0.6.4", "Monet-0.6.4-Installer.iso"),
            "https://github.com/HappyHamster135/Monet/releases/download/v0.6.4/Monet-0.6.4-Installer.iso"
        );
    }

    #[test]
    fn monet_setup_comes_first() {
        assert_eq!(
            installer_names("0.8.0"),
            ["Monet-0.8.0-Setup.iso", "Monet-0.8.0-Installer.iso"]
        );
    }

    #[test]
    fn found_reads_the_last_answer() {
        assert!(found(
            "HTTP/2 302\r\nlocation: x\r\n\r\nHTTP/2 200\r\nContent-Length: 1221263360\r\n"
        ));
        // GitHub's "Not Found" has a length too.
        assert!(!found("HTTP/2 404\r\ncontent-length: 9\r\n"));
        assert!(!found("HTTP/2 302\r\n\r\nHTTP/1.1 404 Not Found\r\n"));
        assert!(!found(""));
    }

    #[test]
    fn labels_read_like_the_box() {
        assert_eq!(label("SanDisk ", " Ultra  ", 32_017_047_552), "SanDisk Ultra · 32 GB");
        assert_eq!(label("", "", 7_800_000_000), "USB stick · 7.8 GB");
    }

    #[test]
    fn writes_are_whole_sectors() {
        assert_eq!(padded(4 << 20), 4 << 20);
        assert_eq!(padded(2048), 4096);
        assert_eq!(padded(4097), 8192);
    }

    #[test]
    fn content_length_after_redirects() {
        let headers =
            "HTTP/2 302\r\ncontent-length: 0\r\nlocation: x\r\n\r\nHTTP/2 200\r\nContent-Length: 1221263360\r\n";
        assert_eq!(content_length(headers), Some(1_221_263_360));
        assert_eq!(content_length("HTTP/2 404\r\n"), None);
    }

    #[test]
    fn time_left() {
        assert_eq!(minutes_left(20.0), 1);
        assert_eq!(minutes_left(185.0), 3);
    }

    #[test]
    fn descriptor_strings() {
        let mut buf = vec![0u8; 64];
        buf[40..47].copy_from_slice(b"SanDisk");
        assert_eq!(descriptor_text(&buf, 40), "SanDisk");
        assert_eq!(descriptor_text(&buf, 0), "");
        assert_eq!(descriptor_text(&buf, 900), "");
    }
}

//! The parts of making a USB stick that don't touch Windows: what to download,
//! how to name a stick, how to cut the image into writes.

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
    if !matches!(current.sector, 512 | 4096) {
        return Err(t!("This device's sector size is not supported. Nothing was written."));
    }
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

pub fn bootable_iso(header: &[u8], total: u64) -> bool {
    header.len() >= 32774
        && total >= header.len() as u64
        && total.is_multiple_of(2048)
        && &header[510..512] == b"\x55\xaa"
        && &header[32769..32774] == b"CD001"
}

/// A write's length rounded up to whole 4 KiB sectors (the stick only takes
/// whole sectors; the ISO is 2 KiB-aligned, so at most 2 KiB of zeros).
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
    fn image_must_fit_including_sector_padding() {
        let selected = Target {
            bytes: 8192,
            sector: 4096,
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
        let mut header = vec![0; 32774];
        assert!(!bootable_iso(&header, 65536));
        header[510..512].copy_from_slice(b"\x55\xaa");
        header[32769..32774].copy_from_slice(b"CD001");
        assert!(bootable_iso(&header, 65536));
        assert!(!bootable_iso(&header, 0));
        assert!(!bootable_iso(&header, 65535));
        assert!(!bootable_iso(&header[..512], 65536));
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

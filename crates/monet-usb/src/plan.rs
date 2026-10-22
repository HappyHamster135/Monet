//! The parts of making a USB stick that don't touch Windows: what to download,
//! how to name a stick, how to cut the image into writes.

/// Where one of this version's files is: the release this program came with.
pub fn release_url(version: &str, name: &str) -> String {
    format!("https://github.com/HappyHamster135/Monet/releases/download/v{version}/{name}")
}

/// This version's installers, best first: Monet Setup, Monet's own (in a
/// release only once it has installed Monet in a test PC), then Fedora's
/// installer dressed as Monet.
pub fn installer_names(version: &str) -> [String; 2] {
    [format!("Monet-{version}-Setup.iso"), format!("Monet-{version}-Installer.iso")]
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
    let name = if name.is_empty() { "USB stick".to_string() } else { name.join(" ") };
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

/// A write's length rounded up to whole 4 KiB sectors (the stick only takes
/// whole sectors; the ISO is 2 KiB-aligned, so at most 2 KiB of zeros).
pub fn padded(len: usize) -> usize {
    len.div_ceil(4096) * 4096
}

/// The last `content-length` in `curl -sIL` output (after redirects).
pub fn content_length(headers: &str) -> Option<u64> {
    headers.lines().rev().find_map(|line| {
        let (name, value) = line.split_once(':')?;
        name.trim().eq_ignore_ascii_case("content-length").then(|| value.trim().parse().ok())?
    })
}

/// "about 3 minutes left".
pub fn minutes_left(seconds: f64) -> String {
    let minutes = (seconds / 60.0).round().max(1.0) as u64;
    if minutes == 1 {
        "about 1 minute left".into()
    } else {
        format!("about {minutes} minutes left")
    }
}

/// A NUL-terminated ASCII string inside a storage descriptor, at `offset`.
pub fn descriptor_text(buf: &[u8], offset: u32) -> String {
    let start = offset as usize;
    if start == 0 || start >= buf.len() {
        return String::new();
    }
    let end = buf[start..].iter().position(|&b| b == 0).map_or(buf.len(), |n| start + n);
    String::from_utf8_lossy(&buf[start..end]).trim().to_string()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn url_names_the_release_and_its_installer() {
        assert_eq!(
            release_url("0.6.4", "Monet-0.6.4-Installer.iso"),
            "https://github.com/HappyHamster135/Monet/releases/download/v0.6.4/Monet-0.6.4-Installer.iso"
        );
    }

    #[test]
    fn monet_setup_comes_first() {
        assert_eq!(installer_names("0.8.0"), ["Monet-0.8.0-Setup.iso", "Monet-0.8.0-Installer.iso"]);
    }

    #[test]
    fn found_reads_the_last_answer() {
        assert!(found("HTTP/2 302\r\nlocation: x\r\n\r\nHTTP/2 200\r\nContent-Length: 1221263360\r\n"));
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
        let headers = "HTTP/2 302\r\ncontent-length: 0\r\nlocation: x\r\n\r\nHTTP/2 200\r\nContent-Length: 1221263360\r\n";
        assert_eq!(content_length(headers), Some(1_221_263_360));
        assert_eq!(content_length("HTTP/2 404\r\n"), None);
    }

    #[test]
    fn time_left() {
        assert_eq!(minutes_left(20.0), "about 1 minute left");
        assert_eq!(minutes_left(185.0), "about 3 minutes left");
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

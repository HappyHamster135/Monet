//! The same write/flush/read-back sequence runs against Windows disks and disposable test disks.
use std::io::{self, Read, Seek, SeekFrom, Write};
use std::ops::{Deref, DerefMut};

pub const CHUNK: usize = 1 << 20;

#[repr(C, align(4096))]
#[derive(Clone)]
struct Sector([u8; 4096]);
struct Buffer(Vec<Sector>);
impl Buffer {
    fn new(size: usize) -> Self {
        Self(vec![Sector([0; 4096]); size.div_ceil(4096)])
    }
}
impl Deref for Buffer {
    type Target = [u8];
    fn deref(&self) -> &[u8] {
        // Sector has no padding; Vec preserves its alignment for uncached Windows disk I/O.
        unsafe { std::slice::from_raw_parts(self.0.as_ptr().cast(), self.0.len() * 4096) }
    }
}
impl DerefMut for Buffer {
    fn deref_mut(&mut self) -> &mut [u8] {
        unsafe { std::slice::from_raw_parts_mut(self.0.as_mut_ptr().cast(), self.0.len() * 4096) }
    }
}

pub trait Destination: Read + Write + Seek {
    /// Validate the device and lock its volumes, then return its capacity in bytes.
    fn prepare(&mut self, total: u64) -> io::Result<u64>;
    /// Clear the old partition layout only after preparation succeeds and validate the reopened device.
    fn reset_layout(&mut self, total: u64) -> io::Result<()>;
    fn sync_media(&mut self) -> io::Result<()>;
}

fn fit_protective_mbr(head: &mut [u8], total: u64, capacity: u64) {
    let Some(prefix) = head.get_mut(..552) else { return };
    let (mbr, gpt) = prefix.split_at_mut(512);
    if mbr[510..] != *b"\x55\xaa" || gpt[..8] != *b"EFI PART" || gpt[24..32] != 1u64.to_le_bytes() {
        return;
    }
    let backup = u64::from_le_bytes(gpt[32..40].try_into().unwrap());
    let sectors = capacity / 512;
    if !(2..total / 512).contains(&backup) || sectors <= backup + 1 {
        return;
    }
    let mut entries = mbr[446..510].chunks_exact_mut(16)
        .filter(|entry| entry.iter().any(|&byte| byte != 0));
    let Some(entry) = entries.next() else { return };
    // Only a pure protective MBR gets a disk-sized entry. A hybrid MBR can
    // describe real partitions, and its layout must be kept as supplied.
    if entries.next().is_some() || entry[0] != 0 || entry[4] != 0xee
        || entry[8..12] != 1u32.to_le_bytes()
        || entry[12..16] != u32::try_from(backup).unwrap_or(u32::MAX).to_le_bytes()
    {
        return;
    }
    let last_lba = u32::try_from(sectors - 1).unwrap_or(u32::MAX);
    entry[12..16].copy_from_slice(&last_lba.to_le_bytes());
}

pub fn write(
    image: &mut (impl Read + Seek),
    disk: &mut impl Destination,
    total: u64,
    mut progress: impl FnMut(u32, u64, u64),
) -> io::Result<()> {
    if total == 0 {
        return Err(io::Error::other(t!(
            "The installer image is empty. Nothing was written."
        )));
    }
    image.rewind()?;
    let first = total.min(CHUNK as u64) as usize;
    let mut head = Buffer::new(first);
    image.read_exact(&mut head[..first])?;
    let capacity = disk.prepare(total)?;
    fit_protective_mbr(&mut head[..first], total, capacity);
    disk.reset_layout(total)?;
    let mut buf = Buffer::new(CHUNK);
    let mut back = Buffer::new(CHUNK);
    // Leave the partition table until last so Windows cannot mount an unfinished new image.
    let mut done = first as u64;
    if done < total {
        disk.seek(SeekFrom::Start(done))?;
    }
    while done < total {
        let n = (total - done).min(CHUNK as u64) as usize;
        let padded = crate::plan::padded(n);
        image.read_exact(&mut buf[..n])?;
        buf[n..padded].fill(0);
        disk.write_all(&buf[..padded])?;
        done += n as u64;
        progress(0, done, total);
    }
    disk.rewind()?;
    disk.write_all(&head)?;
    disk.sync_media()?;
    progress(0, total, total);
    image.rewind()?;
    disk.rewind()?;
    done = 0;
    while done < total {
        let n = (total - done).min(CHUNK as u64) as usize;
        let padded = crate::plan::padded(n);
        image.read_exact(&mut buf[..n])?;
        buf[n..padded].fill(0);
        if done == 0 {
            fit_protective_mbr(&mut buf[..n], total, capacity);
        }
        disk.read_exact(&mut back[..padded])?;
        if back[..padded] != buf[..padded] {
            return Err(io::Error::other(t!(
                "The USB device did not keep what was written. Verification failed."
            )));
        }
        done += n as u64;
        progress(1, done, total);
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Cursor;

    struct FakeDisk {
        bytes: Cursor<Vec<u8>>,
        fault: &'static str,
        writes: Vec<u64>,
        reads: usize,
        synced: bool,
        prepared: bool,
        layout_reset: bool,
    }
    impl FakeDisk {
        fn new(fault: &'static str) -> Self {
            Self {
                bytes: Cursor::new(vec![0xa5; CHUNK * 3]),
                fault,
                writes: Vec::new(),
                reads: 0,
                synced: false,
                prepared: false,
                layout_reset: false,
            }
        }
    }
    impl Destination for FakeDisk {
        fn prepare(&mut self, total: u64) -> io::Result<u64> {
            let capacity = self.bytes.get_ref().len() as u64;
            if self.fault == "lock" || total > capacity {
                return Err(io::Error::other("preflight veto"));
            }
            self.prepared = true;
            Ok(capacity)
        }
        fn reset_layout(&mut self, _total: u64) -> io::Result<()> {
            assert!(self.prepared, "all locks and validation must precede clearing the layout");
            assert!(self.writes.is_empty(), "old partitions must be removed before writing the image");
            if self.fault == "reset" {
                return Err(io::Error::other("layout reset failed"));
            }
            self.layout_reset = true;
            Ok(())
        }
        fn sync_media(&mut self) -> io::Result<()> {
            if self.fault == "flush" {
                return Err(io::Error::other("flush failed"));
            }
            if self.fault == "corrupt" {
                self.bytes.get_mut()[0] ^= 1;
            }
            self.synced = true;
            Ok(())
        }
    }
    impl Read for FakeDisk {
        fn read(&mut self, bytes: &mut [u8]) -> io::Result<usize> {
            assert_eq!(bytes.as_ptr() as usize % 4096, 0);
            assert!(self.synced, "verification must follow a successful flush");
            self.reads += 1;
            if self.fault == "read" {
                return Err(io::Error::other("device removed"));
            }
            self.bytes.read(bytes)
        }
    }
    impl Write for FakeDisk {
        fn write(&mut self, bytes: &[u8]) -> io::Result<usize> {
            assert!(self.layout_reset, "never write through the old partition layout");
            assert_eq!(bytes.as_ptr() as usize % 4096, 0);
            assert_eq!(bytes.len() % 4096, 0);
            assert_eq!(self.bytes.position() % 4096, 0);
            self.writes.push(self.bytes.position());
            match self.fault {
                "write" => Err(io::Error::other("device removed")),
                "zero" => Ok(0),
                "short" => self.bytes.write(&bytes[..bytes.len().min(4096)]),
                _ => self.bytes.write(bytes),
            }
        }
        fn flush(&mut self) -> io::Result<()> {
            Ok(())
        }
    }
    impl Seek for FakeDisk {
        fn seek(&mut self, to: SeekFrom) -> io::Result<u64> {
            self.bytes.seek(to)
        }
    }

    #[test]
    fn image_is_verified_with_padding_and_header_last() {
        let bytes: Vec<u8> = (0..CHUNK * 2 + 2048).map(|i| (i % 251) as u8).collect();
        let total = bytes.len() as u64;
        let mut disk = FakeDisk::new("");
        write(&mut Cursor::new(&bytes), &mut disk, total, |_, _, _| {}).unwrap();
        assert_eq!(disk.writes, [CHUNK as u64, CHUNK as u64 * 2, 0]);
        assert_eq!(&disk.bytes.get_ref()[..bytes.len()], bytes);
        assert!(disk.bytes.get_ref()[bytes.len()..crate::plan::padded(bytes.len())]
            .iter()
            .all(|b| *b == 0));
        assert_eq!(disk.bytes.get_ref()[crate::plan::padded(bytes.len())], 0xa5);
        assert_eq!(disk.reads, 3);
        assert!(disk.layout_reset);
    }

    fn protective_iso() -> Vec<u8> {
        let mut iso = crate::plan::test_iso(32);
        let backup = iso.len() as u64 / 512 - 1;
        iso[450] = 0xee;
        iso[454..458].copy_from_slice(&1u32.to_le_bytes());
        iso[458..462].copy_from_slice(&(backup as u32).to_le_bytes());
        iso[512..520].copy_from_slice(b"EFI PART");
        iso[536..544].copy_from_slice(&1u64.to_le_bytes());
        iso[544..552].copy_from_slice(&backup.to_le_bytes());
        iso
    }

    #[test]
    fn pure_protective_entry_uses_the_validated_disk_size_and_passes_readback() {
        let iso = protective_iso();
        let mut disk = FakeDisk::new("");
        let last_lba = (disk.bytes.get_ref().len() / 512 - 1) as u32;
        write(&mut Cursor::new(&iso), &mut disk, iso.len() as u64, |_, _, _| {}).unwrap();
        let mut expected = iso;
        expected[458..462].copy_from_slice(&last_lba.to_le_bytes());
        assert_eq!(&disk.bytes.get_ref()[..expected.len()], expected);
        assert_eq!(disk.reads, 1);
    }

    #[test]
    fn hybrid_entries_are_kept_and_large_disk_size_is_saturated() {
        let iso = protective_iso();
        let mut hybrid = iso.clone();
        hybrid[466] = 0x17;
        let original = hybrid.clone();
        let total = hybrid.len() as u64;
        fit_protective_mbr(&mut hybrid, total, 2 * total);
        assert_eq!(hybrid, original);

        let mut large = iso;
        fit_protective_mbr(&mut large, total, (u64::from(u32::MAX) + 2) * 512);
        assert_eq!(large[458..462], u32::MAX.to_le_bytes());
    }

    #[test]
    fn lock_capacity_and_empty_image_fail_before_any_write() {
        for (fault, total) in [("lock", 65536), ("", CHUNK as u64 * 4), ("", 0)] {
            let mut disk = FakeDisk::new(fault);
            let mut image = Cursor::new(vec![0x33; CHUNK]);
            assert!(write(&mut image, &mut disk, total, |_, _, _| {}).is_err());
            assert!(disk.writes.is_empty());
            assert!(!disk.layout_reset);
            assert!(disk.bytes.get_ref().iter().all(|b| *b == 0xa5));
        }
    }

    #[test]
    fn every_write_flush_or_verification_failure_prevents_success() {
        for fault in ["reset", "write", "zero", "flush", "read", "corrupt"] {
            let mut disk = FakeDisk::new(fault);
            let mut image = Cursor::new(vec![0x33; CHUNK * 2]);
            assert!(
                write(&mut image, &mut disk, CHUNK as u64 * 2, |_, _, _| {}).is_err(),
                "{fault}"
            );
            if matches!(fault, "reset" | "write" | "zero" | "flush") {
                assert_eq!(disk.reads, 0);
            }
            if fault == "reset" {
                assert!(disk.writes.is_empty());
                assert!(!disk.layout_reset);
            }
        }
    }

    #[test]
    fn shortened_source_never_writes_the_header() {
        let mut disk = FakeDisk::new("");
        assert!(write(
            &mut Cursor::new(vec![0x33; CHUNK + 1]),
            &mut disk,
            CHUNK as u64 + 4096,
            |_, _, _| {}
        )
        .is_err());
        assert!(disk.writes.is_empty());
    }

    #[test]
    fn short_writes_are_completed_and_checked() {
        let mut disk = FakeDisk::new("short");
        let bytes = vec![0x33; 65536];
        write(&mut Cursor::new(&bytes), &mut disk, bytes.len() as u64, |_, _, _| {}).unwrap();
        assert_eq!(&disk.bytes.get_ref()[..bytes.len()], bytes);
    }
}

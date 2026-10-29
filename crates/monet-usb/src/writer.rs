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
    /// Validate identity/capacity and obtain every volume lock before writing anything.
    fn prepare(&mut self, total: u64) -> io::Result<()>;
    fn sync_media(&mut self) -> io::Result<()>;
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
    disk.prepare(total)?;
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
    }
    impl FakeDisk {
        fn new(fault: &'static str) -> Self {
            Self {
                bytes: Cursor::new(vec![0xa5; CHUNK * 3]),
                fault,
                writes: Vec::new(),
                reads: 0,
                synced: false,
            }
        }
    }
    impl Destination for FakeDisk {
        fn prepare(&mut self, total: u64) -> io::Result<()> {
            if self.fault == "lock" || total > self.bytes.get_ref().len() as u64 {
                return Err(io::Error::other("preflight veto"));
            }
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
    }

    #[test]
    fn lock_capacity_and_empty_image_fail_before_any_write() {
        for (fault, total) in [("lock", 65536), ("", CHUNK as u64 * 4), ("", 0)] {
            let mut disk = FakeDisk::new(fault);
            let mut image = Cursor::new(vec![0x33; CHUNK]);
            assert!(write(&mut image, &mut disk, total, |_, _, _| {}).is_err());
            assert!(disk.writes.is_empty());
            assert!(disk.bytes.get_ref().iter().all(|b| *b == 0xa5));
        }
    }

    #[test]
    fn every_write_flush_or_verification_failure_prevents_success() {
        for fault in ["write", "zero", "flush", "read", "corrupt"] {
            let mut disk = FakeDisk::new(fault);
            let mut image = Cursor::new(vec![0x33; CHUNK * 2]);
            assert!(
                write(&mut image, &mut disk, CHUNK as u64 * 2, |_, _, _| {}).is_err(),
                "{fault}"
            );
            if matches!(fault, "write" | "zero" | "flush") {
                assert_eq!(disk.reads, 0);
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

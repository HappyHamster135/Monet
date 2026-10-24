//! USB sticks on Windows: finding them, and writing an image onto one.

use std::ffi::c_void;
use std::fs::{File, OpenOptions};
use std::io::{Read, Write};
use std::mem::{size_of, zeroed};
use std::ptr::null_mut;

use windows_sys::Win32::Foundation::{CloseHandle, GetLastError, GENERIC_READ, GENERIC_WRITE, HANDLE, INVALID_HANDLE_VALUE};
use windows_sys::Win32::Storage::FileSystem::{
    CreateFileW, FlushFileBuffers, ReadFile, SetFilePointerEx, WriteFile, FILE_BEGIN, FILE_FLAG_WRITE_THROUGH,
    FILE_SHARE_READ, FILE_SHARE_WRITE, OPEN_EXISTING,
};
use windows_sys::Win32::System::Ioctl::{
    PropertyStandardQuery, StorageDeviceProperty, DISK_GEOMETRY_EX, FSCTL_DISMOUNT_VOLUME, FSCTL_LOCK_VOLUME,
    IOCTL_DISK_DELETE_DRIVE_LAYOUT, IOCTL_DISK_GET_DRIVE_GEOMETRY_EX, IOCTL_DISK_UPDATE_PROPERTIES,
    IOCTL_STORAGE_GET_DEVICE_NUMBER, IOCTL_STORAGE_QUERY_PROPERTY, STORAGE_DEVICE_DESCRIPTOR, STORAGE_DEVICE_NUMBER,
    STORAGE_PROPERTY_QUERY,
};
use windows_sys::Win32::System::IO::DeviceIoControl;

use crate::plan;

const BUS_USB: i32 = 7;
const CHUNK: usize = 4 << 20;

pub struct Stick {
    pub number: u32,
    pub label: String,
}

fn wide(s: &str) -> Vec<u16> {
    s.encode_utf16().chain(Some(0)).collect()
}

struct Handle(HANDLE);

impl Drop for Handle {
    fn drop(&mut self) {
        unsafe { CloseHandle(self.0) };
    }
}

fn open(path: &str, access: u32, flags: u32) -> Option<Handle> {
    let path = wide(path);
    let h = unsafe {
        CreateFileW(path.as_ptr(), access, FILE_SHARE_READ | FILE_SHARE_WRITE, null_mut(), OPEN_EXISTING, flags, null_mut())
    };
    (h != INVALID_HANDLE_VALUE).then_some(Handle(h))
}

fn ioctl(h: &Handle, code: u32, input: *const c_void, in_len: usize, out: *mut c_void, out_len: usize) -> bool {
    let mut got = 0u32;
    unsafe { DeviceIoControl(h.0, code, input, in_len as u32, out, out_len as u32, &mut got, null_mut()) != 0 }
}

fn device_number(h: &Handle) -> Option<u32> {
    let mut n: STORAGE_DEVICE_NUMBER = unsafe { zeroed() };
    ioctl(h, IOCTL_STORAGE_GET_DEVICE_NUMBER, std::ptr::null(), 0, &mut n as *mut _ as _, size_of::<STORAGE_DEVICE_NUMBER>())
        .then_some(n.DeviceNumber)
}

/// The disk Windows itself runs from, which is never offered.
fn system_disk() -> Option<u32> {
    let drive = std::env::var("SystemDrive").unwrap_or_else(|_| "C:".into());
    device_number(&open(&format!("\\\\.\\{drive}"), 0, 0)?)
}

/// USB disks big enough for Monet, never Windows' own.
pub fn sticks() -> Vec<Stick> {
    let system = system_disk();
    let mut found = Vec::new();
    for number in 0..32u32 {
        let Some(h) = open(&format!("\\\\.\\PhysicalDrive{number}"), 0, 0) else { continue };
        let mut query: STORAGE_PROPERTY_QUERY = unsafe { zeroed() };
        query.PropertyId = StorageDeviceProperty;
        query.QueryType = PropertyStandardQuery;
        let mut buf = vec![0u8; 1024];
        if !ioctl(&h, IOCTL_STORAGE_QUERY_PROPERTY, &query as *const _ as _, size_of::<STORAGE_PROPERTY_QUERY>(),
                  buf.as_mut_ptr() as _, buf.len()) {
            continue;
        }
        let desc = unsafe { &*(buf.as_ptr() as *const STORAGE_DEVICE_DESCRIPTOR) };
        if desc.BusType != BUS_USB || Some(number) == system {
            continue;
        }
        // The size, from a question that needs no read access (the drive is opened with none):
        // IOCTL_DISK_GET_LENGTH_INFO wants read access, so it failed for every disk and no stick showed.
        // The answer can run past DISK_GEOMETRY_EX (partition and detection details): room for those.
        let mut geometry = [0u64; 64];
        if !ioctl(&h, IOCTL_DISK_GET_DRIVE_GEOMETRY_EX, std::ptr::null(), 0, geometry.as_mut_ptr() as _,
                  size_of::<[u64; 64]>()) {
            continue;
        }
        let size = unsafe { (*(geometry.as_ptr() as *const DISK_GEOMETRY_EX)).DiskSize } as u64;
        if size < plan::MIN_STICK {
            continue;
        }
        let vendor = plan::descriptor_text(&buf, desc.VendorIdOffset);
        let product = plan::descriptor_text(&buf, desc.ProductIdOffset);
        found.push(Stick { number, label: plan::label(&vendor, &product, size) });
    }
    found
}

/// Why something went wrong, for whoever helps: Monet-USB-Stick.log in %TEMP%, with Windows' own error code.
fn note(what: &str) {
    let code = unsafe { GetLastError() };
    if let Ok(mut log) = OpenOptions::new().create(true).append(true).open(std::env::temp_dir().join("Monet-USB-Stick.log")) {
        let _ = writeln!(log, "{what}: Windows error {code}");
    }
}

fn write_at(disk: &Handle, data: &[u8], offset: u64) -> Result<(), String> {
    let mut wrote = 0u32;
    if unsafe { WriteFile(disk.0, data.as_ptr(), data.len() as u32, &mut wrote, null_mut()) } == 0
        || wrote as usize != data.len()
    {
        note(&format!("writing {} bytes at {offset}", data.len()));
        return Err(t!("Writing to the USB stick failed. Try another USB port or another stick.").into());
    }
    Ok(())
}

/// Writes the image at `iso` onto disk `number`, then reads it back to check.
/// `progress(phase, done, total)`: phase 0 writing, 1 checking.
pub fn write(number: u32, iso: &str, mut progress: impl FnMut(u32, u64, u64)) -> Result<(), String> {
    // Windows mustn't touch the stick's old volumes while it's written: lock
    // and dismount each (the handles stay open until the end).
    let mut volumes = Vec::new();
    for letter in b'A'..=b'Z' {
        let path = format!("\\\\.\\{}:", letter as char);
        if let Some(v) = open(&path, GENERIC_READ | GENERIC_WRITE, 0) {
            if device_number(&v) == Some(number) {
                ioctl(&v, FSCTL_LOCK_VOLUME, std::ptr::null(), 0, null_mut(), 0);
                ioctl(&v, FSCTL_DISMOUNT_VOLUME, std::ptr::null(), 0, null_mut(), 0);
                volumes.push(v);
            }
        }
    }
    let Some(disk) = open(&format!("\\\\.\\PhysicalDrive{number}"), GENERIC_READ | GENERIC_WRITE, FILE_FLAG_WRITE_THROUGH)
    else {
        note(&format!("opening PhysicalDrive{number}"));
        return Err(t!("Windows didn't let Monet write to the USB stick. Take it out, put it back in, and try again.").into());
    };
    ioctl(&disk, IOCTL_DISK_DELETE_DRIVE_LAYOUT, std::ptr::null(), 0, null_mut(), 0);

    let total = std::fs::metadata(iso).map_err(|e| e.to_string())?.len();
    let mut buf = vec![0u8; CHUNK];
    let mut back = vec![0u8; CHUNK];
    for phase in 0..2u32 {
        let mut file = File::open(iso).map_err(|e| e.to_string())?;
        seek(&disk, 0)?;
        let mut done = 0u64;
        // The first piece, with the image's partition tables, is written last: once they're on
        // the stick Windows mounts the partitions it finds there, and then refuses writes into them.
        let mut head = Vec::new();
        loop {
            let n = read_full(&mut file, &mut buf)?;
            if n == 0 {
                break;
            }
            let len = plan::padded(n);
            buf[n..len].fill(0);
            if phase == 0 {
                if done == 0 {
                    head = buf[..len].to_vec();
                    seek(&disk, len as i64)?;
                } else {
                    write_at(&disk, &buf[..len], done)?;
                }
            } else {
                let mut got = 0u32;
                if unsafe { ReadFile(disk.0, back.as_mut_ptr(), len as u32, &mut got, null_mut()) } == 0
                    || got as usize != len
                    || back[..n] != buf[..n]
                {
                    note(&format!("checking {len} bytes at {done} (read {got})"));
                    return Err(t!("The USB stick didn't keep what was written. Try another stick.").into());
                }
            }
            done += n as u64;
            progress(phase, done, total);
        }
        if phase == 0 {
            seek(&disk, 0)?;
            write_at(&disk, &head, 0)?;
            unsafe { FlushFileBuffers(disk.0) };
        }
    }
    ioctl(&disk, IOCTL_DISK_UPDATE_PROPERTIES, std::ptr::null(), 0, null_mut(), 0);
    drop(volumes);
    Ok(())
}

fn seek(h: &Handle, to: i64) -> Result<(), String> {
    if unsafe { SetFilePointerEx(h.0, to, null_mut(), FILE_BEGIN) } == 0 {
        note(&format!("moving to {to}"));
        return Err(t!("The USB stick stopped answering.").into());
    }
    Ok(())
}

fn read_full(file: &mut File, buf: &mut [u8]) -> Result<usize, String> {
    let mut n = 0;
    while n < buf.len() {
        match file.read(&mut buf[n..]) {
            Ok(0) => break,
            Ok(k) => n += k,
            Err(e) => return Err(e.to_string()),
        }
    }
    Ok(n)
}

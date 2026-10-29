//! Windows disk discovery and exclusive access. The transfer sequence is tested separately.
use crate::{plan, writer};
use std::ffi::c_void;
use std::fs::{File, OpenOptions};
use std::io::{self, Read, Seek, SeekFrom, Write};
use std::mem::{size_of, size_of_val, zeroed};
use std::os::windows::fs::OpenOptionsExt;
use std::os::windows::io::AsRawHandle;
use std::ptr::null_mut;
use windows_sys::Win32::Foundation::{
    CloseHandle, GetLastError, ERROR_NO_MORE_FILES, GENERIC_READ, GENERIC_WRITE, HANDLE, INVALID_HANDLE_VALUE,
};
use windows_sys::Win32::Storage::FileSystem::{
    CreateFileW, FindFirstVolumeW, FindNextVolumeW, FindVolumeClose, FILE_FLAG_NO_BUFFERING, FILE_SHARE_READ,
    FILE_SHARE_WRITE, OPEN_EXISTING,
};
use windows_sys::Win32::System::Ioctl::*;
use windows_sys::Win32::System::SystemInformation::GetWindowsDirectoryW;
use windows_sys::Win32::System::IO::DeviceIoControl;

#[derive(Clone)]
pub struct Stick {
    pub target: plan::Target,
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
struct VolumeSearch(HANDLE);
impl Drop for VolumeSearch {
    fn drop(&mut self) {
        unsafe { FindVolumeClose(self.0) };
    }
}

fn open(path: &str, access: u32, flags: u32) -> io::Result<Handle> {
    let path = wide(path);
    let h = unsafe {
        CreateFileW(
            path.as_ptr(),
            access,
            FILE_SHARE_READ | FILE_SHARE_WRITE,
            null_mut(),
            OPEN_EXISTING,
            flags,
            null_mut(),
        )
    };
    if h == INVALID_HANDLE_VALUE {
        Err(io::Error::last_os_error())
    } else {
        Ok(Handle(h))
    }
}

fn ioctl(
    h: HANDLE,
    code: u32,
    input: *const c_void,
    in_len: usize,
    out: *mut c_void,
    out_len: usize,
) -> io::Result<usize> {
    let mut got = 0;
    if unsafe { DeviceIoControl(h, code, input, in_len as u32, out, out_len as u32, &mut got, null_mut()) } == 0 {
        Err(io::Error::last_os_error())
    } else {
        Ok(got as usize)
    }
}
fn control(h: HANDLE, code: u32) -> io::Result<()> {
    ioctl(h, code, std::ptr::null(), 0, null_mut(), 0).map(|_| ())
}
fn device_number(h: HANDLE) -> io::Result<u32> {
    let mut n: STORAGE_DEVICE_NUMBER = unsafe { zeroed() };
    if ioctl(
        h,
        IOCTL_STORAGE_GET_DEVICE_NUMBER,
        std::ptr::null(),
        0,
        &mut n as *mut _ as _,
        size_of::<STORAGE_DEVICE_NUMBER>(),
    )? < size_of::<STORAGE_DEVICE_NUMBER>()
    {
        return Err(io::Error::other("Windows returned an incomplete disk number."));
    }
    Ok(n.DeviceNumber)
}

fn system_disk() -> io::Result<u32> {
    let mut path = [0u16; 32768];
    let n = unsafe { GetWindowsDirectoryW(path.as_mut_ptr(), path.len() as u32) } as usize;
    if n < 3 || n >= path.len() || path[1] != b':' as u16 {
        return Err(io::Error::other(t!("Windows' system disk could not be identified.")));
    }
    device_number(open(&format!("\\\\.\\{}", String::from_utf16_lossy(&path[..2])), 0, 0)?.0)
}

fn describe(h: HANDLE) -> io::Result<Stick> {
    let mut query: STORAGE_PROPERTY_QUERY = unsafe { zeroed() };
    query.PropertyId = StorageDeviceProperty;
    query.QueryType = PropertyStandardQuery;
    // Storage descriptors contain integers: keep the buffer aligned and check the returned length.
    let mut storage = [0u64; 128];
    let got = ioctl(
        h,
        IOCTL_STORAGE_QUERY_PROPERTY,
        &query as *const _ as _,
        size_of::<STORAGE_PROPERTY_QUERY>(),
        storage.as_mut_ptr() as _,
        size_of_val(&storage),
    )?;
    if got < size_of::<STORAGE_DEVICE_DESCRIPTOR>() || got > size_of_val(&storage) {
        return Err(io::Error::other("Windows returned an incomplete device description."));
    }
    let desc = unsafe { &*(storage.as_ptr() as *const STORAGE_DEVICE_DESCRIPTOR) };
    let bytes = unsafe { std::slice::from_raw_parts(storage.as_ptr() as *const u8, got) };
    let mut geometry = [0u64; 64];
    let got = ioctl(
        h,
        IOCTL_DISK_GET_DRIVE_GEOMETRY_EX,
        std::ptr::null(),
        0,
        geometry.as_mut_ptr() as _,
        size_of_val(&geometry),
    )?;
    if got < size_of::<DISK_GEOMETRY_EX>() {
        return Err(io::Error::other("Windows returned an incomplete disk size."));
    }
    let geometry = unsafe { &*(geometry.as_ptr() as *const DISK_GEOMETRY_EX) };
    let mut identity: STORAGE_DEVICE_NUMBER_EX = unsafe { zeroed() };
    let got = ioctl(
        h,
        IOCTL_STORAGE_GET_DEVICE_NUMBER_EX,
        std::ptr::null(),
        0,
        &mut identity as *mut _ as _,
        size_of::<STORAGE_DEVICE_NUMBER_EX>(),
    )?;
    let guid = identity.DeviceGuid;
    let id = (guid.data1 as u128) << 96
        | (guid.data2 as u128) << 80
        | (guid.data3 as u128) << 64
        | u64::from_be_bytes(guid.data4) as u128;
    if got < size_of::<STORAGE_DEVICE_NUMBER_EX>() || id == 0 || geometry.DiskSize <= 0 {
        return Err(io::Error::other(t!("This device could not be identified safely.")));
    }
    let target = plan::Target {
        number: identity.DeviceNumber,
        id,
        bytes: geometry.DiskSize as u64,
        sector: geometry.Geometry.BytesPerSector,
        usb: desc.BusType == 7,
    };
    let label = plan::label(
        &plan::descriptor_text(bytes, desc.VendorIdOffset),
        &plan::descriptor_text(bytes, desc.ProductIdOffset),
        target.bytes,
    );
    Ok(Stick {
        target,
        label: format!("{label} · Disk {}", target.number),
    })
}

pub fn sticks() -> Vec<Stick> {
    let Ok(system) = system_disk() else { return Vec::new() };
    let mut found = Vec::new();
    for number in 0..32u32 {
        let Ok(h) = open(&format!("\\\\.\\PhysicalDrive{number}"), 0, 0) else {
            continue;
        };
        let Ok(stick) = describe(h.0) else { continue };
        if stick.target.usb && stick.target.number != system && stick.target.bytes >= plan::MIN_STICK {
            found.push(stick);
        }
    }
    found
}

/// Lock everything first. A veto must never be followed by a forced dismount.
fn lock_volumes(number: u32) -> io::Result<Vec<Handle>> {
    let mut name = [0u16; 64];
    let h = unsafe { FindFirstVolumeW(name.as_mut_ptr(), name.len() as u32) };
    if h == INVALID_HANDLE_VALUE {
        return Err(io::Error::last_os_error());
    }
    let _search = VolumeSearch(h);
    let mut locked = Vec::new();
    loop {
        let len = name.iter().position(|c| *c == 0).unwrap_or(name.len());
        let path = String::from_utf16_lossy(&name[..len]);
        let path = path.trim_end_matches('\\');
        // Query before requesting write access: unrelated protected volumes are not locked.
        let volume = open(path, 0, 0)?;
        if device_number(volume.0)? == number {
            let volume = open(path, GENERIC_READ | GENERIC_WRITE, 0)?;
            if device_number(volume.0)? != number {
                return Err(io::Error::other("The device changed while locking it."));
            }
            control(volume.0, FSCTL_LOCK_VOLUME).map_err(|e| {
                io::Error::other(format!(
                    "{} {e}",
                    t!("The USB device is in use or protected. Close its files and try again. Nothing was written.")
                ))
            })?;
            locked.push(volume);
        }
        if unsafe { FindNextVolumeW(h, name.as_mut_ptr(), name.len() as u32) } == 0 {
            if unsafe { GetLastError() } != ERROR_NO_MORE_FILES {
                return Err(io::Error::last_os_error());
            }
            break;
        }
    }
    for volume in &locked {
        control(volume.0, FSCTL_DISMOUNT_VOLUME)?;
    }
    Ok(locked)
}

struct Disk {
    file: File,
    selected: plan::Target,
    volumes: Vec<Handle>,
}
impl Read for Disk {
    fn read(&mut self, buf: &mut [u8]) -> io::Result<usize> {
        self.file.read(buf)
    }
}
impl Write for Disk {
    fn write(&mut self, buf: &[u8]) -> io::Result<usize> {
        self.file.write(buf)
    }
    fn flush(&mut self) -> io::Result<()> {
        self.file.flush()
    }
}
impl Seek for Disk {
    fn seek(&mut self, pos: SeekFrom) -> io::Result<u64> {
        self.file.seek(pos)
    }
}
impl Disk {
    fn validate(&self, total: u64) -> io::Result<()> {
        let current = describe(self.file.as_raw_handle() as HANDLE)?.target;
        plan::check_target(self.selected, current, system_disk().ok(), total).map_err(io::Error::other)
    }
}
impl writer::Destination for Disk {
    fn prepare(&mut self, total: u64) -> io::Result<()> {
        self.validate(total)?;
        self.volumes = lock_volumes(self.selected.number)?;
        self.validate(total)
    }
    fn sync_media(&mut self) -> io::Result<()> {
        self.file.sync_all().map_err(|e| {
            io::Error::other(format!(
                "{} {e}",
                t!("Windows could not finish writing the USB device. It is not ready to use.")
            ))
        })
    }
}

pub fn write(stick: &Stick, image: &mut File, progress: impl FnMut(u32, u64, u64)) -> Result<(), String> {
    let result = (|| -> io::Result<()> {
        let total = image.metadata()?.len();
        // Deny other raw writers even when a blank device has no volumes to lock.
        let file = OpenOptions::new()
            .read(true)
            .write(true)
            .share_mode(FILE_SHARE_READ)
            .custom_flags(FILE_FLAG_NO_BUFFERING)
            .open(format!("\\\\.\\PhysicalDrive{}", stick.target.number))?;
        let mut disk = Disk {
            file,
            selected: stick.target,
            volumes: Vec::new(),
        };
        writer::write(image, &mut disk, total, progress)?;
        control(disk.file.as_raw_handle() as HANDLE, IOCTL_DISK_UPDATE_PROPERTIES)?;
        Ok(())
    })();
    if let Err(error) = &result {
        if let Ok(mut log) = OpenOptions::new()
            .create(true)
            .append(true)
            .open(std::env::temp_dir().join("Monet-USB-Stick.log"))
        {
            let _ = writeln!(log, "Disk {}: {error}", stick.target.number);
        }
    }
    result.map_err(|e| e.to_string())
}

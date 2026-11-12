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
    CloseHandle, GetLastError, ERROR_ACCESS_DENIED, ERROR_LOCK_VIOLATION, ERROR_NOT_READY, ERROR_NO_MORE_FILES,
    ERROR_SHARING_VIOLATION, GENERIC_READ, GENERIC_WRITE, HANDLE, INVALID_HANDLE_VALUE,
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

/// Lock every old volume before changing anything, including partitions without a drive letter.
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
        let volume = open(path, 0, 0).map_err(|e| io::Error::other(format!("Opening {path}: {e}")))?;
        if device_number(volume.0)? == number {
            let volume = open(path, GENERIC_READ | GENERIC_WRITE, 0)
                .map_err(|e| io::Error::other(format!("Opening {path} for locking: {e}")))?;
            if device_number(volume.0)? != number {
                return Err(io::Error::other("The device changed while locking it."));
            }
            when_available(&[ERROR_ACCESS_DENIED, ERROR_SHARING_VIOLATION, ERROR_LOCK_VIOLATION],
                || control(volume.0, FSCTL_LOCK_VOLUME)).map_err(|e| {
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
    Ok(locked)
}

struct Disk {
    file: Option<File>,
    selected: plan::Target,
    volumes: Vec<Handle>,
    layout_change_started: bool,
}
impl Read for Disk {
    fn read(&mut self, buf: &mut [u8]) -> io::Result<usize> {
        self.file.as_mut().unwrap().read(buf)
            .map_err(|e| io::Error::new(e.kind(), format!("Reading the USB device: {e}")))
    }
}
impl Write for Disk {
    fn write(&mut self, buf: &[u8]) -> io::Result<usize> {
        self.file.as_mut().unwrap().write(buf)
            .map_err(|e| io::Error::new(e.kind(), format!("Writing the USB device: {e}")))
    }
    fn flush(&mut self) -> io::Result<()> {
        self.file.as_mut().unwrap().flush()
    }
}
impl Seek for Disk {
    fn seek(&mut self, pos: SeekFrom) -> io::Result<u64> {
        self.file.as_mut().unwrap().seek(pos)
            .map_err(|e| io::Error::new(e.kind(), format!("Seeking on the USB device: {e}")))
    }
}
fn validate(file: &File, selected: plan::Target, total: u64) -> io::Result<()> {
    let current = describe(file.as_raw_handle() as HANDLE)?.target;
    plan::check_target(selected, current, system_disk().ok(), total).map_err(io::Error::other)
}

fn when_available<T>(transient: &[u32], mut operation: impl FnMut() -> io::Result<T>) -> io::Result<T> {
    for attempt in 0..50 {
        match operation() {
            Err(error) if error.raw_os_error().is_some_and(|code| transient.contains(&(code as u32))) && attempt < 49 => {
                std::thread::sleep(std::time::Duration::from_millis(200));
            }
            result => return result,
        }
    }
    unreachable!()
}

fn open_disk(selected: plan::Target, total: u64) -> io::Result<File> {
    when_available(&[ERROR_NOT_READY], || {
        // Deny other raw writers, including on a blank device with no volumes to lock.
        let file = OpenOptions::new().read(true).write(true).share_mode(FILE_SHARE_READ)
            .custom_flags(FILE_FLAG_NO_BUFFERING)
            .open(format!("\\\\.\\PhysicalDrive{}", selected.number))?;
        validate(&file, selected, total)?;
        Ok(file)
    }).map_err(|e| io::Error::other(format!("Opening and validating physical Disk {}: {e}", selected.number)))
}

impl Disk {
    fn reopen(&mut self, total: u64) -> io::Result<()> {
        self.volumes.clear();
        self.file.take();
        self.file = Some(open_disk(self.selected, total)?);
        Ok(())
    }
}
impl writer::Destination for Disk {
    fn prepare(&mut self, total: u64) -> io::Result<u64> {
        validate(self.file.as_ref().unwrap(), self.selected, total)?;
        self.volumes = lock_volumes(self.selected.number)?;
        validate(self.file.as_ref().unwrap(), self.selected, total)?;
        Ok(self.selected.bytes)
    }
    fn reset_layout(&mut self, total: u64) -> io::Result<()> {
        validate(self.file.as_ref().unwrap(), self.selected, total)?;
        let handle = self.file.as_ref().unwrap().as_raw_handle() as HANDLE;
        // Locked volumes already permit raw writes; ISO/Linux partitions need not support dismount.
        // Windows clears both GPT headers too, so an old backup table cannot revive stale partitions.
        self.layout_change_started = true;
        control(handle, IOCTL_DISK_DELETE_DRIVE_LAYOUT).map_err(|e| {
            io::Error::other(format!("Clearing Disk {}'s old partition layout: {e}", self.selected.number))
        })?;
        self.volumes.clear();
        // Removable disks can reject writes with ERROR_NOT_READY until an empty MBR is initialized.
        let empty = CREATE_DISK {
            PartitionStyle: PARTITION_STYLE_MBR,
            Anonymous: CREATE_DISK_0 {
                Mbr: CREATE_DISK_MBR { Signature: (self.selected.id as u32).max(1) },
            },
        };
        ioctl(handle, IOCTL_DISK_CREATE_DISK, &empty as *const _ as _, size_of::<CREATE_DISK>(), null_mut(), 0)
            .map_err(|e| io::Error::other(format!("Initializing Disk {} for writing: {e}", self.selected.number)))?;
        control(handle, IOCTL_DISK_UPDATE_PROPERTIES).map_err(|e| {
            io::Error::other(format!("Refreshing Disk {} after clearing its partition layout: {e}", self.selected.number))
        })?;
        // Partition refresh invalidates old volume handles; wait for the same physical device to return.
        self.reopen(total)
    }
    fn sync_media(&mut self) -> io::Result<()> {
        self.file.as_ref().unwrap().sync_all().map_err(|e| {
            io::Error::other(format!(
                "{} {e}",
                t!("Windows could not finish writing the USB device. It is not ready to use.")
            ))
        })
    }
}

pub struct WriteError {
    pub message: String,
    pub layout_change_started: bool,
}

pub fn write(stick: &Stick, image: &mut File, progress: impl FnMut(u32, u64, u64)) -> Result<(), WriteError> {
    let mut disk = Disk {
        file: None,
        selected: stick.target,
        volumes: Vec::new(),
        layout_change_started: false,
    };
    let result = (|| -> io::Result<()> {
        let total = image.metadata()?.len();
        disk.file = Some(open_disk(stick.target, total)?);
        writer::write(image, &mut disk, total, progress)?;
        disk.reopen(total)?;
        control(disk.file.as_ref().unwrap().as_raw_handle() as HANDLE, IOCTL_DISK_UPDATE_PROPERTIES)
            .map_err(|e| io::Error::other(format!("Refreshing Disk {} after verification: {e}", stick.target.number)))?;
        Ok(())
    })();
    let layout_change_started = disk.layout_change_started;
    drop(disk);
    if let Err(error) = &result {
        if let Ok(mut log) = OpenOptions::new()
            .create(true)
            .append(true)
            .open(std::env::temp_dir().join("Monet-USB-Stick.log"))
        {
            let _ = writeln!(log, "Disk {}: {error}", stick.target.number);
        }
    }
    result.map_err(|error| WriteError {
        message: error.to_string(),
        layout_change_started,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn reenumeration_waits_for_readiness_but_never_ignores_a_changed_or_protected_disk() {
        let mut attempts = 0;
        let ready = when_available(&[ERROR_NOT_READY], || {
            attempts += 1;
            if attempts == 1 { Err(io::Error::from_raw_os_error(ERROR_NOT_READY as i32)) }
            else { Ok(42) }
        }).unwrap();
        assert_eq!((ready, attempts), (42, 2));
        for error in [io::Error::from_raw_os_error(5), io::Error::other("selected device changed")] {
            let mut error = Some(error);
            let mut attempts = 0;
            assert!(when_available::<()>(&[ERROR_NOT_READY], || {
                attempts += 1;
                Err(error.take().expect("permission and identity failures must not be retried"))
            }).is_err());
            assert_eq!(attempts, 1);
        }
        let mut attempts = 0;
        when_available(&[ERROR_ACCESS_DENIED, ERROR_SHARING_VIOLATION, ERROR_LOCK_VIOLATION], || {
            attempts += 1;
            match attempts {
                1 => Err(io::Error::from_raw_os_error(ERROR_ACCESS_DENIED as i32)),
                2 => Err(io::Error::from_raw_os_error(ERROR_SHARING_VIOLATION as i32)),
                _ => Ok(()),
            }
        }).unwrap();
        assert_eq!(attempts, 3);
    }
}

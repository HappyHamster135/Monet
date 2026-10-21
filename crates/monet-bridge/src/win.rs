//! Thin, safe wrappers around the Win32 calls Monet Bridge needs.

use std::ffi::OsString;
use std::os::windows::ffi::OsStringExt;
use std::os::windows::process::CommandExt;
use std::path::PathBuf;
use std::process::Command;
use std::ptr::{null, null_mut};

use monet_core::efi::{EfiError, EfiVars, Result};
use windows_sys::Win32::Foundation::{
    CloseHandle, GetLastError, ERROR_ALREADY_EXISTS, ERROR_ENVVAR_NOT_FOUND, ERROR_INVALID_FUNCTION,
    ERROR_NOT_ALL_ASSIGNED, ERROR_PRIVILEGE_NOT_HELD, HANDLE, INVALID_HANDLE_VALUE, LUID,
};
use windows_sys::Win32::Security::{
    AdjustTokenPrivileges, LookupPrivilegeValueW, LUID_AND_ATTRIBUTES, SE_PRIVILEGE_ENABLED, TOKEN_ADJUST_PRIVILEGES,
    TOKEN_PRIVILEGES, TOKEN_QUERY,
};
use windows_sys::Win32::Storage::FileSystem::GetLogicalDrives;
use windows_sys::Win32::System::Console::{AttachConsole, ATTACH_PARENT_PROCESS};
use windows_sys::Win32::System::Diagnostics::ToolHelp::{
    CreateToolhelp32Snapshot, Process32FirstW, Process32NextW, PROCESSENTRY32W, TH32CS_SNAPPROCESS,
};
use windows_sys::Win32::System::Registry::{RegGetValueW, HKEY, HKEY_CURRENT_USER, HKEY_LOCAL_MACHINE, RRF_RT_REG_SZ};
use windows_sys::Win32::System::Threading::{
    CreateMutexW, GetCurrentProcess, OpenProcess, OpenProcessToken, QueryFullProcessImageNameW,
    PROCESS_NAME_WIN32, PROCESS_QUERY_LIMITED_INFORMATION,
};
use windows_sys::Win32::System::WindowsProgramming::{
    GetFirmwareEnvironmentVariableExW, SetFirmwareEnvironmentVariableExW,
};
use windows_sys::Win32::UI::Shell::ShellExecuteW;
use windows_sys::Win32::UI::WindowsAndMessaging::{
    MB_ICONINFORMATION, MB_OKCANCEL, MB_SETFOREGROUND, MB_TOPMOST, SW_SHOWNORMAL,
};

windows_link::link!("user32.dll" "system" fn MessageBoxTimeoutW(hwnd: *mut core::ffi::c_void, text: *const u16, caption: *const u16, utype: u32, language: u16, milliseconds: u32) -> i32);

pub const CREATE_NO_WINDOW: u32 = 0x0800_0000;

pub fn wide(s: &str) -> Vec<u16> {
    s.encode_utf16().chain(std::iter::once(0)).collect()
}

/// Shows console output when started from a terminal. Monet Bridge is a GUI
/// program so it never flashes a window when started in the background.
pub fn attach_console() {
    // SAFETY: no preconditions; failure just means there is no console.
    unsafe {
        AttachConsole(ATTACH_PARENT_PROCESS);
    }
}

/// Runs a system tool without showing a console window.
pub fn run_hidden(program: &str, args: &[&str]) -> bool {
    Command::new(program)
        .args(args)
        .creation_flags(CREATE_NO_WINDOW)
        .status()
        .map(|s| s.success())
        .unwrap_or(false)
}

// ------------------------------------------------------------- privileges

/// Enables a privilege on our own token. Returns false when the process
/// doesn't hold it, which means it isn't running as administrator.
pub fn enable_privilege(name: &str) -> bool {
    // SAFETY: standard token adjustment with locally owned buffers; the
    // token handle is closed before returning.
    unsafe {
        let mut token: HANDLE = null_mut();
        if OpenProcessToken(GetCurrentProcess(), TOKEN_ADJUST_PRIVILEGES | TOKEN_QUERY, &mut token) == 0 {
            return false;
        }
        let mut luid = LUID { LowPart: 0, HighPart: 0 };
        let name = wide(name);
        let mut ok = LookupPrivilegeValueW(null(), name.as_ptr(), &mut luid) != 0;
        if ok {
            let privileges = TOKEN_PRIVILEGES {
                PrivilegeCount: 1,
                Privileges: [LUID_AND_ATTRIBUTES { Luid: luid, Attributes: SE_PRIVILEGE_ENABLED }],
            };
            ok = AdjustTokenPrivileges(token, 0, &privileges, 0, null_mut(), null_mut()) != 0
                && GetLastError() != ERROR_NOT_ALL_ASSIGNED;
        }
        CloseHandle(token);
        ok
    }
}

/// Needed to read and write UEFI variables.
pub fn enable_firmware_access() -> bool {
    enable_privilege("SeSystemEnvironmentPrivilege")
}

/// A named mutex so only one agent runs per session. Returns false if another
/// instance already holds it. The handle is kept for the process lifetime.
pub fn single_instance(name: &str) -> bool {
    let name = wide(name);
    // SAFETY: creating a named mutex with default security.
    unsafe {
        let handle = CreateMutexW(null(), 1, name.as_ptr());
        !handle.is_null() && GetLastError() != ERROR_ALREADY_EXISTS
    }
}

// ------------------------------------------------------------- UEFI variables

pub struct FirmwareVars;

fn guid_braced(guid: &str) -> Vec<u16> {
    wide(&format!("{{{guid}}}"))
}

fn last_efi_error() -> EfiError {
    // SAFETY: reads the calling thread's last error.
    match unsafe { GetLastError() } {
        ERROR_ENVVAR_NOT_FOUND => EfiError::NotFound,
        ERROR_INVALID_FUNCTION => EfiError::Unsupported,
        ERROR_PRIVILEGE_NOT_HELD => EfiError::PermissionDenied,
        code => EfiError::Io(format!("Windows error {code}")),
    }
}

impl EfiVars for FirmwareVars {
    fn get(&self, guid: &str, name: &str) -> Result<Vec<u8>> {
        let (name, guid) = (wide(name), guid_braced(guid));
        let mut buf = vec![0u8; 8192];
        let mut attributes = 0u32;
        // SAFETY: buffer pointer and length match; strings are NUL-terminated.
        let size = unsafe {
            GetFirmwareEnvironmentVariableExW(
                name.as_ptr(),
                guid.as_ptr(),
                buf.as_mut_ptr().cast(),
                buf.len() as u32,
                &mut attributes,
            )
        };
        if size == 0 {
            return Err(last_efi_error());
        }
        buf.truncate(size as usize);
        Ok(buf)
    }

    fn set(&mut self, guid: &str, name: &str, data: &[u8], attributes: u32) -> Result<()> {
        let (name, guid) = (wide(name), guid_braced(guid));
        // SAFETY: data pointer and length match; strings are NUL-terminated.
        let ok = unsafe {
            SetFirmwareEnvironmentVariableExW(
                name.as_ptr(),
                guid.as_ptr(),
                data.as_ptr().cast(),
                data.len() as u32,
                attributes,
            )
        };
        if ok == 0 {
            Err(last_efi_error())
        } else {
            Ok(())
        }
    }

    fn delete(&mut self, guid: &str, name: &str) -> Result<()> {
        // Writing zero bytes deletes a variable.
        self.set(guid, name, &[], monet_core::efi::ATTR_DEFAULT)
    }
}

// ------------------------------------------------------------- processes

pub struct Process {
    pub exe_name: String,
    /// Full path, when Windows lets us read it.
    pub path: Option<PathBuf>,
}

pub fn processes() -> Vec<Process> {
    let mut out = Vec::new();
    // SAFETY: snapshot walk with a correctly sized PROCESSENTRY32W; every
    // opened handle is closed.
    unsafe {
        let snapshot = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
        if snapshot == INVALID_HANDLE_VALUE {
            return out;
        }
        let mut entry: PROCESSENTRY32W = std::mem::zeroed();
        entry.dwSize = std::mem::size_of::<PROCESSENTRY32W>() as u32;
        let mut more = Process32FirstW(snapshot, &mut entry) != 0;
        while more {
            let len = entry.szExeFile.iter().position(|c| *c == 0).unwrap_or(entry.szExeFile.len());
            let exe_name = String::from_utf16_lossy(&entry.szExeFile[..len]);
            out.push(Process { exe_name, path: process_path(entry.th32ProcessID) });
            more = Process32NextW(snapshot, &mut entry) != 0;
        }
        CloseHandle(snapshot);
    }
    out
}

fn process_path(pid: u32) -> Option<PathBuf> {
    // SAFETY: limited query access; the handle is closed before returning.
    unsafe {
        let handle = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, 0, pid);
        if handle.is_null() {
            return None;
        }
        let mut buf = [0u16; 1024];
        let mut len = buf.len() as u32;
        let ok = QueryFullProcessImageNameW(handle, PROCESS_NAME_WIN32, buf.as_mut_ptr(), &mut len) != 0;
        CloseHandle(handle);
        ok.then(|| PathBuf::from(OsString::from_wide(&buf[..len as usize])))
    }
}

// ------------------------------------------------------------- registry

fn reg_string(root: HKEY, key: &str, value: &str) -> Option<String> {
    let (key, value) = (wide(key), wide(value));
    let mut buf = vec![0u16; 1024];
    let mut size = (buf.len() * 2) as u32;
    // SAFETY: buffer size is given in bytes as RegGetValueW expects.
    let status = unsafe {
        RegGetValueW(root, key.as_ptr(), value.as_ptr(), RRF_RT_REG_SZ, null_mut(), buf.as_mut_ptr().cast(), &mut size)
    };
    if status != 0 {
        return None;
    }
    let len = buf.iter().position(|c| *c == 0).unwrap_or(buf.len());
    Some(String::from_utf16_lossy(&buf[..len]))
}

pub fn reg_machine(key: &str, value: &str) -> Option<String> {
    reg_string(HKEY_LOCAL_MACHINE, key, value)
}

pub fn reg_user(key: &str, value: &str) -> Option<String> {
    reg_string(HKEY_CURRENT_USER, key, value)
}

// ------------------------------------------------------------- shell and UI

/// Opens a URI (steam://, com.epicgames.launcher://) with its registered app.
pub fn open_uri(uri: &str) -> bool {
    let (verb, file) = (wide("open"), wide(uri));
    // SAFETY: all strings are NUL-terminated; the result is only compared.
    let result = unsafe { ShellExecuteW(null_mut(), verb.as_ptr(), file.as_ptr(), null(), null(), SW_SHOWNORMAL) };
    result as isize > 32
}

pub enum Answer {
    Yes,
    No,
    TimedOut,
}

/// A message box with OK and Cancel that answers itself after a timeout.
pub fn ask_with_timeout(text: &str, seconds: u32) -> Answer {
    let (text, caption) = (wide(text), wide("Monet"));
    // SAFETY: strings are NUL-terminated; no owner window.
    let result = unsafe {
        MessageBoxTimeoutW(
            null_mut(),
            text.as_ptr(),
            caption.as_ptr(),
            MB_OKCANCEL | MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND,
            0,
            seconds * 1000,
        )
    };
    match result {
        1 => Answer::Yes,
        32000 => Answer::TimedOut,
        _ => Answer::No,
    }
}

/// A free drive letter for temporarily mounting the EFI partition.
pub fn free_drive_letter() -> Option<char> {
    // SAFETY: no arguments.
    let used = unsafe { GetLogicalDrives() };
    ('M'..='Z').rev().find(|c| used & (1 << (*c as u32 - 'A' as u32)) == 0)
}

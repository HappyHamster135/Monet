//! The window: Monet's paper, a title, the sticks, a progress bar, two buttons.
//! The work happens on another thread, which posts WM_APP when there's news.

use std::os::windows::process::CommandExt;
use std::process::Command;
use std::ptr::{null, null_mut};
use std::sync::atomic::{AtomicIsize, Ordering};
use std::sync::Mutex;
use std::time::{Duration, Instant};

use windows_sys::core::{w, PCWSTR};
use windows_sys::Win32::Foundation::{HWND, LPARAM, LRESULT, WPARAM};
use windows_sys::Win32::Graphics::Gdi::{
    CreateFontW, CreateSolidBrush, SetBkMode, SetTextColor, CLEARTYPE_QUALITY, CLIP_DEFAULT_PRECIS, DEFAULT_CHARSET,
    FF_SWISS, HDC, OUT_DEFAULT_PRECIS, TRANSPARENT,
};
use windows_sys::Win32::System::LibraryLoader::GetModuleHandleW;
use windows_sys::Win32::UI::Controls::{
    InitCommonControlsEx, ICC_PROGRESS_CLASS, ICC_STANDARD_CLASSES, INITCOMMONCONTROLSEX, PBM_SETPOS, PBM_SETRANGE32,
};
use windows_sys::Win32::UI::HiDpi::GetDpiForSystem;
use windows_sys::Win32::UI::Input::KeyboardAndMouse::EnableWindow;
use windows_sys::Win32::UI::WindowsAndMessaging::*;

use crate::{disk, plan};

const VERSION: &str = env!("CARGO_PKG_VERSION");
const ID_STICKS: usize = 10;
const ID_MAKE: usize = 11;
const ID_CLOSE: usize = 12;
const PAPER: u32 = 0x00F7FAFB; // #FBFAF7 (COLORREF is 0x00BBGGRR)
const INK: u32 = 0x00191B1C;
const DIM: u32 = 0x00626B6B;

static MAIN: AtomicIsize = AtomicIsize::new(0);
// One paper brush for the window and its labels (a new one per repaint leaked).
static PAPER_BRUSH: AtomicIsize = AtomicIsize::new(0);
static CONTROLS: Mutex<Vec<isize>> = Mutex::new(Vec::new()); // title, text, sticks, bar, status, make, close
static NEWS: Mutex<News> = Mutex::new(News { text: String::new(), fraction: 0.0, finished: None, busy: false });
static STICKS: Mutex<Vec<(u32, String)>> = Mutex::new(Vec::new());

struct News {
    text: String,
    fraction: f64,
    finished: Option<Result<(), String>>,
    busy: bool,
}

fn wide(s: &str) -> Vec<u16> {
    s.encode_utf16().chain(Some(0)).collect()
}

/// A control by its place in CONTROLS, or none while they're still being made:
/// Windows asks about a label's colors as soon as it gets its font, before the
/// list is filled in (indexing the empty list there ended the program).
fn control(i: usize) -> HWND {
    CONTROLS.lock().unwrap().get(i).copied().unwrap_or(0) as HWND
}

fn tell(text: String, fraction: f64) {
    {
        let mut news = NEWS.lock().unwrap();
        news.text = text;
        news.fraction = fraction;
    }
    unsafe { PostMessageW(MAIN.load(Ordering::SeqCst) as HWND, WM_APP, 0, 0) };
}

fn finish(result: Result<(), String>) {
    {
        let mut news = NEWS.lock().unwrap();
        news.finished = Some(result);
        news.busy = false;
    }
    unsafe { PostMessageW(MAIN.load(Ordering::SeqCst) as HWND, WM_APP, 0, 0) };
}

pub fn run() {
    // Say what went wrong instead of vanishing: there's no console to print to.
    std::panic::set_hook(Box::new(|info| {
        let text = wide(&format!("Make a Monet USB stick stopped unexpectedly.\n\n{info}"));
        unsafe { MessageBoxW(null_mut(), text.as_ptr(), w!("Make a Monet USB stick"), MB_OK | MB_ICONERROR) };
    }));
    unsafe {
        let icc = INITCOMMONCONTROLSEX {
            dwSize: size_of::<INITCOMMONCONTROLSEX>() as u32,
            dwICC: ICC_PROGRESS_CLASS | ICC_STANDARD_CLASSES,
        };
        InitCommonControlsEx(&icc);
        let instance = GetModuleHandleW(null());
        let paper = CreateSolidBrush(PAPER);
        PAPER_BRUSH.store(paper as isize, Ordering::SeqCst);
        let class = w!("MonetUsb");
        let wc = WNDCLASSW {
            style: CS_HREDRAW | CS_VREDRAW,
            lpfnWndProc: Some(window_proc),
            cbClsExtra: 0,
            cbWndExtra: 0,
            hInstance: instance,
            hIcon: LoadIconW(instance, 1 as PCWSTR),
            hCursor: LoadCursorW(null_mut(), IDC_ARROW),
            hbrBackground: paper,
            lpszMenuName: null(),
            lpszClassName: class,
        };
        RegisterClassW(&wc);
        let s = GetDpiForSystem() as i32;
        let px = |n: i32| n * s / 96;
        let mut frame = windows_sys::Win32::Foundation::RECT { left: 0, top: 0, right: px(540), bottom: px(340) };
        let style = WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU | WS_MINIMIZEBOX;
        AdjustWindowRect(&mut frame, style, 0);
        let title = wide("Make a Monet USB stick");
        // Shown once its controls are all there, so it paints them right the first time.
        let hwnd = CreateWindowExW(0, class, title.as_ptr(), style, CW_USEDEFAULT, CW_USEDEFAULT,
                                   frame.right - frame.left, frame.bottom - frame.top, null_mut(), null_mut(),
                                   instance, null());
        MAIN.store(hwnd as isize, Ordering::SeqCst);

        let font = |size: i32, weight: i32| {
            CreateFontW(-px(size), 0, 0, 0, weight, 0, 0, 0, DEFAULT_CHARSET as u32, OUT_DEFAULT_PRECIS as u32,
                        CLIP_DEFAULT_PRECIS as u32, CLEARTYPE_QUALITY as u32, FF_SWISS as u32, w!("Segoe UI"))
        };
        let (big, body) = (font(24, 600), font(14, 400));
        let make = |class: PCWSTR, text: &str, style: u32, x: i32, y: i32, w: i32, h: i32, id: usize, f| {
            let text = wide(text);
            let c = CreateWindowExW(0, class, text.as_ptr(), WS_CHILD | WS_VISIBLE | style, px(x), px(y), px(w), px(h),
                                    hwnd, id as _, instance, null());
            SendMessageW(c, WM_SETFONT, f as usize, 1);
            c as isize
        };
        let controls = vec![
            make(w!("STATIC"), "Make a Monet USB stick", 0, 32, 26, 476, 40, 0, big),
            make(w!("STATIC"),
                 &format!("Monet {VERSION} installs from a USB stick of 2 GB or more. Choose the stick: everything on it is erased."),
                 0, 32, 74, 476, 44, 0, body),
            make(w!("COMBOBOX"), "", CBS_DROPDOWNLIST as u32 | WS_VSCROLL | WS_TABSTOP, 32, 130, 476, 200, ID_STICKS, body),
            make(w!("msctls_progress32"), "", 0, 32, 184, 476, 8, 0, body),
            make(w!("STATIC"), "", 0, 32, 202, 476, 44, 0, body),
            make(w!("BUTTON"), "Make USB stick", BS_DEFPUSHBUTTON as u32 | WS_TABSTOP, 348, 276, 160, 38, ID_MAKE, body),
            make(w!("BUTTON"), "Close", BS_PUSHBUTTON as u32 | WS_TABSTOP, 236, 276, 100, 38, ID_CLOSE, body),
        ];
        SendMessageW(controls[3] as HWND, PBM_SETRANGE32, 0, 1000);
        *CONTROLS.lock().unwrap() = controls;
        refresh_sticks();
        ShowWindow(hwnd, SW_SHOW);

        let mut msg: MSG = std::mem::zeroed();
        while GetMessageW(&mut msg, null_mut(), 0, 0) > 0 {
            if IsDialogMessageW(hwnd, &msg) == 0 {
                TranslateMessage(&msg);
                DispatchMessageW(&msg);
            }
        }
    }
}

fn refresh_sticks() {
    if NEWS.lock().unwrap().busy {
        return;
    }
    let found = disk::sticks();
    let combo = control(2);
    unsafe {
        SendMessageW(combo, CB_RESETCONTENT, 0, 0);
        for stick in &found {
            let label = wide(&stick.label);
            SendMessageW(combo, CB_ADDSTRING, 0, label.as_ptr() as isize);
        }
        if !found.is_empty() {
            SendMessageW(combo, CB_SETCURSEL, 0, 0);
        }
        EnableWindow(control(5), (!found.is_empty()) as i32);
        let text = if found.is_empty() { "Plug in a USB stick (2 GB or more)." } else { "" };
        let text = wide(text);
        SetWindowTextW(control(4), text.as_ptr());
    }
    *STICKS.lock().unwrap() = found.into_iter().map(|s| (s.number, s.label)).collect();
}

fn start(hwnd: HWND) {
    let choice = unsafe { SendMessageW(control(2), CB_GETCURSEL, 0, 0) };
    let Some((number, label)) = STICKS.lock().unwrap().get(choice.max(0) as usize).cloned() else { return };
    let question = wide(&format!("Everything on {label} will be erased.\n\nMake it a Monet USB stick?"));
    let answer = unsafe {
        MessageBoxW(hwnd, question.as_ptr(), w!("Make a Monet USB stick"), MB_OKCANCEL | MB_ICONWARNING | MB_DEFBUTTON2)
    };
    if answer != IDOK {
        return;
    }
    NEWS.lock().unwrap().busy = true;
    unsafe {
        EnableWindow(control(2), 0);
        EnableWindow(control(5), 0);
    }
    std::thread::spawn(move || {
        let mut iso = String::new();
        let result = installer().and_then(|(name, url, total)| {
            iso = std::env::temp_dir().join(name).to_string_lossy().to_string();
            download(&url, &iso, total)
        });
        let result = result.and_then(|()| {
            tell("Writing to the USB stick…".into(), 0.0);
            disk::write(number, &iso, |phase, done, total| {
                let f = done as f64 / total.max(1) as f64;
                let gb = |b: u64| b as f64 / 1e9;
                let what = if phase == 0 { "Writing" } else { "Checking" };
                tell(format!("{what} the USB stick · {:.1} of {:.1} GB", gb(done), gb(total)), f);
            })
        });
        if result.is_ok() {
            let _ = std::fs::remove_file(&iso);
        }
        finish(result);
    });
}

const NO_WINDOW: u32 = 0x0800_0000;

/// Windows' own curl.exe.
fn curl() -> Result<String, String> {
    let root = std::env::var("SystemRoot").unwrap_or_else(|_| "C:\\Windows".into());
    let curl = format!("{root}\\System32\\curl.exe");
    if !std::path::Path::new(&curl).exists() {
        return Err("This Windows can't download Monet by itself: it needs Windows 10 (2018) or newer.".into());
    }
    Ok(curl)
}

/// The best installer this release has, with its size: Monet Setup if it's
/// there, otherwise the other one.
fn installer() -> Result<(String, String, u64), String> {
    let curl = curl()?;
    tell("Getting ready to download Monet…".into(), 0.0);
    for name in plan::installer_names(VERSION) {
        let url = plan::release_url(VERSION, &name);
        let headers = Command::new(&curl).args(["-sIL", &url]).creation_flags(NO_WINDOW).output().map_err(|e| e.to_string())?;
        let headers = String::from_utf8_lossy(&headers.stdout);
        if plan::found(&headers) {
            return Ok((name, url, plan::content_length(&headers).unwrap_or(0)));
        }
    }
    Err("Monet couldn't be downloaded. Check the internet connection, then try again: it picks up where it stopped.".into())
}

/// Downloads with Windows' own curl.exe, which picks up where it stopped.
fn download(url: &str, dest: &str, total: u64) -> Result<(), String> {
    let curl = curl()?;
    let size = || std::fs::metadata(dest).map(|m| m.len()).unwrap_or(0);
    if total > 0 && size() == total {
        return Ok(());
    }
    for _ in 0..5 {
        let mut child = Command::new(&curl)
            .args(["-L", "--fail", "-s", "--retry", "5", "--retry-delay", "3", "-C", "-", "-o", dest, url])
            .creation_flags(NO_WINDOW)
            .spawn()
            .map_err(|e| e.to_string())?;
        let (start, first) = (Instant::now(), size());
        let status = loop {
            if let Some(status) = child.try_wait().map_err(|e| e.to_string())? {
                break status;
            }
            std::thread::sleep(Duration::from_millis(500));
            let got = size();
            let rate = (got.saturating_sub(first)) as f64 / start.elapsed().as_secs_f64().max(0.5);
            let mut line = format!("Downloading Monet · {:.1}", got as f64 / 1e9);
            if total > 0 {
                line += &format!(" of {:.1} GB", total as f64 / 1e9);
                if rate > 0.0 {
                    line += &format!(" · {}", plan::minutes_left((total - got.min(total)) as f64 / rate));
                }
            } else {
                line += " GB";
            }
            tell(line, if total > 0 { got as f64 / total as f64 } else { 0.0 });
        };
        if status.success() && (total == 0 || size() == total) {
            return Ok(());
        }
        tell("The connection dropped. Picking up where it stopped…".into(), 0.0);
        std::thread::sleep(Duration::from_secs(5));
    }
    Err("Monet couldn't be downloaded. Check the internet connection, then try again: it picks up where it stopped.".into())
}

unsafe extern "system" fn window_proc(hwnd: HWND, msg: u32, wparam: WPARAM, lparam: LPARAM) -> LRESULT {
    match msg {
        WM_COMMAND => {
            match wparam & 0xFFFF {
                ID_MAKE => start(hwnd),
                ID_CLOSE => {
                    PostMessageW(hwnd, WM_CLOSE, 0, 0);
                }
                _ => {}
            }
            0
        }
        WM_DEVICECHANGE => {
            refresh_sticks();
            1
        }
        WM_APP => {
            let (text, fraction, finished) = {
                let mut news = NEWS.lock().unwrap();
                (news.text.clone(), news.fraction, news.finished.take())
            };
            let t = wide(&text);
            SetWindowTextW(control(4), t.as_ptr());
            SendMessageW(control(3), PBM_SETPOS, (fraction.clamp(0.0, 1.0) * 1000.0) as usize, 0);
            if let Some(result) = finished {
                let (text, icon) = match &result {
                    Ok(()) => ("Your Monet USB stick is ready.\n\nRestart this PC with it plugged in, and choose the \
                                USB stick in the PC's boot menu.".to_string(), MB_ICONINFORMATION),
                    Err(e) => (e.clone(), MB_ICONERROR),
                };
                let t = wide(&text);
                MessageBoxW(hwnd, t.as_ptr(), w!("Make a Monet USB stick"), MB_OK | icon);
                SetWindowTextW(control(4), wide(if result.is_ok() { "Done." } else { "" }).as_ptr());
                EnableWindow(control(2), 1);
                refresh_sticks();
            }
            0
        }
        WM_CTLCOLORSTATIC => {
            let hdc = wparam as HDC;
            SetBkMode(hdc, TRANSPARENT as i32);
            SetTextColor(hdc, if lparam as HWND == control(0) { INK } else { DIM });
            PAPER_BRUSH.load(Ordering::SeqCst) as LRESULT
        }
        WM_CLOSE => {
            if NEWS.lock().unwrap().busy {
                let answer = MessageBoxW(hwnd, w!("The USB stick isn't finished. Stop anyway?"),
                                         w!("Make a Monet USB stick"), MB_YESNO | MB_ICONWARNING | MB_DEFBUTTON2);
                if answer != IDYES {
                    return 0;
                }
            }
            DestroyWindow(hwnd);
            0
        }
        WM_DESTROY => {
            PostQuitMessage(0);
            0
        }
        _ => DefWindowProcW(hwnd, msg, wparam, lparam),
    }
}

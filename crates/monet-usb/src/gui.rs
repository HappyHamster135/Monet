//! The window: Monet's paper, a title, the sticks, a progress bar, two buttons.
//! Disk discovery and writing run off the window thread.

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

use crate::words::{tr, trf};
use crate::{disk, image, plan};

const VERSION: &str = env!("CARGO_PKG_VERSION");
const ID_STICKS: usize = 10;
const ID_MAKE: usize = 11;
const ID_CLOSE: usize = 12;
const WM_STICKS_READY: u32 = WM_APP + 1;
const PAPER: u32 = 0x00F7FAFB; // #FBFAF7 (COLORREF is 0x00BBGGRR)
const INK: u32 = 0x00191B1C;
const DIM: u32 = 0x00626B6B;

static MAIN: AtomicIsize = AtomicIsize::new(0);
// One paper brush for the window and its labels (a new one per repaint leaked).
static PAPER_BRUSH: AtomicIsize = AtomicIsize::new(0);
static CONTROLS: Mutex<Vec<isize>> = Mutex::new(Vec::new()); // title, text, sticks, bar, status, make, close
static NEWS: Mutex<News> = Mutex::new(News {
    text: String::new(), fraction: 0.0, finished: None, busy: false, posted: false,
});
static STICKS: Mutex<Sticks> = Mutex::new(Sticks {
    listed: Vec::new(), scanning: false, changed: false, result: None,
});

struct News {
    text: String,
    fraction: f64,
    finished: Option<Result<(), String>>,
    busy: bool,
    posted: bool,
}

struct Sticks {
    listed: Vec<disk::Stick>,
    scanning: bool,
    changed: bool,
    result: Option<Vec<disk::Stick>>,
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

fn post_news(news: &mut News) {
    if !news.posted {
        news.posted = unsafe { PostMessageW(MAIN.load(Ordering::SeqCst) as HWND, WM_APP, 0, 0) } != 0;
    }
}

fn tell(text: String, fraction: f64) {
    let mut news = NEWS.lock().unwrap();
    news.text = text;
    news.fraction = fraction;
    post_news(&mut news);
}

fn finish(result: Result<(), String>) {
    let mut news = NEWS.lock().unwrap();
    news.finished = Some(result);
    post_news(&mut news);
}

pub fn run() {
    // Say what went wrong instead of vanishing: there's no console to print to.
    std::panic::set_hook(Box::new(|info| {
        let text = wide(&format!("{}\n\n{info}", tr("Make a Monet USB stick stopped unexpectedly.")));
        let title = wide(&tr("Make a Monet USB stick"));
        unsafe { MessageBoxW(null_mut(), text.as_ptr(), title.as_ptr(), MB_OK | MB_ICONERROR) };
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
        let title = wide(&tr("Make a Monet USB stick"));
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
            make(w!("STATIC"), &tr("Make a Monet USB stick"), 0, 32, 26, 476, 40, 0, big),
            make(w!("STATIC"),
                 &trf("Monet %1 installs from a USB stick of 2 GB or more. Choose the stick: everything on it is erased.",
                      &[VERSION]),
                 0, 32, 74, 476, 44, 0, body),
            make(w!("COMBOBOX"), "", CBS_DROPDOWNLIST as u32 | WS_VSCROLL | WS_TABSTOP, 32, 130, 476, 200, ID_STICKS, body),
            make(w!("msctls_progress32"), "", 0, 32, 184, 476, 8, 0, body),
            make(w!("STATIC"), "", 0, 32, 202, 476, 44, 0, body),
            make(w!("BUTTON"), &tr("Make USB stick"), BS_DEFPUSHBUTTON as u32 | WS_TABSTOP, 348, 276, 160, 38, ID_MAKE, body),
            make(w!("BUTTON"), &tr("Close"), BS_PUSHBUTTON as u32 | WS_TABSTOP, 236, 276, 100, 38, ID_CLOSE, body),
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
    if control(2).is_null() || NEWS.lock().unwrap().busy {
        return;
    }
    {
        let mut sticks = STICKS.lock().unwrap();
        if sticks.scanning {
            sticks.changed = true;
            return;
        }
        sticks.scanning = true;
    }
    unsafe {
        EnableWindow(control(2), 0);
        EnableWindow(control(5), 0);
    }
    std::thread::spawn(|| {
        let found = disk::sticks();
        STICKS.lock().unwrap().result = Some(found);
        unsafe { PostMessageW(MAIN.load(Ordering::SeqCst) as HWND, WM_STICKS_READY, 0, 0) };
    });
}

fn stick_index() -> Option<usize> {
    usize::try_from(unsafe { SendMessageW(control(2), CB_GETCURSEL, 0, 0) }).ok()
}

fn show_sticks() {
    let combo = control(2);
    let index = stick_index();
    let (labels, selection) = {
        let mut sticks = STICKS.lock().unwrap();
        let Some(found) = sticks.result.take() else { return };
        sticks.scanning = false;
        if std::mem::take(&mut sticks.changed) {
            drop(sticks);
            refresh_sticks();
            return;
        }
        // Keep the chosen device through hotplug. If it disappeared, let the
        // user choose again before offering to erase another device.
        let selection = if sticks.listed.is_empty() {
            (!found.is_empty()).then_some(0)
        } else {
            index.and_then(|i| sticks.listed.get(i))
                .and_then(|old| found.iter().position(|new| new.target == old.target))
        };
        let labels = found.iter().map(|stick| wide(&stick.label)).collect::<Vec<_>>();
        sticks.listed = found;
        (labels, selection)
    };
    unsafe {
        SendMessageW(combo, CB_RESETCONTENT, 0, 0);
        for label in &labels {
            SendMessageW(combo, CB_ADDSTRING, 0, label.as_ptr() as isize);
        }
        if let Some(i) = selection {
            SendMessageW(combo, CB_SETCURSEL, i, 0);
        }
        EnableWindow(combo, 1);
        EnableWindow(control(5), selection.is_some() as i32);
        let text = if labels.is_empty() {
            tr("Plug in a USB stick (2 GB or more).")
        } else {
            NEWS.lock().unwrap().text.clone()
        };
        let text = wide(&text);
        SetWindowTextW(control(4), text.as_ptr());
    }
}

fn start(hwnd: HWND) {
    if NEWS.lock().unwrap().busy {
        return;
    }
    let Some(choice) = stick_index() else { return };
    let stick = {
        let sticks = STICKS.lock().unwrap();
        if sticks.scanning {
            return;
        }
        let Some(stick) = sticks.listed.get(choice).cloned() else { return };
        stick
    };
    let title = wide(&tr("Make a Monet USB stick"));
    if let Err(error) = plan::check_sector_size(stick.target.sector) {
        let text = wide(&tr(error));
        unsafe { MessageBoxW(hwnd, text.as_ptr(), title.as_ptr(), MB_OK | MB_ICONERROR) };
        return;
    }
    let question = wide(&trf("Everything on %1 will be erased.\n\nMake it a Monet USB stick?", &[stick.label.as_str()]));
    NEWS.lock().unwrap().busy = true;
    let answer =
        unsafe { MessageBoxW(hwnd, question.as_ptr(), title.as_ptr(), MB_OKCANCEL | MB_ICONWARNING | MB_DEFBUTTON2) };
    if answer != IDOK {
        NEWS.lock().unwrap().busy = false;
        refresh_sticks();
        return;
    }
    unsafe {
        EnableWindow(control(2), 0);
        EnableWindow(control(5), 0);
    }
    std::thread::spawn(move || {
        // An image dropped on the program is written as it is (a Setup ISO the release doesn't have yet),
        // and checked before anything is erased.
        let given = std::env::args().nth(1);
        let mut iso = given.clone().unwrap_or_default();
        let mut expected = None;
        let result = match &given {
            Some(path) => std::fs::metadata(path).map(|_| ()).map_err(|e| format!("{path}: {e}")),
            None => installer().and_then(|(name, url, total)| {
                let output = Command::new(curl()?).args(["-L", "--fail", "-s", "--max-time", "60",
                    &plan::release_url(VERSION, "SHA256SUMS.txt")]).creation_flags(NO_WINDOW).output().map_err(|e| e.to_string())?;
                if !output.status.success() { return Err(tr("The release checksum could not be downloaded. Nothing was written.")); }
                let hash = plan::checksum(&String::from_utf8_lossy(&output.stdout), &name)
                    .ok_or_else(|| tr("This release has no valid installer checksum. Nothing was written."))?;
                iso = std::env::temp_dir().join(plan::cache_name(&name, &hash)).to_string_lossy().to_string();
                expected = Some(hash);
                download(&url, &iso, total)
            }),
        };
        let result = result.and_then(|()| {
            tell(tr("Checking the installer before writing…"), 0.0);
            let mut source = image::open(&iso, expected.as_deref()).map_err(|error| match error {
                image::OpenError::Read(message) => message,
                image::OpenError::Invalid(message) if expected.is_some() => {
                    let next = if std::fs::remove_file(&iso).is_ok() {
                        tr("The failed download was removed. Try again for a fresh copy.")
                    } else {
                        tr("Delete the cached ISO from your temporary folder and try again.")
                    };
                    format!("{}\n\n{next}", tr(message))
                }
                image::OpenError::Invalid(message) => tr(message),
            })?;
            tell(tr("Checking the USB stick before writing…"), 0.0);
            disk::write(&stick, &mut source, |phase, done, total| {
                let f = done as f64 / total.max(1) as f64;
                let gb = |b: u64| b as f64 / 1e9;
                let (done, total) = (format!("{:.1}", gb(done)), format!("{:.1}", gb(total)));
                let line = if phase == 0 {
                    trf("Writing the USB stick · %1 of %2 GB", &[done.as_str(), total.as_str()])
                } else {
                    trf("Checking the USB stick · %1 of %2 GB", &[done.as_str(), total.as_str()])
                };
                tell(line, f);
            })
            .map_err(|error| {
                let message = tr(&error.message);
                if error.layout_change_started {
                    format!("{message}\n\n{}", tr("The USB device is not ready to use. A partial write may require reformatting. This error does not establish whether the hardware is damaged. See Monet-USB-Stick.log in your temporary folder."))
                } else {
                    message
                }
            })
        });
        if result.is_ok() && given.is_none() {
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
        return Err(tr("This Windows can't download Monet by itself: it needs Windows 10 (2018) or newer."));
    }
    Ok(curl)
}

/// The best installer this release has, with its size: Monet Setup if it's
/// there, otherwise the other one.
fn installer() -> Result<(String, String, u64), String> {
    let curl = curl()?;
    tell(tr("Getting ready to download Monet…"), 0.0);
    for name in plan::installer_names(VERSION) {
        let url = plan::release_url(VERSION, &name);
        let headers = Command::new(&curl).args(["-sIL", &url]).creation_flags(NO_WINDOW).output().map_err(|e| e.to_string())?;
        let headers = String::from_utf8_lossy(&headers.stdout);
        if plan::found(&headers) {
            return Ok((name, url, plan::content_length(&headers).unwrap_or(0)));
        }
    }
    Err(tr("Monet couldn't be downloaded. Check the internet connection, then try again: it picks up where it stopped."))
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
            let so_far = format!("{:.1}", got as f64 / 1e9);
            let mut line = if total > 0 {
                trf("Downloading Monet · %1 of %2 GB", &[so_far.as_str(), format!("{:.1}", total as f64 / 1e9).as_str()])
            } else {
                trf("Downloading Monet · %1 GB", &[so_far.as_str()])
            };
            if total > 0 && rate > 0.0 {
                let minutes = plan::minutes_left((total - got.min(total)) as f64 / rate).to_string();
                line += " · ";
                line += &trf("about %1 min left", &[minutes.as_str()]);
            }
            tell(line, if total > 0 { got as f64 / total as f64 } else { 0.0 });
        };
        if status.success() && (total == 0 || size() == total) {
            return Ok(());
        }
        tell(tr("The connection dropped. Picking up where it stopped…"), 0.0);
        std::thread::sleep(Duration::from_secs(5));
    }
    Err(tr("Monet couldn't be downloaded. Check the internet connection, then try again: it picks up where it stopped."))
}

unsafe extern "system" fn window_proc(hwnd: HWND, msg: u32, wparam: WPARAM, lparam: LPARAM) -> LRESULT {
    match msg {
        WM_COMMAND => {
            match wparam & 0xFFFF {
                ID_MAKE => start(hwnd),
                ID_STICKS if wparam >> 16 == CBN_SELCHANGE as usize => {
                    let busy = NEWS.lock().unwrap().busy;
                    let scanning = STICKS.lock().unwrap().scanning;
                    let available = !busy && !scanning && stick_index().is_some();
                    EnableWindow(control(5), available as i32);
                }
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
        WM_STICKS_READY => {
            show_sticks();
            0
        }
        WM_APP => {
            let (text, fraction, finished) = {
                let mut news = NEWS.lock().unwrap();
                news.posted = false;
                (news.text.clone(), news.fraction, news.finished.take())
            };
            let t = wide(&text);
            SetWindowTextW(control(4), t.as_ptr());
            SendMessageW(control(3), PBM_SETPOS, (fraction.clamp(0.0, 1.0) * 1000.0) as usize, 0);
            if let Some(result) = finished {
                let (text, icon) = match &result {
                    Ok(()) => (tr("Your Monet USB stick is ready.\n\nRestart this PC with it plugged in, and choose the \
                                   USB stick in the PC's boot menu."), MB_ICONINFORMATION),
                    // A message that's one of the window's own sentences is said in Windows' language.
                    Err(e) => (tr(e), MB_ICONERROR),
                };
                let t = wide(&text);
                let title = wide(&tr("Make a Monet USB stick"));
                MessageBoxW(hwnd, t.as_ptr(), title.as_ptr(), MB_OK | icon);
                let done = if result.is_ok() { tr("Done.") } else { String::new() };
                {
                    let mut news = NEWS.lock().unwrap();
                    news.busy = false;
                    news.text.clone_from(&done);
                }
                let done = wide(&done);
                SetWindowTextW(control(4), done.as_ptr());
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
                let (question, title) = (wide(&tr("The USB stick isn't finished. Stop anyway?")), wide(&tr("Make a Monet USB stick")));
                let answer = MessageBoxW(hwnd, question.as_ptr(), title.as_ptr(), MB_YESNO | MB_ICONWARNING | MB_DEFBUTTON2);
                if answer != IDYES {
                    return 0;
                }
            }
            DestroyWindow(hwnd);
            0
        }
        WM_DESTROY => {
            MAIN.store(0, Ordering::SeqCst);
            PostQuitMessage(0);
            0
        }
        _ => DefWindowProcW(hwnd, msg, wparam, lparam),
    }
}

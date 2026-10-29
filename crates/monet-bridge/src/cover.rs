//! The Monet cover: Monet's painting over Windows while Windows is only the way to a game,
//! so a trip there looks like Monet, not like Windows' desktop.
//!
//! A full-screen window that never takes the focus and stays off the taskbar: a launcher
//! (asking to sign in, say) and the game open over it, and when the game closes it's what's
//! there. Its scenes: a game starting, the way back (counting down), signing in to the
//! launchers once, and updating games before the PC switches off. Painted off-screen with
//! GDI+ (the painting, the mark, rounded shapes) and GDI (the words: GDI finds a font for
//! every script Windows has, and lays out right-to-left languages), then copied in one go.
//! `monet-bridge cover-preview` paints a scene into a PNG instead, for a look.

use std::path::{Path, PathBuf};
use std::ptr::{null, null_mut};
use std::sync::atomic::{AtomicBool, AtomicIsize, Ordering};
use std::sync::{mpsc, Arc, Mutex};
use std::thread::JoinHandle;

use windows_sys::core::GUID;
use windows_sys::Win32::Foundation::{HWND, LPARAM, LRESULT, POINT, RECT, WPARAM};
use windows_sys::Win32::Graphics::Gdi::{
    AddFontResourceExW, BeginPaint, BitBlt, CreateCompatibleDC, CreateDIBSection, CreateFontW, DeleteDC, DeleteObject,
    DrawTextW, EndPaint, InvalidateRect, ScreenToClient, SelectObject, SetBkMode, SetTextColor, CLEARTYPE_NATURAL_QUALITY, BITMAPINFO,
    BITMAPINFOHEADER, BI_RGB, DEFAULT_CHARSET, DIB_RGB_COLORS, DT_CALCRECT, DT_LEFT, DT_NOPREFIX, DT_RIGHT,
    DT_RTLREADING, DT_SINGLELINE, DT_WORDBREAK, FR_PRIVATE, HDC, HFONT, PAINTSTRUCT, SRCCOPY, TRANSPARENT,
};
use windows_sys::Win32::Graphics::GdiPlus as gp;
use windows_sys::Win32::System::LibraryLoader::GetModuleHandleW;
use windows_sys::Win32::UI::HiDpi::{SetProcessDpiAwarenessContext, DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2};
use windows_sys::Win32::UI::Input::KeyboardAndMouse::{VK_ESCAPE, VK_RETURN};
use windows_sys::Win32::UI::WindowsAndMessaging::{
    CreateWindowExW, DefWindowProcW, DestroyWindow, DispatchMessageW, GetCursorPos, GetMessageW, GetSystemMetrics,
    GetWindowLongPtrW, LoadCursorW, PostMessageW, PostQuitMessage, RegisterClassW, SetCursor,
    SetForegroundWindow, SetWindowLongPtrW, SetWindowPos, ShowWindow, TranslateMessage, GWLP_USERDATA, HWND_BOTTOM,
    HWND_NOTOPMOST, HWND_TOPMOST, IDC_ARROW, IDC_HAND, MA_NOACTIVATE, MSG, SM_CXSCREEN, SM_CYSCREEN, SWP_NOACTIVATE,
    SWP_NOMOVE, SWP_NOSIZE,
    SW_SHOWNOACTIVATE, WM_APP, WM_CLOSE, WM_DESTROY, WM_ERASEBKGND, WM_KEYDOWN, WM_LBUTTONUP, WM_MOUSEACTIVATE,
    WM_PAINT, WM_SETCURSOR, WNDCLASSW, WS_EX_NOACTIVATE, WS_EX_TOOLWINDOW, WS_POPUP,
};

use crate::win::wide;
use crate::words::{rtl, tr, trf};

#[derive(Clone, Debug, PartialEq)]
pub enum Scene {
    /// A game on its way: Windows started for it, and goes back to Monet after.
    Starting { game: String },
    /// Back to Monet in so many seconds, unless asked to stay; with why, when it's not
    /// simply that the game closed.
    Back { seconds: u32, why: Option<String> },
    /// Signing in to the launchers once: each one's name, and whether it keeps you signed in.
    Launchers { rows: Vec<(String, bool)> },
    /// Bringing Windows and its games up to date, then switching off: how it's going.
    Updating { lines: Vec<String> },
    /// Installing the launcher a game in the shared Games folder needs, before the game.
    Preparing { launcher: String },
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Press {
    BackNow,
    Stay,
    Open(usize),
    SwitchOff,
}

const SUN: u32 = 0xFFF2552C; // Monet's sun (GDI+'s ARGB), as Setup's Continue
const LILY: u32 = 0x86DCC8; // "Signed in": Monet's lily, lightened for dusk (RGB, as all the words' colors)
const PNG: GUID = GUID::from_u128(0x557cf406_1a04_11d3_9a73_0000f81ef32e);

fn colorref(rgb: u32) -> u32 {
    ((rgb & 0xFF) << 16) | (rgb & 0xFF00) | ((rgb >> 16) & 0xFF)
}

// ------------------------------------------------------------- the pictures and the font

/// The painting and the mark (next to the program), and Monet's serif for titles.
struct Art {
    token: usize,
    painting: *mut gp::GpBitmap,
    mark: *mut gp::GpBitmap,
    serif: bool,
}

impl Art {
    fn load(dir: &Path) -> Art {
        let mut token = 0usize;
        let input = gp::GdiplusStartupInput { GdiplusVersion: 1, ..Default::default() };
        // SAFETY: plain GDI+ start-up; the bitmaps are disposed of in Drop before shutting it down.
        unsafe {
            gp::GdiplusStartup(&mut token, &input, null_mut());
            let image = |name: &str| {
                let mut bitmap = null_mut();
                let path = wide(&dir.join(name).to_string_lossy());
                if gp::GdipCreateBitmapFromFile(path.as_ptr(), &mut bitmap) != gp::Ok {
                    bitmap = null_mut();
                }
                bitmap
            };
            let fonts = ["Fraunces-Light.ttf", "Fraunces-Regular.ttf"]
                .iter()
                .filter(|f| AddFontResourceExW(wide(&dir.join(f).to_string_lossy()).as_ptr(), FR_PRIVATE, null()) > 0)
                .count();
            Art { token, painting: image("cover.jpg"), mark: image("monet-mark.png"), serif: fonts == 2 }
        }
    }
}

impl Drop for Art {
    fn drop(&mut self) {
        // SAFETY: each bitmap came from GDI+ and is disposed of once, before shutting it down.
        unsafe {
            for bitmap in [self.painting, self.mark] {
                if !bitmap.is_null() {
                    gp::GdipDisposeImage(bitmap.cast());
                }
            }
            gp::GdiplusShutdown(self.token);
        }
    }
}

/// Monet's serif has Latin letters only: a title in another script uses Windows' own font.
fn serif_can(text: &str) -> bool {
    text.chars().all(|c| (c as u32) < 0x250 || ('\u{2000}'..='\u{206F}').contains(&c))
}

// ------------------------------------------------------------- laying a scene out

enum Op {
    Text { font: usize, color: u32, text: String, rect: RECT, end: bool },
    Round { rect: RECT, radius: i32, argb: u32 },
}

struct Fonts(Vec<HFONT>);

impl Fonts {
    fn new(s: f32, serif: bool, title_serif: bool) -> Fonts {
        let make = |px: f32, weight: i32, face: &str| {
            // SAFETY: CreateFontW with a NUL-terminated face name; deleted in Drop.
            unsafe {
                CreateFontW(-(px * s).round() as i32, 0, 0, 0, weight, 0, 0, 0, DEFAULT_CHARSET as u32, 0, 0,
                            CLEARTYPE_NATURAL_QUALITY, 0, wide(face).as_ptr())
            }
        };
        Fonts(vec![
            make(17.0, 600, "Segoe UI"),                                                    // CAPTION
            if title_serif { make(76.0, 300, "Fraunces 72pt SuperSoft Light") } else { make(64.0, 300, "Segoe UI") }, // TITLE
            make(20.0, 400, "Segoe UI"),                                                    // BODY
            make(17.0, 600, "Segoe UI"),                                                    // BUTTON
            make(19.0, 600, "Segoe UI"),                                                    // ROW
            if serif { make(30.0, 400, "Fraunces 72pt SuperSoft") } else { make(28.0, 600, "Segoe UI") }, // WORDMARK
            make(17.0, 400, "Segoe UI"),                                                    // LINE
        ])
    }
}

impl Drop for Fonts {
    fn drop(&mut self) {
        for font in &self.0 {
            // SAFETY: fonts made in new(), no longer selected into any DC.
            unsafe { DeleteObject(*font) };
        }
    }
}

const CAPTION: usize = 0;
const TITLE: usize = 1;
const BODY: usize = 2;
const BUTTON: usize = 3;
const ROW: usize = 4;
const WORDMARK: usize = 5;
const LINE: usize = 6;

/// Where words go: measured on a DC, laid out from the start edge (the right one, right to left).
struct Layout<'a> {
    dc: HDC,
    fonts: &'a Fonts,
    s: f32,
    rtl: bool,
    /// The column's start-edge x and width; titles may run wider.
    x: i32,
    width: i32,
    title_width: i32,
    y: i32,
    ops: Vec<Op>,
    hits: Vec<(RECT, Press)>,
}

impl Layout<'_> {
    fn px(&self, n: f32) -> i32 {
        (n * self.s).round() as i32
    }

    /// A box at `from` (measured from the start edge) and `w` wide, on the right side either way.
    fn place(&self, from: i32, w: i32, top: i32, h: i32) -> RECT {
        let left = if self.rtl { self.x + self.width - from - w } else { self.x + from };
        RECT { left, top, right: left + w, bottom: top + h }
    }

    fn measure(&self, font: usize, text: &str, width: i32, single: bool) -> (i32, i32) {
        let mut rect = RECT { left: 0, top: 0, right: width, bottom: 0 };
        let flags = DT_CALCRECT | DT_NOPREFIX | if single { DT_SINGLELINE } else { DT_WORDBREAK };
        let text = wide(text);
        // SAFETY: the font is selected only for the measurement; strings are NUL-terminated (-1).
        unsafe {
            let old = SelectObject(self.dc, self.fonts.0[font]);
            DrawTextW(self.dc, text.as_ptr(), -1, &mut rect, flags);
            SelectObject(self.dc, old);
        }
        (rect.right - rect.left, rect.bottom - rect.top)
    }

    fn gap(&mut self, n: f32) {
        self.y += self.px(n);
    }

    fn text(&mut self, font: usize, color: u32, text: &str) {
        let width = if font == TITLE { self.title_width } else { self.width };
        let (_, h) = self.measure(font, text, width, false);
        let rect = self.place(0, width, self.y, h);
        self.ops.push(Op::Text { font, color, text: text.into(), rect, end: self.rtl });
        self.y += h;
    }

    /// Buttons in a row from the start edge: (words, the sun's color, what it does).
    fn buttons(&mut self, buttons: &[(String, bool, Press)]) {
        let (h, pad) = (self.px(52.0), self.px(26.0));
        let mut from = 0;
        for (words, sun, press) in buttons {
            let (tw, th) = self.measure(BUTTON, words, self.width, true);
            let rect = self.place(from, tw + 2 * pad, self.y, h);
            self.ops.push(Op::Round { rect, radius: h / 2, argb: if *sun { SUN } else { 0x38FFFFFF } });
            let inner = RECT { left: rect.left + pad, top: rect.top + (h - th) / 2, right: rect.right - pad, bottom: rect.bottom };
            self.ops.push(Op::Text { font: BUTTON, color: 0xFFFFFF, text: words.clone(), rect: inner, end: self.rtl });
            self.hits.push((rect, *press));
            from += tw + 2 * pad + self.px(12.0);
        }
        self.y += h;
    }

    /// The launchers, one card each: the name, then Sign in, or "Signed in" and Open launcher.
    fn rows(&mut self, rows: &[(String, bool)]) {
        let (w, h, pad) = (self.width.min(self.px(640.0)), self.px(64.0), self.px(22.0));
        let (sign_in, open, signed) = (tr("Sign in"), tr("Open launcher"), tr("Signed in"));
        for (i, (name, signed_in)) in rows.iter().enumerate() {
            let card = self.place(0, w, self.y, h);
            self.ops.push(Op::Round { rect: card, radius: self.px(16.0), argb: 0x2AFFFFFF });
            let (_, nh) = self.measure(ROW, name, w, true);
            let name_rect = self.place(pad, w / 2, self.y + (h - nh) / 2, nh);
            self.ops.push(Op::Text { font: ROW, color: 0xFFFFFF, text: name.clone(), rect: name_rect, end: self.rtl });
            // The button, at the far end of the card.
            let label_text = if *signed_in { &open } else { &sign_in };
            let (tw, th) = self.measure(BUTTON, label_text, w, true);
            let (bpad, bh) = (self.px(18.0), self.px(40.0));
            let bw = tw + 2 * bpad;
            let button = self.place(w - self.px(12.0) - bw, bw, self.y + (h - bh) / 2, bh);
            self.ops.push(Op::Round { rect: button, radius: bh / 2, argb: 0x40FFFFFF });
            let label = RECT { left: button.left + bpad, top: button.top + (bh - th) / 2, right: button.right - bpad, bottom: button.bottom };
            self.ops.push(Op::Text { font: BUTTON, color: 0xFFFFFF, text: label_text.clone(), rect: label, end: self.rtl });
            self.hits.push((button, Press::Open(i)));
            if *signed_in {
                let (sw, sh) = self.measure(LINE, &signed, w, true);
                let at = self.place(w - self.px(12.0) - bw - self.px(16.0) - sw, sw, self.y + (h - sh) / 2, sh);
                self.ops.push(Op::Text { font: LINE, color: LILY, text: signed.clone(), rect: at, end: self.rtl });
            }
            self.y += h + self.px(10.0);
        }
        self.y -= self.px(10.0);
    }

    fn lines(&mut self, lines: &[String]) {
        for (i, line) in lines.iter().enumerate() {
            if i > 0 {
                self.gap(6.0);
            }
            self.text(LINE, 0xE6E6EE, &format!("·  {line}"));
        }
    }
}

/// The scene's words and buttons, top to bottom.
fn lay_out(l: &mut Layout, scene: &Scene) {
    let caption = 0xD9DAE2;
    let body = 0xEDEDF2;
    match scene {
        Scene::Starting { game } => {
            l.text(CAPTION, caption, &tr("Starting in Windows"));
            l.gap(8.0);
            l.text(TITLE, 0xFFFFFF, game);
            l.gap(16.0);
            l.text(BODY, body, &tr("When you quit the game, your PC goes back to Monet. If a launcher asks you to sign in, do it once: it remembers you."));
            l.gap(32.0);
            l.buttons(&[(tr("Back to Monet now"), false, Press::BackNow)]);
        }
        Scene::Back { seconds, why } => {
            l.text(CAPTION, caption, &why.clone().unwrap_or_else(|| tr("The game closed")));
            l.gap(8.0);
            l.text(TITLE, 0xFFFFFF, &tr("Back to Monet"));
            l.gap(16.0);
            l.text(BODY, body, &trf("Your PC restarts in Monet in %1 s.", &[&seconds.to_string()]));
            l.gap(32.0);
            l.buttons(&[(tr("Go now"), true, Press::BackNow), (tr("Stay in Windows"), false, Press::Stay)]);
        }
        Scene::Launchers { rows } => {
            l.text(CAPTION, caption, &tr("In Windows, once"));
            l.gap(8.0);
            l.text(TITLE, 0xFFFFFF, &tr("Sign in to your game launchers"));
            l.gap(16.0);
            l.text(BODY, body, &tr("Open each one and sign in, with Remember me ticked. Then the games you play from Monet start without asking."));
            l.gap(28.0);
            l.rows(rows);
            l.gap(32.0);
            l.buttons(&[(tr("Back to Monet"), true, Press::BackNow)]);
        }
        Scene::Updating { lines } => {
            l.text(CAPTION, caption, &tr("In Windows, then off"));
            l.gap(8.0);
            l.text(TITLE, 0xFFFFFF, &tr("Updating your games"));
            l.gap(16.0);
            l.text(BODY, body, &tr("Windows and your game launchers are bringing everything up to date. The PC switches off by itself when they're done."));
            l.gap(24.0);
            l.lines(lines);
            l.gap(32.0);
            l.buttons(&[(tr("Switch off now"), false, Press::SwitchOff)]);
        }
        Scene::Preparing { launcher } => {
            l.text(CAPTION, caption, &tr("Starting in Windows"));
            l.gap(8.0);
            l.text(TITLE, 0xFFFFFF, &trf("Getting %1 ready", &[launcher]));
            l.gap(16.0);
            l.text(BODY, body, &tr("Your game needs it here. Windows installs it once, from what Monet fetched for it, and then your game starts."));
        }
    }
}

fn title_of(scene: &Scene) -> String {
    match scene {
        Scene::Starting { game } => game.clone(),
        Scene::Back { .. } => tr("Back to Monet"),
        Scene::Launchers { .. } => tr("Sign in to your game launchers"),
        Scene::Updating { .. } => tr("Updating your games"),
        Scene::Preparing { launcher } => trf("Getting %1 ready", &[launcher]),
    }
}

// ------------------------------------------------------------- painting

/// Paints `scene` onto `dc` (w × h); returns where its buttons are.
fn paint(dc: HDC, w: i32, h: i32, scene: &Scene, art: &Art) -> Vec<(RECT, Press)> {
    let s = h as f32 / 1080.0;
    let fonts = Fonts::new(s, art.serif, art.serif && serif_can(&title_of(scene)));
    let rtl = rtl();
    let margin = (112.0 * s).round() as i32;
    let width = ((860.0 * s).round() as i32).min(w - 2 * margin);
    let title_width = ((1240.0 * s).round() as i32).min(w - 2 * margin);
    let x = if rtl { w - margin - width } else { margin };
    let mut l = Layout { dc, fonts: &fonts, s, rtl, x, width, title_width, y: 0, ops: Vec::new(), hits: Vec::new() };
    lay_out(&mut l, scene);
    // Laid out from 0: down to sit above the bottom margin.
    let shift = h - (120.0 * s).round() as i32 - l.y;
    let move_down = |r: &mut RECT| {
        r.top += shift;
        r.bottom += shift;
    };
    for op in &mut l.ops {
        match op {
            Op::Text { rect, .. } | Op::Round { rect, .. } => move_down(rect),
        }
    }
    for (rect, _) in &mut l.hits {
        move_down(rect);
    }

    // SAFETY: GDI+ on a DC that stays valid for the call; every object made here is deleted here.
    unsafe {
        let mut g = null_mut();
        gp::GdipCreateFromHDC(dc, &mut g);
        gp::GdipSetSmoothingMode(g, gp::SmoothingModeAntiAlias);
        gp::GdipSetInterpolationMode(g, gp::InterpolationModeHighQualityBicubic);
        gp::GdipSetPixelOffsetMode(g, gp::PixelOffsetModeHighQuality);

        // The painting, filling the screen.
        if art.painting.is_null() {
            fill(g, 0xFF2B3245, 0, 0, w, h);
        } else {
            let (mut iw, mut ih) = (0u32, 0u32);
            gp::GdipGetImageWidth(art.painting.cast(), &mut iw);
            gp::GdipGetImageHeight(art.painting.cast(), &mut ih);
            let scale = (w as f32 / iw as f32).max(h as f32 / ih as f32);
            let (sw, sh) = ((w as f32 / scale) as i32, (h as f32 / scale) as i32);
            gp::GdipDrawImageRectRectI(g, art.painting.cast(), 0, 0, w, h, (iw as i32 - sw) / 2, (ih as i32 - sh) / 2, sw, sh,
                                       gp::UnitPixel, null(), 0, null_mut());
        }
        // Dusk from a little above the words down, so they read on any painting, however
        // many there are.
        let solid = (shift + (40.0 * s) as i32).clamp(0, h);
        let fade = (solid - (300.0 * s) as i32).max(0);
        shade(g, w, fade, solid, 0x000C0E16, 0xA80C0E16);
        shade(g, w, solid, h, 0xA80C0E16, 0xD00C0E16);

        // Monet's mark, top right as in Setup.
        let word = "Monet";
        let old = SelectObject(dc, fonts.0[WORDMARK]);
        let mut wr = RECT { left: 0, top: 0, right: w, bottom: 0 };
        let wide_word = wide(word);
        DrawTextW(dc, wide_word.as_ptr(), -1, &mut wr, DT_CALCRECT | DT_SINGLELINE | DT_NOPREFIX);
        SelectObject(dc, old);
        let (mark, gap, right, mtop) = ((40.0 * s) as i32, (12.0 * s) as i32, w - (64.0 * s) as i32, (56.0 * s) as i32);
        let word_left = right - (wr.right - wr.left);
        if !art.mark.is_null() {
            gp::GdipDrawImageRectI(g, art.mark.cast(), word_left - gap - mark, mtop, mark, mark);
        }

        for op in &l.ops {
            if let Op::Round { rect, radius, argb } = op {
                round(g, *argb, rect, *radius);
            }
        }
        gp::GdipDeleteGraphics(g);

        // The words, after GDI+ is done with the DC.
        SetBkMode(dc, TRANSPARENT as i32);
        let word_rect = RECT { left: word_left, top: mtop + (mark - (wr.bottom - wr.top)) / 2, right, bottom: mtop + mark * 2 };
        draw_text(dc, fonts.0[WORDMARK], 0xFFFFFF, word, word_rect, false, false);
        for op in &l.ops {
            if let Op::Text { font, color, text, rect, end } = op {
                draw_text(dc, fonts.0[*font], *color, text, *rect, *end, rtl);
            }
        }
    }
    l.hits
}

/// A band across the screen from `top` to `bottom`, from one color to the other.
unsafe fn shade(g: *mut gp::GpGraphics, w: i32, top: i32, bottom: i32, from: u32, to: u32) {
    if bottom <= top {
        return;
    }
    let mut brush = null_mut();
    gp::GdipCreateLineBrushI(&gp::Point { X: 0, Y: top - 1 }, &gp::Point { X: 0, Y: bottom + 1 }, from, to,
                             gp::WrapModeTileFlipXY, &mut brush);
    gp::GdipFillRectangleI(g, brush.cast(), 0, top, w, bottom - top);
    gp::GdipDeleteBrush(brush.cast());
}

unsafe fn fill(g: *mut gp::GpGraphics, argb: u32, x: i32, y: i32, w: i32, h: i32) {
    let mut brush = null_mut();
    gp::GdipCreateSolidFill(argb, &mut brush);
    gp::GdipFillRectangleI(g, brush.cast(), x, y, w, h);
    gp::GdipDeleteBrush(brush.cast());
}

unsafe fn round(g: *mut gp::GpGraphics, argb: u32, r: &RECT, radius: i32) {
    let (d, w, h) = (radius * 2, r.right - r.left, r.bottom - r.top);
    let mut path = null_mut();
    gp::GdipCreatePath(gp::FillModeAlternate, &mut path);
    gp::GdipAddPathArcI(path, r.left, r.top, d, d, 180.0, 90.0);
    gp::GdipAddPathArcI(path, r.left + w - d, r.top, d, d, 270.0, 90.0);
    gp::GdipAddPathArcI(path, r.left + w - d, r.top + h - d, d, d, 0.0, 90.0);
    gp::GdipAddPathArcI(path, r.left, r.top + h - d, d, d, 90.0, 90.0);
    gp::GdipClosePathFigure(path);
    let mut brush = null_mut();
    gp::GdipCreateSolidFill(argb, &mut brush);
    gp::GdipFillPath(g, brush.cast(), path);
    gp::GdipDeleteBrush(brush.cast());
    gp::GdipDeletePath(path);
}

unsafe fn draw_text(dc: HDC, font: HFONT, rgb: u32, text: &str, mut rect: RECT, end: bool, rtl: bool) {
    let old = SelectObject(dc, font);
    SetTextColor(dc, colorref(rgb));
    let mut flags = DT_WORDBREAK | DT_NOPREFIX | if end { DT_RIGHT } else { DT_LEFT };
    if rtl {
        flags |= DT_RTLREADING;
    }
    let text = wide(text);
    DrawTextW(dc, text.as_ptr(), -1, &mut rect, flags);
    SelectObject(dc, old);
}

/// A 32-bit picture to paint into, and the DC that holds it.
struct Canvas {
    dc: HDC,
    bitmap: windows_sys::Win32::Graphics::Gdi::HBITMAP,
    old: windows_sys::Win32::Graphics::Gdi::HGDIOBJ,
}

impl Canvas {
    fn new(like: HDC, w: i32, h: i32) -> Canvas {
        // SAFETY: a top-down 32-bit DIB section selected into a fresh memory DC; undone in Drop.
        unsafe {
            let dc = CreateCompatibleDC(like);
            let mut info: BITMAPINFO = std::mem::zeroed();
            info.bmiHeader = BITMAPINFOHEADER {
                biSize: std::mem::size_of::<BITMAPINFOHEADER>() as u32,
                biWidth: w,
                biHeight: -h,
                biPlanes: 1,
                biBitCount: 32,
                biCompression: BI_RGB,
                ..std::mem::zeroed()
            };
            let mut bits = null_mut();
            let bitmap = CreateDIBSection(dc, &info, DIB_RGB_COLORS, &mut bits, null_mut(), 0);
            let old = SelectObject(dc, bitmap);
            Canvas { dc, bitmap, old }
        }
    }
}

impl Drop for Canvas {
    fn drop(&mut self) {
        // SAFETY: undoes new().
        unsafe {
            SelectObject(self.dc, self.old);
            DeleteObject(self.bitmap);
            DeleteDC(self.dc);
        }
    }
}

/// Paints a scene into a PNG, w × h, with the pictures in `dir`: for a look, no window.
pub fn preview(scene: &Scene, dir: &Path, out: &Path, w: i32, h: i32) -> Result<(), String> {
    let art = Art::load(dir);
    let canvas = Canvas::new(null_mut(), w, h);
    paint(canvas.dc, w, h, scene, &art);
    // SAFETY: GDI+ is running (art); the bitmap is disposed of here.
    unsafe {
        let mut bitmap = null_mut();
        gp::GdipCreateBitmapFromHBITMAP(canvas.bitmap, null_mut(), &mut bitmap);
        let path = wide(&out.to_string_lossy());
        let status = gp::GdipSaveImageToFile(bitmap.cast(), path.as_ptr(), &PNG, null());
        gp::GdipDisposeImage(bitmap.cast());
        if status == gp::Ok { Ok(()) } else { Err(format!("couldn't save {} (GDI+ status {status})", out.display())) }
    }
}

// ------------------------------------------------------------- the window

struct Shared {
    scene: Mutex<Scene>,
    press: Mutex<Option<Press>>,
    hwnd: AtomicIsize,
    /// In front of everything while a launcher opens for its game (Cover::hold).
    held: AtomicBool,
}

struct Window {
    shared: Arc<Shared>,
    art: Art,
    hits: Vec<(RECT, Press)>,
}

pub struct Cover {
    shared: Arc<Shared>,
    thread: Option<JoinHandle<()>>,
}

/// The pictures and fonts, next to the program.
fn art_dir() -> PathBuf {
    std::env::current_exe().ok().and_then(|e| e.parent().map(Path::to_path_buf)).unwrap_or_default()
}

const SCENE_CHANGED: u32 = WM_APP + 1;
const LET_GO: u32 = WM_APP + 2;

fn in_front(scene: &Scene) -> bool {
    matches!(scene, Scene::Back { .. })
}

impl Cover {
    /// Covers the screen with `scene`; None if Windows wouldn't make the window.
    pub fn open(scene: Scene) -> Option<Cover> {
        let shared = Arc::new(Shared {
            scene: Mutex::new(scene),
            press: Mutex::new(None),
            hwnd: AtomicIsize::new(0),
            held: AtomicBool::new(false),
        });
        let (ready, made) = mpsc::channel();
        let for_thread = shared.clone();
        let thread = std::thread::spawn(move || run(for_thread, ready));
        if made.recv().ok().flatten().is_none() {
            let _ = thread.join();
            return None;
        }
        let cover = Cover { shared, thread: Some(thread) };
        cover.raise();
        Some(cover)
    }

    pub fn show(&self, scene: Scene) {
        *self.shared.scene.lock().unwrap() = scene;
        self.post(SCENE_CHANGED);
    }

    /// While a launcher opens for its game: the painting stays in front of it, so the game
    /// seems to start from Monet. Let go once the game runs (or the launcher needs you): the
    /// painting goes to the back, under the game and whatever else is open.
    pub fn hold(&self, held: bool) {
        self.shared.held.store(held, Ordering::SeqCst);
        self.post(if held { SCENE_CHANGED } else { LET_GO });
    }

    /// The last button pressed, once.
    pub fn pressed(&self) -> Option<Press> {
        self.shared.press.lock().unwrap().take()
    }

    fn post(&self, msg: u32) {
        let hwnd = self.shared.hwnd.load(Ordering::SeqCst) as HWND;
        // SAFETY: posting to our own window; harmless if it's gone.
        unsafe { PostMessageW(hwnd, msg, 0, 0) };
    }

    fn raise(&self) {
        self.post(SCENE_CHANGED);
    }
}

impl Drop for Cover {
    fn drop(&mut self) {
        self.post(WM_CLOSE);
        if let Some(thread) = self.thread.take() {
            let _ = thread.join();
        }
    }
}

fn run(shared: Arc<Shared>, ready: mpsc::Sender<Option<isize>>) {
    // SAFETY: a window and its message loop on this thread; the Window box lives in
    // GWLP_USERDATA until WM_DESTROY.
    unsafe {
        SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2);
        let instance = GetModuleHandleW(null());
        let class = wide("MonetCover");
        let wc = WNDCLASSW {
            lpfnWndProc: Some(window_proc),
            hInstance: instance,
            lpszClassName: class.as_ptr(),
            hCursor: LoadCursorW(null_mut(), IDC_ARROW),
            ..std::mem::zeroed()
        };
        RegisterClassW(&wc);
        let (w, h) = (GetSystemMetrics(SM_CXSCREEN), GetSystemMetrics(SM_CYSCREEN));
        let title = wide("Monet");
        let hwnd = CreateWindowExW(WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE, class.as_ptr(), title.as_ptr(), WS_POPUP, 0, 0, w, h,
                                   null_mut(), null_mut(), instance, null());
        if hwnd.is_null() {
            let _ = ready.send(None);
            return;
        }
        let window = Box::new(Window { shared: shared.clone(), art: Art::load(&art_dir()), hits: Vec::new() });
        SetWindowLongPtrW(hwnd, GWLP_USERDATA, Box::into_raw(window) as isize);
        shared.hwnd.store(hwnd as isize, Ordering::SeqCst);
        ShowWindow(hwnd, SW_SHOWNOACTIVATE);
        let _ = ready.send(Some(hwnd as isize));
        let mut msg: MSG = std::mem::zeroed();
        while GetMessageW(&mut msg, null_mut(), 0, 0) > 0 {
            TranslateMessage(&msg);
            DispatchMessageW(&msg);
        }
    }
}

unsafe extern "system" fn window_proc(hwnd: HWND, msg: u32, wparam: WPARAM, lparam: LPARAM) -> LRESULT {
    let window = GetWindowLongPtrW(hwnd, GWLP_USERDATA) as *mut Window;
    if window.is_null() {
        return DefWindowProcW(hwnd, msg, wparam, lparam);
    }
    let window = &mut *window;
    let shared = window.shared.clone();
    let front = || in_front(&shared.scene.lock().unwrap());
    match msg {
        WM_PAINT => {
            let mut ps: PAINTSTRUCT = std::mem::zeroed();
            let dc = BeginPaint(hwnd, &mut ps);
            let (w, h) = (GetSystemMetrics(SM_CXSCREEN), GetSystemMetrics(SM_CYSCREEN));
            let canvas = Canvas::new(dc, w, h);
            let scene = window.shared.scene.lock().unwrap().clone();
            window.hits = paint(canvas.dc, w, h, &scene, &window.art);
            BitBlt(dc, 0, 0, w, h, canvas.dc, 0, 0, SRCCOPY);
            EndPaint(hwnd, &ps);
            0
        }
        WM_ERASEBKGND => 1,
        SCENE_CHANGED => {
            // The way back comes to the front (and takes the keyboard); a held cover stays in
            // front without the keyboard; the rest stays under whatever opens next.
            if front() {
                SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE);
                SetForegroundWindow(hwnd);
            } else if shared.held.load(Ordering::SeqCst) {
                SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE);
            } else {
                SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE);
            }
            InvalidateRect(hwnd, null(), 0);
            0
        }
        LET_GO if !front() => {
            SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE);
            SetWindowPos(hwnd, HWND_BOTTOM, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE);
            0
        }
        WM_MOUSEACTIVATE if !front() => MA_NOACTIVATE as LRESULT,
        WM_SETCURSOR => {
            let mut at = POINT { x: 0, y: 0 };
            GetCursorPos(&mut at);
            ScreenToClient(hwnd, &mut at);
            let over = window.hits.iter().any(|(r, _)| inside(r, at.x, at.y));
            SetCursor(LoadCursorW(null_mut(), if over { IDC_HAND } else { IDC_ARROW }));
            1
        }
        WM_LBUTTONUP => {
            let (x, y) = ((lparam & 0xFFFF) as i16 as i32, ((lparam >> 16) & 0xFFFF) as i16 as i32);
            if let Some((_, press)) = window.hits.iter().find(|(r, _)| inside(r, x, y)) {
                *window.shared.press.lock().unwrap() = Some(*press);
            }
            0
        }
        WM_KEYDOWN if front() => {
            let press = match wparam as u16 {
                VK_RETURN => Some(Press::BackNow),
                VK_ESCAPE => Some(Press::Stay),
                _ => None,
            };
            if press.is_some() {
                *window.shared.press.lock().unwrap() = press;
            }
            0
        }
        WM_CLOSE => {
            DestroyWindow(hwnd);
            0
        }
        WM_DESTROY => {
            drop(Box::from_raw(window as *mut Window));
            SetWindowLongPtrW(hwnd, GWLP_USERDATA, 0);
            PostQuitMessage(0);
            0
        }
        _ => DefWindowProcW(hwnd, msg, wparam, lparam),
    }
}

fn inside(r: &RECT, x: i32, y: i32) -> bool {
    x >= r.left && x < r.right && y >= r.top && y < r.bottom
}

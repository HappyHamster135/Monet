//! Make a Monet USB stick: the Windows program in each release. It lists USB
//! sticks (never the disk Windows runs from), downloads this version's
//! installer with Windows' own curl.exe (picking up where it stopped), writes
//! it onto the chosen stick exactly and reads it back to check. Nothing else
//! to install.

#![cfg_attr(windows, windows_subsystem = "windows")]

/// Marks words the window shows, for tools/make-translations.py; they're said
/// in Windows' language where they're shown (words::tr).
#[cfg(windows)]
macro_rules! t {
    ($text:literal) => {
        $text
    };
}

#[cfg_attr(not(windows), allow(dead_code))]
mod plan;

#[cfg(windows)]
mod disk;
#[cfg(windows)]
mod gui;
#[cfg(windows)]
mod words;
#[cfg(windows)]
mod words_table;

#[cfg(windows)]
fn main() {
    gui::run();
}

#[cfg(not(windows))]
fn main() {
    eprintln!("Make a Monet USB stick runs on Windows. On Linux, write {} with your disk tool.",
              plan::installer_names(env!("CARGO_PKG_VERSION"))[0]);
    std::process::exit(1);
}

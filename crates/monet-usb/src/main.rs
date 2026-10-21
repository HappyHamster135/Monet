//! Make a Monet USB stick: the Windows program in each release. It lists USB
//! sticks (never the disk Windows runs from), downloads this version's
//! installer with Windows' own curl.exe (picking up where it stopped), writes
//! it onto the chosen stick exactly and reads it back to check. Nothing else
//! to install.

#![cfg_attr(windows, windows_subsystem = "windows")]

#[cfg_attr(not(windows), allow(dead_code))]
mod plan;

#[cfg(windows)]
mod disk;
#[cfg(windows)]
mod gui;

#[cfg(windows)]
fn main() {
    gui::run();
}

#[cfg(not(windows))]
fn main() {
    eprintln!("Make a Monet USB stick runs on Windows. On Linux, write {} with your disk tool.",
              plan::installer_name(env!("CARGO_PKG_VERSION")));
    std::process::exit(1);
}

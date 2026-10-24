//! `monet-bridge`: the Windows half of Monet.

// A GUI program, so it never flashes a console window when it runs in the
// background. Console commands attach to the parent terminal instead.
#![cfg_attr(windows, windows_subsystem = "windows")]

#[cfg_attr(not(windows), allow(dead_code))]
mod parse;

#[cfg(windows)]
mod bridge;
#[cfg(windows)]
mod cover;
#[cfg(windows)]
mod launchers;
#[cfg(windows)]
mod win;
// The words in Windows' language: Make-USB-Stick's lookup, with this program's own table.
#[cfg(windows)]
#[path = "../../monet-usb/src/words.rs"]
mod words;
#[cfg(windows)]
mod words_table;

#[cfg(windows)]
fn main() -> std::process::ExitCode {
    bridge::main()
}

#[cfg(not(windows))]
fn main() -> std::process::ExitCode {
    eprintln!("Monet Bridge runs on Windows.");
    std::process::ExitCode::FAILURE
}

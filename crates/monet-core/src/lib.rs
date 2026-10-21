//! Shared logic for both sides of the switch.
//!
//! Monet (Linux) and Monet Bridge (Windows) talk to each other through UEFI
//! variables, which both systems can read and write without sharing a disk:
//!
//! - `BootNext` (standard) picks the system that starts on the next boot.
//! - `MonetLaunch` (our own GUID) carries a small JSON [`LaunchRequest`].
//!
//! The list of installed Windows games travels the other way as a JSON file on
//! the EFI system partition (see [`games`]).

pub mod boot;
pub mod efi;
pub mod games;
pub mod load_option;
pub mod request;

pub const VERSION: &str = env!("CARGO_PKG_VERSION");

//! Windows: Monet's icon and a manifest (administrator, since it writes a
//! whole disk; sharp on high-DPI screens; today's controls), via windres.

use std::path::PathBuf;
use std::process::Command;

fn main() {
    let target = std::env::var("TARGET").unwrap_or_default();
    println!("cargo:rerun-if-changed=monet-usb.manifest");
    println!("cargo:rerun-if-changed=../../windows/monet.ico");
    if !target.contains("windows-gnu") {
        return;
    }
    let dir = PathBuf::from(std::env::var("CARGO_MANIFEST_DIR").unwrap());
    let out = PathBuf::from(std::env::var("OUT_DIR").unwrap());
    let rc = out.join("monet-usb.rc");
    let icon = dir.join("../../windows/monet.ico");
    let manifest = dir.join("monet-usb.manifest");
    std::fs::write(&rc, format!("1 ICON \"{}\"\n1 24 \"{}\"\n", icon.display(), manifest.display())).unwrap();
    let obj = out.join("monet-usb-res.o");
    let windres = std::env::var("WINDRES").unwrap_or_else(|_| "x86_64-w64-mingw32-windres".into());
    let ok = Command::new(windres).arg(&rc).args(["-O", "coff", "-o"]).arg(&obj).status().is_ok_and(|s| s.success());
    assert!(ok, "windres couldn't build the icon and manifest");
    println!("cargo:rustc-link-arg-bins={}", obj.display());
}

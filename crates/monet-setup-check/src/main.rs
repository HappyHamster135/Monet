#[cfg(windows)]
mod native;
#[cfg(windows)]
mod win_deploy;

#[cfg(windows)]
fn run() -> Result<(), String> {
    use monet_setup_check::{select, Manifest};
    use std::io::Read;
    let args: Vec<_> = std::env::args().skip(1).collect();
    if args.len() == 2 && args[0] == "--deploy" {
        return win_deploy::run(std::path::Path::new(&args[1]));
    }
    if args.len() != 2 || args[1].len() != 1 {
        return Err("Usage: monet-setup-check.exe <preparation.json> <setup drive letter>".into());
    }
    let mut data = Vec::new();
    std::fs::File::open(&args[0])
        .map_err(|e| e.to_string())?
        .take(16 * 1024 + 1)
        .read_to_end(&mut data)
        .map_err(|e| e.to_string())?;
    if data.len() > 16 * 1024 {
        return Err("The preparation record is too large.".into());
    }
    let manifest: Manifest =
        serde_json::from_slice(&data).map_err(|e| format!("Invalid preparation record: {e}"))?;
    manifest.validate()?;
    let volumes = native::volumes(&manifest.disk_guid, &manifest.efi.guid)
        .map_err(|e| format!("Could not inspect the Windows disks: {e}"))?;
    let selection = select(&manifest, args[1].chars().next().unwrap(), &volumes)?;
    println!(
        "{}",
        serde_json::to_string(&selection).map_err(|e| e.to_string())?
    );
    Ok(())
}

#[cfg(windows)]
fn main() -> std::process::ExitCode {
    match run() {
        Ok(()) => std::process::ExitCode::SUCCESS,
        Err(error) => {
            eprintln!("Windows Setup: {error}");
            std::process::ExitCode::FAILURE
        }
    }
}

#[cfg(not(windows))]
fn main() -> std::process::ExitCode {
    eprintln!("Monet's read-only Windows Setup checker runs on Windows.");
    std::process::ExitCode::FAILURE
}

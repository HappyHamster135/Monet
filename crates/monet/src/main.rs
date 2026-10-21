//! `monet`: play Windows games from Monet with one click.

mod efivarfs;
mod esp;

use std::fs;
use std::io::IsTerminal;
use std::os::unix::process::CommandExt;
use std::path::PathBuf;
use std::process::{Command, ExitCode};
use std::time::{SystemTime, UNIX_EPOCH};

use monet_core::boot::{self, BootEntry};
use monet_core::efi::{EfiError, EfiVars, GLOBAL_GUID, LAUNCH_VAR, MONET_GUID};
use monet_core::games::{self, GameList};
use monet_core::request::{self, LaunchRequest};

use efivarfs::EfiVarFs;

const HELP: &str = "\
Monet: play Windows games with one click.

Usage:
  monet                     Show status
  monet play <game>         Restart in Windows and start a game
  monet windows             Restart in Windows
  monet games [--json]      List Windows games
  monet doctor              Check that everything is set up
  monet make-default        Start Monet by default when the PC turns on
  monet shortcuts           Add Windows games to the app menu

Options:
  --confirm                 Ask before restarting (used by the app menu)
";

type Res<T> = Result<T, String>;

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let confirm = args.iter().any(|a| a == "--confirm");
    let json = args.iter().any(|a| a == "--json");
    let mut words = Vec::new();
    let mut iter = args.iter();
    while let Some(arg) = iter.next() {
        if arg == "--game" {
            iter.next();
        } else if !arg.starts_with("--") {
            words.push(arg.as_str());
        }
    }

    let result = match words.as_slice() {
        [] if args.iter().any(|a| a == "--version") => {
            println!("monet {}", monet_core::VERSION);
            Ok(())
        }
        [] if args.iter().any(|a| a == "--help") => {
            print!("{HELP}");
            Ok(())
        }
        [] | ["status"] => status(),
        ["help"] => {
            print!("{HELP}");
            Ok(())
        }
        ["version"] => {
            println!("monet {}", monet_core::VERSION);
            Ok(())
        }
        ["games"] => list_games(json),
        ["play", id] => switch(Some(id), confirm),
        ["windows"] => switch(None, confirm),
        ["doctor"] => doctor(),
        ["make-default"] => elevate(&["helper", "make-default"]),
        ["shortcuts"] => shortcuts(),
        ["helper", "switch"] => helper_switch(option_value(&args, "--game")),
        ["helper", "sync"] => helper_sync(),
        ["helper", "make-default"] => helper_make_default(),
        _ => Err("Unknown command. Run `monet help` to see what Monet can do.".to_string()),
    };

    match result {
        Ok(()) => ExitCode::SUCCESS,
        Err(message) => {
            show_error(&message, confirm);
            ExitCode::FAILURE
        }
    }
}

fn option_value(args: &[String], name: &str) -> Option<String> {
    let pos = args.iter().position(|a| a == name)?;
    args.get(pos + 1).cloned()
}

fn now() -> u64 {
    SystemTime::now().duration_since(UNIX_EPOCH).map(|d| d.as_secs()).unwrap_or(0)
}

fn state_dir() -> PathBuf {
    std::env::var_os("MONET_STATE_DIR")
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from("/var/lib/monet"))
}

fn games_cache() -> PathBuf {
    state_dir().join("games.json")
}

fn load_games() -> Option<GameList> {
    GameList::parse(&fs::read(games_cache()).ok()?).ok()
}

fn efi() -> Res<EfiVarFs> {
    EfiVarFs::open().map_err(|_| {
        "This PC didn't start in UEFI mode, so Monet can't switch to Windows.".to_string()
    })
}

fn find_windows(efi: &dyn EfiVars) -> Res<BootEntry> {
    let entries = boot::list_entries(efi).map_err(|e| format!("Couldn't read the boot entries: {e}"))?;
    boot::find_windows(&entries).cloned().ok_or_else(|| {
        "Windows wasn't found on this PC. Install Windows first, then try again.".to_string()
    })
}

fn ago(then: u64) -> String {
    let secs = now().saturating_sub(then);
    match secs {
        0..=89 => "just now".into(),
        90..=5399 => format!("{} minutes ago", (secs + 30) / 60),
        5400..=129_599 => format!("{} hours ago", (secs + 1800) / 3600),
        _ => format!("{} days ago", (secs + 43_200) / 86_400),
    }
}

// ---------------------------------------------------------------- user commands

fn status() -> Res<()> {
    println!("Monet {}\n", monet_core::VERSION);
    let windows = match efi() {
        Ok(efi) => match find_windows(&efi) {
            Ok(_) => "Ready".to_string(),
            Err(_) => "Not found".to_string(),
        },
        Err(_) => "Unavailable (not a UEFI system)".to_string(),
    };
    println!("  Windows   {windows}");
    match load_games() {
        Some(list) if !list.games.is_empty() => {
            let n = list.games.len();
            let noun = if n == 1 { "game" } else { "games" };
            println!("  Games     {n} Windows {noun}, updated {}", ago(list.updated));
        }
        _ => println!("  Games     None yet. Start Windows once with Monet Bridge installed."),
    }
    println!("\nRun `monet help` to see what Monet can do.");
    Ok(())
}

fn list_games(json: bool) -> Res<()> {
    let list = load_games().unwrap_or_default();
    if json {
        println!("{}", serde_json::to_string(&list.games).map_err(|e| e.to_string())?);
        return Ok(());
    }
    if list.games.is_empty() {
        println!("No Windows games yet. Start Windows once with Monet Bridge installed.");
        return Ok(());
    }
    let width = list.games.iter().map(|g| g.name.chars().count()).max().unwrap_or(0);
    for game in &list.games {
        println!("{:width$}   {}", game.name, game.id);
    }
    Ok(())
}

fn switch(game: Option<&str>, confirm: bool) -> Res<()> {
    if let Some(id) = game {
        if !games::is_valid_id(id) {
            return Err(format!("\"{id}\" isn't a game Monet knows. Run `monet games` to see the list."));
        }
    }
    // Check before asking anything, so problems show up right away.
    let efi = efi()?;
    find_windows(&efi)?;

    if confirm {
        let name = game.and_then(|id| load_games()?.find(id).map(|g| g.name.clone()));
        let title = match (&name, game) {
            (Some(name), _) => format!("Play {name} on Windows?"),
            (None, Some(_)) => "Play on Windows?".to_string(),
            (None, None) => "Restart in Windows?".to_string(),
        };
        let text = match game {
            Some(_) => "Your PC will restart in Windows and start the game. When you quit, it comes back to Monet.",
            None => "Your PC will restart in Windows. Open apps will close.",
        };
        if !ask(&title, text, "Restart") {
            return Ok(());
        }
    }

    let mut args = vec!["helper", "switch"];
    if let Some(id) = game {
        args.extend(["--game", id]);
    }
    elevate(&args)
}

fn doctor() -> Res<()> {
    let ok = |s: &str| println!("  ✓  {s}");
    let warn = |s: &str| println!("  !  {s}");
    let bad = |s: &str| println!("  ✗  {s}");
    println!("Monet {}\n", monet_core::VERSION);

    let Ok(efi) = efi() else {
        bad("This PC didn't start in UEFI mode. Monet needs UEFI.");
        return Ok(());
    };
    ok("UEFI firmware");

    match efi.get(GLOBAL_GUID, "SecureBoot") {
        Ok(v) if v.first() == Some(&1) => ok("Secure Boot is on"),
        Ok(_) => warn("Secure Boot is off. Some anti-cheat games (Valorant, Call of Duty) need it on."),
        Err(_) => warn("Couldn't read the Secure Boot state"),
    }

    let entries = boot::list_entries(&efi).unwrap_or_default();
    match boot::find_windows(&entries) {
        Some(w) => ok(&format!("Windows found ({}, entry {:04X})", w.option.description, w.number)),
        None => bad("Windows wasn't found. Install Windows on this PC first."),
    }

    match (boot::boot_current(&efi), boot::boot_order(&efi)) {
        (Ok(current), Ok(order)) if order.first() == Some(&current) => ok("Monet starts by default"),
        (Ok(_), Ok(_)) => warn("Another system starts by default. Run `monet make-default` to fix it."),
        _ => warn("Couldn't read the boot order"),
    }

    if efi.get(MONET_GUID, LAUNCH_VAR).is_ok() {
        warn("A Windows game launch is still waiting. It is ignored after 6 hours.");
    }

    match load_games() {
        Some(list) if !list.games.is_empty() => {
            ok(&format!("{} Windows games, updated {}", list.games.len(), ago(list.updated)))
        }
        _ => warn("No Windows games yet. Install Monet Bridge in Windows and start Windows once."),
    }

    let enabled = Command::new("systemctl")
        .args(["is-enabled", "--quiet", "monet-sync.service"])
        .status()
        .map(|s| s.success())
        .unwrap_or(false);
    if enabled {
        ok("Games list syncs at startup");
    } else {
        warn("The games sync service isn't enabled. Run the Monet installer again.");
    }

    if fs::read_dir("/etc/polkit-1/rules.d")
        .map(|d| d.filter_map(|e| e.ok()).any(|e| e.file_name().to_string_lossy().contains("monet")))
        .unwrap_or(false)
    {
        ok("One-click switching is allowed without a password");
    } else {
        warn("Switching will ask for your password. Run the Monet installer again to fix it.");
    }

    if let Ok(version) = fs::read_to_string("/proc/driver/nvidia/version") {
        let line = version.lines().next().unwrap_or("").to_string();
        let driver = line.split_whitespace().find(|w| w.chars().next().is_some_and(|c| c.is_ascii_digit()) && w.contains('.'));
        ok(&format!("NVIDIA driver {}", driver.unwrap_or("loaded")));
    }
    Ok(())
}

/// Adds every Windows game to the app menu, so it can be found by search.
fn shortcuts() -> Res<()> {
    let home = std::env::var_os("HOME").ok_or("HOME isn't set")?;
    let dir = PathBuf::from(home).join(".local/share/applications");
    fs::create_dir_all(&dir).map_err(|e| e.to_string())?;
    let exe = std::env::current_exe().map_err(|e| e.to_string())?;
    let list = load_games().unwrap_or_default();

    let mut wanted = Vec::new();
    for game in &list.games {
        let file = format!("monet-game-{}.desktop", game.id.replace(':', "-"));
        let entry = format!(
            "[Desktop Entry]\nType=Application\nName={}\nComment=Plays on Windows\nExec={} play {} --confirm\nIcon=monet-windows\nCategories=Game;\nX-Monet-Game={}\n",
            game.name.replace('\\', "\\\\"),
            exe.display(),
            game.id,
            game.id
        );
        let path = dir.join(&file);
        if fs::read_to_string(&path).ok().as_deref() != Some(entry.as_str()) {
            fs::write(&path, entry).map_err(|e| e.to_string())?;
        }
        wanted.push(file);
    }

    for entry in fs::read_dir(&dir).map_err(|e| e.to_string())?.filter_map(|e| e.ok()) {
        let name = entry.file_name().to_string_lossy().into_owned();
        if name.starts_with("monet-game-") && name.ends_with(".desktop") && !wanted.contains(&name) {
            let _ = fs::remove_file(entry.path());
        }
    }
    Ok(())
}

// ---------------------------------------------------------------- helpers (root)

fn is_root() -> bool {
    // SAFETY: geteuid has no preconditions.
    unsafe { libc::geteuid() == 0 }
}

/// Runs a helper command as root. pkexec asks for nothing when the Monet
/// polkit rule is installed.
fn elevate(args: &[&str]) -> Res<()> {
    let exe = std::env::current_exe().map_err(|e| e.to_string())?;
    if is_root() {
        let status = Command::new(&exe).args(args).status().map_err(|e| e.to_string())?;
        return if status.success() { Ok(()) } else { Err(String::new()) };
    }
    let err = Command::new("pkexec").arg(&exe).args(args).exec();
    Err(format!("Couldn't get permission to switch: {err}"))
}

fn require_root() -> Res<()> {
    if is_root() {
        Ok(())
    } else {
        Err("This needs to run as root.".into())
    }
}

fn helper_switch(game: Option<String>) -> Res<()> {
    require_root()?;
    let mut efi = efi()?;
    let windows = find_windows(&efi)?;
    let current = boot::boot_current(&efi)
        .map_err(|e| format!("Couldn't tell which boot entry Monet started from: {e}"))?;
    if current == windows.number {
        return Err("Monet seems to have started from the Windows entry, which shouldn't happen.".into());
    }

    let request = LaunchRequest::new(game, current, now()).map_err(|e| e.to_string())?;
    request::write(&mut efi, &request).map_err(|e| format!("Couldn't save the game request: {e}"))?;
    if let Err(e) = boot::set_boot_next(&mut efi, windows.number) {
        let _ = request::clear(&mut efi);
        return Err(format!("Couldn't set Windows to start next: {e}"));
    }

    if std::env::var_os("MONET_NO_REBOOT").is_some() {
        println!("Windows starts on the next restart.");
        return Ok(());
    }
    let status = Command::new("systemctl").arg("reboot").status().map_err(|e| e.to_string())?;
    if status.success() {
        Ok(())
    } else {
        Err("The restart was blocked. Restart your PC to continue in Windows.".into())
    }
}

fn helper_sync() -> Res<()> {
    require_root()?;
    let Some(list) = esp::find_games_list() else {
        return Ok(());
    };
    let dir = state_dir();
    fs::create_dir_all(&dir).map_err(|e| e.to_string())?;
    let tmp = dir.join(".games.json.tmp");
    fs::write(&tmp, list.to_json()).map_err(|e| e.to_string())?;
    fs::rename(&tmp, games_cache()).map_err(|e| e.to_string())?;
    println!("Synced {} Windows games.", list.games.len());
    Ok(())
}

fn helper_make_default() -> Res<()> {
    require_root()?;
    let mut efi = efi()?;
    let current = boot::boot_current(&efi).map_err(|e| e.to_string())?;
    match boot::move_to_front(&mut efi, current) {
        Ok(true) => println!("Monet now starts by default."),
        Ok(false) => println!("Monet already starts by default."),
        Err(EfiError::Invalid(_)) => return Err("Monet's boot entry isn't in the boot order.".into()),
        Err(e) => return Err(e.to_string()),
    }
    Ok(())
}

// ---------------------------------------------------------------- dialogs

fn has(cmd: &str) -> bool {
    Command::new("sh")
        .args(["-c", &format!("command -v {cmd} >/dev/null 2>&1")])
        .status()
        .map(|s| s.success())
        .unwrap_or(false)
}

/// Asks a yes/no question with a native dialog. Without a dialog tool the
/// click that started us counts as the answer.
fn ask(title: &str, text: &str, ok_label: &str) -> bool {
    if has("kdialog") {
        return Command::new("kdialog")
            .args(["--title", title, "--continue-label", ok_label, "--warningcontinuecancel", text])
            .status()
            .map(|s| s.success())
            .unwrap_or(false);
    }
    if has("zenity") {
        return Command::new("zenity")
            .args(["--question", "--title", title, "--text", text, "--ok-label", ok_label, "--cancel-label", "Cancel"])
            .status()
            .map(|s| s.success())
            .unwrap_or(false);
    }
    true
}

fn show_error(message: &str, gui: bool) {
    if message.is_empty() {
        return;
    }
    eprintln!("{message}");
    if gui && !std::io::stderr().is_terminal() {
        if has("kdialog") {
            let _ = Command::new("kdialog").args(["--title", "Monet", "--sorry", message]).status();
        } else if has("zenity") {
            let _ = Command::new("zenity").args(["--warning", "--title", "Monet", "--text", message]).status();
        }
    }
}

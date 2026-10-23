//! `monet`: play Windows games from Monet with one click.

/// Marks words people read, for tools/make-translations.py. They're said in the
/// person's language where they're shown: `say()` here, Settings' i18n, or the
/// session's `monet-quick say`.
macro_rules! t {
    ($text:literal) => {
        $text
    };
}

mod efivarfs;
mod esp;
mod trip;
mod windows_setup;

use std::fs;
use std::io::IsTerminal;
use std::os::unix::process::CommandExt;
use std::path::{Path, PathBuf};
use std::process::{Command, ExitCode};
use std::time::{SystemTime, UNIX_EPOCH};

use monet_core::boot::{self, BootEntry};
use monet_core::efi::{EfiError, EfiVars, GLOBAL_GUID, LAUNCH_VAR, MONET_GUID};
use monet_core::games::{self, Game, GameList};
use monet_core::request::{self, LaunchRequest};

use efivarfs::EfiVarFs;
use trip::{Method, Trip};
use windows_setup::Outcome;

const HELP: &str = "\
Monet: play Windows games with one click.

Usage:
  monet                     Show status
  monet play <game>         Restart in Windows and start a game
  monet windows             Restart in Windows
  monet games [--json]      List Windows games
  monet doctor              Check that everything is set up
  monet update              Install the newest Monet and app updates (Monet starts
                            the new version at the next restart)
  monet update --check      Only look: is there anything new?
  monet auto-updates on|off Update by itself in the background (on unless turned off)
  monet rollback            Go back to the Monet from before the last update (at the
                            next restart)
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
        if arg == "--game" || arg == "--iso" {
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
        ["windows"] if args.iter().any(|a| a == "--first-run") => first_run_windows(),
        ["windows"] => switch(None, confirm),
        ["doctor"] => doctor(),
        ["make-default"] => elevate(&["helper", "make-default"]),
        ["update"] if args.iter().any(|a| a == "--check") => {
            let helper: &[&str] = if json { &["helper", "update", "--check", "--json"] } else { &["helper", "update", "--check"] };
            elevate(helper)
        }
        ["update"] => elevate(&["helper", "update"]),
        ["helper", "update"] => helper_update(args.iter().any(|a| a == "--check"), json),
        ["auto-updates", which @ ("on" | "off")] => elevate(&["helper", "auto-updates", *which]),
        ["helper", "auto-updates", which @ ("on" | "off")] => helper_auto_updates(*which == "on"),
        ["rollback"] => elevate(&["helper", "rollback"]),
        ["helper", "rollback"] => helper_rollback(),
        ["shortcuts"] => shortcuts(),
        ["helper", "switch"] => helper_switch(option_value(&args, "--game")),
        ["helper", "check-switch"] => helper_check_switch(),
        ["helper", "sync"] => helper_sync(),
        ["helper", "make-default"] => helper_make_default(),
        ["helper", "stage-windows"] => helper_stage_windows().map(|_| ()),
        ["helper", "prepare-windows"] => helper_prepare_windows(option_value(&args, "--iso")),
        ["setup-notice"] => {
            if let Some(message) = notice() {
                println!("{message}");
            }
            Ok(())
        }
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

/// The games Monet Bridge found in Windows.
fn load_games() -> Option<GameList> {
    GameList::parse(&fs::read(games_cache()).ok()?).ok()
}

/// Games Monet always offers on Windows, even before Windows has them:
/// `share/monet/windows-games.json` (comes with Monet) and
/// `~/.config/monet/windows-games.json` (your own), both in the games-list format.
fn extra_games() -> Vec<Game> {
    let mut files: Vec<PathBuf> = windows_setup::share_dir().map(|d| d.join("windows-games.json")).into_iter().collect();
    if let Some(home) = std::env::var_os("HOME") {
        files.push(PathBuf::from(home).join(".config/monet/windows-games.json"));
    }
    files
        .iter()
        .filter_map(|f| GameList::parse(&fs::read(f).ok()?).ok())
        .flat_map(|l| l.games)
        .collect()
}

/// Everything that plays on Windows: what Windows has, plus the extras.
fn all_games() -> GameList {
    let mut list = load_games().unwrap_or_default();
    for game in extra_games() {
        if list.find(&game.id).is_none() {
            list.games.push(game);
        }
    }
    list.games.sort_by_key(|g| g.name.to_lowercase());
    list
}

fn windows_setup_status() -> Option<Outcome> {
    if load_games().is_some_and(|l| !l.games.is_empty()) {
        return Some(Outcome::Installed);
    }
    Outcome::from_code(&fs::read_to_string(state_dir().join(windows_setup::STATUS_FILE)).ok()?)
}

fn save_windows_setup_status(outcome: Outcome) {
    let _ = fs::create_dir_all(state_dir());
    let _ = fs::write(state_dir().join(windows_setup::STATUS_FILE), outcome.code());
}

/// A one-line message when the user needs to do something to finish setup.
/// Something the person should know at sign-in: a trip to Windows that went
/// wrong, or Windows setup that needs a hand.
fn notice() -> Option<String> {
    let trip = fs::read_to_string(trip_paths().notice()).unwrap_or_default();
    if !trip.trim().is_empty() {
        return Some(trip.trim().to_string());
    }
    setup_notice().map(str::to_string)
}

fn trip_paths() -> trip::Paths {
    trip::Paths::new(state_dir())
}

fn setup_notice() -> Option<&'static str> {
    match windows_setup_status()? {
        Outcome::DownloadFailed | Outcome::Failed | Outcome::NoSpace => {
            Some(t!("Windows isn't installed yet. Choose Windows in the app menu to finish setting it up."))
        }
        Outcome::BitLocker => Some(t!(
            "Windows is encrypted with BitLocker, so Monet can't set it up for you. \
             In Windows, open Monet for Windows and run Install Monet."
        )),
        Outcome::Hibernated => {
            Some(t!("Windows is asleep, so Monet can't set it up yet. Open Windows, choose Restart, and Monet finishes the rest."))
        }
        _ => None,
    }
}

fn efi() -> Res<EfiVarFs> {
    EfiVarFs::open().map_err(|_| {
        t!("This PC didn't start in UEFI mode, so Monet can't switch to Windows.").to_string()
    })
}

/// The Windows boot entry that can start (old, dead entries are skipped).
fn find_windows(efi: &dyn EfiVars) -> Res<BootEntry> {
    trip::choose(efi, &trip_paths())
        .ok_or_else(|| t!("Windows wasn't found on this PC. Install Windows first, then try again.").to_string())
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
            Ok(_) => t!("Ready").to_string(),
            Err(_) => t!("Not found").to_string(),
        },
        Err(_) => t!("Unavailable (not a UEFI system)").to_string(),
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
    let list = all_games();
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
    if find_windows(&efi).is_err() && windows_setup_status().is_some_and(Outcome::is_fresh_install) {
        // Installing Windows downloads a lot and restarts: only when asked
        // (the app menu's Windows), never from a Play button.
        if !confirm {
            return Err(t!("Windows isn't installed yet. Choose Windows in the app menu to finish setting it up.").into());
        }
        return finish_windows_setup(true);
    }
    // Otherwise the helper finds Windows, or makes it a boot entry if the
    // PC lost it, and says so if it can't.

    if confirm {
        let name = game.and_then(|id| all_games().find(id).map(|g| g.name.clone()));
        let title = match (&name, game) {
            (Some(name), _) => say(t!("Play %1 on Windows?"), &[name.as_str()]),
            (None, Some(_)) => t!("Play on Windows?").to_string(),
            (None, None) => t!("Restart in Windows?").to_string(),
        };
        let text = match game {
            Some(_) => t!("Your PC will restart in Windows and start the game. When you quit, it comes back to Monet."),
            None => t!("Your PC will restart in Windows. Open apps will close."),
        };
        if !ask(&title, text, t!("Restart")) {
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

    let paths = trip_paths();
    let windows = trip::describe(&efi, &paths);
    for (entry, reach) in &windows {
        if *reach == boot::Reach::No {
            warn(&format!("Boot{:04X} is an old Windows entry that can't start. Monet skips it.", entry.number));
        }
    }
    match trip::choose(&efi, &paths) {
        Some(w) => ok(&format!("Windows found ({}, entry {:04X})", w.option.description, w.number)),
        None if windows.is_empty() => bad("Windows wasn't found. Install Windows on this PC first."),
        None => bad("None of the Windows boot entries can start. Choose Play and Monet makes a new one."),
    }
    if trip::firmware_skips_boot_next(&paths) {
        warn("This PC skips one-time starts, so Monet puts Windows first for each trip and back after.");
    }
    if let Ok(text) = fs::read_to_string(paths.notice()) {
        warn(text.trim());
    }

    match (boot::boot_current(&efi), boot::boot_order(&efi)) {
        (Ok(current), Ok(order)) if order.first() == Some(&current) => ok("Monet starts by default"),
        (Ok(_), Ok(_)) => warn("Another system starts by default. Run `monet make-default` to fix it."),
        _ => warn("Couldn't read the boot order"),
    }

    if efi.get(MONET_GUID, LAUNCH_VAR).is_ok() {
        warn("A Windows game launch is still waiting. It is ignored after 6 hours.");
    }

    match windows_setup_status() {
        Some(Outcome::Installed) => ok("Monet Bridge is installed in Windows"),
        Some(Outcome::Staged) => warn("Windows is ready. Open Windows once to finish setting up."),
        Some(Outcome::NotFound) => bad("Windows wasn't found when Monet looked for it."),
        Some(Outcome::NoPayload) => warn("This copy of Monet doesn't include the Windows files."),
        Some(Outcome::Pending) => warn("Windows installs itself at the next restart."),
        Some(Outcome::Waiting) => warn("Windows downloads and gets ready after you sign in to Monet."),
        Some(Outcome::Preparing) => warn("Windows is being downloaded and prepared."),
        Some(Outcome::DownloadFailed) => {
            bad("Windows couldn't be downloaded. Choose Windows in the app menu to try again.")
        }
        Some(Outcome::NoSpace) => bad("There isn't enough free space on the disk for Windows."),
        Some(Outcome::Failed) => {
            bad("Windows couldn't be prepared. See /var/log/monet-windows.log, or choose Windows to try again.")
        }
        Some(_) => warn(setup_notice().unwrap_or("Windows isn't set up yet.")),
        None => warn("Windows hasn't been set up yet. It happens at the next restart."),
    }

    match load_games() {
        Some(list) if !list.games.is_empty() => {
            ok(&format!("{} Windows games, updated {}", list.games.len(), ago(list.updated)))
        }
        _ => warn("No Windows games yet. They show up after Windows has started once with Monet Bridge."),
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
    let list = all_games();

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
    // Windows is shut down right now, the safest moment to prepare it.
    if !windows_setup_status().is_some_and(Outcome::is_done) {
        let _ = helper_stage_windows();
    }
    let paths = trip_paths();
    let mut efi = efi()?;
    let current = boot::boot_current(&efi)
        .map_err(|e| format!("Couldn't tell which boot entry Monet started from: {e}"))?;
    let windows = match trip::choose(&efi, &paths) {
        Some(w) => w,
        None => {
            // The PC lost Windows' entry, or only has dead ones: make one
            // from Windows' boot manager on the EFI partition.
            match trip::add_windows_entry(&mut efi, current) {
                Ok(true) => trip::log(&paths, now(), "added a Windows Boot Manager entry"),
                Ok(false) => {}
                Err(e) => trip::log(&paths, now(), &format!("couldn't add a Windows entry: {e}")),
            }
            trip::choose(&efi, &paths)
                .ok_or(t!("Windows wasn't found on this PC. Install Windows first, then try again."))?
        }
    };
    if current == windows.number {
        return Err(t!("Monet seems to have started from the Windows entry, which shouldn't happen.").into());
    }

    // A Windows that's still finishing its own setup restarts on the way, and
    // some firmware ignores one-time starts: then Windows goes first in the
    // boot order too, and Monet Bridge (or Monet's next start) puts Monet back.
    let installed = windows_setup_status() == Some(Outcome::Installed);
    let method = if installed && !trip::firmware_skips_boot_next(&paths) { Method::Once } else { Method::First };

    let request = LaunchRequest::new(game, current, now()).map_err(|e| e.to_string())?;
    request::write(&mut efi, &request).map_err(|e| format!("Couldn't save the game request: {e}"))?;
    let undo = |efi: &mut EfiVarFs| {
        let _ = request::clear(efi);
        let _ = efi.delete(GLOBAL_GUID, "BootNext");
        let _ = boot::move_to_front(efi, current);
    };
    if let Err(e) = boot::set_boot_next(&mut efi, windows.number) {
        undo(&mut efi);
        return Err(format!("Couldn't set Windows to start next: {e}"));
    }
    if method == Method::First {
        if let Err(e) = trip::put_windows_first(&mut efi, windows.number) {
            undo(&mut efi);
            return Err(format!("Couldn't put Windows first: {e}"));
        }
    }
    // Make sure the firmware really has both before restarting.
    let next_ok = matches!(boot::boot_next(&efi), Ok(Some(n)) if n == windows.number);
    if !next_ok || efi.get(MONET_GUID, LAUNCH_VAR).is_err() {
        undo(&mut efi);
        trip::log(&paths, now(), &format!("the firmware didn't keep the switch: {}", trip::snapshot(&efi)));
        return Err(
            t!("This PC's firmware didn't keep the switch to Windows. Restart and choose Windows in the PC's boot menu.").into(),
        );
    }

    let trip = Trip { created: now(), entry: windows.number, monet: current, method };
    trip::save(&paths, &trip)?;
    trip::log(
        &paths,
        now(),
        &format!(
            "to Boot{:04X} ({method:?}) for {}; Monet {}; {}",
            windows.number,
            request.game.as_deref().unwrap_or("Windows"),
            monet_core::VERSION,
            trip::snapshot(&efi)
        ),
    );

    if std::env::var_os("MONET_NO_REBOOT").is_some() {
        println!("Windows starts on the next restart.");
        return Ok(());
    }
    // Through the firmware: a soft reboot or kexec would skip BootNext.
    let status = Command::new("systemctl")
        .arg("reboot")
        .env("SYSTEMCTL_SKIP_AUTO_SOFT_REBOOT", "1")
        .env("SYSTEMCTL_SKIP_AUTO_KEXEC", "1")
        .status()
        .map_err(|e| e.to_string())?;
    if status.success() {
        Ok(())
    } else {
        Err(t!("The restart was blocked. Restart your PC to continue in Windows.").into())
    }
}

/// At Monet's start (monet-sync.service): if a trip to Windows just came
/// back without Windows, say why, tidy up, and try another way next time.
fn helper_check_switch() -> Res<()> {
    require_root()?;
    let Ok(mut efi) = EfiVarFs::open() else { return Ok(()) };
    let paths = trip_paths();
    let setup_done = windows_setup_status() == Some(Outcome::Installed);
    if let Some(notice) = trip::check_after_boot(&mut efi, &paths, now(), setup_done) {
        println!("{notice}");
    }
    // Windows' boot manager is on an EFI partition but no entry can start it
    // (bcdboot didn't add one, or only dead ones are left): add one, so Play
    // works. Monet stays first.
    if trip::choose(&efi, &paths).is_none() {
        if let Ok(current) = boot::boot_current(&efi) {
            match trip::add_windows_entry(&mut efi, current) {
                Ok(true) => trip::log(&paths, now(), "added a Windows Boot Manager entry at startup"),
                Ok(false) => {}
                Err(e) => trip::log(&paths, now(), &format!("couldn't add a Windows entry at startup: {e}")),
            }
        }
    }
    Ok(())
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
    save_windows_setup_status(Outcome::Installed);
    remove_setup_boot_entry();
    println!("Synced {} Windows games.", list.games.len());
    Ok(())
}

fn helper_stage_windows() -> Res<Outcome> {
    require_root()?;
    if let Some(done) = windows_setup_status().filter(|o| o.is_done()) {
        return Ok(done);
    }
    let outcome = windows_setup::stage(windows_setup::payload_dir().as_deref())?;
    // Before Monet's own Windows install has run, its partition is empty.
    let fresh = windows_setup_status().is_some_and(Outcome::is_fresh_install);
    if !(fresh && outcome == Outcome::NotFound) {
        save_windows_setup_status(outcome);
    }
    println!(
        "{}",
        match outcome {
            Outcome::Staged => "Windows is ready. Monet Bridge installs the next time Windows starts.",
            Outcome::Installed => "Monet Bridge is already installed in Windows.",
            Outcome::NotFound => "Windows wasn't found on this PC.",
            Outcome::NoPayload => "This copy of Monet doesn't include the Windows files.",
            Outcome::BitLocker | Outcome::Hibernated => setup_notice().unwrap_or_default(),
            _ => "",
        }
    );
    Ok(outcome)
}

/// Removes the one-time "Monet Windows Setup" boot entry after Windows is in.
fn remove_setup_boot_entry() {
    let Ok(mut efi) = EfiVarFs::open() else { return };
    let entries = boot::list_entries(&efi).unwrap_or_default();
    for entry in entries.iter().filter(|e| e.option.description == "Monet Windows Setup") {
        let mut order = boot::boot_order(&efi).unwrap_or_default();
        order.retain(|n| *n != entry.number);
        let _ = efi.set(GLOBAL_GUID, "BootOrder", &monet_core::efi::write_u16_list(&order), monet_core::efi::ATTR_DEFAULT);
        let _ = efi.delete(GLOBAL_GUID, &monet_core::efi::boot_var_name(entry.number));
    }
}

/// Runs the Windows download and setup (the "Monet and Windows" install).
fn helper_prepare_windows(iso: Option<String>) -> Res<()> {
    require_root()?;
    let script = windows_setup::libexec_dir()
        .map(|d| d.join("monet-prepare-windows"))
        .filter(|p| p.is_file())
        .ok_or(t!("This copy of Monet can't install Windows by itself."))?;
    let mut cmd = Command::new(script);
    if let Some(iso) = iso {
        cmd.args(["--iso", &iso]);
    }
    let status = cmd.status().map_err(|e| e.to_string())?;
    if status.success() {
        Ok(())
    } else {
        Err(String::new())
    }
}

/// When Monet's own Windows install didn't finish: try again, from a file
/// in Downloads if there is one, then restart into the Windows install.
/// "Monet and Windows": right after the first sign-in, Windows downloads with
/// its progress showing, then Monet asks to restart and install it. (The
/// installer used to do this silently at its very end.)
fn first_run_windows() -> Res<()> {
    if windows_setup_status() != Some(Outcome::Waiting) {
        return Ok(());
    }
    let title = say(t!("Getting Windows ready for your games"), &[]);
    let text = say(
        t!("Monet is downloading Windows (about 7 GB). You can keep using your PC; Monet asks before it restarts."),
        &[],
    );
    let _ = Command::new("notify-send")
        .args(["--app-name=Monet", "--icon=monet-windows", title.as_str(), text.as_str()])
        .status();
    finish_windows_setup(false)
}

/// Downloads Windows and gets it ready to install itself, showing progress.
/// `ask_first`: ask before starting (the app menu); after the first sign-in
/// it was already chosen in the installer. Restarting is always asked.
fn finish_windows_setup(ask_first: bool) -> Res<()> {
    let iso = downloaded_windows_iso();
    let question = match &iso {
        Some(p) => say(
            t!("Monet can install Windows from %1. Your PC restarts and Windows installs itself."),
            &[p.file_name().map(|n| n.to_string_lossy().into_owned()).unwrap_or_default().as_str()],
        ),
        None => t!("Windows isn't installed yet. Monet downloads it from Microsoft (about 7 GB) and installs it. \
                 This takes about 30 minutes.")
        .to_string(),
    };
    if ask_first && !ask(t!("Set up Windows?"), &question, t!("Set Up")) {
        return Ok(());
    }
    let mut args = vec!["helper".to_string(), "prepare-windows".to_string()];
    if let Some(p) = &iso {
        args.extend(["--iso".to_string(), p.display().to_string()]);
    }
    let exe = std::env::current_exe().map_err(|e| e.to_string())?;
    let mut child = if is_root() {
        Command::new(&exe).args(&args).spawn()
    } else {
        Command::new("pkexec").arg(&exe).args(&args).spawn()
    }
    .map_err(|e| e.to_string())?;
    let code = show_progress_while(&mut child);
    // pkexec says 126 when the password prompt was dismissed: the person chose not to.
    if code == Some(126) && !is_root() {
        return Ok(());
    }
    let reason = fs::read_to_string(WINDOWS_PROGRESS).ok().and_then(|p| stop_reason(&p));
    match windows_setup_status() {
        Some(Outcome::Pending) if code == Some(0) => {
            if ask(
                t!("Windows is ready"),
                t!("Restart now to install Windows? It takes about 10 minutes, then you're back in Monet."),
                t!("Restart"),
            ) {
                let _ = Command::new("systemctl").arg("reboot").status();
            }
            Ok(())
        }
        Some(Outcome::DownloadFailed) => {
            let text = t!("Microsoft didn't allow the automatic download. Download Windows 11 from Microsoft's page \
                        (choose \"Download Windows 11 Disk Image (ISO)\"), keep it in Downloads, then choose Windows again.");
            if ask(t!("Download Windows"), text, t!("Open Microsoft's Page")) {
                let _ = Command::new("xdg-open").arg("https://www.microsoft.com/software-download/windows11").status();
            }
            Ok(())
        }
        // What went wrong in plain words; the helper's own account behind Details.
        Some(Outcome::NoSpace) => Err(format!(
            "{}. {}\n\n{}",
            capitalized(&say(reason.as_deref().unwrap_or(t!("there isn't enough free space for Windows")), &[])),
            say(t!("Windows needs about 72 GB of the disk to itself, and 16 GB free in Monet while it downloads."), &[]),
            windows_log_tail()
        )),
        _ => Err(format!(
            "{}\n\n{}",
            say(t!("Windows couldn't be set up this time. Choose Windows in the app menu to try again."), &[]),
            reason.map(|r| capitalized(&r) + ".\n\n").unwrap_or_default() + &windows_log_tail()
        )),
    }
}

/// Where the Windows helper says how far it is: "PERCENT<tab>WHAT IT'S DOING".
const WINDOWS_PROGRESS: &str = "/run/monet/windows-progress";

/// Why the Windows helper stopped, in its own words: when it gives up it leaves
/// "0<tab>there isn't enough free space ..." where its progress was.
fn stop_reason(progress: &str) -> Option<String> {
    let (percent, text) = progress.trim().split_once('\t')?;
    (percent == "0" && text != "Getting Windows ready").then(|| text.to_string())
}

fn capitalized(text: &str) -> String {
    let mut chars = text.chars();
    chars.next().map(|c| c.to_uppercase().chain(chars).collect()).unwrap_or_default()
}

/// The end of the Windows helper's log, for a dialog's Details.
fn windows_log_tail() -> String {
    let log = fs::read_to_string("/var/log/monet-windows.log").unwrap_or_default();
    let lines: Vec<&str> = log.lines().collect();
    lines[lines.len().saturating_sub(12)..].join("\n")
}

/// The Downloads folder as the account names it in `user-dirs.dirs` (xdg-user-dirs:
/// "Hämtningar" in Swedish), else ~/Downloads.
fn downloads_dir(home: &Path, user_dirs: &str) -> PathBuf {
    user_dirs
        .lines()
        .find_map(|line| line.trim().strip_prefix("XDG_DOWNLOAD_DIR="))
        .map(|value| PathBuf::from(value.trim_matches('"').replace("$HOME", &home.to_string_lossy())))
        .filter(|path| path.is_absolute() && path != home)
        .unwrap_or_else(|| home.join("Downloads"))
}

/// A Windows 11 ISO the user downloaded, newest first.
fn downloaded_windows_iso() -> Option<PathBuf> {
    let home = PathBuf::from(std::env::var_os("HOME")?);
    let config = std::env::var_os("XDG_CONFIG_HOME").map(PathBuf::from).unwrap_or_else(|| home.join(".config"));
    let dir = downloads_dir(&home, &fs::read_to_string(config.join("user-dirs.dirs")).unwrap_or_default());
    let mut isos: Vec<_> = fs::read_dir(dir)
        .ok()?
        .flatten()
        .map(|e| e.path())
        .filter(|p| {
            let name = p.file_name().map(|n| n.to_string_lossy().to_lowercase()).unwrap_or_default();
            name.ends_with(".iso") && name.contains("win")
        })
        .collect();
    isos.sort_by_key(|p| std::cmp::Reverse(fs::metadata(p).and_then(|m| m.modified()).ok()));
    isos.into_iter().next()
}

/// Shows a progress dialog fed by the setup script until it finishes, and
/// gives back how it ended (its exit code).
fn show_progress_while(child: &mut std::process::Child) -> Option<i32> {
    let first = say(t!("Getting Windows ready"), &[]);
    let dialog = Command::new("kdialog")
        .args(["--title", "Monet", "--progressbar", first.as_str(), "100"])
        .output()
        .ok()
        .map(|o| String::from_utf8_lossy(&o.stdout).split_whitespace().map(String::from).collect::<Vec<_>>())
        .filter(|parts| parts.len() == 2);
    let qdbus = ["qdbus6", "qdbus-qt6", "qdbus"].into_iter().find(|c| has(c));
    // The label as the helper wrote it, and as it's shown: said again only when it changes.
    let mut shown = (String::new(), String::new());
    loop {
        if let Ok(Some(status)) = child.try_wait() {
            if let (Some(d), Some(q)) = (&dialog, qdbus) {
                let _ = Command::new(q).args([&d[0], &d[1], "close"]).status();
            }
            return status.code();
        }
        if let (Some(d), Some(q), Ok(text)) = (&dialog, qdbus, fs::read_to_string(WINDOWS_PROGRESS)) {
            if let Some((pct, label)) = text.trim().split_once('\t') {
                // "TEXT<tab>VALUE...": TEXT in the person's language, its %1... filled in.
                if label != shown.0 {
                    let mut parts = label.split('\t');
                    let words = parts.next().unwrap_or_default();
                    let values: Vec<&str> = parts.collect();
                    shown = (label.to_string(), say(words, &values));
                }
                let _ = Command::new(q).args([&d[0], &d[1], "Set", "", "value", pct]).status();
                let _ = Command::new(q).args([&d[0], &d[1], "setLabelText", shown.1.as_str()]).status();
            }
        }
        std::thread::sleep(std::time::Duration::from_secs(2));
    }
}

/// What `monet update --check` found.
#[derive(Debug, PartialEq, Eq)]
struct UpdateCheck {
    /// A newer Monet is waiting to be downloaded.
    system: bool,
    /// Its version, when the image says.
    version: Option<String>,
    /// How many apps have updates.
    apps: usize,
}

/// Reads `bootc upgrade --check`: "Update available for: ..." with an
/// optional "  Version: ..." line, or "No changes in: ...".
fn parse_bootc_check(out: &str) -> Option<(bool, Option<String>)> {
    if out.contains("No changes in") {
        return Some((false, None));
    }
    if !out.contains("Update available") {
        return None;
    }
    let version = out
        .lines()
        .find_map(|l| l.trim().strip_prefix("Version:"))
        .map(|v| v.trim().to_string())
        .filter(|v| !v.is_empty());
    Some((true, version))
}

/// Counts the apps in `flatpak remote-ls --updates --columns=application`.
fn count_app_updates(out: &str) -> usize {
    out.lines().filter(|l| !l.trim().is_empty() && !l.starts_with("Application")).count()
}

fn check_for_updates() -> Res<UpdateCheck> {
    let offline = "Monet couldn't look for updates. Check your internet connection and try again.";
    let (system, version) = if has("bootc") {
        let out = Command::new("bootc").args(["upgrade", "--check"]).output().map_err(|e| e.to_string())?;
        if !out.status.success() {
            return Err(offline.into());
        }
        parse_bootc_check(&String::from_utf8_lossy(&out.stdout)).ok_or(offline)?
    } else {
        // rpm-ostree says 77 when there's nothing new.
        let status = Command::new("rpm-ostree").args(["upgrade", "--check"]).status().map_err(|e| e.to_string())?;
        match status.code() {
            Some(0) => (true, None),
            Some(77) => (false, None),
            _ => return Err(offline.into()),
        }
    };
    let apps = if has("flatpak") {
        Command::new("flatpak")
            .args(["remote-ls", "--updates", "--columns=application"])
            .output()
            .map(|o| count_app_updates(&String::from_utf8_lossy(&o.stdout)))
            .unwrap_or(0)
    } else {
        0
    };
    Ok(UpdateCheck { system, version, apps })
}

/// Where turning automatic updates off is kept: monet-update.service doesn't
/// run while it's there (ConditionPathExists=!).
const AUTO_UPDATES_OFF: &str = "auto-updates-off";

/// Automatic updates, on unless turned off: Settings → Updates or `monet auto-updates`.
fn helper_auto_updates(on: bool) -> Res<()> {
    require_root()?;
    let path = state_dir().join(AUTO_UPDATES_OFF);
    if on {
        if let Err(e) = fs::remove_file(&path) {
            if e.kind() != std::io::ErrorKind::NotFound {
                return Err(e.to_string());
            }
        }
        println!("Monet and your apps update by themselves.");
    } else {
        fs::create_dir_all(state_dir()).map_err(|e| e.to_string())?;
        fs::write(&path, "off\n").map_err(|e| e.to_string())?;
        println!("Monet updates only when you ask, in Settings → Updates.");
    }
    Ok(())
}

/// The Monet from before the last update starts at the next restart (bootc keeps
/// it, as the start menu's second entry): Settings → Updates → Go back.
fn helper_rollback() -> Res<()> {
    require_root()?;
    let status = if has("bootc") {
        Command::new("bootc").arg("rollback").status()
    } else {
        Command::new("rpm-ostree").arg("rollback").status()
    }
    .map_err(|e| e.to_string())?;
    if !status.success() {
        return Err("There's no earlier Monet on this PC to go back to.".into());
    }
    println!("The Monet from before starts the next time you restart.");
    Ok(())
}

/// Looks for updates, or installs them: when someone asks (Settings → Updates,
/// `monet update`), and daily by itself unless that's turned off (monet-update.timer).
fn helper_update(check: bool, json: bool) -> Res<()> {
    require_root()?;
    if check {
        let found = check_for_updates()?;
        if json {
            let value = serde_json::json!({ "system": found.system, "version": found.version, "apps": found.apps });
            println!("{value}");
        } else if !found.system && found.apps == 0 {
            println!("Monet and your apps are up to date.");
        } else {
            if found.system {
                println!("A new version of Monet is ready to install.");
            }
            if found.apps > 0 {
                println!("{} app update{} ready to install.", found.apps, if found.apps == 1 { " is" } else { "s are" });
            }
            println!("Run `monet update` to install.");
        }
        return Ok(());
    }

    println!("Downloading the newest Monet…");
    let status = if has("bootc") {
        Command::new("bootc").arg("upgrade").status()
    } else {
        Command::new("rpm-ostree").arg("upgrade").status()
    }
    .map_err(|e| e.to_string())?;
    if !status.success() {
        return Err("The update didn't finish. Check your internet connection and try again.".into());
    }
    if has("flatpak") {
        println!("Updating your apps…");
        // Apps that fail to update keep working as they are.
        let _ = Command::new("flatpak").args(["update", "-y", "--noninteractive"]).status();
        // And what no app uses anymore (old runtimes) makes room.
        let _ = Command::new("flatpak").args(["uninstall", "--unused", "-y", "--noninteractive"]).status();
    }
    println!("Done. Restart your PC to use the newest Monet.");
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

/// Words in the person's language, from Monet's catalog (the session's
/// `monet-quick say` looks them up), with %1, %2... filled in. English when
/// there's no translation or no helper.
fn say(text: &str, values: &[&str]) -> String {
    let said = windows_setup::libexec_dir()
        .map(|dir| dir.join("monet-quick"))
        .and_then(|helper| Command::new(helper).arg("say").arg(text).args(values).output().ok())
        .filter(|out| out.status.success() && !out.stdout.is_empty())
        .map(|out| String::from_utf8_lossy(&out.stdout).trim_end_matches('\n').to_string());
    said.unwrap_or_else(|| {
        let mut english = text.to_string();
        for (i, value) in values.iter().enumerate().rev() {
            english = english.replace(&format!("%{}", i + 1), value);
        }
        english
    })
}

/// Asks a yes/no question with a native dialog. Without a dialog tool the
/// click that started us counts as the answer.
fn ask(title: &str, text: &str, ok_label: &str) -> bool {
    let (title, text, ok_label, cancel) = (say(title, &[]), say(text, &[]), say(ok_label, &[]), say("Cancel", &[]));
    if has("kdialog") {
        // A question, not a warning: no warning sign for "Set up Windows?".
        return Command::new("kdialog")
            .args([
                "--title",
                title.as_str(),
                "--yes-label",
                ok_label.as_str(),
                "--no-label",
                cancel.as_str(),
                "--yesno",
                text.as_str(),
            ])
            .status()
            .map(|s| s.success())
            .unwrap_or(false);
    }
    if has("zenity") {
        return Command::new("zenity")
            .args([
                "--question",
                "--title",
                title.as_str(),
                "--text",
                text.as_str(),
                "--ok-label",
                ok_label.as_str(),
                "--cancel-label",
                cancel.as_str(),
            ])
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
    // A message made of one marked sentence is said in the person's language.
    let said = say(message, &[]);
    let message = said.as_str();
    eprintln!("{message}");
    if gui && !std::io::stderr().is_terminal() {
        // What went wrong, then, after a blank line, the details behind a button.
        let (text, details) = message.split_once("\n\n").unwrap_or((message, ""));
        if has("kdialog") {
            let mut cmd = Command::new("kdialog");
            cmd.args(["--title", "Monet"]);
            if details.trim().is_empty() {
                cmd.args(["--sorry", text]);
            } else {
                cmd.args(["--detailedsorry", text, details]);
            }
            let _ = cmd.status();
        } else if has("zenity") {
            let _ = Command::new("zenity").args(["--warning", "--title", "Monet", "--text", text]).status();
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn finds_downloads_where_the_account_keeps_them() {
        let home = Path::new("/home/claude");
        let swedish = "# written by xdg-user-dirs-update\nXDG_DESKTOP_DIR=\"$HOME/Skrivbord\"\nXDG_DOWNLOAD_DIR=\"$HOME/Hämtningar\"\n";
        assert_eq!(downloads_dir(home, swedish), PathBuf::from("/home/claude/Hämtningar"));
        assert_eq!(downloads_dir(home, ""), PathBuf::from("/home/claude/Downloads"));
        // Turned off (the folder is home itself) means none of its own.
        assert_eq!(downloads_dir(home, "XDG_DOWNLOAD_DIR=\"$HOME/\"\n"), PathBuf::from("/home/claude/Downloads"));
    }

    #[test]
    fn reads_bootc_update_checks() {
        let found = "Update available for: ostree-image-signed:docker://ghcr.io/happyhamster135/monet:latest\n  Version: 0.5.2\n  Digest: sha256:abc\n";
        assert_eq!(parse_bootc_check(found), Some((true, Some("0.5.2".to_string()))));
        assert_eq!(parse_bootc_check("Update available for: docker://x\n  Digest: sha256:abc\n"), Some((true, None)));
        assert_eq!(parse_bootc_check("No changes in: ostree-image-signed:docker://x\n"), Some((false, None)));
        assert_eq!(parse_bootc_check("error: something else\n"), None);
    }

    #[test]
    fn reads_why_windows_setup_stopped() {
        let stopped = "0\tthere isn't enough free space on the disk for Windows\n";
        assert_eq!(stop_reason(stopped).as_deref(), Some("there isn't enough free space on the disk for Windows"));
        assert_eq!(stop_reason("0\tGetting Windows ready\n"), None);
        assert_eq!(stop_reason("45\tDownloading Windows\n"), None);
        assert_eq!(stop_reason(""), None);
        assert_eq!(capitalized("there isn't room"), "There isn't room");
        assert_eq!(capitalized(""), "");
    }

    #[test]
    fn counts_app_updates() {
        assert_eq!(count_app_updates(""), 0);
        assert_eq!(count_app_updates("org.mozilla.firefox\ncom.valvesoftware.Steam\n\n"), 2);
        assert_eq!(count_app_updates("Application ID\norg.mozilla.firefox\n"), 1);
    }
}

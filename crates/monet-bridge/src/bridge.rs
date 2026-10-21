//! Monet Bridge: the Windows half of the switch.
//!
//! Runs as three scheduled tasks created by the installer:
//!
//! - `\Monet\Agent`  (at sign-in, as administrator): waits for a request
//!   from Monet, starts the game, and returns to Monet when it closes.
//! - `\Monet\Launch` (on demand, as the normal user): starts the game, so
//!   launchers never run as administrator.
//! - `\Monet\Back`   (on demand, as administrator): the "Back to Monet"
//!   shortcut, so it works without a UAC prompt.

use std::collections::HashSet;
use std::fs::{self, OpenOptions};
use std::io::Write;
use std::path::{Path, PathBuf};
use std::process::{Command, ExitCode};
use std::thread::sleep;
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

use serde::{Deserialize, Serialize};

use monet_core::boot::{self, BootEntry};
use monet_core::games::{self, Game, GameList, ESP_PATH};
use monet_core::request::{self, LaunchRequest};

use crate::parse;
use crate::win::{self, Answer, FirmwareVars};

type Res<T> = Result<T, String>;

const POLL: Duration = Duration::from_secs(3);
const START_TIMEOUT: Duration = Duration::from_secs(30 * 60);
const QUIT_GRACE: Duration = Duration::from_secs(20);
const RETURN_COUNTDOWN_SECS: u32 = 15;

pub fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let command = args.first().map(String::as_str).unwrap_or("back");
    if !matches!(command, "agent" | "launch-pending") {
        win::attach_console();
    }
    let result = match command {
        "agent" => agent(),
        "launch-pending" => launch_pending(),
        "back" => back(),
        "finish-setup" => finish_setup(),
        "scan" => {
            let list: Vec<_> = scan().iter().map(|g| g.summary()).collect();
            println!("{}", serde_json::to_string_pretty(&list).unwrap_or_default());
            Ok(())
        }
        "publish" => need_admin().and_then(|_| publish(&scan())),
        "status" => status(),
        "version" | "--version" => {
            println!("monet-bridge {}", monet_core::VERSION);
            Ok(())
        }
        _ => Err("Usage: monet-bridge [back | status | scan | publish | version]".into()),
    };
    match result {
        Ok(()) => ExitCode::SUCCESS,
        Err(e) => {
            log(&format!("error: {e}"));
            eprintln!("{e}");
            ExitCode::FAILURE
        }
    }
}

// ------------------------------------------------------------- files

fn data_dir() -> PathBuf {
    let base = std::env::var_os("ProgramData").map(PathBuf::from).unwrap_or_else(|| "C:\\ProgramData".into());
    base.join("Monet")
}

fn now() -> u64 {
    SystemTime::now().duration_since(UNIX_EPOCH).map(|d| d.as_secs()).unwrap_or(0)
}

fn log(message: &str) {
    let line = format!("{} {message}\n", now());
    let user_dir = std::env::var_os("LOCALAPPDATA").map(|d| PathBuf::from(d).join("Monet"));
    for dir in std::iter::once(data_dir()).chain(user_dir) {
        let path = dir.join("bridge.log");
        if fs::metadata(&path).map(|m| m.len() > 1_000_000).unwrap_or(false) {
            let _ = fs::rename(&path, dir.join("bridge.old.log"));
        }
        let _ = fs::create_dir_all(&dir);
        if let Ok(mut f) = OpenOptions::new().create(true).append(true).open(&path) {
            if f.write_all(line.as_bytes()).is_ok() {
                return;
            }
        }
    }
}

#[derive(Serialize, Deserialize)]
struct State {
    /// Boot entry of Monet, learned from the last request.
    monet_entry: Option<u16>,
    /// Put Monet back first in the boot order if Windows moved itself up.
    #[serde(default = "yes")]
    keep_monet_first: bool,
}

fn yes() -> bool {
    true
}

impl State {
    fn path() -> PathBuf {
        data_dir().join("state.json")
    }

    fn load() -> State {
        fs::read(Self::path())
            .ok()
            .and_then(|d| serde_json::from_slice(&d).ok())
            .unwrap_or(State { monet_entry: None, keep_monet_first: true })
    }

    fn save(&self) {
        let _ = fs::create_dir_all(data_dir());
        if let Ok(json) = serde_json::to_vec_pretty(self) {
            let _ = fs::write(Self::path(), json);
        }
    }
}

#[derive(Serialize, Deserialize)]
struct Pending {
    game: String,
    created: u64,
}

fn pending_path() -> PathBuf {
    data_dir().join("pending.json")
}

// ------------------------------------------------------------- games

enum Launch {
    Uri(String),
    Exe { path: PathBuf, args: Vec<String> },
}

struct WinGame {
    id: String,
    name: String,
    launch: Launch,
    /// Folder the game runs from, used to tell when it has closed.
    dir: Option<PathBuf>,
}

impl WinGame {
    fn summary(&self) -> serde_json::Value {
        let launch = match &self.launch {
            Launch::Uri(uri) => uri.clone(),
            Launch::Exe { path, args } => format!("{} {}", path.display(), args.join(" ")),
        };
        serde_json::json!({ "id": self.id, "name": self.name, "launch": launch, "dir": self.dir })
    }
}

fn scan() -> Vec<WinGame> {
    let mut found = Vec::new();
    found.extend(scan_steam());
    found.extend(scan_epic());
    found.extend(scan_riot());
    found.extend(scan_custom());
    found.retain(|g| games::is_valid_id(&g.id) && !games::clean_name(&g.name).is_empty());
    found
}

fn scan_steam() -> Vec<WinGame> {
    let root = win::reg_user("Software\\Valve\\Steam", "SteamPath")
        .or_else(|| win::reg_machine("SOFTWARE\\WOW6432Node\\Valve\\Steam", "InstallPath"))
        .map(|p| PathBuf::from(p.replace('/', "\\")))
        .unwrap_or_else(|| PathBuf::from("C:\\Program Files (x86)\\Steam"));

    let mut libraries = vec![root.clone()];
    if let Ok(text) = fs::read_to_string(root.join("steamapps\\libraryfolders.vdf")) {
        for lib in parse::steam_libraries(&text) {
            let lib = PathBuf::from(lib);
            if !libraries.iter().any(|l| l.as_os_str().eq_ignore_ascii_case(lib.as_os_str())) {
                libraries.push(lib);
            }
        }
    }

    let mut out = Vec::new();
    for lib in libraries {
        let apps = lib.join("steamapps");
        let Ok(entries) = fs::read_dir(&apps) else { continue };
        for entry in entries.flatten() {
            let name = entry.file_name().to_string_lossy().to_lowercase();
            if !(name.starts_with("appmanifest_") && name.ends_with(".acf")) {
                continue;
            }
            let Some(app) = fs::read_to_string(entry.path()).ok().and_then(|t| parse::steam_app(&t)) else {
                continue;
            };
            out.push(WinGame {
                id: format!("steam:{}", app.appid),
                name: app.name,
                launch: Launch::Uri(format!("steam://rungameid/{}", app.appid)),
                dir: Some(apps.join("common").join(app.installdir)),
            });
        }
    }
    out
}

fn scan_epic() -> Vec<WinGame> {
    let manifests = data_dir().parent().unwrap_or(Path::new("C:\\ProgramData")).join("Epic\\EpicGamesLauncher\\Data\\Manifests");
    let Ok(entries) = fs::read_dir(manifests) else { return Vec::new() };
    entries
        .flatten()
        .filter(|e| e.path().extension().is_some_and(|x| x.eq_ignore_ascii_case("item")))
        .filter_map(|e| parse::epic_app(&fs::read_to_string(e.path()).ok()?))
        .map(|app| WinGame {
            id: format!("epic:{}", app.app_name),
            name: app.display_name,
            launch: Launch::Uri(app.launch_uri),
            dir: (!app.install_location.is_empty()).then(|| PathBuf::from(app.install_location)),
        })
        .collect()
}

fn scan_riot() -> Vec<WinGame> {
    let riot = data_dir().parent().unwrap_or(Path::new("C:\\ProgramData")).join("Riot Games");
    let Some(client) = fs::read_to_string(riot.join("RiotClientInstalls.json"))
        .ok()
        .and_then(|j| parse::riot_client_path(&j))
        .map(PathBuf::from)
    else {
        return Vec::new();
    };
    let Ok(entries) = fs::read_dir(riot.join("Metadata")) else { return Vec::new() };

    let mut out = Vec::new();
    for entry in entries.flatten() {
        let folder = entry.file_name().to_string_lossy().into_owned();
        let Some((product, patchline)) = folder.split_once('.') else { continue };
        let settings = entry.path().join(format!("{folder}.product_settings.yaml"));
        let Some(dir) = fs::read_to_string(settings).ok().and_then(|y| parse::riot_install_path(&y)) else {
            continue;
        };
        if product == "riot_client" {
            continue;
        }
        let id = if patchline == "live" { format!("riot:{product}") } else { format!("riot:{folder}") };
        let mut name = parse::riot_name(product);
        if patchline != "live" {
            name = format!("{name} ({})", patchline.to_uppercase());
        }
        out.push(WinGame {
            id,
            name,
            launch: Launch::Exe {
                path: client.clone(),
                args: vec![format!("--launch-product={product}"), format!("--launch-patchline={patchline}")],
            },
            dir: Some(PathBuf::from(dir)),
        });
    }
    out
}

/// Games added by hand in `C:\ProgramData\Monet\custom-games.json`, for
/// launchers Monet doesn't know yet:
///
/// ```json
/// [{ "name": "Overwatch 2", "uri": "battlenet://Pro", "dir": "C:\\Program Files (x86)\\Overwatch" },
///  { "name": "Some Game", "exe": "D:\\Games\\Some Game\\game.exe", "args": ["-dx12"] }]
/// ```
fn scan_custom() -> Vec<WinGame> {
    #[derive(Deserialize)]
    struct Custom {
        name: String,
        exe: Option<PathBuf>,
        #[serde(default)]
        args: Vec<String>,
        uri: Option<String>,
        dir: Option<PathBuf>,
    }
    let Some(list) = fs::read(data_dir().join("custom-games.json"))
        .ok()
        .and_then(|d| serde_json::from_slice::<Vec<Custom>>(&d).ok())
    else {
        return Vec::new();
    };
    list.into_iter()
        .filter_map(|c| {
            let dir = c.dir.or_else(|| c.exe.as_ref().and_then(|e| e.parent().map(Path::to_path_buf)));
            let launch = match (c.uri, c.exe) {
                (Some(uri), _) => Launch::Uri(uri),
                (None, Some(path)) => Launch::Exe { path, args: c.args },
                (None, None) => return None,
            };
            Some(WinGame { id: format!("custom:{}", parse::slug(&c.name)), name: c.name, launch, dir })
        })
        .collect()
}

fn game_list(found: &[WinGame]) -> GameList {
    let games = found.iter().map(|g| Game { id: g.id.clone(), name: games::clean_name(&g.name) }).collect();
    GameList::new(games, now())
}

/// Shares the games list with Monet through the EFI system partition. The
/// partition is mounted only for the moment it takes to write the file, so a
/// hibernated Windows never holds it open.
fn publish(found: &[WinGame]) -> Res<()> {
    let letter = win::free_drive_letter().ok_or("no free drive letter")?;
    let drive = format!("{letter}:");
    if !win::run_hidden("mountvol", &[&drive, "/S"]) {
        return Err("couldn't mount the EFI system partition".into());
    }
    let target = PathBuf::from(format!("{drive}\\")).join(ESP_PATH.replace('/', "\\"));
    let result = (|| -> std::io::Result<()> {
        fs::create_dir_all(target.parent().expect("path has a parent"))?;
        let tmp = target.with_extension("tmp");
        fs::write(&tmp, game_list(found).to_json())?;
        fs::rename(&tmp, &target)
    })();
    win::run_hidden("mountvol", &[&drive, "/D"]);
    result.map_err(|e| format!("couldn't write the games list: {e}"))?;
    log(&format!("published {} games", found.len()));
    Ok(())
}

// ------------------------------------------------------------- the agent

fn need_admin() -> Res<()> {
    if win::enable_firmware_access() {
        Ok(())
    } else {
        Err("Monet Bridge needs to run as administrator for this.".into())
    }
}

fn agent() -> Res<()> {
    if !win::single_instance("Local\\MonetBridgeAgent") {
        return Ok(());
    }
    need_admin()?;
    log(&format!("agent {} started", monet_core::VERSION));
    let mut efi = FirmwareVars;
    let mut state = State::load();
    repair_boot_order(&mut efi, &state);
    if let Err(e) = publish(&scan()) {
        log(&e);
    }

    loop {
        match request::take(&mut efi) {
            Ok(Some(req)) => handle(&mut efi, &mut state, req),
            Ok(None) => {}
            Err(e) => log(&format!("unreadable request removed: {e}")),
        }
        sleep(POLL);
    }
}

/// Windows updates sometimes put Windows first in the boot order again.
fn repair_boot_order(efi: &mut FirmwareVars, state: &State) {
    let (true, Some(monet)) = (state.keep_monet_first, state.monet_entry) else { return };
    match boot::move_to_front(efi, monet) {
        Ok(true) => log(&format!("moved Monet (Boot{monet:04X}) back to the front of the boot order")),
        Ok(false) => {}
        Err(e) => log(&format!("couldn't check the boot order: {e}")),
    }
}

fn handle(efi: &mut FirmwareVars, state: &mut State, req: LaunchRequest) {
    if !req.is_fresh(now()) {
        log("ignored an old request");
        return;
    }
    let entries = boot::list_entries(efi).unwrap_or_default();
    if entries.iter().any(|e| e.number == req.return_to && !e.is_windows()) {
        state.monet_entry = Some(req.return_to);
        state.save();
        repair_boot_order(efi, state);
    }
    let Some(id) = req.game else {
        log("opened Windows from Monet");
        return;
    };

    let found = scan();
    let Some(game) = found.iter().find(|g| g.id == id) else {
        log(&format!("game {id} not found"));
        let answer = win::ask_with_timeout(
            "Monet couldn't find this game in Windows. It may have been uninstalled.\n\nClick OK to go back to Monet, or Cancel to stay in Windows.",
            60,
        );
        if !matches!(answer, Answer::No) {
            if let Err(e) = go_back(efi, state, &found) {
                log(&e);
            }
        }
        return;
    };
    log(&format!("starting {} ({id})", game.name));

    let pending = Pending { game: id.clone(), created: now() };
    let _ = fs::write(pending_path(), serde_json::to_vec(&pending).unwrap_or_default());
    if !win::run_hidden("schtasks", &["/run", "/tn", "\\Monet\\Launch"]) {
        log("launch task missing; starting the game directly");
        launch(game);
    }

    let Some(dir) = &game.dir else { return };
    if !wait_for_game(dir) {
        log("the game didn't start; staying in Windows");
        return;
    }
    let _ = fs::remove_file(pending_path());
    log(&format!("{} closed", game.name));

    let text = format!(
        "Going back to Monet in {RETURN_COUNTDOWN_SECS} seconds.\n\nClick Cancel to stay in Windows."
    );
    match win::ask_with_timeout(&text, RETURN_COUNTDOWN_SECS) {
        Answer::Yes | Answer::TimedOut => {
            if let Err(e) = go_back(efi, state, &found) {
                log(&e);
            }
        }
        Answer::No => log("staying in Windows"),
    }
}

// ------------------------------------------------------------- launching and waiting

fn launch(game: &WinGame) -> bool {
    match &game.launch {
        Launch::Uri(uri) => win::open_uri(uri),
        Launch::Exe { path, args } => {
            let mut cmd = Command::new(path);
            cmd.args(args);
            if let Some(parent) = path.parent() {
                cmd.current_dir(parent);
            }
            cmd.spawn().is_ok()
        }
    }
}

/// Runs as the normal user (the `\Monet\Launch` task).
fn launch_pending() -> Res<()> {
    let data = fs::read(pending_path()).map_err(|e| format!("no pending game: {e}"))?;
    let pending: Pending = serde_json::from_slice(&data).map_err(|e| e.to_string())?;
    if now().abs_diff(pending.created) > 120 {
        return Err("the pending game is too old".into());
    }
    let found = scan();
    let game = found.iter().find(|g| g.id == pending.game).ok_or("game not found")?;
    if launch(game) {
        Ok(())
    } else {
        Err(format!("couldn't start {}", game.name))
    }
}

/// Helper programs that live in game folders but don't mean the game runs.
const NOT_THE_GAME: &[&str] = &[
    "unitycrashhandler64.exe",
    "unitycrashhandler32.exe",
    "crashreportclient.exe",
    "easyanticheat_setup.exe",
    "easyanticheat_eos_setup.exe",
    "vc_redist.x64.exe",
    "vc_redist.x86.exe",
    "dxsetup.exe",
    "uninstall.exe",
    "unins000.exe",
];

/// Names of the programs in a game folder, used when Windows won't tell us a
/// process's full path (anti-cheat often protects the game process).
fn exe_names(dir: &Path) -> HashSet<String> {
    let mut names = HashSet::new();
    let mut stack = vec![(dir.to_path_buf(), 0)];
    let mut visited = 0;
    while let Some((path, depth)) = stack.pop() {
        let Ok(entries) = fs::read_dir(&path) else { continue };
        for entry in entries.flatten() {
            visited += 1;
            if visited > 20_000 {
                return names;
            }
            let p = entry.path();
            if p.is_dir() {
                if depth < 6 {
                    stack.push((p, depth + 1));
                }
            } else if let Some(name) = p.file_name().map(|n| n.to_string_lossy().to_lowercase()) {
                if name.ends_with(".exe") && !NOT_THE_GAME.contains(&name.as_str()) {
                    names.insert(name);
                }
            }
        }
    }
    names
}

fn game_running(dir: &str, names: &HashSet<String>) -> bool {
    win::processes().iter().any(|p| match &p.path {
        Some(path) => {
            let path = path.to_string_lossy().to_lowercase();
            path.starts_with(dir) && !NOT_THE_GAME.iter().any(|n| path.ends_with(n))
        }
        None => names.contains(&p.exe_name.to_lowercase()),
    })
}

/// Waits for the game to start, then for it to close. Returns false if it
/// never started.
fn wait_for_game(dir: &Path) -> bool {
    let names = exe_names(dir);
    let mut prefix = dir.to_string_lossy().to_lowercase();
    if !prefix.ends_with('\\') {
        prefix.push('\\');
    }

    let started = Instant::now();
    while !game_running(&prefix, &names) {
        if started.elapsed() > START_TIMEOUT {
            return false;
        }
        sleep(POLL);
    }

    let mut gone_since: Option<Instant> = None;
    loop {
        if game_running(&prefix, &names) {
            gone_since = None;
        } else if gone_since.get_or_insert_with(Instant::now).elapsed() >= QUIT_GRACE {
            return true;
        }
        sleep(POLL);
    }
}

// ------------------------------------------------------------- going back

fn return_target(entries: &[BootEntry], state: &State) -> Option<u16> {
    if let Some(n) = state.monet_entry {
        if entries.iter().any(|e| e.number == n && !e.is_windows()) {
            return Some(n);
        }
    }
    entries.iter().find(|e| e.is_other_os()).map(|e| e.number)
}

fn go_back(efi: &mut FirmwareVars, state: &State, found: &[WinGame]) -> Res<()> {
    if let Err(e) = publish(found) {
        log(&e);
    }
    let entries = boot::list_entries(efi).map_err(|e| e.to_string())?;
    let target = return_target(&entries, state).ok_or("Monet's boot entry wasn't found")?;
    if state.monet_entry != Some(target) {
        // First trip back (for example right after Monet installed Windows):
        // remember Monet, and make it the default again.
        let mut learned = State::load();
        learned.monet_entry = Some(target);
        learned.save();
        repair_boot_order(efi, &learned);
    }
    boot::set_boot_next(efi, target).map_err(|e| format!("couldn't set Monet to start next: {e}"))?;
    log(&format!("returning to Monet (Boot{target:04X})"));

    // Hibernate so Windows resumes in seconds next time. Restart if
    // hibernation is turned off.
    if !win::run_hidden("shutdown", &["/h"]) {
        win::run_hidden("shutdown", &["/r", "/t", "0"]);
    }
    Ok(())
}

fn back() -> Res<()> {
    if !win::enable_firmware_access() {
        // Not elevated: ask the administrator task to do it (no UAC prompt).
        return if win::run_hidden("schtasks", &["/run", "/tn", "\\Monet\\Back"]) {
            Ok(())
        } else {
            Err("Monet Bridge isn't installed correctly. Run the installer again.".into())
        };
    }
    let mut efi = FirmwareVars;
    let state = State::load();
    go_back(&mut efi, &state, &scan())
}

/// Shown once, right after Monet set up Windows by itself.
fn finish_setup() -> Res<()> {
    let text = format!(
        "Windows is ready for Monet.\n\nGoing back to Monet in {RETURN_COUNTDOWN_SECS} seconds. Click Cancel to stay in Windows."
    );
    match win::ask_with_timeout(&text, RETURN_COUNTDOWN_SECS) {
        Answer::No => Ok(()),
        Answer::Yes | Answer::TimedOut => back(),
    }
}

fn status() -> Res<()> {
    println!("Monet Bridge {}\n", monet_core::VERSION);
    if !win::enable_firmware_access() {
        println!("Run as administrator to see boot details.");
    } else {
        let efi = FirmwareVars;
        let entries = boot::list_entries(&efi).map_err(|e| e.to_string())?;
        let state = State::load();
        let target = return_target(&entries, &state);
        for e in &entries {
            let mark = if e.is_windows() {
                "  (Windows)"
            } else if Some(e.number) == target {
                "  (Monet)"
            } else {
                ""
            };
            println!("  Boot{:04X}  {}{mark}", e.number, e.option.description);
        }
        if let Ok(Some(next)) = boot::boot_next(&efi) {
            println!("\n  Next start: Boot{next:04X}");
        }
        println!();
    }
    let found = scan();
    println!("  {} games found", found.len());
    for g in &found {
        println!("    {}  ({})", g.name, g.id);
    }
    Ok(())
}

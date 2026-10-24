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
use std::os::windows::process::CommandExt;
use std::path::{Path, PathBuf};
use std::process::{Command, ExitCode};
use std::thread::sleep;
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

use serde::{Deserialize, Serialize};

use monet_core::boot::{self, BootEntry};
use monet_core::games::{self, Game, GameList, ESP_PATH};
use monet_core::request::{self, LaunchRequest};

use crate::cover::{self, Cover, Press, Scene};
use crate::launchers;
use crate::parse;
use crate::win::{self, Answer, FirmwareVars};
use crate::words::{tr, trf};

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
        "cover-preview" => cover_preview(&args[1..]),
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
    #[serde(default)]
    game: String,
    created: u64,
    /// Launchers to open instead of a game (their keys), quietly on the update trip.
    #[serde(default)]
    open: Vec<String>,
    #[serde(default)]
    quietly: bool,
}

fn pending_path() -> PathBuf {
    data_dir().join("pending.json")
}

/// When Monet last sent the PC here on purpose (a game, or just Windows).
fn asked_path() -> PathBuf {
    data_dir().join("asked")
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

/// Every Steam library's `steamapps` folder, and the `appmanifest_*.acf` files in it.
fn steam_manifests() -> Vec<(PathBuf, PathBuf)> {
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
            if name.starts_with("appmanifest_") && name.ends_with(".acf") {
                out.push((apps.clone(), entry.path()));
            }
        }
    }
    out
}

fn scan_steam() -> Vec<WinGame> {
    steam_manifests()
        .into_iter()
        .filter_map(|(apps, manifest)| {
            let app = parse::steam_app(&fs::read_to_string(manifest).ok()?)?;
            Some(WinGame {
                id: format!("steam:{}", app.appid),
                name: app.name,
                launch: Launch::Uri(format!("steam://rungameid/{}", app.appid)),
                dir: Some(apps.join("common").join(app.installdir)),
            })
        })
        .collect()
}

/// How many games Steam is updating right now.
fn steam_updating() -> usize {
    steam_manifests()
        .iter()
        .filter(|(_, manifest)| fs::read_to_string(manifest).is_ok_and(|t| parse::steam_updating(&t)))
        .count()
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
    let mut list = GameList::new(games, now());
    list.games_updated = fs::read_to_string(games_updated_path()).ok().and_then(|t| t.trim().parse().ok());
    list
}

/// When the last update trip finished, for Monet's Settings.
fn games_updated_path() -> PathBuf {
    data_dir().join("games-updated")
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
    // An update trip that restarted Windows to finish its updates carries on, then switches off.
    if let Some(trip) = fs::read(update_trip_path()).ok().and_then(|d| serde_json::from_slice::<UpdateTrip>(&d).ok()) {
        if trip.restarted && now().saturating_sub(trip.started) < 3 * 60 * 60 {
            update_trip(&mut efi, trip.started, true);
        }
        let _ = fs::remove_file(update_trip_path());
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
    let _ = fs::write(asked_path(), now().to_string());
    let entries = boot::list_entries(efi).unwrap_or_default();
    if entries.iter().any(|e| e.number == req.return_to && !e.is_windows()) {
        state.monet_entry = Some(req.return_to);
        state.save();
        repair_boot_order(efi, state);
    }
    match req.task.as_deref() {
        Some("launchers") => return sign_in_trip(efi, state),
        Some("update") => return update_trip(efi, now(), false),
        _ => {}
    }
    let Some(id) = req.game else {
        log("opened Windows from Monet");
        return;
    };

    let found = scan();
    let known = found.iter().find(|g| g.id == id);
    // A Steam game Windows doesn't have yet: Steam offers to install it,
    // and Monet waits for it to start.
    let steam_appid = id.strip_prefix("steam:").map(str::to_string);
    if known.is_none() && steam_appid.is_none() {
        log(&format!("game {id} not found"));
        let cover = Cover::open(Scene::Back { seconds: RETURN_COUNTDOWN_SECS, why: None });
        let why = tr("Monet couldn't find this game in Windows. It may have been uninstalled.");
        if count_down(cover.as_ref(), Some(why)) {
            if let Err(e) = go_back(efi, state, &found) {
                log(&e);
            }
        }
        return;
    }
    let name = known.map(|g| g.name.clone()).unwrap_or_else(|| id.clone());
    log(&format!("starting {name} ({id})"));
    // Monet's painting instead of Windows' desktop while the game gets going.
    let cover = Cover::open(Scene::Starting { game: games::clean_name(&name) });
    let back_now = std::cell::Cell::new(false);
    let asked_back = || {
        if cover.as_ref().is_some_and(|c| c.pressed() == Some(Press::BackNow)) {
            back_now.set(true);
        }
        back_now.get()
    };

    let pending = Pending { game: id.clone(), created: now(), open: Vec::new(), quietly: false };
    if !run_as_person(&pending) {
        log("launch task missing; starting the game directly");
        match (known, &steam_appid) {
            (Some(game), _) => {
                launch(game);
            }
            (None, Some(appid)) => {
                win::open_uri(&format!("steam://rungameid/{appid}"));
            }
            (None, None) => {}
        }
    }

    let dir = match (known.and_then(|g| g.dir.clone()), &steam_appid) {
        (Some(dir), _) => Some(dir),
        (None, Some(_)) => wait_for_steam_install(&id, &asked_back),
        (None, None) => None,
    };
    let played = dir.is_some_and(|dir| wait_for_game(&dir, &asked_back));
    let _ = fs::remove_file(pending_path());
    if back_now.get() {
        log(&format!("Back to Monet before {name} started"));
        if let Err(e) = go_back(efi, state, &found) {
            log(&e);
        }
        return;
    }
    if !played {
        // The cover goes: Windows as it is, to sort out what kept the game from starting.
        log(&format!("{name} didn't start; staying in Windows"));
        return;
    }
    log(&format!("{name} closed"));
    if count_down(cover.as_ref(), None) {
        if let Err(e) = go_back(efi, state, &found) {
            log(&e);
        }
    } else {
        log("staying in Windows");
    }
}

/// Starts what's pending as the person (the `\Monet\Launch` task), never as administrator.
fn run_as_person(pending: &Pending) -> bool {
    fs::write(pending_path(), serde_json::to_vec(pending).unwrap_or_default()).is_ok()
        && win::run_hidden("schtasks", &["/run", "/tn", "\\Monet\\Launch"])
}

/// Back to Monet after a countdown, on the cover (or a message box without it), unless the
/// person stays. True to go back.
fn count_down(cover: Option<&Cover>, why: Option<String>) -> bool {
    let Some(cover) = cover else {
        let text = format!(
            "{}\n\n{}",
            trf("Your PC restarts in Monet in %1 s.", &[&RETURN_COUNTDOWN_SECS.to_string()]),
            tr("Click Cancel to stay in Windows.")
        );
        return !matches!(win::ask_with_timeout(&text, RETURN_COUNTDOWN_SECS), Answer::No);
    };
    for left in (1..=RETURN_COUNTDOWN_SECS).rev() {
        cover.show(Scene::Back { seconds: left, why: why.clone() });
        let tick = Instant::now();
        while tick.elapsed() < Duration::from_secs(1) {
            match cover.pressed() {
                Some(Press::BackNow) => return true,
                Some(Press::Stay) => return false,
                _ => sleep(Duration::from_millis(100)),
            }
        }
    }
    true
}

// ------------------------------------------------------------- signing in once

/// A trip to sign in to the game launchers: the cover lists them, each with Open (as the
/// person; the launcher comes up over the cover) and whether it keeps you signed in, which
/// it looks at again every few seconds. Back to Monet ends it.
fn sign_in_trip(efi: &mut FirmwareVars, state: &mut State) {
    log("signing in to launchers");
    let rows = || -> Vec<(String, bool)> {
        launchers::installed().iter().map(|l| (l.name.to_string(), launchers::signed_in(l.key))).collect()
    };
    let Some(cover) = Cover::open(Scene::Launchers { rows: rows() }) else {
        log("no cover; staying in Windows");
        return;
    };
    let mut looked = Instant::now();
    loop {
        match cover.pressed() {
            Some(Press::Open(i)) => {
                if let Some(launcher) = launchers::installed().get(i) {
                    log(&format!("opening {}", launcher.name));
                    let pending = Pending { game: String::new(), created: now(), open: vec![launcher.key.into()], quietly: false };
                    run_as_person(&pending);
                }
            }
            Some(Press::BackNow) => {
                if let Err(e) = go_back(efi, state, &scan()) {
                    log(&e);
                }
                return;
            }
            _ => {}
        }
        if looked.elapsed() > Duration::from_secs(5) {
            cover.show(Scene::Launchers { rows: rows() });
            looked = Instant::now();
        }
        sleep(Duration::from_millis(200));
    }
}

// ------------------------------------------------------------- updating, then off

/// An update trip that's restarting Windows to finish its updates.
#[derive(Serialize, Deserialize)]
struct UpdateTrip {
    started: u64,
    restarted: bool,
}

fn update_trip_path() -> PathBuf {
    data_dir().join("update-trip.json")
}

/// What Update-Windows.ps1 says.
#[derive(Deserialize, Default)]
struct WindowsUpdate {
    #[serde(default)]
    state: String,
    #[serde(default)]
    reboot: bool,
}

fn windows_update_path() -> PathBuf {
    data_dir().join("windows-update.json")
}

fn updates_line_windows(state: &str) -> String {
    match state {
        "downloading" => tr("Windows Update: downloading"),
        "installing" => tr("Windows Update: installing"),
        "done" => tr("Windows Update: done"),
        "failed" => tr("Windows Update: couldn't finish, it tries again next time"),
        _ => tr("Windows Update: looking for updates"),
    }
}

fn updates_line_steam(updating: usize) -> String {
    if updating == 0 {
        tr("Steam: nothing updating right now")
    } else {
        trf("Steam: updating (%1)", &[&updating.to_string()])
    }
}

fn updates_line_downloads(rate: u64) -> String {
    if rate < parse::QUIET_RATE {
        tr("Downloads: quiet")
    } else {
        trf("Downloads: %1 MB/s", &[&format!("{:.1}", rate as f64 / 1e6)])
    }
}

/// A trip to bring Windows and its games up to date, then switch off: Windows Update
/// (Update-Windows.ps1) and every launcher, opened quietly as the person, until it's all
/// quiet (parse::updates_settled). If Windows wants a restart to finish its updates (and
/// signs in by itself), it comes back here once (`resumed`) before switching off.
fn update_trip(efi: &mut FirmwareVars, started_at: u64, resumed: bool) {
    log(if resumed { "update trip: back after Windows' restart" } else { "update trip" });
    let mut lines = vec![updates_line_windows("")];
    let cover = Cover::open(Scene::Updating { lines: lines.clone() });
    let _ = fs::remove_file(windows_update_path());
    let script = install_dir().join("Update-Windows.ps1");
    let mut windows = Command::new("powershell.exe")
        .args(["-NoProfile", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden", "-File"])
        .arg(&script)
        .creation_flags(win::CREATE_NO_WINDOW)
        .spawn()
        .map_err(|e| log(&format!("Windows Update didn't start: {e}")))
        .ok();
    let has_steam = launchers::installed().iter().any(|l| l.key == "steam");
    if !resumed {
        let keys = launchers::installed().iter().map(|l| l.key.to_string()).collect();
        run_as_person(&Pending { game: String::new(), created: now(), open: keys, quietly: true });
    }

    let started = Instant::now();
    let (mut bytes, mut measured, mut quiet_since) = (win::received_bytes(), Instant::now(), Instant::now());
    let mut early = false;
    loop {
        sleep(Duration::from_secs(1));
        if cover.as_ref().is_some_and(|c| c.pressed() == Some(Press::SwitchOff)) {
            log("update trip: switched off early");
            early = true;
            break;
        }
        if measured.elapsed() < Duration::from_secs(10) {
            continue;
        }
        let now_bytes = win::received_bytes();
        let rate = now_bytes.saturating_sub(bytes) / measured.elapsed().as_secs().max(1);
        (bytes, measured) = (now_bytes, Instant::now());
        if rate >= parse::QUIET_RATE {
            quiet_since = Instant::now();
        }
        let said: WindowsUpdate = fs::read(windows_update_path()).ok().and_then(|d| serde_json::from_slice(&d).ok()).unwrap_or_default();
        let windows_done = windows.as_mut().is_none_or(|c| c.try_wait().ok().flatten().is_some());
        let steam = if has_steam { steam_updating() } else { 0 };
        lines = vec![updates_line_windows(if windows_done && said.state.is_empty() { "failed" } else { &said.state })];
        if has_steam {
            lines.push(updates_line_steam(steam));
        }
        lines.push(updates_line_downloads(rate));
        if let Some(cover) = &cover {
            cover.show(Scene::Updating { lines: lines.clone() });
        }
        // Back after a restart, only Windows' own finishing is left: no launchers to wait for.
        let (elapsed, quiet) = (started.elapsed().as_secs(), quiet_since.elapsed().as_secs());
        let settled = if resumed {
            windows_done || elapsed >= parse::UPDATE_LIMIT / 3
        } else {
            parse::updates_settled(elapsed, quiet, windows_done, steam > 0)
        };
        if settled {
            break;
        }
    }

    let _ = fs::write(games_updated_path(), now().to_string());
    if let Err(e) = publish(&scan()) {
        log(&e);
    }
    let said: WindowsUpdate = fs::read(windows_update_path()).ok().and_then(|d| serde_json::from_slice(&d).ok()).unwrap_or_default();
    let signs_in_by_itself = win::reg_machine("SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\Winlogon", "AutoAdminLogon")
        .is_some_and(|v| v.trim() == "1");
    if said.reboot && !resumed && !early && signs_in_by_itself {
        // Windows finishes its updates while it restarts: here once more, then off.
        let trip = UpdateTrip { started: started_at, restarted: true };
        let _ = fs::write(update_trip_path(), serde_json::to_vec(&trip).unwrap_or_default());
        if let Ok(current) = boot::boot_current(efi) {
            let _ = boot::set_boot_next(efi, current);
        }
        log("update trip: restarting Windows to finish its updates");
        win::run_hidden("shutdown", &["/r", "/t", "0"]);
        return;
    }
    let _ = fs::remove_file(update_trip_path());
    log("update trip: done, switching off");
    win::run_hidden("shutdown", &["/s", "/t", "0"]);
}

/// Where monet-bridge.exe and its files are.
fn install_dir() -> PathBuf {
    std::env::current_exe().ok().and_then(|e| e.parent().map(Path::to_path_buf)).unwrap_or_default()
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
    if !pending.open.is_empty() {
        for key in &pending.open {
            if !launchers::open(key, pending.quietly) {
                log(&format!("couldn't open {key}"));
            }
        }
        return Ok(());
    }
    let found = scan();
    match found.iter().find(|g| g.id == pending.game) {
        Some(game) if launch(game) => Ok(()),
        Some(game) => Err(format!("couldn't start {}", game.name)),
        // Not installed yet: Steam asks to install it, then starts it.
        None => match pending.game.strip_prefix("steam:") {
            Some(appid) if win::open_uri(&format!("steam://rungameid/{appid}")) => Ok(()),
            _ => Err("game not found".into()),
        },
    }
}

/// How long to wait for Steam to download a game that wasn't installed.
const INSTALL_TIMEOUT: Duration = Duration::from_secs(3 * 60 * 60);

/// Waits until Steam has installed the game, then returns its folder; None when it took too
/// long or `stop` says so (Back to Monet on the cover).
fn wait_for_steam_install(id: &str, stop: &dyn Fn() -> bool) -> Option<PathBuf> {
    log(&format!("waiting for Steam to install {id}"));
    let started = Instant::now();
    let mut looked: Option<Instant> = None;
    while started.elapsed() < INSTALL_TIMEOUT {
        if stop() {
            return None;
        }
        if looked.is_none_or(|t| t.elapsed() >= Duration::from_secs(10)) {
            if let Some(dir) = scan_steam().into_iter().find(|g| g.id == id).and_then(|g| g.dir) {
                return Some(dir);
            }
            looked = Some(Instant::now());
        }
        sleep(Duration::from_millis(500));
    }
    None
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
/// never started, or `stop` said so before it did (Back to Monet on the cover).
fn wait_for_game(dir: &Path, stop: &dyn Fn() -> bool) -> bool {
    let names = exe_names(dir);
    let mut prefix = dir.to_string_lossy().to_lowercase();
    if !prefix.ends_with('\\') {
        prefix.push('\\');
    }

    let started = Instant::now();
    while !game_running(&prefix, &names) {
        // A few seconds between looks at the process list, answering Back to Monet meanwhile.
        let look = Instant::now();
        while look.elapsed() < POLL {
            if started.elapsed() > START_TIMEOUT || stop() {
                return false;
            }
            sleep(Duration::from_millis(250));
        }
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

    // On the way out, Bridge brings itself up to date (once a day at most) and the update
    // task restarts the PC; a Bridge without that task restarts straight away.
    if update_then_restart() {
        return Ok(());
    }
    // Restart, not hibernate: a hibernated PC stays off until someone presses
    // the power button, and a hibernated Windows drive can't be written from Monet.
    if !win::run_hidden("shutdown", &["/r", "/t", "0"]) {
        return Err("couldn't restart into Monet".into());
    }
    Ok(())
}

/// Hands the restart to `\Monet\Update` (Update-Monet.ps1), which updates Bridge when a
/// newer Monet is out and then restarts whatever happened. True once it has taken over
/// (renamed the marker); false when it didn't start in time, and the caller restarts.
fn update_then_restart() -> bool {
    let marker = data_dir().join("update-then-restart");
    let claimed = data_dir().join("update-claimed");
    let _ = fs::remove_file(&claimed);
    if fs::write(&marker, now().to_string()).is_err() {
        return false;
    }
    if win::run_hidden("schtasks", &["/run", "/tn", "\\Monet\\Update"]) {
        let started = Instant::now();
        while started.elapsed() < Duration::from_secs(30) {
            if claimed.exists() {
                return true;
            }
            sleep(Duration::from_millis(500));
        }
        log("the update task didn't start; restarting");
    }
    // Taken over between the last look and now: the task restarts the PC.
    fs::remove_file(&marker).is_err() && claimed.exists()
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

/// True when Monet sent the PC to Windows on purpose in the last few minutes:
/// a request still waiting in the firmware, or one the agent just took.
fn sent_on_purpose() -> bool {
    let waiting = win::enable_firmware_access() && request::peek(&FirmwareVars).is_some();
    let recent = fs::read_to_string(asked_path())
        .ok()
        .and_then(|t| t.trim().parse::<u64>().ok())
        .is_some_and(|t| now().saturating_sub(t) < 15 * 60);
    waiting || recent
}

/// Shown once, right after Monet set up Windows by itself.
fn finish_setup() -> Res<()> {
    // Someone pressed Play (or Restart in Windows) while Windows was still
    // setting up: stay for the game instead of going straight back.
    if sent_on_purpose() {
        log("setup finished during a trip from Monet; staying in Windows");
        return Ok(());
    }
    let cover = Cover::open(Scene::Back { seconds: RETURN_COUNTDOWN_SECS, why: None });
    if count_down(cover.as_ref(), Some(tr("Windows is ready for Monet."))) {
        back()
    } else {
        Ok(())
    }
}

/// `monet-bridge cover-preview SCENE OUT.png [PICTURES]`: a scene of the cover in a PNG, with
/// made-up games and launchers (MONET_LANGID=0x407 for German, say).
fn cover_preview(args: &[String]) -> Res<()> {
    let [which, out, rest @ ..] = args else {
        return Err("Usage: monet-bridge cover-preview starting|back|launchers|updating OUT.png [PICTURES]".into());
    };
    let scene = match which.as_str() {
        "starting" => Scene::Starting { game: "VALORANT".into() },
        "back" => Scene::Back { seconds: 12, why: None },
        "launchers" => Scene::Launchers {
            rows: vec![("Steam".into(), true), ("Riot Client".into(), false), ("Battle.net".into(), false), ("EA app".into(), false)],
        },
        "updating" => Scene::Updating {
            lines: vec![updates_line_windows("installing"), updates_line_steam(2), updates_line_downloads(24_000_000)],
        },
        _ => return Err(format!("no scene called {which}")),
    };
    let dir = rest.first().map(PathBuf::from).unwrap_or_else(|| {
        std::env::current_exe().ok().and_then(|e| e.parent().map(Path::to_path_buf)).unwrap_or_default()
    });
    cover::preview(&scene, &dir, Path::new(out), 1920, 1080)
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

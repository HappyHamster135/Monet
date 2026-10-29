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
/// How long Monet's painting stays in front of a launcher whose game hasn't started: after
/// that the launcher must want something (signing in, an update) and comes into view.
const LAUNCHER_PATIENCE: Duration = Duration::from_secs(60);

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
    /// A program, started in `cwd` (its own folder when None).
    Exe { path: PathBuf, args: Vec<String>, cwd: Option<PathBuf> },
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
            Launch::Exe { path, args, .. } => format!("{} {}", path.display(), args.join(" ")),
        };
        serde_json::json!({ "id": self.id, "name": self.name, "launch": launch, "dir": self.dir })
    }
}

fn scan() -> Vec<WinGame> {
    let mut found = Vec::new();
    found.extend(scan_steam());
    found.extend(scan_epic());
    found.extend(scan_riot());
    found.extend(scan_gog());
    found.extend(scan_listed());
    found.extend(scan_shared_battlenet());
    found.extend(scan_ubisoft());
    found.extend(scan_ea());
    found.extend(scan_custom());
    // One of each: a launcher's own entry first (a Battle.net game it found in the shared
    // folder once it was told where).
    let mut seen = std::collections::HashSet::new();
    found.retain(|g| games::is_valid_id(&g.id) && !games::clean_name(&g.name).is_empty() && seen.insert(g.id.clone()));
    found
}

fn steam_root() -> PathBuf {
    win::reg_user("Software\\Valve\\Steam", "SteamPath")
        .or_else(|| win::reg_machine("SOFTWARE\\WOW6432Node\\Valve\\Steam", "InstallPath"))
        .map(|p| PathBuf::from(p.replace('/', "\\")))
        .unwrap_or_else(|| PathBuf::from("C:\\Program Files (x86)\\Steam"))
}

/// Every Steam library's `steamapps` folder, and the `appmanifest_*.acf` files in it. The
/// Games folder Monet shares counts even before Steam lists it.
fn steam_manifests() -> Vec<(PathBuf, PathBuf)> {
    let root = steam_root();
    let mut libraries = vec![root.clone()];
    let listed = fs::read_to_string(root.join("steamapps\\libraryfolders.vdf")).map(|t| parse::steam_libraries(&t)).unwrap_or_default();
    for lib in listed.into_iter().map(PathBuf::from).chain(shared_games()) {
        if !libraries.iter().any(|l| l.as_os_str().eq_ignore_ascii_case(lib.as_os_str())) {
            libraries.push(lib);
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

/// `C:\Games`, the Steam library Monet shares with Windows (Monet makes it, and its
/// `libraryfolder.vdf`, when Windows' drive is safe to write): a game installed there on
/// either side plays on both.
fn shared_games() -> Option<PathBuf> {
    let drive = std::env::var("SystemDrive").unwrap_or_else(|_| "C:".into());
    let folder = PathBuf::from(format!("{drive}\\Games"));
    folder.join("libraryfolder.vdf").is_file().then_some(folder)
}

fn steam_running() -> bool {
    win::processes().iter().any(|p| p.exe_name.eq_ignore_ascii_case("steam.exe"))
}

/// Adds the shared Games folder to Windows' Steam's libraries, when it isn't there yet. As
/// the person (Steam is theirs): a running Steam is asked to quit first, as it writes its
/// own list back when it does. Files Monet made there already let everyone write (Linux's
/// NTFS drivers give new files Everyone: full control), so Steam can update them.
fn share_with_steam() {
    let Some(folder) = shared_games() else { return };
    let root = steam_root();
    let lists = [root.join("steamapps\\libraryfolders.vdf"), root.join("config\\libraryfolders.vdf")];
    let folder_text = folder.to_string_lossy().into_owned();
    let missing = |list: &Path| fs::read_to_string(list).is_ok_and(|t| !parse::library_listed(&t, &folder_text));
    if !lists.iter().any(|l| missing(l)) {
        return;
    }
    if steam_running() {
        log("asking Steam to quit, to add the Games folder Monet shares");
        let _ = Command::new(root.join("steam.exe")).arg("-shutdown").creation_flags(win::CREATE_NO_WINDOW).spawn();
        let asked = Instant::now();
        while steam_running() {
            if asked.elapsed() > Duration::from_secs(30) {
                log("Steam didn't quit; the Games folder waits for next time");
                return;
            }
            sleep(Duration::from_millis(500));
        }
    }
    let contentid = fs::read_to_string(folder.join("libraryfolder.vdf"))
        .ok()
        .and_then(|t| parse::vdf_get(&parse::vdf_pairs(&t), "contentid").map(str::to_string))
        .unwrap_or_else(|| "0".into());
    for list in lists.iter().filter(|l| missing(l)) {
        let Some(text) = fs::read_to_string(list).ok().and_then(|t| parse::with_library(&t, &folder_text, &contentid)) else {
            continue;
        };
        // Steam's own list as it was, once; then the new one in one step.
        let before = list.with_extension("vdf.before-monet");
        if !before.exists() {
            let _ = fs::copy(list, &before);
        }
        let temp = list.with_extension("vdf.monet");
        match fs::write(&temp, text).and_then(|_| fs::rename(&temp, list)) {
            Ok(()) => log(&format!("added {} to Steam's libraries ({})", folder.display(), list.display())),
            Err(e) => log(&format!("couldn't add the Games folder to {}: {e}", list.display())),
        }
    }
}

/// Epic's games that Heroic installed in the shared Games folder in Monet, made known to Epic's
/// own launcher the way legendary's EGL sync does: Monet leaves the game's manifest in its
/// `.egstore` and a note in `Games\.monet\epic`, and this writes the launcher's `.item` for each
/// it hasn't got, checked once by the launcher before it plays, and again when Heroic updated
/// the game (the launcher's entry still the one Bridge wrote). One the launcher updated itself,
/// or has elsewhere, is left alone. The launcher reads them as it starts, so a running one is
/// closed. As administrator, at the agent's start, before any trip's game.
fn share_with_epic() {
    let Some(shared) = shared_games() else { return };
    let Ok(notes) = fs::read_dir(shared.join(".monet\\epic")) else { return };
    let data = data_dir().parent().unwrap_or(Path::new("C:\\ProgramData")).join("Epic\\EpicGamesLauncher\\Data");
    if !data.is_dir() {
        return; // no Epic Games Launcher in this Windows
    }
    let manifests = data.join("Manifests");
    let field = |v: &serde_json::Value, key: &str| v.get(key).and_then(|x| x.as_str()).unwrap_or("").to_string();
    // What the launcher has now: app name -> (install location, version). One in the shared
    // folder whose game is gone (Heroic removed it in Monet) goes too.
    let mut have = std::collections::HashMap::new();
    let shared_text = shared.to_string_lossy().into_owned();
    for entry in fs::read_dir(&manifests).into_iter().flatten().flatten() {
        if let Some(item) = fs::read(entry.path()).ok().and_then(|d| serde_json::from_slice::<serde_json::Value>(&d).ok()) {
            let location = field(&item, "InstallLocation");
            let inside = location.to_lowercase().starts_with(&format!("{}\\", shared_text.to_lowercase()));
            if inside && !Path::new(&location).is_dir() {
                log(&format!("{} is gone from {shared_text}: Epic's launcher forgets it", field(&item, "AppName")));
                let _ = fs::remove_file(entry.path());
                continue;
            }
            have.insert(field(&item, "AppName"), (location, field(&item, "AppVersionString")));
        }
    }
    // The version Bridge last handed over, per game: an entry still at it is Bridge's to update.
    let written_path = data_dir().join("epic-written.json");
    let mut written: std::collections::HashMap<String, String> =
        fs::read(&written_path).ok().and_then(|d| serde_json::from_slice(&d).ok()).unwrap_or_default();
    let mut added = 0;
    for note in notes.flatten().filter(|e| e.path().extension().is_some_and(|x| x == "json")) {
        let Some(value) = fs::read(note.path()).ok().and_then(|d| serde_json::from_slice::<serde_json::Value>(&d).ok()) else {
            continue;
        };
        let folder = field(&value, "folder").replace('/', "\\");
        if folder.is_empty() || folder.contains(':') || folder.starts_with('\\') || folder.split('\\').any(|p| p == "..") {
            continue;
        }
        let location = shared.join(&folder);
        if !location.join(".egstore").is_dir() {
            continue;
        }
        let location = location.to_string_lossy().into_owned();
        let (app, version) = (field(&value, "AppName"), field(&value, "AppVersionString"));
        match have.get(&app) {
            Some((there, _)) if !parse::same_folder(there, &location) => continue,
            Some((_, now)) if *now == version || written.get(&app) != Some(now) => continue,
            _ => {}
        }
        let Some(item) = parse::egl_item(&value, &location, true) else { continue };
        let _ = fs::create_dir_all(&manifests);
        let path = manifests.join(format!("{}.item", field(&value, "guid")));
        match fs::write(&path, serde_json::to_vec_pretty(&item).unwrap_or_default()) {
            Ok(()) => {
                log(&format!("Epic's launcher has {app} {version} now ({location})"));
                written.insert(app, version);
                added += 1;
            }
            Err(e) => log(&format!("couldn't hand {app} to Epic's launcher: {e}")),
        }
    }
    if added > 0 {
        let _ = fs::write(&written_path, serde_json::to_vec(&written).unwrap_or_default());
    }
    if added > 0 && win::processes().iter().any(|p| p.exe_name.eq_ignore_ascii_case("EpicGamesLauncher.exe")) {
        win::run_hidden("taskkill", &["/IM", "EpicGamesLauncher.exe", "/F"]);
    }
}

/// Windows' clock in Monet's time zone, from the trip's request (already checked to be a
/// name Windows could have): the same time on both sides, after a journey too.
fn set_time_zone(zone: &str) {
    let now = Command::new("tzutil")
        .arg("/g")
        .creation_flags(win::CREATE_NO_WINDOW)
        .output()
        .map(|o| String::from_utf8_lossy(&o.stdout).trim().to_string())
        .unwrap_or_default();
    if !now.eq_ignore_ascii_case(zone) && win::run_hidden("tzutil", &["/s", zone]) {
        log(&format!("time zone: {zone} (was {now}), as in Monet"));
    }
}

// ------------------------------------------------------------- Wi-Fi in both

/// The Wi-Fi networks Monet joined that Windows didn't know: Monet leaves each as a WLAN profile
/// in `C:\ProgramData\Monet\wifi` while Windows is off, and they're added here for everyone,
/// then removed (they hold the password). At the agent's start, as administrator.
fn add_wifi() {
    let dir = data_dir().join("wifi");
    // Only administrators read it: Monet writes there only when it's there, and Linux's NTFS
    // driver gives each file it makes its folder's permissions.
    if fs::create_dir_all(&dir).is_ok() {
        let folder = dir.to_string_lossy().into_owned();
        win::run_hidden("icacls", &[&folder, "/inheritance:r", "/grant:r", "*S-1-5-32-544:(OI)(CI)F", "*S-1-5-18:(OI)(CI)F"]);
    }
    let Ok(entries) = fs::read_dir(&dir) else { return };
    let mut added = 0;
    for path in entries.flatten().map(|e| e.path()).filter(|p| p.extension().is_some_and(|x| x.eq_ignore_ascii_case("xml"))) {
        let file = format!("filename={}", path.display());
        if win::run_hidden("netsh", &["wlan", "add", "profile", &file, "user=all"]) {
            added += 1;
        }
        let _ = fs::remove_file(&path);
    }
    if added > 0 {
        log(&format!("added {added} Wi-Fi network(s) from Monet"));
    }
}

/// On the way back: Windows' Wi-Fi networks, keys and all, for Monet to take the ones it doesn't
/// know at its next start (and remove), in a folder only administrators can read.
fn export_wifi() {
    let out = data_dir().join("wifi-out");
    let _ = fs::remove_dir_all(&out);
    if fs::create_dir_all(&out).is_err() {
        return;
    }
    let folder = out.to_string_lossy().into_owned();
    win::run_hidden("icacls", &[&folder, "/inheritance:r", "/grant:r", "*S-1-5-32-544:(OI)(CI)F", "*S-1-5-18:(OI)(CI)F"]);
    win::run_hidden("netsh", &["wlan", "export", "profile", "key=clear", &format!("folder={folder}")]);
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
                cwd: None,
            },
            dir: Some(PathBuf::from(dir)),
        });
    }
    out
}

/// GOG's games in the shared Games folder (Heroic put them there in Monet). They're DRM-free,
/// so each starts with no launcher, as its own `goggame-<id>.info` says, a folder or two in.
fn scan_gog() -> Vec<WinGame> {
    let Some(shared) = shared_games() else { return Vec::new() };
    let mut out: Vec<WinGame> = Vec::new();
    let mut folders = vec![(shared, 0)];
    while let Some((folder, depth)) = folders.pop() {
        let Ok(entries) = fs::read_dir(&folder) else { continue };
        for entry in entries.flatten() {
            let path = entry.path();
            let name = entry.file_name().to_string_lossy().to_lowercase();
            if path.is_dir() {
                if depth < 2 && name != "steamapps" && !name.starts_with('.') {
                    folders.push((path, depth + 1));
                }
            } else if name.starts_with("goggame-") && name.ends_with(".info") {
                let Some(game) = fs::read_to_string(&path).ok().and_then(|t| parse::gog_game(&t)) else { continue };
                let id = format!("gog:{}", game.id);
                if out.iter().any(|g| g.id == id) {
                    continue;
                }
                let cwd = (!game.working_dir.is_empty()).then(|| folder.join(&game.working_dir));
                out.push(WinGame {
                    id,
                    name: game.name,
                    launch: Launch::Exe { path: folder.join(&game.exe), args: game.args, cwd },
                    dir: Some(folder.clone()),
                });
            }
        }
    }
    out
}

const UNINSTALL: [&str; 2] =
    ["SOFTWARE\\WOW6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall", "SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall"];

/// Battle.net's and Rockstar's games, from Windows' list of programs (as Playnite finds them),
/// each started through its own launcher.
fn scan_listed() -> Vec<WinGame> {
    let launcher = |key: &str| launchers::installed().into_iter().find(|l| l.key == key).map(|l| l.exe);
    // Battle.net.exe takes --exec; its launcher, where that's all there is, hands it on.
    let battlenet = launcher("battlenet").map(|exe| {
        let client = exe.with_file_name("Battle.net.exe");
        if client.is_file() { client } else { exe }
    });
    let rockstar = launcher("rockstar");
    let mut out: Vec<WinGame> = Vec::new();
    for root in UNINSTALL {
        for key in win::reg_machine_subkeys(root) {
            let path = format!("{root}\\{key}");
            let value = |name: &str| win::reg_machine(&path, name).unwrap_or_default();
            let name = value("DisplayName");
            let Some(id) = parse::listed_game(&name, &value("UninstallString")) else { continue };
            let dir = PathBuf::from(value("InstallLocation").trim_matches('"'));
            if out.iter().any(|g| g.id == id) || !dir.is_dir() {
                continue;
            }
            let (client, args) = match id.split_once(':') {
                Some(("battlenet", code)) => (&battlenet, vec![format!("--exec=launch {code}")]),
                Some(("rockstar", _)) => (&rockstar, vec!["-launchTitleInFolder".into(), dir.display().to_string()]),
                _ => continue,
            };
            let Some(client) = client else { continue };
            out.push(WinGame { id, name, launch: Launch::Exe { path: client.clone(), args, cwd: None }, dir: Some(dir) });
        }
    }
    out
}

/// Battle.net's games Battle.net in Monet installed in the shared Games folder (each has the
/// `.build.info` Battle.net's agent writes, which names the game), a folder or two in. Windows'
/// Battle.net may not know one yet: asked to play it, it offers Locate the game, once.
fn scan_shared_battlenet() -> Vec<WinGame> {
    let Some(shared) = shared_games() else { return Vec::new() };
    let client = launchers::installed().into_iter().find(|l| l.key == "battlenet").map(|l| l.exe.with_file_name("Battle.net.exe"));
    let client = client.unwrap_or_else(|| {
        let x86 = std::env::var_os("ProgramFiles(x86)").map(PathBuf::from).unwrap_or_else(|| PathBuf::from("C:\\Program Files (x86)"));
        x86.join("Battle.net\\Battle.net.exe")
    });
    let mut out = Vec::new();
    let mut folders = vec![(shared, 0)];
    while let Some((folder, depth)) = folders.pop() {
        let Ok(entries) = fs::read_dir(&folder) else { continue };
        for entry in entries.flatten() {
            let path = entry.path();
            let name = entry.file_name().to_string_lossy().into_owned();
            if !entry.file_type().is_ok_and(|t| t.is_dir()) || name.starts_with('.') || name.eq_ignore_ascii_case("steamapps") {
                continue;
            }
            let code = fs::read_to_string(path.join(".build.info"))
                .ok()
                .and_then(|text| parse::build_info_product(&text))
                .and_then(|uid| parse::battlenet_code(&uid));
            match code {
                Some(code) => out.push(WinGame {
                    id: format!("battlenet:{code}"),
                    name: name.clone(),
                    launch: Launch::Exe { path: client.clone(), args: vec![format!("--exec=launch {code}")], cwd: None },
                    dir: Some(path),
                }),
                None if depth < 1 => folders.push((path, depth + 1)),
                None => {}
            }
        }
    }
    out
}

/// An EA game's id and what its `__Installer\installerdata.xml` says, when the folder has one.
fn ea_game_in(dir: &Path) -> Option<(String, parse::EaGame)> {
    let xml = fs::read(dir.join("__Installer\\installerdata.xml")).ok()?;
    let game = parse::ea_game(&parse::text_of(&xml))?;
    Some((format!("ea:{}", game.offers[0]), game))
}

/// The folders of EA's games in Windows' list of programs: the ones the EA app here installed,
/// and so knows.
fn ea_listed() -> Vec<PathBuf> {
    let mut out: Vec<PathBuf> = Vec::new();
    for root in UNINSTALL {
        for key in win::reg_machine_subkeys(root) {
            let dir = PathBuf::from(win::reg_machine(&format!("{root}\\{key}"), "InstallLocation").unwrap_or_default().trim_matches('"'));
            if dir.join("__Installer\\installerdata.xml").is_file() && !out.contains(&dir) {
                out.push(dir);
            }
        }
    }
    out
}

/// EA's games, each started by the EA app from the offer ids in its folder (as Lutris does):
/// the ones Windows lists, the rest of EA Games, and the shared Games folder's, which the EA
/// app in Monet put there. One of those the EA app here doesn't know yet opens its page
/// instead (no download: it's asked to install it where it is, and finds it there).
fn scan_ea() -> Vec<WinGame> {
    let listed = ea_listed();
    let x64 = std::env::var_os("ProgramFiles").map(PathBuf::from).unwrap_or_else(|| PathBuf::from("C:\\Program Files"));
    let mut folders = listed.clone();
    for parent in std::iter::once(x64.join("EA Games")).chain(shared_games()) {
        let Ok(entries) = fs::read_dir(&parent) else { continue };
        folders.extend(entries.flatten().map(|e| e.path()).filter(|d| !folders.contains(d)).collect::<Vec<_>>());
    }
    let shared = shared_games();
    let mut out: Vec<WinGame> = Vec::new();
    for dir in folders {
        let Some((id, game)) = ea_game_in(&dir) else { continue };
        if out.iter().any(|g| g.id == id) {
            continue;
        }
        let known = listed.contains(&dir) || !shared.as_ref().is_some_and(|s| dir.starts_with(s));
        let uri = format!("origin2://game/launch?offerIds={}{}", game.offers.join(","), if known { "&autoDownload=1" } else { "" });
        let name = game.title.unwrap_or_else(|| dir.file_name().map(|n| n.to_string_lossy().into_owned()).unwrap_or_default());
        out.push(WinGame { id, name, launch: Launch::Uri(uri), dir: Some(dir) });
    }
    out
}

/// Ubisoft's games Ubisoft Connect in Monet installed in the shared Games folder, handed to
/// Ubisoft Connect here as it notes its own installs (its `Installs` key, the folder in it),
/// from what Monet noted (`Games\.monet\ubisoft`). One it has already, here or
/// elsewhere, is left alone. At the agent's start, as administrator.
fn share_with_ubisoft() {
    let Some(shared) = shared_games() else { return };
    let Ok(entries) = fs::read_dir(shared.join(".monet\\ubisoft")) else { return };
    for entry in entries.flatten() {
        let Some((id, folder)) = fs::read_to_string(entry.path()).ok().and_then(|t| parse::ubisoft_note(&t)) else { continue };
        let dir = shared.join(&folder);
        let key = format!("SOFTWARE\\WOW6432Node\\Ubisoft\\Launcher\\Installs\\{id}");
        if !dir.is_dir() || win::reg_machine(&key, "InstallDir").is_some_and(|d| Path::new(&d).is_dir()) {
            continue;
        }
        // As Ubisoft Connect writes it: forward slashes, and one at the end.
        let value = format!("{}/", dir.display().to_string().replace('\\', "/").trim_end_matches('/'));
        if win::run_hidden("reg", &["add", &format!("HKLM\\{key}"), "/v", "InstallDir", "/t", "REG_SZ", "/d", &value, "/f"]) {
            log(&format!("Ubisoft Connect has {folder} from the shared Games folder"));
        }
    }
}

/// Ubisoft Connect's games: its own list in the registry (as Playnite reads it), named as
/// Windows' list of programs names them, started through its `uplay://` link.
fn scan_ubisoft() -> Vec<WinGame> {
    let mut out: Vec<WinGame> = Vec::new();
    for root in ["SOFTWARE\\WOW6432Node\\Ubisoft\\Launcher\\Installs", "SOFTWARE\\Ubisoft\\Launcher\\Installs"] {
        for id in win::reg_machine_subkeys(root) {
            let Some(dir) = win::reg_machine(&format!("{root}\\{id}"), "InstallDir").map(|d| PathBuf::from(d.replace('/', "\\")))
            else {
                continue;
            };
            if id.is_empty() || !id.chars().all(|c| c.is_ascii_digit()) || !dir.is_dir() || out.iter().any(|g| g.id.ends_with(&format!(":{id}"))) {
                continue;
            }
            let name = UNINSTALL
                .iter()
                .find_map(|u| win::reg_machine(&format!("{u}\\Uplay Install {id}"), "DisplayName"))
                .or_else(|| dir.file_name().map(|n| n.to_string_lossy().into_owned()))
                .unwrap_or_default();
            out.push(WinGame { id: format!("ubisoft:{id}"), name, launch: Launch::Uri(format!("uplay://launch/{id}")), dir: Some(dir) });
        }
    }
    out
}

/// `C:\Shared with Monet`, the folder for files on both sides (Monet makes it, beside the Games
/// folder, when Windows' drive is safe to write): a download saved there once is in both.
fn shared_files() -> Option<PathBuf> {
    let drive = std::env::var("SystemDrive").unwrap_or_else(|_| "C:".into());
    let folder = PathBuf::from(format!("{drive}\\Shared with Monet"));
    folder.is_dir().then_some(folder)
}

/// What Monet sent Windows to open (Files' Open in Windows on a Windows program): each program
/// and installer in the folder for files on both sides, a few folders in at most, as
/// `program:<slug of its path there>` (as Monet names it). Not games: they're never published.
fn scan_programs() -> Vec<WinGame> {
    let Some(root) = shared_files() else { return Vec::new() };
    let mut out = Vec::new();
    let mut folders = vec![(root.clone(), 0)];
    while let Some((folder, depth)) = folders.pop() {
        let Ok(entries) = fs::read_dir(&folder) else { continue };
        for entry in entries.flatten() {
            let path = entry.path();
            let Ok(kind) = entry.file_type() else { continue };
            if kind.is_dir() && !kind.is_symlink() && depth < 3 {
                folders.push((path, depth + 1));
                continue;
            }
            let Some(extension) = path.extension().map(|x| x.to_string_lossy().to_lowercase()) else { continue };
            let cwd = Some(folder.clone());
            let launch = match extension.as_str() {
                "exe" if kind.is_file() => Launch::Exe { path: path.clone(), args: Vec::new(), cwd },
                "msi" if kind.is_file() => {
                    Launch::Exe { path: PathBuf::from("msiexec.exe"), args: vec!["/i".into(), path.display().to_string()], cwd }
                }
                _ => continue,
            };
            let Ok(place) = path.strip_prefix(&root) else { continue };
            let name = path.file_stem().map(|s| s.to_string_lossy().into_owned()).unwrap_or_default();
            out.push(WinGame { id: format!("program:{}", parse::slug(&place.to_string_lossy())), name, launch, dir: Some(folder.clone()) });
        }
    }
    out
}

/// The apps in the Start menu (the person's own, then everyone's), as Monet's app menu lists
/// them: `app:<slug of the shortcut's place under Programs>`, opened through the shortcut
/// itself. Run as the person (`launch_pending`), so %APPDATA% is theirs.
fn scan_apps() -> Vec<WinGame> {
    let menu = "Microsoft\\Windows\\Start Menu\\Programs";
    let roots = ["APPDATA", "ProgramData"].into_iter().filter_map(std::env::var_os).map(|v| PathBuf::from(v).join(menu));
    let mut out = Vec::new();
    for root in roots {
        let mut folders = vec![(root.clone(), 0)];
        while let Some((folder, depth)) = folders.pop() {
            let Ok(entries) = fs::read_dir(&folder) else { continue };
            for entry in entries.flatten() {
                let path = entry.path();
                let Ok(kind) = entry.file_type() else { continue };
                if kind.is_dir() && !kind.is_symlink() && depth < 3 {
                    folders.push((path, depth + 1));
                } else if kind.is_file() && path.extension().is_some_and(|x| x.eq_ignore_ascii_case("lnk")) {
                    let Ok(place) = path.with_extension("").strip_prefix(&root).map(Path::to_path_buf) else { continue };
                    let id = format!("app:{}", parse::slug(&place.to_string_lossy()));
                    let name = path.file_stem().map(|s| s.to_string_lossy().into_owned()).unwrap_or_default();
                    out.push(WinGame { id, name, launch: Launch::Uri(path.display().to_string()), dir: None });
                }
            }
        }
    }
    // The Store's apps, which have no shortcut: by the id Windows' Start menu knows them by.
    let listed = shared_games().and_then(|s| fs::read_to_string(s.join(STORE_APPS)).ok()).unwrap_or_default();
    for (name, app) in parse::store_apps(&listed) {
        let launch = Launch::Exe { path: PathBuf::from("explorer.exe"), args: vec![format!("shell:AppsFolder\\{app}")], cwd: None };
        out.push(WinGame { id: format!("app:{}", parse::slug(&app)), name, launch, dir: None });
    }
    out
}

/// Where the Store's apps are listed for Monet, in the shared Games folder.
const STORE_APPS: &str = ".monet\\store-apps.json";

/// The Microsoft Store's apps in the person's Start menu (iCloud, WhatsApp, the new Teams),
/// which have no shortcut Monet could read on Windows' drive: their names and ids, for Monet's
/// app menu (monet-windows-drive). The Agent runs as the person, so the list is theirs.
fn list_store_apps() {
    let Some(shared) = shared_games() else { return };
    let script = "[Console]::OutputEncoding = [Text.Encoding]::UTF8; \
                  $apps = @(Get-StartApps | Where-Object { $_.AppID -like '*!*' } | Select-Object Name, AppID); \
                  ConvertTo-Json -InputObject $apps -Compress";
    let Ok(out) = Command::new("powershell.exe")
        .args(["-NoProfile", "-NonInteractive", "-Command", script])
        .creation_flags(win::CREATE_NO_WINDOW)
        .output()
    else {
        return;
    };
    if !out.status.success() {
        return log("couldn't list the Store's apps");
    }
    let apps: Vec<_> = parse::store_apps(&String::from_utf8_lossy(&out.stdout))
        .into_iter()
        .map(|(name, id)| serde_json::json!({ "name": name, "id": id }))
        .collect();
    let file = shared.join(STORE_APPS);
    let _ = fs::create_dir_all(shared.join(".monet"));
    let temp = file.with_extension("json.part");
    if fs::write(&temp, serde_json::to_vec(&apps).unwrap_or_default()).and_then(|()| fs::rename(&temp, &file)).is_err() {
        log("couldn't keep the list of the Store's apps");
    }
}

/// Windows' accounts can write in the folders Monet shares (the Games folder, and the one for
/// files on both sides): Linux's NTFS drivers give what they make its folder's permissions,
/// and C:\'s own let people add folders but not write in them, so Steam here couldn't install
/// in a Games folder Monet made. Once for each, everything in it then (as administrator).
fn open_shared_folders() {
    let drive = std::env::var("SystemDrive").unwrap_or_else(|_| "C:".into());
    for name in ["Games", "Shared with Monet"] {
        let folder = PathBuf::from(format!("{drive}\\{name}"));
        let marker = data_dir().join(format!("opened-{}", parse::slug(name)));
        if !folder.is_dir() || marker.exists() {
            continue;
        }
        let path = folder.to_string_lossy().into_owned();
        if win::run_hidden("icacls", &[&path, "/grant", "*S-1-5-11:(OI)(CI)M", "/T", "/C", "/Q"]) {
            let _ = fs::write(&marker, now().to_string());
            log(&format!("{path}: Windows' accounts can write there"));
        }
    }
}

/// The folder for files on both sides in Explorer's Quick Access, once for each account (as
/// the person: pins are each person's own).
fn pin_shared_files() {
    let (Some(folder), Some(local)) = (shared_files(), std::env::var_os("LOCALAPPDATA")) else { return };
    let marker = PathBuf::from(local).join("Monet\\shared-pinned");
    if marker.exists() {
        return;
    }
    let script = format!("(New-Object -ComObject Shell.Application).Namespace('{}').Self.InvokeVerb('pintohome')", folder.display());
    if win::run_hidden("powershell.exe", &["-NoProfile", "-NonInteractive", "-Command", &script]) {
        let _ = fs::create_dir_all(marker.parent().unwrap_or(Path::new(".")));
        let _ = fs::write(&marker, now().to_string());
    }
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
                (None, Some(path)) => Launch::Exe { path, args: c.args, cwd: None },
                (None, None) => return None,
            };
            Some(WinGame { id: format!("custom:{}", parse::slug(&c.name)), name: c.name, launch, dir })
        })
        .collect()
}

fn game_list(found: &[WinGame]) -> GameList {
    // Battle.net's and Ubisoft's games their launchers in Monet put in the shared Games folder,
    // which their launcher here may not know yet (Battle.net's until it lists one itself): the
    // folder it may ask for, once.
    let known = known_to_launchers();
    let played = playtime();
    let games = found
        .iter()
        .map(|g| Game {
            id: g.id.clone(),
            name: games::clean_name(&g.name),
            locate: locate(g, &known),
            minutes: played.get(&g.id).copied().unwrap_or(0),
        })
        .collect();
    let mut list = GameList::new(games, now());
    list.games_updated = fs::read_to_string(games_updated_path()).ok().and_then(|t| t.trim().parse().ok());
    list
}

/// {game id: minutes played}: the trips' games, timed from when Bridge saw each start until it
/// closed, for Monet's Games (with Steam's and Heroic's own counts there).
fn playtime_path() -> PathBuf {
    data_dir().join("playtime.json")
}

fn playtime() -> std::collections::HashMap<String, u64> {
    fs::read(playtime_path()).ok().and_then(|data| serde_json::from_slice(&data).ok()).unwrap_or_default()
}

fn add_playtime(id: &str, time: Duration) {
    let mut played = playtime();
    // A minute at least: it did start.
    *played.entry(id.to_string()).or_insert(0) += (time.as_secs() / 60).max(1);
    if let Err(e) = serde_json::to_vec(&played).map_err(|e| e.to_string()).and_then(|data| {
        let temp = playtime_path().with_extension("new");
        fs::write(&temp, data).and_then(|_| fs::rename(&temp, playtime_path())).map_err(|e| e.to_string())
    }) {
        log(&format!("couldn't keep the playtime: {e}"));
    }
}

/// The ids of the games Windows' launchers know (their own installs, in Windows' list of
/// programs): Battle.net's and EA's.
fn known_to_launchers() -> Vec<String> {
    let mut known: Vec<String> = scan_listed().into_iter().map(|g| g.id).collect();
    known.extend(ea_listed().iter().filter_map(|d| ea_game_in(d)).map(|(id, _)| id));
    known
}

/// Where a game a launcher in Monet put in the shared Games folder is, for its launcher here,
/// which may not know it yet: the folder to locate (Battle.net, Ubisoft Connect), or for the
/// EA app, which has no Locate, the folder to install it to, where it finds it. "" when
/// there's nothing to do.
fn locate(g: &WinGame, known: &[String]) -> String {
    let in_shared = g.dir.as_ref().zip(shared_games()).is_some_and(|(d, s)| d.starts_with(&s));
    let unknown = g.id.starts_with("ubisoft:")
        || ((g.id.starts_with("battlenet:") || g.id.starts_with("ea:")) && !known.contains(&g.id));
    match &g.dir {
        Some(dir) if in_shared && unknown && g.id.starts_with("ea:") => dir.parent().map(|p| p.display().to_string()).unwrap_or_default(),
        Some(dir) if in_shared && unknown => dir.display().to_string(),
        _ => String::new(),
    }
}

/// When the last update trip finished, for Monet's Settings.
fn games_updated_path() -> PathBuf {
    data_dir().join("games-updated")
}

/// Shares the games list with Monet through the EFI system partition. The
/// partition is mounted only for the moment it takes to write the file, so a
/// hibernated Windows never holds it open.
fn publish(found: &[WinGame]) -> Res<()> {
    on_esp(ESP_PATH, game_list(found).to_json().as_bytes()).map_err(|e| format!("couldn't write the games list: {e}"))?;
    log(&format!("published {} games", found.len()));
    Ok(())
}

/// Writes a file on the EFI system partition (whole or not at all), mounted only for the moment
/// it takes.
fn on_esp(path: &str, data: &[u8]) -> Res<()> {
    let letter = win::free_drive_letter().ok_or("no free drive letter")?;
    let drive = format!("{letter}:");
    if !win::run_hidden("mountvol", &[&drive, "/S"]) {
        return Err("couldn't mount the EFI system partition".into());
    }
    let target = PathBuf::from(format!("{drive}\\")).join(path.replace('/', "\\"));
    let result = (|| -> std::io::Result<()> {
        fs::create_dir_all(target.parent().expect("path has a parent"))?;
        let tmp = target.with_extension("tmp");
        fs::write(&tmp, data)?;
        fs::rename(&tmp, &target)
    })();
    win::run_hidden("mountvol", &[&drive, "/D"]);
    result.map_err(|e| e.to_string())
}

// ------------------------------------------------------------- the BitLocker key, for Monet

/// The folder Monet leaves its lock in while Windows' drive is open to it: administrators only,
/// so no other account can leave a lock of its own (Linux's NTFS driver gives what Monet writes
/// there the folder's permissions). The keys handed over are noted there too.
fn from_monet() -> PathBuf {
    data_dir().join("from-monet")
}

/// Where the locked recovery keys go, for Monet's next start (monet-windows-drive takes them).
const HANDED: &str = "EFI/Monet/bitlocker.json";

/// Asks Windows for the system drive's recovery keys (BitLocker's own WMI class, as
/// administrator) once it's fully encrypted, and locks each with Monet's lock (RSA-OAEP).
/// `LOCK` is replaced with the lock, checked by `parse::rsa_lock`. Prints only locked keys.
const HAND_OVER: &str = r#"
$ErrorActionPreference = 'Stop'
$v = Get-CimInstance -Namespace 'root/cimv2/Security/MicrosoftVolumeEncryption' -ClassName Win32_EncryptableVolume -Filter "DriveLetter='$env:SystemDrive'"
if (-not $v -or (Invoke-CimMethod -InputObject $v -MethodName GetConversionStatus).ConversionStatus -ne 1) { '[]'; exit 0 }
$ids = @((Invoke-CimMethod -InputObject $v -MethodName GetKeyProtectors -Arguments @{ KeyProtectorType = [uint32]3 }).VolumeKeyProtectorID)
$rsa = New-Object System.Security.Cryptography.RSACryptoServiceProvider
$rsa.FromXmlString('LOCK')
$out = @(foreach ($id in $ids) {
    if (-not $id) { continue }
    $pw = (Invoke-CimMethod -InputObject $v -MethodName GetKeyProtectorNumericalPassword -Arguments @{ VolumeKeyProtectorID = $id }).NumericalPassword
    if ($pw) { [pscustomobject]@{ id = $id; key = [Convert]::ToBase64String($rsa.Encrypt([Text.Encoding]::ASCII.GetBytes($pw), $true)) } }
})
ConvertTo-Json -InputObject $out -Compress
"#;

/// Makes the folder for Monet's lock, for administrators only.
fn make_lock_folder() {
    let dir = from_monet();
    if fs::create_dir_all(&dir).is_ok() {
        let folder = dir.to_string_lossy().into_owned();
        win::run_hidden("icacls", &[&folder, "/inheritance:r", "/grant:r", "*S-1-5-32-544:(OI)(CI)F", "*S-1-5-18:(OI)(CI)F"]);
    }
}

/// When Windows' drive is encrypted (Windows 11 turns device encryption on when someone signs in
/// with a Microsoft account), Monet can't reach it until someone types the recovery key there.
/// So its recovery keys go to Monet by themselves: locked with Monet's lock, on the EFI
/// partition, once for each key. Monet opens them at its next start and takes the file away.
fn hand_over_bitlocker_key() {
    let Some(lock) = fs::read_to_string(from_monet().join("monet-key.xml")).ok().and_then(|x| parse::rsa_lock(&x)) else {
        return;
    };
    let Ok(out) = Command::new("powershell.exe")
        .args(["-NoProfile", "-NonInteractive", "-Command", &HAND_OVER.replace("LOCK", &lock)])
        .creation_flags(win::CREATE_NO_WINDOW)
        .output()
    else {
        return;
    };
    let keys = parse::handed_keys(&String::from_utf8_lossy(&out.stdout));
    let sent_path = from_monet().join("bitlocker-sent");
    let sent = fs::read_to_string(&sent_path).unwrap_or_default();
    if keys.is_empty() || keys.iter().all(|(id, _)| sent.lines().any(|l| l == id)) {
        return;
    }
    let file = serde_json::json!({ "keys": keys.iter().map(|(id, key)| serde_json::json!({ "id": id, "key": key })).collect::<Vec<_>>() });
    match on_esp(HANDED, &serde_json::to_vec(&file).unwrap_or_default()) {
        Ok(()) => {
            let ids: String = keys.iter().map(|(id, _)| format!("{id}\n")).collect();
            let _ = fs::write(&sent_path, ids);
            log(&format!("handed {} recovery key(s) to Monet, locked", keys.len()));
        }
        Err(e) => log(&format!("couldn't hand the recovery key to Monet: {e}")),
    }
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
    keep_install_settings();
    // The folders Monet shares, writable here (the first time, in the background: everything
    // in them); Epic's games Monet put in the shared Games folder, before the list goes to
    // Monet; and the Wi-Fi networks Monet joined.
    std::thread::spawn(open_shared_folders);
    std::thread::spawn(list_store_apps);
    // BitLocker: the folder for Monet's lock, and the recovery key for Monet once there is one.
    make_lock_folder();
    std::thread::spawn(hand_over_bitlocker_key);
    share_with_epic();
    share_with_ubisoft();
    add_wifi();
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

/// What installing Monet set in Windows, which a Windows update can put back: Fast Startup off
/// (on, shutting down leaves Windows' drive half asleep, closed to Monet until a full restart),
/// and the clock kept in UTC as Monet keeps it (else it's off by the time zone after each switch).
fn keep_install_settings() {
    const SETTINGS: [(&str, &str, u32); 2] = [
        ("SYSTEM\\CurrentControlSet\\Control\\Session Manager\\Power", "HiberbootEnabled", 0),
        ("SYSTEM\\CurrentControlSet\\Control\\TimeZoneInformation", "RealTimeIsUniversal", 1),
    ];
    for (key, value, wanted) in SETTINGS {
        if win::reg_machine_dword(key, value) == Some(wanted) {
            continue;
        }
        let data = wanted.to_string();
        if win::run_hidden("reg", &["add", &format!("HKLM\\{key}"), "/v", value, "/t", "REG_DWORD", "/d", &data, "/f"]) {
            log(&format!("{value} was changed (a Windows update?): {wanted} again, as installing Monet set it"));
        }
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
    if let Some(zone) = &req.tz {
        set_time_zone(zone);
    }
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
    // A Windows program Monet sent (Files' Open in Windows): started as the person, never as
    // administrator (anyone can change what's in the shared folder), and Windows stays, as
    // it does when opened from Monet; Back to Monet goes back.
    // An app in the Start menu (Word, from Monet's app menu) goes the same way, found as the
    // person: their own Start menu is theirs to read.
    if id.starts_with("program:") || id.starts_with("app:") {
        match scan_programs().into_iter().find(|p| p.id == id) {
            Some(program) => log(&format!("opening {} from Monet", program.name)),
            None if id.starts_with("app:") => log(&format!("opening {id} from Monet")),
            None => {
                log(&format!("{id} isn't in the Games folder"));
                return;
            }
        }
        let pending = Pending { game: id, created: now(), open: Vec::new(), quietly: false };
        if !run_as_person(&pending) {
            log("launch task missing; the program waits");
        }
        return;
    }

    // A game in the shared Games folder whose launcher Windows hasn't got yet (Epic's for one
    // Heroic put there, Ubisoft Connect or Battle.net for one theirs in Monet did): the
    // launcher first, from the installer Monet fetched while you were in Monet.
    if let Some(key) = missing_launcher(&id, &scan()) {
        log(&format!("installing {key}'s launcher for a game in the shared Games folder"));
        // Monet's painting meanwhile, saying what's happening, rather than Windows' desktop.
        let name = match key {
            "epic" => "Epic Games",
            "ubisoft" => "Ubisoft Connect",
            "ea" => "EA app",
            _ => "Battle.net",
        };
        let _preparing = Cover::open(Scene::Preparing { launcher: name.into() });
        let installed = install_launcher(key);
        log(&format!("{key}'s launcher {}", if installed { "is installed" } else { "couldn't be installed" }));
    }
    if id.starts_with("epic:") {
        share_with_epic();
    }
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
    // Monet's painting instead of Windows' desktop while the game gets going. A game a launcher
    // starts (the EA app, Battle.net...) seems to start from Monet: the painting stays in front
    // of the launcher until the game runs, then the launcher is minimized and closed after.
    // Not when the launcher must show something (a game it doesn't know yet, to locate).
    let launcher = id.split(':').next().and_then(launchers::of_store);
    let quiet = launcher.is_some() && known.is_some_and(|g| g.dir.is_some() && locate(g, &known_to_launchers()).is_empty());
    let cover = Cover::open(Scene::Starting { game: games::clean_name(&name) });
    if quiet {
        if let Some(cover) = &cover {
            cover.hold(true);
        }
    }
    let back_now = std::cell::Cell::new(false);
    let held = std::cell::Cell::new(quiet);
    let since = Instant::now();
    let let_go = || {
        if held.replace(false) {
            if let Some(cover) = &cover {
                cover.hold(false);
            }
        }
    };
    let asked_back = || {
        if cover.as_ref().is_some_and(|c| c.pressed() == Some(Press::BackNow)) {
            back_now.set(true);
        }
        // The launcher wants something (signing in, an update): it comes into view.
        if since.elapsed() > LAUNCHER_PATIENCE {
            let_go();
        }
        back_now.get()
    };
    let game_dir = known.and_then(|g| g.dir.clone());
    let started = || {
        let_go();
        if let Some(key) = launcher.filter(|_| quiet) {
            // Give the launcher a moment to finish opening, then out of the way.
            sleep(Duration::from_secs(2));
            win::minimize_windows_of(&launchers::running(key, game_dir.as_deref()));
        }
    };

    let pending = Pending { game: id.clone(), created: now(), open: Vec::new(), quietly: false };
    if !run_as_person(&pending) {
        log("launch task missing; starting the game directly");
        match (known, &steam_appid) {
            // Here as administrator: never a GOG game's program, which anyone can change in
            // the shared Games folder.
            (Some(game), _) if game.id.starts_with("gog:") => log(&format!("{} waits for the launch task", game.name)),
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
    let played = dir.and_then(|dir| wait_for_game(&dir, &asked_back, &started));
    if let Some(time) = played {
        add_playtime(&id, time);
    }
    let _ = fs::remove_file(pending_path());
    if back_now.get() {
        log(&format!("Back to Monet before {name} started"));
        if let Err(e) = go_back(efi, state, &found) {
            log(&e);
        }
        return;
    }
    if played.is_none() {
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
        // Its launcher goes too (Monet started it for the game), once it's done with its cloud
        // saves; Windows restarting in Monet closes it otherwise.
        if let Some(key) = launcher {
            drop(cover);
            wait_for_quiet(Duration::from_secs(60));
            let left = launchers::running(key, game_dir.as_deref());
            log(&format!("closing {key} ({} programs)", left.len()));
            win::end_processes(&left);
        }
    }
}

/// Waits until the network has been quiet for a few seconds (a launcher putting its game's
/// saves in the cloud), at most `most`.
fn wait_for_quiet(most: Duration) {
    let started = Instant::now();
    let (mut bytes, mut quiet_since) = (win::network_bytes(), Instant::now());
    while started.elapsed() < most && quiet_since.elapsed() < Duration::from_secs(8) {
        sleep(Duration::from_secs(1));
        let now_bytes = win::network_bytes();
        if now_bytes.saturating_sub(bytes) > 128 * 1024 {
            quiet_since = Instant::now();
        }
        bytes = now_bytes;
    }
}

/// Each launcher Monet can fetch the installer of: what its installer is called in the shared
/// Games folder's `.monet\installers` (monet-quick launchers names them so).
const INSTALLERS: [(&str, &str); 5] = [
    ("epic", "EpicGamesLauncherInstaller.msi"),
    ("ubisoft", "UbisoftConnectInstaller.exe"),
    ("battlenet", "Battle.net-Setup.exe"),
    ("ea", "EAappInstaller.exe"),
    // Fetched for someone who uses Discord in Monet; put in on the trip to sign in to launchers.
    ("discord", "DiscordSetup.exe"),
];

fn launcher_installed(key: &str) -> bool {
    match key {
        "epic" => data_dir().parent().unwrap_or(Path::new("C:\\ProgramData")).join("Epic\\EpicGamesLauncher\\Data").is_dir(),
        _ => launchers::installed().iter().any(|l| l.key == key),
    }
}

/// The launcher a game in the shared Games folder needs and Windows hasn't got.
fn missing_launcher(id: &str, found: &[WinGame]) -> Option<&'static str> {
    let shared = shared_games()?;
    let (store, app) = id.split_once(':')?;
    let key = INSTALLERS.iter().map(|(key, _)| *key).find(|key| *key == store)?;
    let in_shared = match key {
        "epic" => shared.join(".monet\\epic").join(format!("{app}.json")).is_file(),
        _ => found.iter().any(|g| g.id == id && g.dir.as_ref().is_some_and(|d| d.starts_with(&shared))),
    };
    (in_shared && !launcher_installed(key)).then_some(key)
}

/// Install-Launcher.ps1 for a launcher, with the installer Monet fetched if there is one.
/// Whether Monet fetched that installer into the shared Games folder (`.monet\installers`).
fn installer_fetched(key: &str) -> bool {
    let file = INSTALLERS.iter().find(|(k, _)| *k == key).map(|(_, file)| *file).unwrap_or_default();
    !file.is_empty() && shared_games().is_some_and(|s| s.join(".monet\\installers").join(file).is_file())
}

fn installer_command(key: &str) -> Command {
    let mut command = Command::new("powershell.exe");
    command
        .args(["-NoProfile", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden", "-File"])
        .arg(install_dir().join("Install-Launcher.ps1"))
        .args(["-Launcher", key])
        .creation_flags(win::CREATE_NO_WINDOW);
    let file = INSTALLERS.iter().find(|(k, _)| *k == key).map(|(_, file)| *file).unwrap_or_default();
    if let Some(installer) = shared_games().map(|s| s.join(".monet\\installers").join(file)).filter(|p| p.is_file()) {
        command.arg("-Installer").arg(installer);
    }
    command
}

/// Installs a launcher: Epic's and Ubisoft's with no questions, here as administrator;
/// Battle.net's and the EA app's show their own window, so they run as the person (each asks
/// for an administrator itself), and Discord installs for the person alone, so as them too;
/// Monet waits. Whether it's there afterwards.
fn install_launcher(key: &str) -> bool {
    if !matches!(key, "battlenet" | "ea" | "discord") {
        return installer_command(key).status().is_ok_and(|s| s.success()) && launcher_installed(key);
    }
    let pending = Pending { game: String::new(), created: now(), open: vec![format!("install:{key}")], quietly: false };
    if !run_as_person(&pending) {
        return false;
    }
    let started = Instant::now();
    while started.elapsed() < Duration::from_secs(20 * 60) {
        if launcher_installed(key) {
            return true;
        }
        sleep(Duration::from_secs(5));
    }
    false
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
    // Discord, for someone who uses it in Monet (its installer is there for them): in first,
    // so it's signed in to with the rest and Windows starts it at sign-in after, for calls.
    if !launcher_installed("discord") && installer_fetched("discord") {
        let _preparing = Cover::open(Scene::Preparing { launcher: "Discord".into() });
        let installed = install_launcher("discord");
        log(&format!("Discord {}", if installed { "is installed" } else { "couldn't be installed" }));
    }
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
    let (mut bytes, mut measured, mut quiet_since) = (win::network_bytes(), Instant::now(), Instant::now());
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
        let now_bytes = win::network_bytes();
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
        Launch::Exe { path, args, cwd } => {
            let mut cmd = Command::new(path);
            cmd.args(args);
            if let Some(dir) = cwd.as_deref().or(path.parent()) {
                cmd.current_dir(dir);
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
    // Before Steam starts for the game (or the launchers): the Games folder Monet shares; and
    // the folder for files on both sides in Explorer.
    share_with_steam();
    pin_shared_files();
    if !pending.open.is_empty() {
        for key in &pending.open {
            // A launcher to install with its own window (Battle.net's), as the person.
            if let Some(launcher) = key.strip_prefix("install:") {
                if !installer_command(launcher).status().is_ok_and(|s| s.success()) {
                    log(&format!("couldn't install {launcher}"));
                }
            } else if !launchers::open(key, pending.quietly) {
                log(&format!("couldn't open {key}"));
            }
        }
        return Ok(());
    }
    let found = match pending.game.split_once(':').map(|(store, _)| store) {
        Some("program") => scan_programs(),
        Some("app") => scan_apps(),
        _ => scan(),
    };
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

/// Waits for the game to start (then `started`), then for it to close. Returns how long it ran,
/// or None if it never started, or `stop` said so before it did (Back to Monet on the cover).
fn wait_for_game(dir: &Path, stop: &dyn Fn() -> bool, started: &dyn Fn()) -> Option<Duration> {
    let names = exe_names(dir);
    let mut prefix = dir.to_string_lossy().to_lowercase();
    if !prefix.ends_with('\\') {
        prefix.push('\\');
    }

    let since = Instant::now();
    while !game_running(&prefix, &names) {
        // A second between looks at the process list, answering Back to Monet meanwhile.
        let look = Instant::now();
        while look.elapsed() < Duration::from_secs(1) {
            if since.elapsed() > START_TIMEOUT || stop() {
                return None;
            }
            sleep(Duration::from_millis(250));
        }
    }
    started();

    let running = Instant::now();
    let mut gone_since: Option<Instant> = None;
    loop {
        if game_running(&prefix, &names) {
            gone_since = None;
        } else if let Some(gone) = gone_since {
            if gone.elapsed() >= QUIT_GRACE {
                return Some(gone.duration_since(running));
            }
        } else {
            gone_since = Some(Instant::now());
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
    export_wifi();
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
        return Err("Usage: monet-bridge cover-preview starting|back|launchers|updating|preparing OUT.png [PICTURES]".into());
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
        "preparing" => Scene::Preparing { launcher: "Battle.net".into() },
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

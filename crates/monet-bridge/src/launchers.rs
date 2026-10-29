//! The game launchers this Windows has: where they are, how to open them (quietly, for the
//! update trip), and whether they keep you signed in, as far as their own files say.

use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;

use crate::parse;
use crate::win;

pub struct Launcher {
    /// Stays the same in files and requests: "steam", "epic"...
    pub key: &'static str,
    pub name: &'static str,
    pub exe: PathBuf,
}

/// Arguments that open a launcher without its window in front, where it has them.
fn quiet_args(key: &str) -> &'static [&'static str] {
    match key {
        "steam" | "epic" => &["-silent"],
        _ => &[],
    }
}

fn env_dir(name: &str, fallback: &str) -> PathBuf {
    std::env::var_os(name).map(PathBuf::from).unwrap_or_else(|| PathBuf::from(fallback))
}

/// Where each launcher would be. The first that exists counts.
fn places() -> Vec<(&'static str, &'static str, Vec<PathBuf>)> {
    let x86 = env_dir("ProgramFiles(x86)", "C:\\Program Files (x86)");
    let x64 = env_dir("ProgramFiles", "C:\\Program Files");
    let steam = win::reg_user("Software\\Valve\\Steam", "SteamExe")
        .map(|p| PathBuf::from(p.replace('/', "\\")))
        .unwrap_or_else(|| x86.join("Steam\\steam.exe"));
    let riot = fs::read_to_string(env_dir("ProgramData", "C:\\ProgramData").join("Riot Games\\RiotClientInstalls.json"))
        .ok()
        .and_then(|j| parse::riot_client_path(&j))
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from("C:\\Riot Games\\Riot Client\\RiotClientServices.exe"));
    vec![
        ("steam", "Steam", vec![steam]),
        ("epic", "Epic Games", vec![
            x86.join("Epic Games\\Launcher\\Portal\\Binaries\\Win64\\EpicGamesLauncher.exe"),
            x86.join("Epic Games\\Launcher\\Portal\\Binaries\\Win32\\EpicGamesLauncher.exe"),
        ]),
        ("riot", "Riot Client", vec![riot]),
        ("battlenet", "Battle.net", vec![x86.join("Battle.net\\Battle.net Launcher.exe"), x86.join("Battle.net\\Battle.net.exe")]),
        ("ea", "EA app", vec![x64.join("Electronic Arts\\EA Desktop\\EA Desktop\\EALauncher.exe")]),
        ("ubisoft", "Ubisoft Connect", vec![
            x86.join("Ubisoft\\Ubisoft Game Launcher\\UbisoftConnect.exe"),
            x86.join("Ubisoft\\Ubisoft Game Launcher\\upc.exe"),
        ]),
        ("gog", "GOG Galaxy", vec![x86.join("GOG Galaxy\\GalaxyClient.exe")]),
        ("rockstar", "Rockstar Games Launcher", vec![x64.join("Rockstar Games\\Launcher\\Launcher.exe")]),
        // Not a launcher, but signed in to once with them, for calls in Windows (Monet puts it in
        // for someone who uses it there); each Windows account has its own, opened by its updater.
        ("discord", "Discord", vec![env_dir("LOCALAPPDATA", "").join("Discord\\Update.exe")]),
    ]
}

pub fn installed() -> Vec<Launcher> {
    places()
        .into_iter()
        .filter_map(|(key, name, paths)| paths.into_iter().find(|p| p.is_file()).map(|exe| Launcher { key, name, exe }))
        .collect()
}

/// True when the launcher's own files say it keeps you signed in. Launchers that don't say
/// are false: Monet doesn't claim what it can't see.
pub fn signed_in(key: &str) -> bool {
    let local = env_dir("LOCALAPPDATA", "");
    let read = |path: PathBuf| fs::read_to_string(path).unwrap_or_default();
    match key {
        "steam" => win::reg_user("Software\\Valve\\Steam", "AutoLoginUser").is_some_and(|u| !u.is_empty()),
        "epic" => parse::epic_remembers(&read(local.join("EpicGamesLauncher\\Saved\\Config\\Windows\\GameUserSettings.ini"))),
        "riot" => parse::riot_remembers(&read(local.join("Riot Games\\Riot Client\\Data\\RiotGamesPrivateSettings.yaml"))),
        _ => false,
    }
}

/// The launcher a game of this store is started through and comes back up with, which Monet
/// keeps out of sight and closes after: not Steam (friends, chat), nor GOG's games (no launcher).
pub fn of_store(store: &str) -> Option<&'static str> {
    ["ea", "battlenet", "ubisoft", "epic", "rockstar", "riot"].into_iter().find(|key| *key == store)
}

/// The folder all of a launcher's programs run from (never its games): Epic's web helper is a
/// few folders from its launcher, the EA app's are one up from EALauncher.
fn home(launcher: &Launcher) -> Option<PathBuf> {
    match launcher.key {
        "epic" => launcher.exe.ancestors().find(|a| a.file_name().is_some_and(|n| n.eq_ignore_ascii_case("Launcher"))).map(Path::to_path_buf),
        "ea" => launcher.exe.parent().and_then(Path::parent).map(Path::to_path_buf),
        _ => launcher.exe.parent().map(Path::to_path_buf),
    }
}

/// The launcher's programs running now, by process id: not its Windows services (EA's and
/// Rockstar's background services), which Windows itself keeps, nor the game's (`except`: its
/// folder, which Ubisoft keeps inside its launcher's).
pub fn running(key: &str, except: Option<&Path>) -> Vec<u32> {
    let Some(home) = installed().into_iter().find(|l| l.key == key).and_then(|l| home(&l)) else { return Vec::new() };
    let folder = |p: &Path| {
        let mut text = p.to_string_lossy().to_lowercase();
        if !text.ends_with('\\') {
            text.push('\\');
        }
        text
    };
    let (prefix, game) = (folder(&home), except.map(folder));
    win::processes()
        .into_iter()
        .filter(|p| {
            let name = p.exe_name.to_lowercase();
            p.path.as_ref().is_some_and(|path| {
                let path = path.to_string_lossy().to_lowercase();
                path.starts_with(&prefix) && !game.as_ref().is_some_and(|g| path.starts_with(g))
            }) && !name.ends_with("service.exe")
                && !name.ends_with("svc.exe")
        })
        .map(|p| p.pid)
        .collect()
}

/// Opens a launcher. Runs as the person (the `\Monet\Launch` task), never as administrator.
pub fn open(key: &str, quietly: bool) -> bool {
    let Some(launcher) = installed().into_iter().find(|l| l.key == key) else { return false };
    let mut command = Command::new(&launcher.exe);
    if key == "discord" {
        command.args(["--processStart", "Discord.exe"]);
        if quietly {
            command.args(["--process-start-args", "--start-minimized"]);
        }
    } else if quietly {
        command.args(quiet_args(key));
    }
    if let Some(dir) = launcher.exe.parent() {
        command.current_dir(dir);
    }
    command.spawn().is_ok()
}

//! The game launchers this Windows has: where they are, how to open them (quietly, for the
//! update trip), and whether they keep you signed in, as far as their own files say.

use std::fs;
use std::path::PathBuf;
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

/// Opens a launcher. Runs as the person (the `\Monet\Launch` task), never as administrator.
pub fn open(key: &str, quietly: bool) -> bool {
    let Some(launcher) = installed().into_iter().find(|l| l.key == key) else { return false };
    let mut command = Command::new(&launcher.exe);
    if quietly {
        command.args(quiet_args(key));
    }
    if let Some(dir) = launcher.exe.parent() {
        command.current_dir(dir);
    }
    command.spawn().is_ok()
}

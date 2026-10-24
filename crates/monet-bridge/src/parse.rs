//! Readers for launcher files (pure functions, so they're testable anywhere).

use monet_core::games;

/// Every `"key" "value"` pair in a Valve KeyValues (VDF/ACF) text file, in
/// order, ignoring nesting. Enough for `libraryfolders.vdf` and
/// `appmanifest_*.acf`.
pub fn vdf_pairs(text: &str) -> Vec<(String, String)> {
    let mut tokens = Vec::new();
    let mut chars = text.chars().peekable();
    while let Some(c) = chars.next() {
        match c {
            '"' => {
                let mut s = String::new();
                while let Some(c) = chars.next() {
                    match c {
                        '\\' => match chars.next() {
                            Some('n') => s.push('\n'),
                            Some('t') => s.push('\t'),
                            Some(other) => s.push(other),
                            None => {}
                        },
                        '"' => break,
                        _ => s.push(c),
                    }
                }
                tokens.push(Some(s));
            }
            '{' | '}' => tokens.push(None),
            '/' if chars.peek() == Some(&'/') => {
                for c in chars.by_ref() {
                    if c == '\n' {
                        break;
                    }
                }
            }
            _ => {}
        }
    }

    let mut pairs = Vec::new();
    let mut i = 0;
    while i + 1 < tokens.len() {
        match (&tokens[i], &tokens[i + 1]) {
            (Some(k), Some(v)) => {
                pairs.push((k.clone(), v.clone()));
                i += 2;
            }
            _ => i += 1,
        }
    }
    pairs
}

pub fn vdf_get<'a>(pairs: &'a [(String, String)], key: &str) -> Option<&'a str> {
    pairs.iter().find(|(k, _)| k.eq_ignore_ascii_case(key)).map(|(_, v)| v.as_str())
}

/// Library folders listed in `libraryfolders.vdf`.
pub fn steam_libraries(text: &str) -> Vec<String> {
    vdf_pairs(text)
        .into_iter()
        .filter(|(k, _)| k.eq_ignore_ascii_case("path"))
        .map(|(_, v)| v)
        .collect()
}

pub struct SteamApp {
    pub appid: String,
    pub name: String,
    pub installdir: String,
}

/// Steam ids of tools that show up as "apps" but aren't games.
const STEAM_TOOLS: &[&str] = &["228980", "250820", "1007", "1070560", "1391110", "1628350"];

/// A fully installed game from an `appmanifest_*.acf`, or None for tools,
/// half-downloaded games and anything malformed.
pub fn steam_app(text: &str) -> Option<SteamApp> {
    let pairs = vdf_pairs(text);
    let appid = vdf_get(&pairs, "appid")?.to_string();
    let name = vdf_get(&pairs, "name")?.to_string();
    let installdir = vdf_get(&pairs, "installdir")?.to_string();
    let flags: u32 = vdf_get(&pairs, "StateFlags").and_then(|f| f.parse().ok()).unwrap_or(0);
    let installed = flags & 4 != 0;
    let tool = STEAM_TOOLS.contains(&appid.as_str())
        || name.starts_with("Proton")
        || name.starts_with("Steam Linux Runtime")
        || name.contains("Redistributable");
    let valid = games::is_valid_id(&format!("steam:{appid}")) && !installdir.contains("..");
    (installed && !tool && valid).then_some(SteamApp { appid, name, installdir })
}

pub struct EpicApp {
    pub app_name: String,
    pub display_name: String,
    pub install_location: String,
    pub launch_uri: String,
}

/// A game from an Epic Games Launcher `.item` manifest. Skips DLC and
/// non-game apps.
pub fn epic_app(text: &str) -> Option<EpicApp> {
    let v: serde_json::Value = serde_json::from_str(text).ok()?;
    let s = |key: &str| v.get(key).and_then(|x| x.as_str()).unwrap_or("").to_string();
    let app_name = s("AppName");
    let main = s("MainGameAppName");
    if !main.is_empty() && main != app_name {
        return None; // DLC
    }
    if v.get("bIsApplication").and_then(|b| b.as_bool()) == Some(false) {
        return None;
    }
    if !games::is_valid_id(&format!("epic:{app_name}")) {
        return None;
    }
    let (namespace, item) = (s("CatalogNamespace"), s("CatalogItemId"));
    let launch_uri = format!(
        "com.epicgames.launcher://apps/{}%3A{}%3A{}?action=launch&silent=true",
        url_part(&namespace),
        url_part(&item),
        url_part(&app_name)
    );
    Some(EpicApp { display_name: s("DisplayName"), install_location: s("InstallLocation"), app_name, launch_uri })
}

fn url_part(s: &str) -> String {
    s.chars().filter(|c| c.is_ascii_alphanumeric() || matches!(c, '-' | '_' | '.')).collect()
}

/// `product_install_full_path` from a Riot `*.product_settings.yaml`.
pub fn riot_install_path(yaml: &str) -> Option<String> {
    yaml.lines().find_map(|line| {
        let value = line.trim().strip_prefix("product_install_full_path:")?;
        let value = value.trim().trim_matches(|c| c == '"' || c == '\'');
        (!value.is_empty()).then(|| value.replace('/', "\\"))
    })
}

/// `RiotClientServices.exe` path from `RiotClientInstalls.json`.
pub fn riot_client_path(json: &str) -> Option<String> {
    let v: serde_json::Value = serde_json::from_str(json).ok()?;
    ["rc_default", "rc_live"]
        .iter()
        .find_map(|k| v.get(k).and_then(|p| p.as_str()))
        .map(|p| p.replace('/', "\\"))
}

/// Friendly names for Riot product ids.
pub fn riot_name(product: &str) -> String {
    match product {
        "valorant" => "VALORANT".into(),
        "league_of_legends" => "League of Legends".into(),
        "bacon" => "Legends of Runeterra".into(),
        "lion" => "2XKO".into(),
        other => other
            .split('_')
            .map(|w| {
                let mut c = w.chars();
                c.next().map(|f| f.to_uppercase().collect::<String>() + c.as_str()).unwrap_or_default()
            })
            .collect::<Vec<_>>()
            .join(" "),
    }
}

/// Whether Steam is updating a game right now (`appmanifest_*.acf`: StateFlags 256, update
/// running, or 1024, update started). One only waiting for an update (2) or paused (512)
/// doesn't count: Steam may have scheduled it for later.
pub fn steam_updating(text: &str) -> bool {
    let flags: u32 = vdf_get(&vdf_pairs(text), "StateFlags").and_then(|f| f.parse().ok()).unwrap_or(0);
    flags & (256 | 1024) != 0
}

/// Whether Epic's launcher keeps you signed in: `Enable=True` under `[RememberMe]` in its
/// `GameUserSettings.ini`.
pub fn epic_remembers(ini: &str) -> bool {
    let mut section = "";
    for line in ini.lines().map(str::trim) {
        if line.starts_with('[') {
            section = line;
        } else if section.eq_ignore_ascii_case("[RememberMe]") && line.replace(' ', "").eq_ignore_ascii_case("Enable=True") {
            return true;
        }
    }
    false
}

/// Whether the Riot Client keeps you signed in: "Stay signed in" keeps its session cookie
/// (`ssid`) in `RiotGamesPrivateSettings.yaml`.
pub fn riot_remembers(yaml: &str) -> bool {
    yaml.contains("ssid")
}

/// An update trip ends once Windows Update has finished, no Steam game is mid-update and
/// the downloads have been quiet for five minutes (the other launchers say nothing, so the
/// network speaks for them), but not before they've had ten minutes to start and look; or
/// after an hour and a half whatever happens. All in seconds.
pub const UPDATE_LIMIT: u64 = 90 * 60;
pub const UPDATE_AT_LEAST: u64 = 10 * 60;
pub const UPDATE_QUIET: u64 = 5 * 60;
/// Received bytes a second below which the downloads count as quiet.
pub const QUIET_RATE: u64 = 250_000;

pub fn updates_settled(elapsed: u64, quiet_for: u64, windows_done: bool, steam_busy: bool) -> bool {
    elapsed >= UPDATE_LIMIT || (windows_done && !steam_busy && quiet_for >= UPDATE_QUIET && elapsed >= UPDATE_AT_LEAST)
}

/// Turns a display name into the key part of a `custom:` id.
pub fn slug(name: &str) -> String {
    let mut out = String::new();
    for c in name.chars() {
        if c.is_ascii_alphanumeric() {
            out.push(c.to_ascii_lowercase());
        } else if !out.ends_with('-') && !out.is_empty() {
            out.push('-');
        }
    }
    let out = out.trim_end_matches('-');
    out.chars().take(64).collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    const LIBRARIES: &str = r#"
"libraryfolders"
{
	"0"
	{
		"path"		"C:\\Program Files (x86)\\Steam"
		"apps" { "228980" "1" }
	}
	"1"
	{
		"path"		"D:\\SteamLibrary"
	}
}"#;

    #[test]
    fn steam_library_paths() {
        assert_eq!(steam_libraries(LIBRARIES), vec!["C:\\Program Files (x86)\\Steam", "D:\\SteamLibrary"]);
    }

    #[test]
    fn steam_manifests() {
        let game = r#""AppState" { "appid" "1172470" "name" "Apex Legends" "StateFlags" "4" "installdir" "Apex Legends" }"#;
        let app = steam_app(game).unwrap();
        assert_eq!((app.appid.as_str(), app.name.as_str(), app.installdir.as_str()), ("1172470", "Apex Legends", "Apex Legends"));

        let downloading = game.replace("\"4\"", "\"1026\"");
        assert!(steam_app(&downloading).is_none());
        let updating = game.replace("\"4\"", "\"6\"");
        assert!(steam_app(&updating).is_some());
        let redist = r#""AppState" { "appid" "228980" "name" "Steamworks Common Redistributables" "StateFlags" "4" "installdir" "x" }"#;
        assert!(steam_app(redist).is_none());
    }

    #[test]
    fn epic_manifests() {
        let item = r#"{"AppName":"Fortnite","MainGameAppName":"Fortnite","DisplayName":"Fortnite",
            "InstallLocation":"C:\\Program Files\\Epic Games\\Fortnite","CatalogNamespace":"fn",
            "CatalogItemId":"4fe75bbc5a674f4f9b356b5c90567da5","bIsApplication":true}"#;
        let app = epic_app(item).unwrap();
        assert_eq!(app.display_name, "Fortnite");
        assert_eq!(
            app.launch_uri,
            "com.epicgames.launcher://apps/fn%3A4fe75bbc5a674f4f9b356b5c90567da5%3AFortnite?action=launch&silent=true"
        );
        let dlc = item.replace(r#""AppName":"Fortnite""#, r#""AppName":"FortniteDLC""#);
        assert!(epic_app(&dlc).is_none());
    }

    #[test]
    fn riot_files() {
        let yaml = "product_install_full_path: \"C:/Riot Games/VALORANT/live\"\nproduct_install_root: \"C:/Riot Games\"\n";
        assert_eq!(riot_install_path(yaml).unwrap(), "C:\\Riot Games\\VALORANT\\live");
        let installs = r#"{"associated_client":{},"rc_default":"C:/Riot Games/Riot Client/RiotClientServices.exe"}"#;
        assert_eq!(riot_client_path(installs).unwrap(), "C:\\Riot Games\\Riot Client\\RiotClientServices.exe");
        assert_eq!(riot_name("valorant"), "VALORANT");
        assert_eq!(riot_name("some_new_game"), "Some New Game");
    }

    #[test]
    fn what_launchers_say() {
        let game = |flags: &str| format!(r#""AppState" {{ "appid" "730" "name" "Counter-Strike 2" "StateFlags" "{flags}" }}"#);
        assert!(!steam_updating(&game("4")));        // up to date
        assert!(steam_updating(&game("1026")));      // downloading an update
        assert!(!steam_updating(&game("6")));        // waiting for one Steam may do later
        assert!(!steam_updating(&game("518")));      // paused

        let epic = "[Launcher]\nDefaultAppInstallLocation=C:\\Games\n\n[RememberMe]\nEnable = True\nData=abc\n";
        assert!(epic_remembers(epic));
        assert!(!epic_remembers(&epic.replace("True", "False")));
        assert!(!epic_remembers("[Other]\nEnable=True\n"));
        assert!(riot_remembers("riot-login:\n  persist:\n    session:\n      cookies:\n        - name: \"ssid\"\n"));
        assert!(!riot_remembers("riot-login:\n  persist: {}\n"));
    }

    #[test]
    fn an_update_trip_ends_when_everything_is_quiet() {
        let min = 60;
        assert!(!updates_settled(5 * min, 5 * min, true, false));     // launchers still starting
        assert!(updates_settled(12 * min, 5 * min, true, false));
        assert!(!updates_settled(12 * min, 5 * min, false, false));   // Windows Update still at it
        assert!(!updates_settled(12 * min, 5 * min, true, true));     // Steam mid-update
        assert!(!updates_settled(12 * min, 2 * min, true, false));    // still downloading
        assert!(updates_settled(UPDATE_LIMIT, 0, false, true));       // time's up whatever happens
    }

    #[test]
    fn slugs() {
        assert_eq!(slug("Overwatch 2"), "overwatch-2");
        assert_eq!(slug("  Diablo® IV: Season ★ "), "diablo-iv-season");
        assert!(games::is_valid_id(&format!("custom:{}", slug("Call of Duty®: Black Ops 6"))));
    }
}

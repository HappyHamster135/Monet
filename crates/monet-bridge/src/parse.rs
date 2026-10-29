//! Readers for launcher files (pure functions, so they're testable anywhere).

use monet_core::games;

enum Token {
    Text(String),
    Open,
    Close,
}

/// The quoted texts and braces of a Valve KeyValues (VDF/ACF) text file, in order.
fn vdf_tokens(text: &str) -> Vec<Token> {
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
                tokens.push(Token::Text(s));
            }
            '{' => tokens.push(Token::Open),
            '}' => tokens.push(Token::Close),
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
    tokens
}

/// Every `"key" "value"` pair in a Valve KeyValues (VDF/ACF) text file, in
/// order, ignoring nesting. Enough for `libraryfolders.vdf` and
/// `appmanifest_*.acf`.
pub fn vdf_pairs(text: &str) -> Vec<(String, String)> {
    let tokens = vdf_tokens(text);
    let mut pairs = Vec::new();
    let mut i = 0;
    while i + 1 < tokens.len() {
        match (&tokens[i], &tokens[i + 1]) {
            (Token::Text(k), Token::Text(v)) => {
                pairs.push((k.clone(), v.clone()));
                i += 2;
            }
            _ => i += 1,
        }
    }
    pairs
}

/// The same folder as Windows sees it: any case, either slash, with or without a last one.
pub fn same_folder(a: &str, b: &str) -> bool {
    let clean = |p: &str| p.replace('/', "\\").trim_end_matches('\\').to_lowercase();
    clean(a) == clean(b)
}

/// Whether `libraryfolders.vdf` lists `folder` as one of Steam's libraries.
pub fn library_listed(text: &str, folder: &str) -> bool {
    steam_libraries(text).iter().any(|p| same_folder(p, folder))
}

/// `libraryfolders.vdf` with `folder` added as Steam's next library, the way Steam writes
/// one (its games it finds by itself), or None when the file has no list to add it to.
pub fn with_library(text: &str, folder: &str, contentid: &str) -> Option<String> {
    let end = text.rfind('}')?;
    // The libraries are numbered: the keys that open a block one level in.
    let (mut depth, mut key, mut next) = (0, None::<String>, 0u32);
    for token in vdf_tokens(text) {
        match token {
            Token::Open => {
                if depth == 1 {
                    if let Some(n) = key.as_deref().and_then(|k| k.parse::<u32>().ok()) {
                        next = next.max(n + 1);
                    }
                }
                depth += 1;
                key = None;
            }
            Token::Close => {
                depth -= 1;
                key = None;
            }
            Token::Text(s) => key = Some(s),
        }
    }
    if depth != 0 {
        return None;
    }
    let quote = |s: &str| s.replace('\\', "\\\\").replace('"', "\\\"");
    let entry = format!(
        "\t\"{next}\"\n\t{{\n\t\t\"path\"\t\t\"{}\"\n\t\t\"label\"\t\t\"\"\n\t\t\"contentid\"\t\t\"{}\"\n\
         \t\t\"totalsize\"\t\t\"0\"\n\t\t\"update_clean_bytes_tally\"\t\t\"0\"\n\t\t\"time_last_update_verified\"\t\t\"0\"\n\
         \t\t\"apps\"\n\t\t{{\n\t\t}}\n\t}}\n",
        quote(folder),
        quote(contentid)
    );
    // Before the closing brace's own line, or right before the brace when it shares one.
    let line = text[..end].rfind('\n').map(|i| i + 1).unwrap_or(0);
    let at = if text[line..end].trim().is_empty() { line } else { end };
    let lead = if text[..at].ends_with('\n') { "" } else { "\n" };
    Some(format!("{}{lead}{entry}{}", &text[..at], &text[at..]))
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

/// A GOG game, from the `goggame-<id>.info` in its folder: what its primary play task starts.
pub struct GogGame {
    pub id: String,
    pub name: String,
    /// The program and the folder it runs in, both from the game's own folder.
    pub exe: String,
    pub args: Vec<String>,
    pub working_dir: String,
}

/// A path in a game's own folder, nothing outside it (no drive, no root, no "..").
fn inside(p: &str) -> bool {
    !p.is_empty() && !p.contains(':') && !p.starts_with('\\') && !p.split('\\').any(|part| part == "..")
}

/// GOG's games are DRM-free, so one installed in the Games folder Monet shares (by Heroic, in
/// Monet) starts in Windows with no launcher: its own info file says how.
pub fn gog_game(text: &str) -> Option<GogGame> {
    let v: serde_json::Value = serde_json::from_str(text.trim_start_matches('\u{feff}')).ok()?;
    let id = v.get("gameId").and_then(|x| x.as_str())?.to_string();
    let name = v.get("name").and_then(|x| x.as_str())?.to_string();
    let tasks = v.get("playTasks")?.as_array()?;
    let task = tasks
        .iter()
        .find(|t| t.get("isPrimary").and_then(|p| p.as_bool()) == Some(true))
        .filter(|t| t.get("type").and_then(|x| x.as_str()).is_none_or(|kind| kind == "FileTask"))?;
    let text = |key: &str| task.get(key).and_then(|x| x.as_str()).unwrap_or("").replace('/', "\\");
    let (exe, working_dir) = (text("path"), text("workingDir"));
    if !games::is_valid_id(&format!("gog:{id}")) || !inside(&exe) || !(working_dir.is_empty() || inside(&working_dir)) {
        return None;
    }
    // shortcut: arguments split on spaces; GOG's rarely quote any.
    let args = text("arguments").split_whitespace().map(str::to_string).collect();
    Some(GogGame { id, name, exe, args, working_dir })
}

/// Battle.net's games, as Playnite lists them: the uid its uninstaller is given (`--uid=…`),
/// and the code its client starts the game by (`Battle.net.exe --exec="launch CODE"`).
const BATTLENET: &[(&str, &str)] = &[
    ("wow", "WoW"), ("diablo3", "D3"), ("s2", "S2"), ("s1", "S1"), ("hs_beta", "WTCG"), ("heroes", "Hero"),
    ("prometheus", "Pro"), ("viper", "VIPR"), ("odin", "ODIN"), ("w3", "W3"), ("lazarus", "LAZR"), ("zeus", "ZEUS"),
    ("wlby", "WLBY"), ("osi", "OSI"), ("rtro", "RTRO"), ("fore", "FORE"), ("anbs", "ANBS"), ("auks", "AUKS"),
    ("fen", "Fen"), ("d1", "D1"), ("w1r", "W1R"), ("w2r", "W2R"), ("w1", "W1"), ("w2", "W2"), ("gryphon", "GRY"),
    ("aris", "ARIS"), ("scorpio", "SCOR"), ("arkansas", "ARK"), ("libra", "LBRA"), ("pinta", "PNTA"), ("aqua", "AQUA"),
];

/// A game another launcher put in Windows' list of programs, by how its uninstaller is started:
/// `battlenet:CODE` (Blizzard's, given the game's uid) or `rockstar:TITLE` (Rockstar Games
/// Launcher's, `-uninstall=TITLE`). Test and beta versions aren't games of their own.
pub fn listed_game(name: &str, uninstall: &str) -> Option<String> {
    if name.trim().is_empty() || name.ends_with("Test") || name.ends_with("Beta") {
        return None;
    }
    let lower = uninstall.to_lowercase();
    if lower.contains("rockstar") {
        let title = lower[lower.rfind("uninstall=")? + 10..].trim().trim_matches('"');
        let ok = !title.is_empty() && title.len() <= 32 && title.chars().all(|c| c.is_ascii_alphanumeric() || c == '_');
        return ok.then(|| format!("rockstar:{title}"));
    }
    let after = &uninstall[uninstall.find("Battle.net")?..];
    let uid = after[after.find("--uid=")? + 6..].split(|c: char| c.is_whitespace() || c == '"').next()?;
    battlenet_code(uid).map(|code| format!("battlenet:{code}"))
}

/// The code Battle.net's client starts a game by, from the game's uid: its own, or a longer
/// spelling of it (fenris is Fen's), the longest that fits. Not a variant (wow_classic):
/// that's another game, which the code would start the wrong one of.
pub fn battlenet_code(uid: &str) -> Option<&'static str> {
    let uid = uid.to_lowercase();
    BATTLENET
        .iter()
        .filter(|(known, _)| uid.strip_prefix(known).is_some_and(|rest| !rest.starts_with('_')))
        .max_by_key(|(known, _)| known.len())
        .map(|(_, code)| *code)
}

/// The game's uid from a Battle.net game folder's `.build.info` (its Product column, on the
/// active row), as Battle.net's agent writes it beside each game it installs.
pub fn build_info_product(text: &str) -> Option<String> {
    let mut lines = text.lines().filter(|l| !l.trim().is_empty() && !l.starts_with('#'));
    let header: Vec<String> =
        lines.next()?.split('|').map(|c| c.split('!').next().unwrap_or("").trim().to_lowercase()).collect();
    let product = header.iter().position(|c| c == "product")?;
    let active = header.iter().position(|c| c == "active");
    let rows: Vec<Vec<&str>> = lines.map(|l| l.split('|').collect()).collect();
    let row = rows.iter().find(|r| active.is_some_and(|a| r.get(a) == Some(&"1"))).or(rows.first())?;
    let uid = row.get(product)?.trim();
    (!uid.is_empty() && uid.chars().all(|c| c.is_ascii_alphanumeric() || c == '_')).then(|| uid.to_string())
}

/// An EA game, from the `__Installer\installerdata.xml` the EA app keeps in its folder: the
/// offer ids the EA app starts it by (`origin2://game/launch?offerIds=…`, as Lutris does),
/// and its title.
#[derive(Debug, PartialEq)]
pub struct EaGame {
    pub offers: Vec<String>,
    pub title: Option<String>,
}

pub fn ea_game(xml: &str) -> Option<EaGame> {
    fn between<'a>(text: &'a str, open: &str, close: &str) -> Vec<&'a str> {
        text.split(open).skip(1).filter_map(|part| part.split(close).next()).collect()
    }
    let ids = between(xml, "<contentIDs>", "</contentIDs>").into_iter().next()?;
    let offers: Vec<String> = between(ids, "<contentID>", "</contentID>").into_iter().map(|id| id.trim().to_string()).collect();
    let ok = |id: &String| !id.is_empty() && id.len() <= 48 && !id.starts_with('.') && id.chars().all(|c| c.is_ascii_alphanumeric() || matches!(c, '.' | '_' | '-'));
    if offers.is_empty() || !offers.iter().all(ok) {
        return None;
    }
    // English when there is one (the title in other languages is the same name, mostly).
    let titles = between(xml, "<gameTitle", "</gameTitle>");
    let title = titles.iter().find(|t| t.contains("\"en_US\"")).or(titles.first()).and_then(|t| t.split_once('>'));
    let title = title.map(|(_, name)| unescape(name).split_whitespace().collect::<Vec<_>>().join(" "));
    Some(EaGame { offers, title: title.filter(|t| !t.is_empty()) })
}

/// XML's escapes undone: the five named ones and numbered ones (`&#8482;` for ™).
fn unescape(text: &str) -> String {
    let mut out = String::new();
    let mut rest = text;
    while let Some(at) = rest.find('&') {
        out.push_str(&rest[..at]);
        rest = &rest[at..];
        let end = rest.find(';').filter(|e| *e <= 10);
        let said = end.and_then(|e| match &rest[1..e] {
            "amp" => Some('&'),
            "lt" => Some('<'),
            "gt" => Some('>'),
            "quot" => Some('"'),
            "apos" => Some('\''),
            code => code
                .strip_prefix("#x")
                .map(|hex| u32::from_str_radix(hex, 16))
                .or_else(|| code.strip_prefix('#').map(str::parse))
                .and_then(Result::ok)
                .and_then(char::from_u32),
        });
        match (said, end) {
            (Some(c), Some(e)) => {
                out.push(c);
                rest = &rest[e + 1..];
            }
            _ => {
                out.push('&');
                rest = &rest[1..];
            }
        }
    }
    out.push_str(rest);
    out
}

/// A text file as its writer wrote it: UTF-16 with its mark (as some installers write), or UTF-8.
pub fn text_of(bytes: &[u8]) -> String {
    match bytes {
        [0xFF, 0xFE, rest @ ..] => String::from_utf16_lossy(&rest.chunks_exact(2).map(|p| u16::from_le_bytes([p[0], p[1]])).collect::<Vec<_>>()),
        [0xEF, 0xBB, 0xBF, rest @ ..] => String::from_utf8_lossy(rest).into_owned(),
        _ => String::from_utf8_lossy(bytes).into_owned(),
    }
}

/// What Monet noted for a Ubisoft game its Ubisoft Connect installed in the shared Games folder
/// (`Games\.monet\ubisoft\ID.json`): (id, folder in Games), the folder in Windows' spelling.
pub fn ubisoft_note(text: &str) -> Option<(String, String)> {
    let v: serde_json::Value = serde_json::from_str(text).ok()?;
    let id = v.get("id")?.as_str()?.to_string();
    let folder = v.get("folder")?.as_str()?.replace('/', "\\");
    let ok = !id.is_empty() && id.len() <= 12 && id.chars().all(|c| c.is_ascii_digit()) && inside(&folder);
    ok.then_some((id, folder))
}

/// The Epic Games Launcher's `.item` manifest for a game Monet put in the shared Games folder,
/// as legendary's own EGL sync writes one (its template, then the game's values): `note` is
/// what Monet left in `Games\.monet\epic\APP.json`, `location` where the game is in Windows.
/// None when the note isn't one Monet would write.
pub fn egl_item(note: &serde_json::Value, location: &str, validate: bool) -> Option<serde_json::Value> {
    let text = |key: &str| note.get(key).and_then(|x| x.as_str()).unwrap_or("").to_string();
    let (app, guid) = (text("AppName"), text("guid"));
    let valid_guid = guid.len() == 32 && guid.chars().all(|c| c.is_ascii_hexdigit() && !c.is_ascii_lowercase());
    let (exe, folder) = (text("LaunchExecutable").replace('/', "\\"), text("MandatoryAppFolderName"));
    if !games::is_valid_id(&format!("epic:{app}")) || !valid_guid || text("CatalogItemId").is_empty() || text("CatalogNamespace").is_empty()
        || !inside(&exe) || !(folder.is_empty() || inside(&folder))
    {
        return None;
    }
    let list = |key: &str| note.get(key).filter(|x| x.is_array()).cloned().unwrap_or_else(|| serde_json::json!([]));
    let mut item = serde_json::json!({
        "AppCategories": ["public", "games", "applications"], "AppName": "", "AppVersionString": "", "BaseURLs": [],
        "BuildLabel": "", "CatalogItemId": "", "CatalogNamespace": "", "ChunkDbs": [], "CompatibleApps": [],
        "DisplayName": "", "FormatVersion": 0, "FullAppName": "", "HostInstallationGuid": "", "InstallComponents": [],
        "InstallLocation": "", "InstallSessionId": "", "InstallSize": 0, "InstallTags": [], "InstallationGuid": "",
        "LaunchCommand": "", "LaunchExecutable": "", "MainGameAppName": "", "MainWindowProcessName": "",
        "MandatoryAppFolderName": "", "ManifestLocation": "", "OwnershipToken": "", "PrereqIds": [], "ProcessNames": [],
        "StagingLocation": "", "TechnicalType": "", "VaultThumbnailUrl": "", "VaultTitleText": "", "bCanRunOffline": true,
        "bIsApplication": true, "bIsExecutable": true, "bIsIncompleteInstall": false, "bIsManaged": false,
        "bNeedsValidation": false, "bRequiresAuth": true
    });
    let fields = [
        ("AppName", serde_json::json!(app)),
        ("MainGameAppName", serde_json::json!(app)),
        ("AppVersionString", serde_json::json!(text("AppVersionString"))),
        ("BaseURLs", list("BaseURLs")),
        ("BuildLabel", serde_json::json!("Live")),
        ("CatalogItemId", serde_json::json!(text("CatalogItemId"))),
        ("CatalogNamespace", serde_json::json!(text("CatalogNamespace"))),
        ("DisplayName", serde_json::json!(text("DisplayName"))),
        ("InstallLocation", serde_json::json!(location)),
        ("InstallSize", serde_json::json!(note.get("InstallSize").and_then(|x| x.as_u64()).unwrap_or(0))),
        ("InstallTags", list("InstallTags")),
        ("InstallationGuid", serde_json::json!(guid)),
        ("LaunchCommand", serde_json::json!(text("LaunchCommand"))),
        ("LaunchExecutable", serde_json::json!(exe)),
        ("MandatoryAppFolderName", serde_json::json!(folder)),
        ("ManifestLocation", serde_json::json!(format!("{location}\\.egstore"))),
        ("OwnershipToken", serde_json::json!(if note.get("OwnershipToken").and_then(|x| x.as_bool()) == Some(true) { "true" } else { "false" })),
        ("StagingLocation", serde_json::json!(format!("{location}\\.egstore\\bps"))),
        ("bCanRunOffline", serde_json::json!(note.get("bCanRunOffline").and_then(|x| x.as_bool()).unwrap_or(true))),
        // The first time Epic's launcher meets the files it checks them, as after moving a game.
        ("bNeedsValidation", serde_json::json!(validate)),
    ];
    for (key, value) in fields {
        item[key] = value;
    }
    Some(item)
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

/// Monet's lock for the BitLocker recovery key, as Monet leaves it (`<RSAKeyValue><Modulus>…
/// </Modulus><Exponent>…</Exponent></RSAKeyValue>`, base64 inside and nothing else, so it can go
/// into a PowerShell string as it is). At least 2048 bits.
pub fn rsa_lock(xml: &str) -> Option<String> {
    let xml = xml.trim();
    let rest = xml.strip_prefix("<RSAKeyValue><Modulus>")?;
    let (modulus, rest) = rest.split_once("</Modulus><Exponent>")?;
    let exponent = rest.strip_suffix("</Exponent></RSAKeyValue>")?;
    let base64 = |s: &str| !s.is_empty() && s.len() <= 1024 && s.chars().all(|c| c.is_ascii_alphanumeric() || matches!(c, '+' | '/' | '='));
    (base64(modulus) && base64(exponent) && modulus.len() >= 344).then(|| xml.to_string())
}

/// The recovery keys Windows gave, locked with Monet's lock (`[{"id", "key"}]` from the
/// hand-over's script): (the key protector's id, the locked key in base64).
pub fn handed_keys(json: &str) -> Vec<(String, String)> {
    let value: serde_json::Value = serde_json::from_str(json.trim()).unwrap_or_default();
    let items = match value {
        serde_json::Value::Array(items) => items,
        one @ serde_json::Value::Object(_) => vec![one],
        _ => Vec::new(),
    };
    items
        .iter()
        .filter_map(|item| {
            let id = item.get("id")?.as_str()?;
            let key = item.get("key")?.as_str()?;
            let guid = id.len() == 38 && id.starts_with('{') && id.ends_with('}')
                && id[1..37].chars().all(|c| c.is_ascii_hexdigit() || c == '-');
            let sealed = !key.is_empty() && key.len() <= 2048 && key.chars().all(|c| c.is_ascii_alphanumeric() || matches!(c, '+' | '/' | '='));
            (guid && sealed).then(|| (id.to_string(), key.to_string()))
        })
        .collect()
}

/// The Microsoft Store's apps from `Get-StartApps` as JSON (`[{"Name", "AppID"}]`, or one such
/// object alone): (name, app id) of each whose id is a Store app's, `Family_PublisherId!App`.
/// What Windows' Start menu lists in its own words, so nothing else is taken.
pub fn store_apps(json: &str) -> Vec<(String, String)> {
    let value: serde_json::Value = serde_json::from_str(json.trim()).unwrap_or_default();
    let items = match value {
        serde_json::Value::Array(items) => items,
        one @ serde_json::Value::Object(_) => vec![one],
        _ => Vec::new(),
    };
    items
        .iter()
        .filter_map(|item| {
            let name = item.get("Name").or_else(|| item.get("name"))?.as_str()?.trim();
            let id = item.get("AppID").or_else(|| item.get("id"))?.as_str()?.trim();
            (!name.is_empty() && name.len() <= 200 && is_store_app_id(id)).then(|| (name.to_string(), id.to_string()))
        })
        .collect()
}

/// `Family_PublisherId!App`: letters, digits, dots and dashes, a 13-character publisher id.
fn is_store_app_id(id: &str) -> bool {
    let word = |s: &str| !s.is_empty() && s.chars().all(|c| c.is_ascii_alphanumeric() || matches!(c, '.' | '-' | '_'));
    let Some((family, app)) = id.split_once('!') else { return false };
    let Some((name, publisher)) = family.rsplit_once('_') else { return false };
    id.len() <= 200
        && word(name)
        && word(app)
        && !app.contains('_')
        && publisher.len() == 13
        && publisher.chars().all(|c| c.is_ascii_lowercase() || c.is_ascii_digit())
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
    fn the_shared_games_folder_joins_steams_libraries() {
        assert!(library_listed(LIBRARIES, "d:/steamlibrary/"));
        assert!(!library_listed(LIBRARIES, "C:\\Games"));
        let added = with_library(LIBRARIES, "C:\\Games", "5869431672083316431").unwrap();
        assert!(library_listed(&added, "C:\\Games"));
        assert_eq!(steam_libraries(&added), vec!["C:\\Program Files (x86)\\Steam", "D:\\SteamLibrary", "C:\\Games"]);
        // The next number, written as Steam writes its own, inside the list.
        assert!(added.contains("\t\"2\"\n\t{\n\t\t\"path\"\t\t\"C:\\\\Games\"\n"));
        assert!(added.trim_end().ends_with("\t}\n}"));
        assert_eq!(vdf_get(&vdf_pairs(&added), "contentid"), Some("5869431672083316431"));
        // A list all on one line, and none at all.
        let one_line = with_library(r#""libraryfolders" { "0" { "path" "C:\\Steam" } }"#, "C:\\Games", "1").unwrap();
        assert_eq!(steam_libraries(&one_line), vec!["C:\\Steam", "C:\\Games"]);
        assert!(with_library("", "C:\\Games", "1").is_none());
        assert!(with_library(r#""libraryfolders" { "0" { }"#, "C:\\Games", "1").is_none());
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
    fn gog_games_start_from_their_own_info_file() {
        let info = "\u{feff}{\"gameId\": \"1207658924\", \"name\": \"Unreal Tournament 2004\", \"playTasks\": [
            {\"isPrimary\": false, \"type\": \"FileTask\", \"path\": \"manual.pdf\"},
            {\"isPrimary\": true, \"type\": \"FileTask\", \"path\": \"System/UT2004.exe\", \"workingDir\": \"System\", \"arguments\": \"-nohomedir -log\"}]}";
        let game = gog_game(info).unwrap();
        assert_eq!((game.id.as_str(), game.name.as_str()), ("1207658924", "Unreal Tournament 2004"));
        assert_eq!((game.exe.as_str(), game.working_dir.as_str()), ("System\\UT2004.exe", "System"));
        assert_eq!(game.args, vec!["-nohomedir", "-log"]);
        for bad in ["..\\..\\Windows\\evil.exe", "C:\\Windows\\evil.exe", "\\evil.exe"] {
            assert!(gog_game(&info.replace("System/UT2004.exe", &bad.replace('\\', "\\\\"))).is_none(), "{bad}");
        }
        assert!(gog_game(&info.replace("1207658924", "12 34")).is_none());
        assert!(gog_game(&info.replace("\"isPrimary\": true", "\"isPrimary\": false")).is_none());
        assert!(gog_game(&info.replace("\"type\": \"FileTask\", \"path\": \"System", "\"type\": \"URLTask\", \"path\": \"System")).is_none());
    }

    #[test]
    fn epic_items_are_written_as_legendary_writes_them() {
        let note = serde_json::json!({
            "guid": "0123456789ABCDEF0123456789ABCDEF", "folder": "Fortnite", "AppName": "Fortnite",
            "DisplayName": "Fortnite", "CatalogItemId": "4fe75bbc5a674f4f9b356b5c90567da5", "CatalogNamespace": "fn",
            "AppVersionString": "++Fortnite+Release-32.00", "BaseURLs": ["https://epicgames-download1.akamaized.net"],
            "InstallSize": 98765, "InstallTags": [], "LaunchCommand": "", "LaunchExecutable": "FortniteGame/Binaries/Win64/FortniteLauncher.exe",
            "OwnershipToken": false, "bCanRunOffline": false});
        let item = egl_item(&note, "C:\\Games\\Fortnite", true).unwrap();
        assert_eq!(item["InstallLocation"], "C:\\Games\\Fortnite");
        assert_eq!(item["ManifestLocation"], "C:\\Games\\Fortnite\\.egstore");
        assert_eq!(item["StagingLocation"], "C:\\Games\\Fortnite\\.egstore\\bps");
        assert_eq!(item["LaunchExecutable"], "FortniteGame\\Binaries\\Win64\\FortniteLauncher.exe");
        assert_eq!((item["OwnershipToken"].as_str(), item["bNeedsValidation"].as_bool()), (Some("false"), Some(true)));
        assert_eq!((item["MainGameAppName"].as_str(), item["BuildLabel"].as_str()), (Some("Fortnite"), Some("Live")));
        assert_eq!(item["bIsApplication"], true);
        // What Bridge reads back from Epic's launcher finds it, as one Epic installed.
        let app = epic_app(&item.to_string()).unwrap();
        assert_eq!((app.app_name.as_str(), app.install_location.as_str()), ("Fortnite", "C:\\Games\\Fortnite"));
        let mut bad = note.clone();
        bad["guid"] = serde_json::json!("not-a-guid");
        assert!(egl_item(&bad, "C:\\Games\\x", false).is_none());
        let mut bad = note.clone();
        bad["AppName"] = serde_json::json!("a b");
        assert!(egl_item(&bad, "C:\\Games\\x", false).is_none());
        // Only a program in the game's own folder.
        let mut bad = note.clone();
        bad["LaunchExecutable"] = serde_json::json!("../../Windows/System32/cmd.exe");
        assert!(egl_item(&bad, "C:\\Games\\x", false).is_none());
    }

    #[test]
    fn ubisoft_and_battlenet_games_from_windows_list_of_programs() {
        let blizzard = |uid: &str| format!("\"C:\\ProgramData\\Battle.net\\Agent\\Blizzard Uninstaller.exe\" --lang=enUS --uid={uid} --displayname=\"x\"");
        assert_eq!(listed_game("Overwatch", &blizzard("prometheus")).as_deref(), Some("battlenet:Pro"));
        assert_eq!(listed_game("Call of Duty", &blizzard("auks")).as_deref(), Some("battlenet:AUKS"));
        assert_eq!(listed_game("Hearthstone", &blizzard("hs_beta")).as_deref(), Some("battlenet:WTCG"));
        assert_eq!(listed_game("Warcraft II: Remastered", &blizzard("w2r")).as_deref(), Some("battlenet:W2R"));
        assert_eq!(listed_game("Overwatch Test", &blizzard("prometheus_test")), None);
        assert_eq!(listed_game("Nope", &blizzard("unknown")), None);
        assert_eq!(listed_game("Diablo IV", &blizzard("fenris")).as_deref(), Some("battlenet:Fen"));
        assert_eq!(listed_game("World of Warcraft Classic", &blizzard("wow_classic")), None);
        let rockstar = "\"C:\\Program Files\\Rockstar Games\\Launcher\\uninstall.exe\" -uninstall=gta5";
        assert_eq!(listed_game("Grand Theft Auto V", rockstar).as_deref(), Some("rockstar:gta5"));
        assert_eq!(listed_game("Odd", "C:\\Rockstar Games\\uninstall.exe -uninstall=a;b").as_deref(), None);
        assert_eq!(listed_game("Counter-Strike 2", "steam://uninstall/730"), None);
        for id in ["battlenet:Pro", "ubisoft:635", "rockstar:gta5"] {
            assert!(games::is_valid_id(id));
        }
    }

    #[test]
    fn battlenet_and_ubisoft_games_monet_installed_in_the_shared_folder() {
        let info = "Branch!STRING:0|Active!DEC:1|Build Key!HEX:16|Version!STRING:0|Product!STRING:0\n\
                    eu|0|aa|1.0|odin\n\
                    eu|1|bb|2.0|auks\n";
        assert_eq!(build_info_product(info).as_deref(), Some("auks"));
        assert_eq!(battlenet_code("auks"), Some("AUKS"));
        assert_eq!(battlenet_code("Fenris"), Some("Fen"));
        assert_eq!(build_info_product("Branch!STRING:0|Version!STRING:0\neu|1.0\n"), None);
        assert_eq!(build_info_product("Product!STRING:0\nx;rm\n"), None);
        assert_eq!(
            ubisoft_note(r#"{"id": "635", "folder": "Assassin's Creed Unity"}"#),
            Some(("635".into(), "Assassin's Creed Unity".into()))
        );
        assert_eq!(ubisoft_note(r#"{"id": "635", "folder": "Games/AC"}"#).map(|n| n.1), Some("Games\\AC".into()));
        assert_eq!(ubisoft_note(r#"{"id": "635", "folder": "../Windows"}"#), None);
        assert_eq!(ubisoft_note(r#"{"id": "6 3", "folder": "AC"}"#), None);
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
        // A program Monet sent, named as monet-quick's program_slug names it (tests/test_look.py).
        assert_eq!(slug("PaintDotNet Setup (2).exe"), "paintdotnet-setup-2-exe");
        assert_eq!(slug("Ünïcode Tool.msi"), "n-code-tool-msi");
        assert_eq!(slug("Mods\\Tool.exe"), "mods-tool-exe");
        assert!(games::is_valid_id(&format!("program:{}", slug("7z2409-x64.exe"))));
        // An app in the Start menu, by its place under Programs (monet-windows-drive's slug_of).
        assert_eq!(slug("Adobe\\Adobe Photoshop 2025"), "adobe-adobe-photoshop-2025");
        assert!(games::is_valid_id(&format!("app:{}", slug("Word"))));
        // A Store app, by its app id (monet-windows-drive's slug_of names it the same).
        assert_eq!(slug("5319275A.WhatsAppDesktop_cv1g1gvanyjgm!App"), "5319275a-whatsappdesktop-cv1g1gvanyjgm-app");
    }

    #[test]
    fn monets_lock_and_the_keys_locked_with_it() {
        let modulus = "A".repeat(512);
        let lock = format!("<RSAKeyValue><Modulus>{modulus}</Modulus><Exponent>AQAB</Exponent></RSAKeyValue>\n");
        assert_eq!(rsa_lock(&lock).as_deref(), Some(lock.trim()));
        // Nothing that could break out of a PowerShell string, and no small keys.
        assert_eq!(rsa_lock(&lock.replace("AQAB", "AQ'AB")), None);
        assert_eq!(rsa_lock(&lock.replace(&modulus, "AAAA")), None);
        assert_eq!(rsa_lock("<RSAKeyValue><Modulus>x</Modulus></RSAKeyValue>"), None);
        let json = r#"[{"id":"{0F3E2A1B-1C2D-4E5F-8A9B-0C1D2E3F4A5B}","key":"c2VhbGVk+/="},
            {"id":"not a guid","key":"c2VhbGVk"},{"id":"{0F3E2A1B-1C2D-4E5F-8A9B-0C1D2E3F4A5C}","key":"bad key!"}]"#;
        assert_eq!(handed_keys(json), vec![("{0F3E2A1B-1C2D-4E5F-8A9B-0C1D2E3F4A5B}".to_string(), "c2VhbGVk+/=".to_string())]);
        assert_eq!(handed_keys(r#"{"id":"{0F3E2A1B-1C2D-4E5F-8A9B-0C1D2E3F4A5B}","key":"QQ=="}"#).len(), 1);
        assert!(handed_keys("[]").is_empty());
    }

    #[test]
    fn store_apps_from_the_start_menu() {
        let json = r#"[{"Name":"WhatsApp","AppID":"5319275A.WhatsAppDesktop_cv1g1gvanyjgm!App"},
            {"Name":"iCloud","AppID":"AppleInc.iCloud_nzyj5cx40ttqa!iCloud"},
            {"Name":"Word","AppID":"{6D809377-6AF0-444B-8957-A3773F02200E}\\Microsoft Office\\root\\Office16\\WINWORD.EXE"},
            {"Name":"Evil","AppID":"a_b!c d"}, {"Name":"","AppID":"X.Y_cv1g1gvanyjgm!App"},
            {"Name":"Short","AppID":"X.Y_short!App"}]"#;
        assert_eq!(
            store_apps(json),
            vec![
                ("WhatsApp".to_string(), "5319275A.WhatsAppDesktop_cv1g1gvanyjgm!App".to_string()),
                ("iCloud".to_string(), "AppleInc.iCloud_nzyj5cx40ttqa!iCloud".to_string()),
            ]
        );
        // PowerShell writes one app alone as an object, not a list.
        assert_eq!(store_apps(r#"{"Name":"Spotify","AppID":"SpotifyAB.SpotifyMusic_zpdnekdrzrea0!Spotify"}"#).len(), 1);
        assert!(store_apps("not json").is_empty());
        assert!(store_apps("").is_empty());
    }

    #[test]
    fn ea_games_from_their_installer_data() {
        let xml = r#"<?xml version="1.0" encoding="utf-8"?>
<DiPManifest version="4.0">
  <contentIDs>
    <contentID>Origin.OFR.50.0005831</contentID>
    <contentID>1026480</contentID>
  </contentIDs>
  <gameTitles>
    <gameTitle locale="de_DE">EA SPORTS FC™ 26</gameTitle>
    <gameTitle locale="en_US">EA SPORTS FC™ 26 &amp; More</gameTitle>
  </gameTitles>
</DiPManifest>"#;
        let game = ea_game(xml).unwrap();
        assert_eq!(game.offers, ["Origin.OFR.50.0005831", "1026480"]);
        assert_eq!(game.title.as_deref(), Some("EA SPORTS FC™ 26 & More"));
        assert_eq!(unescape("FC&#8482; 26 &#x2122; &amp;&lt;&gt; & &bogus; &#1114112;"), "FC™ 26 ™ &<> & &bogus; &#1114112;");
        assert!(games::is_valid_id(&format!("ea:{}", game.offers[0])));
        // No ids, or ids that couldn't go on a command line: not a game Monet starts.
        assert_eq!(ea_game("<DiPManifest><gameTitles/></DiPManifest>"), None);
        assert_eq!(ea_game("<contentIDs><contentID>1&amp;x</contentID></contentIDs>"), None);
        assert_eq!(ea_game("<contentIDs><contentID>12</contentID></contentIDs>").unwrap().title, None);
        let utf16: Vec<u8> = [0xFF, 0xFE].into_iter().chain("<a>é</a>".encode_utf16().flat_map(u16::to_le_bytes)).collect();
        assert_eq!(text_of(&utf16), "<a>é</a>");
        assert_eq!(text_of(b"\xEF\xBB\xBFok"), "ok");
    }
}

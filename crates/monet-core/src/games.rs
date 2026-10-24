//! The list of installed Windows games, shared from Windows to Monet.
//!
//! Monet Bridge writes it to `\EFI\Monet\games.json` on the EFI system
//! partition. At boot, Monet copies it to `/var/lib/monet/games.json`.

use serde::{Deserialize, Serialize};

/// Location on the EFI system partition, with `/` separators.
pub const ESP_PATH: &str = "EFI/Monet/games.json";

pub const STORES: &[&str] = &["steam", "epic", "riot", "custom"];

const MAX_GAMES: usize = 2000;
const MAX_NAME: usize = 120;

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Game {
    /// `store:key`, for example `steam:1172470` or `riot:valorant`.
    pub id: String,
    pub name: String,
}

impl Game {
    pub fn store(&self) -> &str {
        self.id.split(':').next().unwrap_or("")
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Default, Serialize, Deserialize)]
pub struct GameList {
    pub v: u32,
    /// Unix time the list was written.
    pub updated: u64,
    pub games: Vec<Game>,
    /// Unix time Windows and its games were last brought up to date (an update trip).
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub games_updated: Option<u64>,
}

impl GameList {
    pub fn new(mut games: Vec<Game>, updated: u64) -> Self {
        let mut seen = std::collections::HashSet::new();
        games.retain(|g| seen.insert(g.id.clone()));
        games.sort_by_key(|g| g.name.to_lowercase());
        GameList { v: 1, updated, games, games_updated: None }
    }

    /// Parses a list written by the other system. Anything malformed is
    /// dropped rather than trusted.
    pub fn parse(data: &[u8]) -> Result<Self, String> {
        let mut list: GameList = serde_json::from_slice(data).map_err(|e| e.to_string())?;
        if list.v != 1 {
            return Err(format!("unknown games list version {}", list.v));
        }
        list.games.truncate(MAX_GAMES);
        list.games.retain(|g| is_valid_id(&g.id));
        for game in &mut list.games {
            game.name = clean_name(&game.name);
        }
        list.games.retain(|g| !g.name.is_empty());
        Ok(list)
    }

    pub fn to_json(&self) -> String {
        serde_json::to_string_pretty(self).expect("games list always serializes")
    }

    pub fn find(&self, id: &str) -> Option<&Game> {
        self.games.iter().find(|g| g.id == id)
    }
}

/// Ids travel between systems and end up in command lines, so they are kept
/// to a strict, boring alphabet: `store:key` with `[A-Za-z0-9._-]`.
pub fn is_valid_id(id: &str) -> bool {
    let Some((store, key)) = id.split_once(':') else {
        return false;
    };
    STORES.contains(&store)
        && !key.is_empty()
        && key.len() <= 64
        && !key.starts_with('.')
        && key.chars().all(|c| c.is_ascii_alphanumeric() || matches!(c, '.' | '_' | '-'))
}

/// Removes control characters and trims a display name.
pub fn clean_name(name: &str) -> String {
    let cleaned: String = name.chars().filter(|c| !c.is_control()).collect();
    let trimmed = cleaned.trim();
    match trimmed.char_indices().nth(MAX_NAME) {
        Some((cut, _)) => trimmed[..cut].trim_end().to_string(),
        None => trimmed.to_string(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn ids() {
        for ok in ["steam:730", "riot:valorant", "epic:Fortnite", "custom:my-game_2.0"] {
            assert!(is_valid_id(ok), "{ok}");
        }
        for bad in ["730", "steam:", "gog:1", "steam:7 30", "steam:a/b", "riot:..", "steam:$(x)", "custom:a'b"] {
            assert!(!is_valid_id(bad), "{bad}");
        }
    }

    #[test]
    fn parse_sanitizes() {
        let json = br#"{"v":1,"updated":5,"games":[
            {"id":"steam:730","name":"Counter-Strike 2"},
            {"id":"steam:bad id","name":"Nope"},
            {"id":"riot:valorant","name":"VALORANT\n[Desktop Entry]"},
            {"id":"custom:x","name":"   "}
        ]}"#;
        let list = GameList::parse(json).unwrap();
        assert_eq!(list.games.len(), 2);
        assert_eq!(list.games[1].name, "VALORANT[Desktop Entry]");
        assert_eq!(list.find("steam:730").unwrap().store(), "steam");
    }

    #[test]
    fn new_sorts_and_dedups() {
        let list = GameList::new(
            vec![
                Game { id: "steam:2".into(), name: "beta".into() },
                Game { id: "steam:1".into(), name: "Alpha".into() },
                Game { id: "steam:1".into(), name: "Alpha".into() },
            ],
            9,
        );
        assert_eq!(list.games.iter().map(|g| g.id.as_str()).collect::<Vec<_>>(), ["steam:1", "steam:2"]);
        assert_eq!(GameList::parse(list.to_json().as_bytes()).unwrap(), list);
    }

    #[test]
    fn long_names_are_cut_on_char_boundaries() {
        let name = "é".repeat(200);
        assert_eq!(clean_name(&name).chars().count(), MAX_NAME);
    }
}

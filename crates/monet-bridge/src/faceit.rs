//! FACEIT, for Counter-Strike 2. CS2 plays in Monet, but FACEIT's matches and its anti-cheat
//! run only in Windows. When the person asks (Games, in Monet), Monet Bridge sets FACEIT up in
//! Monet's Windows with FACEIT's own installers: downloaded over HTTPS from FACEIT, run only
//! when Windows says FACEIT signed them, and shown to the person, whose terms they are to accept.
//! Nothing here signs in, accepts terms, or turns a protection off.
//!
//! This part is what holds the Windows side to that, testable anywhere: where the installers
//! come from, whose signature counts, the order of things, and what's noted for Monet
//! (`faceit.json` in ProgramData\Monet, which Monet reads from Windows' drive). bridge.rs does
//! the downloading, checking and running. Another platform's anti-cheat (Riot's Vanguard, say)
//! would be one more `Kit`.

use std::collections::BTreeMap;
use std::path::Path;

use serde::{Deserialize, Serialize};

/// Something Monet sets up in Windows for a game's competitive platform, with its maker's own
/// installers.
pub struct Kit {
    /// Its name in files and requests ("faceit": the `faceit-setup` and `faceit` tasks).
    pub key: &'static str,
    pub name: &'static str,
    /// The game it's for, as Monet names games.
    pub game: &'static str,
    /// In the order they're installed.
    pub parts: &'static [Part],
    /// Who signs its installers: their certificate's organization (O=), any case.
    pub publishers: &'static [&'static str],
    /// Where its installers may come from, redirects included: these hosts, or under these
    /// domains. Always HTTPS.
    pub hosts: &'static [&'static str],
    pub domains: &'static [&'static str],
}

pub struct Part {
    /// Its name in files ("anticheat", "client").
    pub key: &'static str,
    pub name: &'static str,
    /// Its maker's own download, always the newest.
    pub url: &'static str,
    /// What the download is called here.
    pub file: &'static str,
    /// Where it is once it's installed: the first that's there counts.
    pub places: &'static [Place],
    /// Its Windows service, when it has one (a service's key stays when its folder moves).
    pub service: Option<&'static str>,
    /// What its shortcut in the Start menu may be called, which opens it as the Start menu does.
    pub shortcuts: &'static [&'static str],
    /// The program that runs while it's working, to wait for before the game starts.
    pub process: Option<&'static str>,
}

/// A program's place, under a folder whose name each PC knows.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Place {
    /// Under Program Files.
    ProgramFiles(&'static str),
    /// Under the person's own AppData\Local.
    LocalAppData(&'static str),
}

// FACEIT's installers and requirements, as FACEIT publishes them (looked up 2026-11-16):
// - The anti-cheat, an Inno Setup installer for everyone on the PC:
//   https://anticheat-client.faceit-cdn.net/FACEITInstaller_64.exe (winget's
//   FACEITLTD.FACEITAC, publisher FACEIT LTD; FACEIT's own page for it is
//   https://www.faceit.com/en/anti-cheat). It installs to Program Files\FACEIT AC
//   (faceitclient.exe, faceitservice.exe and the FACEIT_AC.sys driver, loaded as Windows
//   starts) with the FACEITService service, as FACEIT's support pages name them.
// - The FACEIT app itself: https://faceit-client.faceit-cdn.net/release/FACEIT-setup-latest.exe
//   (winget's FACEITLTD.FACEITClient, publisher FACEIT Ltd.), in the person's AppData\Local.
// - What it asks of Windows: https://support.faceit.com/hc/en-us/articles/23117181142556
//   (TPM 2.0 and Secure Boot for every player since 25 November 2025; IOMMU and
//   virtualization-based security in waves, and Windows 11 from 14 October 2026 by
//   https://www.faceit.com/en/news/faceit-rollout-of-tpm-secure-boot-iommu-and-vbs).
// Their signing certificate couldn't be inspected when this was written (the downloads weren't
// reachable then): winget names the publisher FACEIT LTD, so either way of writing a limited
// company counts. Get-AuthenticodeSignature on a real download says which it is.
pub static FACEIT: Kit = Kit {
    key: "faceit",
    name: "FACEIT",
    game: "steam:730",
    // The anti-cheat first: the app then finds it, and doesn't offer it again.
    parts: &[
        Part {
            key: "anticheat",
            name: "FACEIT Anti-Cheat",
            url: "https://anticheat-client.faceit-cdn.net/FACEITInstaller_64.exe",
            file: "FACEITInstaller_64.exe",
            places: &[Place::ProgramFiles("FACEIT AC\\faceitclient.exe")],
            service: Some("FACEITService"),
            shortcuts: &["FACEIT AC", "FACEIT Anti-Cheat"],
            process: Some("faceitclient.exe"),
        },
        Part {
            key: "client",
            name: "FACEIT",
            url: "https://faceit-client.faceit-cdn.net/release/FACEIT-setup-latest.exe",
            file: "FACEIT-setup-latest.exe",
            places: &[
                Place::LocalAppData("FACEIT\\FACEIT.exe"),
                Place::LocalAppData("FACEITApp\\FACEIT.exe"),
                Place::ProgramFiles("FACEIT\\FACEIT.exe"),
            ],
            service: None,
            shortcuts: &["FACEIT"],
            process: None,
        },
    ],
    publishers: &["FACEIT LTD", "FACEIT LIMITED"],
    hosts: &["anticheat-client.faceit-cdn.net", "faceit-client.faceit-cdn.net"],
    domains: &["faceit-cdn.net", "faceit.com"],
};

/// The kit a task sets up or plays with: `faceit-setup` and `faceit`.
pub fn kit_for(task: &str) -> Option<&'static Kit> {
    [&FACEIT].into_iter().find(|kit| task == kit.key || task.strip_suffix("-setup") == Some(kit.key))
}

impl Kit {
    pub fn part(&self, key: &str) -> Option<&Part> {
        self.parts.iter().find(|p| p.key == key)
    }

    /// Whether an address is the maker's own: HTTPS, on one of its download hosts or under its
    /// domains, nothing hidden in it (no account, no other port).
    pub fn official(&self, url: &str) -> bool {
        let Some(rest) = url.strip_prefix("https://") else { return false };
        let authority = rest.split(['/', '?', '#']).next().unwrap_or_default();
        let host = match authority.rsplit_once(':') {
            Some((host, "443")) => host,
            Some(_) => return false,
            None => authority,
        };
        let host = host.to_ascii_lowercase();
        if host.is_empty() || !host.chars().all(|c| c.is_ascii_alphanumeric() || matches!(c, '.' | '-')) {
            return false;
        }
        self.hosts.contains(&host.as_str()) || self.domains.iter().any(|d| host.ends_with(&format!(".{d}")))
    }

    /// Whether a certificate's subject (as Windows writes it: `CN=…, O=…, C=GB`) names the maker
    /// as its organization.
    pub fn signed_by_maker(&self, subject: &str) -> bool {
        subject_fields(subject)
            .iter()
            .filter(|(field, _)| field == "O")
            .any(|(_, name)| self.publishers.iter().any(|p| normal_name(p) == normal_name(name)))
    }
}

/// A certificate subject's fields, (FIELD, value), as Windows writes them: commas between,
/// a value with a comma in quotes ("" for a quote inside).
pub fn subject_fields(subject: &str) -> Vec<(String, String)> {
    let mut parts = Vec::new();
    let (mut current, mut quoted) = (String::new(), false);
    let mut chars = subject.chars().peekable();
    while let Some(c) = chars.next() {
        match c {
            '"' if quoted && chars.peek() == Some(&'"') => {
                chars.next();
                current.push('"');
            }
            '"' => quoted = !quoted,
            ',' | ';' if !quoted => parts.push(std::mem::take(&mut current)),
            _ => current.push(c),
        }
    }
    parts.push(current);
    parts
        .iter()
        .filter_map(|part| part.split_once('='))
        .map(|(field, value)| (field.trim().to_ascii_uppercase(), value.trim().to_string()))
        .collect()
}

/// A company's name to compare: capitals, single spaces, no full stop at the end.
fn normal_name(name: &str) -> String {
    name.split_whitespace().collect::<Vec<_>>().join(" ").trim_end_matches('.').to_uppercase()
}

/// What Windows says about a file's Authenticode signature (Get-AuthenticodeSignature).
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Signature {
    /// Windows checked it, all the way to a certificate it trusts.
    pub valid: bool,
    /// Who signed it.
    pub subject: String,
}

/// The signature check's answer (`{"status": "Valid", "subject": "CN=…"}`).
pub fn signature(json: &str) -> Option<Signature> {
    let value: serde_json::Value = serde_json::from_str(json.trim()).ok()?;
    let status = value.get("status")?.as_str()?;
    let subject = value.get("subject").and_then(|s| s.as_str()).unwrap_or_default();
    Some(Signature { valid: status == "Valid", subject: subject.chars().filter(|c| !c.is_control()).take(400).collect() })
}

/// How setting up one part went.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Step {
    /// It was there already.
    There,
    /// Installed now.
    Installed,
    /// Its installer closed and it isn't there: cancelled, terms not accepted, or it failed.
    NotFinished,
    /// It couldn't be downloaded (offline, or FACEIT's server didn't answer).
    NoDownload,
    /// What came wasn't signed by its maker (or came from somewhere else): not run.
    NotSigned,
    /// Back to Monet before it was done.
    Stopped,
    /// Not tried, as one before it didn't go.
    Skipped,
}

/// What's happening, for the cover.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Doing {
    Downloading,
    Checking,
    Installing,
}

/// What setting up needs of Windows. bridge.rs has the real one; the tests' is made up.
pub trait Pc {
    fn installed(&self, part: &Part) -> bool;
    /// Downloads `url` into `to`: the address it came from in the end (after redirects), or why not.
    fn download(&self, url: &str, to: &Path) -> Result<String, String>;
    /// What Windows says of the file's signature; None when it couldn't say.
    fn signature(&self, file: &Path) -> Option<Signature>;
    /// Runs the installer as the person, in its own window, and waits for it to close; false
    /// when it never started.
    fn run(&self, part: &Part, file: &Path) -> bool;
    /// A moment before trying again (Wi-Fi may still be connecting).
    fn pause(&self);
    /// The person chose Back to Monet.
    fn stopped(&self) -> bool;
    fn doing(&self, part: &Part, doing: Doing);
}

/// How each part went, in order: (its key, how).
pub type Steps = Vec<(&'static str, Step)>;

/// How many times a download is tried.
pub const TRIES: usize = 4;

/// Sets up what's missing of a kit, one part after another, each from its maker's download
/// once Windows says the maker signed it (in `dir`, which only administrators can change).
/// `noted` hears how each part went as it goes, so it's kept even if an installer restarts
/// the PC. Once one doesn't go, the rest wait for next time.
pub fn set_up(kit: &Kit, pc: &dyn Pc, dir: &Path, mut noted: impl FnMut(&Part, Step)) -> Steps {
    let mut steps = Vec::new();
    let mut going = true;
    for part in kit.parts {
        let step = if !going {
            Step::Skipped
        } else if pc.installed(part) {
            Step::There
        } else if pc.stopped() {
            Step::Stopped
        } else {
            install(kit, part, pc, dir)
        };
        going = matches!(step, Step::There | Step::Installed);
        noted(part, step);
        steps.push((part.key, step));
    }
    steps
}

fn install(kit: &Kit, part: &Part, pc: &dyn Pc, dir: &Path) -> Step {
    let file = dir.join(part.file);
    let _ = std::fs::remove_file(&file);
    pc.doing(part, Doing::Downloading);
    let mut came_from = None;
    for attempt in 0..TRIES {
        if attempt > 0 {
            pc.pause();
        }
        if pc.stopped() {
            return Step::Stopped;
        }
        if let Ok(from) = pc.download(part.url, &file) {
            came_from = Some(from);
            break;
        }
        let _ = std::fs::remove_file(&file);
    }
    let Some(from) = came_from else { return Step::NoDownload };
    pc.doing(part, Doing::Checking);
    let signed = kit.official(&from)
        && pc.signature(&file).is_some_and(|s| s.valid && kit.signed_by_maker(&s.subject));
    if !signed {
        let _ = std::fs::remove_file(&file);
        return Step::NotSigned;
    }
    if pc.stopped() {
        let _ = std::fs::remove_file(&file);
        return Step::Stopped;
    }
    pc.doing(part, Doing::Installing);
    let ran = pc.run(part, &file);
    let _ = std::fs::remove_file(&file);
    if ran && pc.installed(part) {
        Step::Installed
    } else {
        Step::NotFinished
    }
}

/// What Windows says of the protections FACEIT asks for (each None when it couldn't say).
#[derive(Clone, Debug, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Security {
    pub secure_boot: Option<bool>,
    /// The TPM's version when it's on ("2.0"), "" without one.
    pub tpm: String,
    /// Virtualization-based security running.
    pub vbs: Option<bool>,
    /// Memory integrity (HVCI) running.
    pub memory_integrity: Option<bool>,
}

/// The security check's answer (`{"secureBoot": true, "tpm": "2.0", "vbs": …, "memoryIntegrity": …}`).
pub fn security(json: &str) -> Option<Security> {
    let value: serde_json::Value = serde_json::from_str(json.trim()).ok()?;
    let flag = |name: &str| value.get(name).and_then(serde_json::Value::as_bool);
    let tpm = value.get("tpm").and_then(|t| t.as_str()).unwrap_or_default().trim();
    let tpm = if !tpm.is_empty() && tpm.len() <= 8 && tpm.chars().all(|c| c.is_ascii_digit() || c == '.') { tpm } else { "" };
    Some(Security { secure_boot: flag("secureBoot"), tpm: tpm.to_string(), vbs: flag("vbs"), memory_integrity: flag("memoryIntegrity") })
}

/// When it was last set up, and how each part went.
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct Setup {
    pub when: u64,
    pub steps: BTreeMap<String, Step>,
}

/// What Monet Bridge notes for Monet (`faceit.json`): which parts are installed, when it last
/// looked, how the last setting up went, and what Windows says of its protections.
#[derive(Clone, Debug, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct Record {
    pub v: u32,
    pub checked: u64,
    pub installed: BTreeMap<String, bool>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub setup: Option<Setup>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub security: Option<Security>,
}

impl Record {
    /// The record kept before, or a new one; an unreadable one starts again.
    pub fn read(data: Option<&[u8]>) -> Record {
        data.and_then(|d| serde_json::from_slice::<Record>(d).ok()).filter(|r| r.v == 1).unwrap_or(Record { v: 1, ..Record::default() })
    }

    /// Notes which parts are installed now. True when that changed.
    pub fn look(&mut self, kit: &Kit, installed: impl Fn(&Part) -> bool, now: u64) -> bool {
        let found: BTreeMap<String, bool> = kit.parts.iter().map(|p| (p.key.to_string(), installed(p))).collect();
        let changed = found != self.installed;
        self.installed = found;
        self.checked = now;
        changed
    }

    /// Notes how a part's setting up went (and whether it's installed now).
    pub fn note(&mut self, part: &Part, step: Step, now: u64) {
        let setup = self.setup.get_or_insert_with(|| Setup { when: now, steps: BTreeMap::new() });
        setup.when = now;
        setup.steps.insert(part.key.to_string(), step);
        self.installed.insert(part.key.to_string(), matches!(step, Step::There | Step::Installed));
        self.checked = now;
    }

    /// A new setup: its parts not tried yet.
    pub fn start_setup(&mut self, kit: &Kit, now: u64) {
        self.setup = Some(Setup { when: now, steps: kit.parts.iter().map(|p| (p.key.to_string(), Step::Skipped)).collect() });
    }

    pub fn ready(&self, kit: &Kit) -> bool {
        kit.parts.iter().all(|p| self.installed.get(p.key) == Some(&true))
    }

    pub fn to_json(&self) -> Vec<u8> {
        serde_json::to_vec_pretty(self).unwrap_or_default()
    }
}

/// Why setting up didn't finish, for the cover: the first part that didn't go.
pub fn first_problem(steps: &[(&str, Step)]) -> Option<Step> {
    steps.iter().map(|(_, s)| *s).find(|s| !matches!(s, Step::There | Step::Installed))
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::cell::{Cell, RefCell};
    use std::collections::HashSet;
    use std::path::PathBuf;

    const SIGNED: &str = "CN=FACEIT LTD, O=FACEIT LTD, L=London, C=GB";

    /// A made-up Windows: what's installed, what each download gives, who signed it, and what
    /// running an installer does. No network, nothing run.
    struct FakePc {
        installed: RefCell<HashSet<&'static str>>,
        /// Each download's answer in turn (the address it came from, or a failure); after
        /// these, it comes straight from the address asked for.
        downloads: RefCell<Vec<Result<String, String>>>,
        asked: RefCell<Vec<String>>,
        signature: Option<Signature>,
        /// What running each part's installer does: installs it, or it's closed first.
        installs: bool,
        ran: RefCell<Vec<(&'static str, PathBuf, Vec<u8>)>>,
        pauses: Cell<usize>,
        stop_after: Cell<Option<usize>>,
        doing: RefCell<Vec<(&'static str, Doing)>>,
    }

    impl FakePc {
        fn new() -> FakePc {
            FakePc {
                installed: RefCell::new(HashSet::new()),
                downloads: RefCell::new(Vec::new()),
                asked: RefCell::new(Vec::new()),
                signature: Some(Signature { valid: true, subject: SIGNED.into() }),
                installs: true,
                ran: RefCell::new(Vec::new()),
                pauses: Cell::new(0),
                stop_after: Cell::new(None),
                doing: RefCell::new(Vec::new()),
            }
        }
    }

    impl Pc for FakePc {
        fn installed(&self, part: &Part) -> bool {
            self.installed.borrow().contains(part.key)
        }
        fn download(&self, url: &str, to: &Path) -> Result<String, String> {
            self.asked.borrow_mut().push(url.to_string());
            let answer = if self.downloads.borrow().is_empty() { Ok(url.to_string()) } else { self.downloads.borrow_mut().remove(0) };
            if answer.is_ok() {
                std::fs::write(to, b"MZ installer").unwrap();
            }
            answer
        }
        fn signature(&self, file: &Path) -> Option<Signature> {
            assert!(file.is_file(), "checked before it's gone");
            self.signature.clone()
        }
        fn run(&self, part: &Part, file: &Path) -> bool {
            self.ran.borrow_mut().push((part.key, file.to_path_buf(), std::fs::read(file).unwrap()));
            if self.installs {
                self.installed.borrow_mut().insert(part.key);
            }
            true
        }
        fn pause(&self) {
            self.pauses.set(self.pauses.get() + 1);
        }
        fn stopped(&self) -> bool {
            match self.stop_after.get() {
                Some(0) => true,
                Some(n) => {
                    self.stop_after.set(Some(n - 1));
                    false
                }
                None => false,
            }
        }
        fn doing(&self, part: &Part, doing: Doing) {
            self.doing.borrow_mut().push((part.key, doing));
        }
    }

    struct Dir(PathBuf);
    impl Dir {
        fn new(name: &str) -> Dir {
            let dir = std::env::temp_dir().join(format!("monet-faceit-{name}-{}", std::process::id()));
            let _ = std::fs::remove_dir_all(&dir);
            std::fs::create_dir_all(&dir).unwrap();
            Dir(dir)
        }
        fn is_empty(&self) -> bool {
            std::fs::read_dir(&self.0).unwrap().next().is_none()
        }
    }
    impl Drop for Dir {
        fn drop(&mut self) {
            let _ = std::fs::remove_dir_all(&self.0);
        }
    }

    fn run(pc: &FakePc, dir: &Dir) -> (Steps, Steps) {
        let mut noted = Vec::new();
        let steps = set_up(&FACEIT, pc, &dir.0, |part, step| noted.push((part.key, step)));
        (steps, noted)
    }

    #[test]
    fn the_anticheat_then_the_app_from_faceits_own_downloads() {
        let (pc, dir) = (FakePc::new(), Dir::new("happy"));
        let (steps, noted) = run(&pc, &dir);
        assert_eq!(steps, vec![("anticheat", Step::Installed), ("client", Step::Installed)]);
        assert_eq!(noted, steps, "each noted as it went");
        assert_eq!(
            *pc.asked.borrow(),
            vec!["https://anticheat-client.faceit-cdn.net/FACEITInstaller_64.exe", "https://faceit-client.faceit-cdn.net/release/FACEIT-setup-latest.exe"]
        );
        let ran = pc.ran.borrow();
        assert_eq!(ran.iter().map(|(k, f, _)| (*k, f.file_name().unwrap().to_string_lossy().into_owned())).collect::<Vec<_>>(),
                   vec![("anticheat", "FACEITInstaller_64.exe".to_string()), ("client", "FACEIT-setup-latest.exe".to_string())]);
        assert!(ran.iter().all(|(_, f, data)| f.starts_with(&dir.0) && data == b"MZ installer"));
        assert!(dir.is_empty(), "the installers go once they've run");
        assert_eq!(pc.doing.borrow()[..3], [("anticheat", Doing::Downloading), ("anticheat", Doing::Checking), ("anticheat", Doing::Installing)]);
        assert_eq!(pc.pauses.get(), 0);
    }

    #[test]
    fn whats_there_already_isnt_downloaded_again() {
        let (pc, dir) = (FakePc::new(), Dir::new("there"));
        pc.installed.borrow_mut().insert("anticheat");
        let (steps, _) = run(&pc, &dir);
        assert_eq!(steps, vec![("anticheat", Step::There), ("client", Step::Installed)]);
        assert_eq!(pc.asked.borrow().len(), 1);
        pc.installed.borrow_mut().insert("client");
        pc.asked.borrow_mut().clear();
        assert_eq!(run(&pc, &dir).0, vec![("anticheat", Step::There), ("client", Step::There)]);
        assert!(pc.asked.borrow().is_empty());
    }

    #[test]
    fn a_download_is_tried_a_few_times_then_waits_for_next_time() {
        let (pc, dir) = (FakePc::new(), Dir::new("offline"));
        *pc.downloads.borrow_mut() = vec![Err("offline".into()); TRIES];
        let (steps, _) = run(&pc, &dir);
        assert_eq!(steps, vec![("anticheat", Step::NoDownload), ("client", Step::Skipped)]);
        assert_eq!(pc.asked.borrow().len(), TRIES);
        assert_eq!(pc.pauses.get(), TRIES - 1);
        assert!(pc.ran.borrow().is_empty());
        // Wi-Fi comes in on the third try.
        let (pc, dir) = (FakePc::new(), Dir::new("late"));
        *pc.downloads.borrow_mut() = vec![Err("offline".into()), Err("offline".into())];
        assert_eq!(run(&pc, &dir).0[0], ("anticheat", Step::Installed));
        assert_eq!(pc.pauses.get(), 2);
    }

    #[test]
    fn only_what_faceit_signed_runs() {
        // Signed by someone else, a signature Windows doesn't trust, or none it could read.
        for signature in [
            Some(Signature { valid: true, subject: "CN=Someone, O=Someone Else Ltd, C=GB".into() }),
            Some(Signature { valid: true, subject: "CN=FACEIT LTD, O=Not FACEIT LTD".into() }),
            Some(Signature { valid: false, subject: SIGNED.into() }),
            None,
        ] {
            let (mut pc, dir) = (FakePc::new(), Dir::new("unsigned"));
            pc.signature = signature;
            let (steps, _) = run(&pc, &dir);
            assert_eq!(steps, vec![("anticheat", Step::NotSigned), ("client", Step::Skipped)]);
            assert!(pc.ran.borrow().is_empty());
            assert!(dir.is_empty(), "what wasn't run is gone");
        }
    }

    #[test]
    fn a_download_that_ends_up_somewhere_else_isnt_run() {
        for from in ["https://faceit-cdn.net.example.com/FACEITInstaller_64.exe", "http://anticheat-client.faceit-cdn.net/FACEITInstaller_64.exe"] {
            let (pc, dir) = (FakePc::new(), Dir::new("elsewhere"));
            *pc.downloads.borrow_mut() = vec![Ok(from.into())];
            assert_eq!(run(&pc, &dir).0[0], ("anticheat", Step::NotSigned));
            assert!(pc.ran.borrow().is_empty());
        }
        // A redirect within FACEIT's own is fine.
        let (pc, dir) = (FakePc::new(), Dir::new("redirect"));
        *pc.downloads.borrow_mut() = vec![Ok("https://cdn2.faceit-cdn.net/FACEITInstaller_64.exe".into())];
        assert_eq!(run(&pc, &dir).0[0], ("anticheat", Step::Installed));
    }

    #[test]
    fn an_installer_closed_before_it_finished_leaves_the_rest() {
        let (mut pc, dir) = (FakePc::new(), Dir::new("closed"));
        pc.installs = false;
        let (steps, noted) = run(&pc, &dir);
        assert_eq!(steps, vec![("anticheat", Step::NotFinished), ("client", Step::Skipped)]);
        assert_eq!(noted.len(), 2);
        assert_eq!(pc.ran.borrow().len(), 1, "the app's installer isn't pushed after the anti-cheat's was closed");
    }

    #[test]
    fn back_to_monet_stops_it() {
        let (pc, dir) = (FakePc::new(), Dir::new("back"));
        pc.stop_after.set(Some(0));
        assert_eq!(run(&pc, &dir).0, vec![("anticheat", Step::Stopped), ("client", Step::Skipped)]);
        assert!(pc.asked.borrow().is_empty());
        // Downloaded and checked, then Back to Monet: not run.
        let (pc, dir) = (FakePc::new(), Dir::new("back-late"));
        pc.stop_after.set(Some(2));
        assert_eq!(run(&pc, &dir).0[0], ("anticheat", Step::Stopped));
        assert!(pc.ran.borrow().is_empty());
        assert!(dir.is_empty());
    }

    #[test]
    fn faceits_own_addresses() {
        let kit = &FACEIT;
        for ok in [
            "https://anticheat-client.faceit-cdn.net/FACEITInstaller_64.exe",
            "https://faceit-client.faceit-cdn.net/release/FACEIT-setup-latest.exe",
            "https://FACEIT-CLIENT.faceit-cdn.net:443/release/x.exe",
            "https://cdn.faceit.com/x.exe",
        ] {
            assert!(kit.official(ok), "{ok}");
        }
        for bad in [
            "http://anticheat-client.faceit-cdn.net/FACEITInstaller_64.exe",
            "https://anticheat-client.faceit-cdn.net.example.com/x.exe",
            "https://evilfaceit-cdn.net/x.exe",
            "https://faceit-cdn.net@example.com/x.exe",
            "https://user@anticheat-client.faceit-cdn.net/x.exe",
            "https://anticheat-client.faceit-cdn.net:8443/x.exe",
            "https://anticheat-client.faceit-cdn.net\\@example.com/x.exe",
            "ftp://faceit.com/x.exe",
            "https:///x.exe",
            "",
        ] {
            assert!(!kit.official(bad), "{bad}");
        }
        for part in kit.parts {
            assert!(kit.official(part.url), "{}", part.url);
            assert!(part.url.ends_with(part.file));
        }
    }

    #[test]
    fn faceit_as_the_certificates_organization() {
        let kit = &FACEIT;
        for ok in [SIGNED, "CN=FACEIT Limited, O=FACEIT Limited, C=GB", "O=\"FACEIT Ltd.\", C=GB", "C=GB, O=faceit  ltd"] {
            assert!(kit.signed_by_maker(ok), "{ok}");
        }
        for bad in ["CN=FACEIT LTD, O=Example", "CN=FACEIT LTD", "O=\"FACEIT LTD, Example\"", "O=FACEIT LTD Example", "OU=FACEIT LTD", ""] {
            assert!(!kit.signed_by_maker(bad), "{bad}");
        }
        assert_eq!(subject_fields("CN=\"A, \"\"B\"\"\", O=C"), vec![("CN".into(), "A, \"B\"".into()), ("O".into(), "C".into())]);
    }

    #[test]
    fn windows_word_on_a_signature() {
        assert_eq!(
            signature(r#"{"status":"Valid","subject":"CN=FACEIT LTD, O=FACEIT LTD"}"#),
            Some(Signature { valid: true, subject: "CN=FACEIT LTD, O=FACEIT LTD".into() })
        );
        assert_eq!(signature(r#"{"status":"HashMismatch","subject":""}"#).map(|s| s.valid), Some(false));
        assert_eq!(signature(r#"{"status":"NotSigned"}"#).map(|s| s.valid), Some(false));
        assert_eq!(signature("not json"), None);
        assert_eq!(signature(r#"{"subject":"O=FACEIT LTD"}"#), None);
    }

    #[test]
    fn windows_word_on_its_protections() {
        let found = security(r#"{"secureBoot":true,"tpm":"2.0","vbs":false,"memoryIntegrity":null}"#).unwrap();
        assert_eq!(found, Security { secure_boot: Some(true), tpm: "2.0".into(), vbs: Some(false), memory_integrity: None });
        assert_eq!(security(r#"{"tpm":"2.0; rm"}"#).unwrap().tpm, "");
        assert_eq!(security("[]").map(|s| s.secure_boot), Some(None));
        assert_eq!(security(""), None);
    }

    #[test]
    fn whats_noted_for_monet() {
        let mut record = Record::read(None);
        assert!(record.look(&FACEIT, |p| p.key == "anticheat", 100));
        assert!(!record.look(&FACEIT, |p| p.key == "anticheat", 200), "the same as before");
        assert_eq!(record.checked, 200);
        record.start_setup(&FACEIT, 300);
        record.note(&FACEIT.parts[0], Step::There, 300);
        let json = String::from_utf8(record.to_json()).unwrap();
        assert!(json.contains(r#""client": "skipped""#) && json.contains(r#""anticheat": "there""#), "{json}");
        record.note(&FACEIT.parts[1], Step::Installed, 310);
        assert!(record.ready(&FACEIT));
        record.security = security(r#"{"secureBoot":true,"tpm":"2.0"}"#);
        let again = Record::read(Some(&record.to_json()));
        assert_eq!(again, record);
        assert!(String::from_utf8(record.to_json()).unwrap().contains(r#""secureBoot": true"#));
        // Something unreadable, or from a later Monet, starts again.
        assert_eq!(Record::read(Some(b"{")), Record { v: 1, ..Record::default() });
        assert_eq!(Record::read(Some(br#"{"v":2,"checked":1,"installed":{}}"#)).checked, 0);
        assert_eq!(first_problem(&[("anticheat", Step::There), ("client", Step::NotSigned)]), Some(Step::NotSigned));
        assert_eq!(first_problem(&[("anticheat", Step::There), ("client", Step::Installed)]), None);
    }

    #[test]
    fn the_tasks_name_the_kit() {
        assert_eq!(kit_for("faceit").map(|k| k.key), Some("faceit"));
        assert_eq!(kit_for("faceit-setup").map(|k| k.game), Some("steam:730"));
        assert!(kit_for("launchers").is_none() && kit_for("setup").is_none());
        assert_eq!(FACEIT.part("client").map(|p| p.name), Some("FACEIT"));
        // The anti-cheat's service and program are what FACEIT's support pages name.
        assert_eq!(FACEIT.part("anticheat").and_then(|p| p.service), Some("FACEITService"));
    }
}

//! Help stays read-only even when it follows an updating or privileged command.
use std::fs;
use std::path::PathBuf;
use std::process::{Command, Stdio};
use std::time::{SystemTime, UNIX_EPOCH};

struct Fixture(PathBuf);

impl Drop for Fixture {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.0);
    }
}

#[test]
fn subcommand_help_returns_before_updaters_elevation_and_state_writes() {
    let stamp = SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_nanos();
    let fixture = Fixture(std::env::temp_dir().join(format!("monet-help-{}-{stamp}", std::process::id())));
    fs::create_dir(&fixture.0).unwrap();
    let state = fixture.0.join("state");
    let cases: &[&[&str]] = &[
        &["--help"],
        &["update", "--help"],
        &["update", "--check", "--beta", "--help"],
        &["rollback", "--help"],
        &["helper", "update", "--help"],
        &["helper", "switch-desktop", "--help"],
    ];
    for args in cases {
        let output = Command::new(env!("CARGO_BIN_EXE_monet"))
            .args(*args)
            // A regression cannot find any real updater or elevation executable.
            .env("PATH", "")
            .env("MONET_STATE_DIR", &state)
            .stdin(Stdio::null())
            .output().unwrap();
        assert!(output.status.success(), "{args:?}: {}", String::from_utf8_lossy(&output.stderr));
        assert!(String::from_utf8_lossy(&output.stdout).contains("monet update --check"), "{args:?}");
        assert!(output.stderr.is_empty(), "{args:?}");
        assert!(!state.exists(), "Help must not create updater state: {args:?}");
    }
}

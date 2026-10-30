//! Exercise the real CLI using only fake updater executables in a private user namespace.
#![cfg(target_os = "linux")]

use std::fs;
use std::os::unix::fs::{PermissionsExt, symlink};
use std::path::PathBuf;
use std::process::{Command, Output, Stdio};
use std::time::{SystemTime, UNIX_EPOCH};

struct Fixture(PathBuf);

impl Drop for Fixture {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.0);
    }
}

impl Fixture {
    fn script(&self, name: &str, body: &str) {
        let path = self.0.join(name);
        fs::write(&path, format!("#!/bin/sh\n{body}\n")).unwrap();
        fs::set_permissions(path, fs::Permissions::from_mode(0o700)).unwrap();
    }

    fn run(&self, check: bool, os_exit: &str, apps_exit: &str) -> Output {
        let mut cmd = Command::new("/usr/bin/unshare");
        cmd.args(["--user", "--map-root-user", "--"])
            .arg(env!("CARGO_BIN_EXE_monet"))
            .args(["helper", "update"])
            // No /usr/bin fallback: a missing fake cannot invoke the host's updater.
            .env("PATH", &self.0)
            .env("MONET_STATE_DIR", self.0.join("state"))
            .env("FIXTURE_LOG", self.0.join("commands"))
            .env("OS_EXIT", os_exit)
            .env("APPS_EXIT", apps_exit)
            .stdin(Stdio::null());
        if check {
            cmd.args(["--check", "--json"]);
        }
        cmd.output().unwrap()
    }

    fn log(&self) -> String {
        fs::read_to_string(self.0.join("commands")).unwrap_or_default()
    }
}

#[test]
fn failed_app_checks_and_updates_are_retryable_and_never_report_success() {
    let available = Command::new("/usr/bin/unshare")
        .args(["--user", "--map-root-user", "--", "/bin/true"])
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .status();
    if !available.is_ok_and(|s| s.success()) {
        eprintln!("SKIP updater CLI fixture: private user namespaces are unavailable");
        return;
    }
    let stamp = SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_nanos();
    let fixture = Fixture(std::env::temp_dir().join(format!("monet-update-{}-{stamp}", std::process::id())));
    fs::create_dir(&fixture.0).unwrap();
    fs::set_permissions(&fixture.0, fs::Permissions::from_mode(0o700)).unwrap();
    symlink("/bin/sh", fixture.0.join("sh")).unwrap();
    fixture.script("bootc", r#"
printf 'bootc %s\n' "$*" >> "$FIXTURE_LOG"
printf 'No changes in: fixture\n'
exit "$OS_EXIT"
"#);
    fixture.script("flatpak", r#"
printf 'flatpak %s\n' "$*" >> "$FIXTURE_LOG"
case "$1" in
    remote-ls) printf 'org.fixture.App\n'; exit "$APPS_EXIT" ;;
    update) exit "$APPS_EXIT" ;;
    uninstall) exit 0 ;;
    *) exit 90 ;;
esac
"#);

    let failed_check = fixture.run(true, "0", "1");
    assert!(!failed_check.status.success());
    assert!(String::from_utf8_lossy(&failed_check.stderr).contains("App updates couldn't be checked"));
    assert!(!String::from_utf8_lossy(&failed_check.stdout).contains("\"apps\""));

    let retried_check = fixture.run(true, "0", "0");
    assert!(retried_check.status.success());
    let found: serde_json::Value = serde_json::from_slice(&retried_check.stdout).unwrap();
    assert_eq!(found["apps"], 1);
    assert_eq!(found["system"], false);

    fs::write(fixture.0.join("commands"), "").unwrap();
    let failed_update = fixture.run(false, "0", "1");
    assert!(!failed_update.status.success());
    assert!(String::from_utf8_lossy(&failed_update.stderr).contains("Some apps couldn't update"));
    assert!(!String::from_utf8_lossy(&failed_update.stdout).contains("Done."));
    assert!(!fixture.log().contains("uninstall"));

    let retried_update = fixture.run(false, "0", "0");
    assert!(retried_update.status.success());
    assert!(fixture.log().contains("uninstall --unused"));

    fs::write(fixture.0.join("commands"), "").unwrap();
    let failed_system = fixture.run(false, "1", "0");
    assert!(!failed_system.status.success());
    assert!(!fixture.log().contains("flatpak"));
}

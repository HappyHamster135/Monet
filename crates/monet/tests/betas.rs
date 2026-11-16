//! Betas through the real CLI: fake rpm-ostree, skopeo, bootc and flatpak in a private user
//! namespace, so nothing reaches the host's updater or the registry.
#![cfg(target_os = "linux")]

use std::fs;
use std::os::unix::fs::{PermissionsExt, symlink};
use std::path::PathBuf;
use std::process::{Command, Output, Stdio};
use std::time::{SystemTime, UNIX_EPOCH};

const REPOSITORY: &str = "ghcr.io/happyhamster135/monet";

struct Fixture(PathBuf);

impl Drop for Fixture {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.0);
    }
}

fn digest(digit: char) -> String {
    format!("sha256:{}", digit.to_string().repeat(64))
}

impl Fixture {
    fn new() -> Option<Fixture> {
        let available = Command::new("/usr/bin/unshare")
            .args(["--user", "--map-root-user", "--", "/bin/true"])
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status();
        if !available.is_ok_and(|s| s.success()) {
            eprintln!("SKIP beta CLI fixture: private user namespaces are unavailable");
            return None;
        }
        let stamp = SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_nanos();
        let fixture = Fixture(std::env::temp_dir().join(format!("monet-beta-{}-{stamp}", std::process::id())));
        fs::create_dir_all(fixture.0.join("registry")).unwrap();
        fs::set_permissions(&fixture.0, fs::Permissions::from_mode(0o700)).unwrap();
        symlink("/bin/sh", fixture.0.join("sh")).unwrap();
        symlink("/bin/cat", fixture.0.join("cat")).unwrap();
        fixture.script("systemd-inhibit", r#"
printf 'inhibit %s\n' "$*" >> "$FIXTURE_LOG"
while [ "$1" != -- ]; do shift; done
shift
exec "$@"
"#);
        fixture.script("rpm-ostree", r#"
printf 'rpm-ostree %s\n' "$*" >> "$FIXTURE_LOG"
[ "$1" = status ] && exec cat "$FIXTURE_DIR/status.json"
exit 90
"#);
        // Answers for Monet's NVIDIA repository only, from registry/<tag>; "manifest unknown" otherwise.
        fixture.script("skopeo", r#"
printf 'skopeo %s\n' "$*" >> "$FIXTURE_LOG"
for last; do :; done
image=${last#docker://}
if [ "${image%:*}" = ghcr.io/happyhamster135/monet ] && [ -f "$FIXTURE_DIR/registry/${image##*:}" ]; then
    exec cat "$FIXTURE_DIR/registry/${image##*:}"
fi
printf 'reading manifest %s: manifest unknown\n' "$image" >&2
exit 1
"#);
        fixture.script("bootc", r#"
printf 'bootc %s\n' "$*" >> "$FIXTURE_LOG"
case "$1" in
    upgrade) printf 'No changes in: fixture\n' ;;
    switch) exit "${SWITCH_EXIT:-0}" ;;
    status) printf '{"status":{"staged":{"image":{}}}}\n' ;;
esac
"#);
        fixture.script("flatpak", r#"
printf 'flatpak %s\n' "$*" >> "$FIXTURE_LOG"
exit 0
"#);
        Some(fixture)
    }

    fn script(&self, name: &str, body: &str) {
        let path = self.0.join(name);
        fs::write(&path, format!("#!/bin/sh\n{body}\n")).unwrap();
        fs::set_permissions(path, fs::Permissions::from_mode(0o700)).unwrap();
    }

    /// The PC starts `tag` of Monet's NVIDIA image, which says it's `version`.
    fn on(&self, tag: &str, version: &str) {
        let status = serde_json::json!({"deployments": [{"booted": true, "version": version,
            "container-image-reference": format!("ostree-image-signed:docker://{REPOSITORY}:{tag}")}]});
        fs::write(self.0.join("status.json"), status.to_string()).unwrap();
    }

    fn publish(&self, tag: &str, digest: &str, version: &str, tags: &[&str]) {
        let found = serde_json::json!({"Digest": digest, "RepoTags": tags,
            "Labels": {"org.opencontainers.image.version": version, "version": version}});
        fs::write(self.0.join("registry").join(tag), found.to_string()).unwrap();
    }

    fn run(&self, args: &[&str]) -> Output {
        fs::write(self.0.join("commands"), "").unwrap();
        Command::new("/usr/bin/unshare")
            .args(["--user", "--map-root-user", "--"])
            .arg(env!("CARGO_BIN_EXE_monet"))
            .args(["helper", "update"])
            .args(args)
            // No /usr/bin fallback: a missing fake cannot invoke the host's updater.
            .env("PATH", &self.0)
            .env("MONET_STATE_DIR", self.0.join("state"))
            .env("FIXTURE_DIR", &self.0)
            .env("FIXTURE_LOG", self.0.join("commands"))
            .stdin(Stdio::null())
            .output()
            .unwrap()
    }

    fn check(&self, beta: bool) -> serde_json::Value {
        let out = self.run(if beta { &["--check", "--json", "--beta"] } else { &["--check", "--json"] });
        assert!(out.status.success(), "{}", String::from_utf8_lossy(&out.stderr));
        serde_json::from_slice(&out.stdout).unwrap()
    }

    fn log(&self) -> String {
        fs::read_to_string(self.0.join("commands")).unwrap_or_default()
    }
}

#[test]
fn a_beta_is_offered_installed_only_when_chosen_and_left_for_its_release() {
    let Some(fixture) = Fixture::new() else { return };
    let tags = ["latest", "0.9.8-6", "beta", "0.9.8-7-beta.1", "0.9.8-7-beta.2", "sha256-abc.sig"];
    fixture.publish("latest", &digest('a'), "0.9.8-6", &tags);
    // Beta 2 is still being published: it has its tag, but :beta is still beta 1.
    fixture.publish("beta", &digest('b'), "0.9.8-7", &tags);
    fixture.publish("0.9.8-7-beta.1", &digest('b'), "0.9.8-7", &tags);
    fixture.publish("0.9.8-7-beta.2", &digest('c'), "0.9.8-7", &tags);

    // On the release: the normal check is as it was, and asks the registry nothing.
    fixture.on("latest", "0.9.8-6");
    let found = fixture.check(false);
    assert_eq!(found["system"], false);
    assert!(found.get("beta").is_none());
    assert!(fixture.log().contains("bootc upgrade --check"));
    assert!(!fixture.log().contains("skopeo"));

    // With betas shown: the newest whole beta, with its notes.
    let found = fixture.check(true);
    assert_eq!(found["system"], false);
    assert_eq!(found["beta"]["tag"], "0.9.8-7-beta.1");
    assert_eq!(found["beta"]["version"], "0.9.8-7");
    assert_eq!(found["beta"]["number"], 1);
    assert_eq!(found["beta"]["notes"], "https://github.com/HappyHamster135/Monet/releases/tag/v0.9.8-7-beta.1");
    assert!(found["betaMessage"].is_null());

    // The daily update never brings it.
    let out = fixture.run(&[]);
    assert!(out.status.success(), "{}", String::from_utf8_lossy(&out.stderr));
    assert!(fixture.log().contains("bootc upgrade\n"));
    assert!(!fixture.log().contains("switch"));

    // Install beta: exactly the one shown, by its own tag, with its signature checked.
    let out = fixture.run(&["--beta", "0.9.8-7-beta.2"]);
    assert!(!out.status.success());
    assert!(String::from_utf8_lossy(&out.stderr).contains("The beta on offer has changed"));
    assert!(!fixture.log().contains("switch"));
    let out = fixture.run(&["--beta", "latest"]);
    assert!(!out.status.success());
    assert!(!fixture.log().contains("skopeo"));
    let out = fixture.run(&["--beta", "0.9.8-7-beta.1"]);
    assert!(out.status.success(), "{}", String::from_utf8_lossy(&out.stderr));
    assert!(fixture.log().contains("--what=sleep --mode=block"));
    assert!(fixture.log().contains(&format!("bootc switch --enforce-container-sigpolicy {REPOSITORY}:0.9.8-7-beta.1\n")));
    assert!(!fixture.log().contains("bootc upgrade"));
    assert!(!fixture.log().contains("flatpak"));
    assert!(String::from_utf8_lossy(&out.stdout).contains("Restart your PC to use the beta."));

    // On beta 1: no other beta comes by itself, and an older release isn't an update.
    fixture.on("0.9.8-7-beta.1", "0.9.8-7");
    let found = fixture.check(true);
    assert_eq!(found["system"], false);
    assert!(found["beta"].is_null());
    assert!(!fixture.log().contains("bootc upgrade"));
    let out = fixture.run(&[]);
    assert!(out.status.success(), "{}", String::from_utf8_lossy(&out.stderr));
    assert!(!fixture.log().contains("bootc upgrade"));
    assert!(!fixture.log().contains("bootc switch"));
    assert!(fixture.log().contains("flatpak update"));

    // Beta 2 finished: offered, but still never installed by the daily update.
    fixture.publish("beta", &digest('c'), "0.9.8-7", &tags);
    assert_eq!(fixture.check(true)["beta"]["tag"], "0.9.8-7-beta.2");
    assert!(fixture.run(&[]).status.success());
    assert!(!fixture.log().contains("bootc switch"));

    // The release of that version is out: the daily update moves the PC to it.
    fixture.publish("latest", &digest('d'), "0.9.8-7", &tags);
    let found = fixture.check(false);
    assert_eq!(found["system"], true);
    assert_eq!(found["version"], "0.9.8-7");
    let out = fixture.run(&[]);
    assert!(out.status.success(), "{}", String::from_utf8_lossy(&out.stderr));
    assert!(fixture.log().contains(&format!("bootc switch --enforce-container-sigpolicy {REPOSITORY}:latest\n")));
    assert!(!fixture.log().contains("bootc upgrade"));

    // Unless that release already didn't start here: then the next one.
    fs::create_dir_all(fixture.0.join("state")).unwrap();
    fs::write(fixture.0.join("state/went-back.json"), serde_json::json!({"digest": digest('d')}).to_string()).unwrap();
    assert_eq!(fixture.check(false)["system"], false);
    assert!(fixture.run(&[]).status.success());
    assert!(!fixture.log().contains("bootc switch"));
    fs::remove_file(fixture.0.join("state/went-back.json")).unwrap();

    // A failed switch is reported, and the apps wait.
    fixture.script("bootc", r#"
printf 'bootc %s\n' "$*" >> "$FIXTURE_LOG"
printf 'error: Signature verification failed\n' >&2
exit 1
"#);
    let out = fixture.run(&[]);
    assert!(!out.status.success());
    assert!(String::from_utf8_lossy(&out.stderr).contains("Signature verification failed"));
    assert!(!fixture.log().contains("flatpak"));
}

#[test]
fn betas_are_only_for_monets_own_images_and_a_registry_problem_hides_nothing() {
    let Some(fixture) = Fixture::new() else { return };
    let status = serde_json::json!({"deployments": [{"booted": true, "version": "0.9.8-6",
        "container-image-reference": "ostree-image-signed:docker://ghcr.io/someone/monet:0.9.8-7-beta.1"}]});
    fs::write(fixture.0.join("status.json"), status.to_string()).unwrap();
    let found = fixture.check(true);
    assert!(found["beta"].is_null());
    // Someone else's image with a beta-like tag updates as before.
    assert!(fixture.log().contains("bootc upgrade --check"));
    assert!(!fixture.log().contains("skopeo"));
    let out = fixture.run(&["--beta"]);
    assert!(!out.status.success());
    assert!(String::from_utf8_lossy(&out.stderr).contains("only for Monet's own"));

    // The registry can't be reached: the release check still answers, and says why.
    fixture.on("latest", "0.9.8-6");
    fixture.script("skopeo", "printf 'pinging container registry ghcr.io: connection refused\\n' >&2; exit 1");
    let found = fixture.check(true);
    assert_eq!(found["system"], false);
    assert!(found["beta"].is_null());
    assert!(found["betaMessage"].as_str().unwrap().contains("connection refused"));
}

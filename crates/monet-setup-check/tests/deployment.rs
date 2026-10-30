use monet_setup_check::{
    deployment::{self, Backend, Job, Payload, Phase, CHECKPOINT},
    Manifest, Partition,
};
use std::fs;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicU64, Ordering};

static NEXT: AtomicU64 = AtomicU64::new(0);
struct Fixture {
    root: PathBuf,
    setup: PathBuf,
    target: PathBuf,
    data: Vec<u8>,
    job: Job,
}
impl Drop for Fixture {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.root);
    }
}
impl Fixture {
    fn new() -> Self {
        let root = std::env::temp_dir().join(format!(
            "monet-deployment-{}-{}",
            std::process::id(),
            NEXT.fetch_add(1, Ordering::Relaxed)
        ));
        fs::create_dir(&root).unwrap();
        let setup = root.join("setup");
        let target = root.join("target");
        fs::create_dir(&setup).unwrap();
        fs::create_dir(&target).unwrap();
        let part = |n: u64, fs: &str, serial: &str| Partition {
            guid: format!("11111111-1111-1111-1111-{n:012}"),
            offset: n * 1024 * 1024,
            length: 1024 * 1024,
            filesystem: fs.into(),
            filesystem_id: serial.into(),
        };
        let mut job = Job {
            version: 1,
            id: "22222222-2222-2222-2222-222222222222".into(),
            partitions: Manifest {
                version: 1,
                disk_guid: "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee".into(),
                windows: part(1, "ntfs", "0123456789ABCDEF"),
                setup: part(2, "vfat", "1234-ABCD"),
                efi: part(3, "vfat", "ABCD-5678"),
            },
            files: vec![],
        };
        for name in [
            "sources/install.swm",
            "sources/install2.swm",
            "monet/unattend.xml",
            "monet/bridge/monet-bridge.exe",
            "monet/bridge/Install-Monet.ps1",
        ] {
            let path = setup.join(name);
            fs::create_dir_all(path.parent().unwrap()).unwrap();
            fs::write(path, name).unwrap();
            job.files.push(Payload {
                path: name.into(),
                size: name.len() as u64,
                sha256: deployment::digest(name.as_bytes()),
            });
        }
        let data = serde_json::to_vec(&job).unwrap();
        Self {
            root,
            setup,
            target,
            data,
            job,
        }
    }
    fn run(&self, host: &mut Fake) -> Result<(), String> {
        deployment::deploy(&self.data, &self.setup, &self.target, host)
    }
    fn phase(&self) -> Phase {
        serde_json::from_slice::<deployment::Checkpoint>(
            &fs::read(self.target.join(CHECKPOINT)).unwrap(),
        )
        .unwrap()
        .phase
    }
}
#[derive(Default)]
struct Fake {
    checks: usize,
    applies: usize,
    boots: usize,
    fail_check: usize,
    fail_apply: bool,
    fail_boot: bool,
}
impl Backend for Fake {
    fn recheck(&mut self) -> Result<(), String> {
        self.checks += 1;
        if self.checks == self.fail_check {
            Err("disk changed".into())
        } else {
            Ok(())
        }
    }
    fn apply(&mut self, _: &Path, target: &Path) -> Result<(), String> {
        let state: deployment::Checkpoint =
            serde_json::from_slice(&fs::read(target.join(CHECKPOINT)).unwrap()).unwrap();
        assert_eq!(state.phase, Phase::Applying); // Receipt must precede the very first image write.
        self.applies += 1;
        fs::create_dir_all(target.join("Windows/System32")).unwrap();
        fs::write(
            target.join("Windows/System32/winload.efi"),
            "fixture loader",
        )
        .unwrap();
        if self.fail_apply {
            Err("interrupted DISM".into())
        } else {
            Ok(())
        }
    }
    fn boot(&mut self, target: &Path) -> Result<(), String> {
        let state: deployment::Checkpoint =
            serde_json::from_slice(&fs::read(target.join(CHECKPOINT)).unwrap()).unwrap();
        assert_eq!(state.phase, Phase::Applied); // Enable boot only after the no-reapply checkpoint.
        self.boots += 1;
        if self.fail_boot {
            Err("EFI unavailable".into())
        } else {
            Ok(())
        }
    }
}

#[cfg(windows)]
#[test]
fn verified_payloads_cannot_be_replaced_or_deleted_while_windows_is_applying() {
    struct Locked(Fake);
    impl Backend for Locked {
        fn recheck(&mut self) -> Result<(), String> {
            self.0.recheck()
        }
        fn apply(&mut self, setup: &Path, target: &Path) -> Result<(), String> {
            let file = setup.join("sources/install.swm");
            let write = fs::OpenOptions::new().write(true).open(&file).unwrap_err();
            assert_eq!(write.raw_os_error(), Some(32)); // ERROR_SHARING_VIOLATION
            assert_eq!(fs::remove_file(&file).unwrap_err().raw_os_error(), Some(32));
            assert_eq!(
                fs::rename(&file, setup.join("sources/replaced.swm"))
                    .unwrap_err()
                    .raw_os_error(),
                Some(32)
            );
            self.0.apply(setup, target)
        }
        fn boot(&mut self, target: &Path) -> Result<(), String> {
            self.0.boot(target)
        }
    }
    let f = Fixture::new();
    deployment::deploy(&f.data, &f.setup, &f.target, &mut Locked(Fake::default())).unwrap();
    // Handles are released once the transaction returns, including for later cleanup.
    fs::write(
        f.setup.join("sources/install.swm"),
        "unlocked after completion",
    )
    .unwrap();
}

#[test]
fn fresh_install_verifies_copies_and_becomes_an_idempotent_completed_job() {
    let f = Fixture::new();
    let mut host = Fake::default();
    f.run(&mut host).unwrap();
    assert_eq!(f.phase(), Phase::Complete);
    assert_eq!(
        fs::read(f.target.join("ProgramData/Monet/Setup/monet-bridge.exe")).unwrap(),
        b"monet/bridge/monet-bridge.exe"
    );
    fs::write(
        f.target.join("Windows/System32/winload.efi"),
        "later Windows update",
    )
    .unwrap();
    fs::write(
        f.setup.join("sources/install.swm"),
        "unused after completion",
    )
    .unwrap();
    f.run(&mut host).unwrap();
    assert_eq!((host.applies, host.boots), (1, 1));
    assert_eq!(
        fs::read_to_string(f.target.join("Windows/System32/winload.efi")).unwrap(),
        "later Windows update"
    );
}

#[test]
fn interrupted_apply_resumes_the_same_image_without_formatting_or_deleting_other_files() {
    let f = Fixture::new();
    let mut host = Fake {
        fail_apply: true,
        ..Fake::default()
    };
    assert!(f.run(&mut host).is_err());
    assert_eq!(f.phase(), Phase::Applying);
    fs::write(f.target.join("keep-my-file.txt"), "preserve").unwrap();
    host.fail_apply = false;
    f.run(&mut host).unwrap();
    assert_eq!((host.applies, host.boots), (2, 1));
    assert_eq!(
        fs::read_to_string(f.target.join("keep-my-file.txt")).unwrap(),
        "preserve"
    );
}

#[test]
fn failed_boot_configuration_never_reapplies_a_successful_windows_image() {
    let f = Fixture::new();
    let mut host = Fake {
        fail_boot: true,
        ..Fake::default()
    };
    assert!(f.run(&mut host).is_err());
    assert_eq!(f.phase(), Phase::Applied);
    fs::write(
        f.target.join("Windows/System32/winload.efi"),
        "preserve applied image",
    )
    .unwrap();
    host.fail_boot = false;
    f.run(&mut host).unwrap();
    assert_eq!((host.applies, host.boots), (1, 2));
    assert_eq!(
        fs::read_to_string(f.target.join("Windows/System32/winload.efi")).unwrap(),
        "preserve applied image"
    );
}

#[test]
fn damaged_payload_or_extra_split_is_rejected_before_any_target_write() {
    for extra in [false, true] {
        let f = Fixture::new();
        let mut host = Fake::default();
        if extra {
            fs::write(f.setup.join("sources/install9.swm"), "foreign").unwrap();
        } else {
            fs::write(f.setup.join("sources/install.swm"), "wrong checksum data").unwrap();
        }
        assert!(f.run(&mut host).is_err());
        assert_eq!(host.applies, 0);
        assert_eq!(fs::read_dir(&f.target).unwrap().count(), 0);
    }
}

#[test]
fn unrecorded_data_and_different_or_damaged_checkpoints_never_install() {
    for record in [
        None,
        Some(b"damaged".to_vec()),
        Some(
            br#"{"version":1,"job_id":"foreign","manifest_sha256":"bad","phase":"applying"}"#
                .to_vec(),
        ),
    ] {
        let f = Fixture::new();
        let mut host = Fake::default();
        if let Some(data) = record {
            fs::write(f.target.join(CHECKPOINT), data).unwrap();
        } else {
            fs::write(f.target.join("personal.txt"), "keep").unwrap();
        }
        assert!(f.run(&mut host).is_err());
        assert_eq!((host.applies, host.boots), (0, 0));
    }
}

#[test]
fn identity_changes_or_failed_checkpoint_write_prevent_image_application() {
    for fail_check in [1, 2, 3] {
        let f = Fixture::new();
        let mut host = Fake {
            fail_check,
            ..Fake::default()
        };
        assert!(f.run(&mut host).is_err());
        assert_eq!(host.applies, 0);
    }
    let f = Fixture::new();
    let mut host = Fake::default();
    fs::create_dir(f.target.join(".monet-setup.next")).unwrap();
    assert!(f.run(&mut host).is_err());
    assert_eq!(host.applies, 0);
}

#[test]
fn manifest_rejects_traversal_alternate_streams_reserved_names_and_case_aliases() {
    let f = Fixture::new();
    for name in [
        "../outside",
        "monet/bridge/x:stream",
        "monet/bridge/NUL.txt",
        "monet//bridge",
        "monet/bridge/trailing.",
        "monet/bridge/CON",
        "monet\\bridge\\file",
    ] {
        let mut job = f.job.clone();
        job.files[1].path = name.into();
        assert!(job.validate().is_err(), "{name}");
    }
    let mut job = f.job.clone();
    let mut clone = job.files[0].clone();
    clone.path = clone.path.to_uppercase();
    job.files.push(clone);
    assert!(job.validate().is_err());
}

#[cfg(unix)]
#[test]
fn target_symlink_cannot_redirect_bridge_copies_outside_the_prepared_volume() {
    let f = Fixture::new();
    let mut host = Fake {
        fail_boot: true,
        ..Fake::default()
    };
    assert!(f.run(&mut host).is_err());
    fs::remove_dir_all(f.target.join("ProgramData")).unwrap();
    let outside = f.root.join("outside");
    fs::create_dir(&outside).unwrap();
    std::os::unix::fs::symlink(&outside, f.target.join("ProgramData")).unwrap();
    host.fail_boot = false;
    assert!(f.run(&mut host).unwrap_err().contains("symbolic link"));
    assert_eq!(fs::read_dir(outside).unwrap().count(), 0);
}

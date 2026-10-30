//! Interoperability fixtures use disposable regular files, never block devices.
#![cfg(target_os = "linux")]

use monet_setup_check::{fat32_id, select, Manifest, Volume, BASIC_DATA, EFI_SYSTEM};
use std::path::Path;
use std::process::Command;

#[test]
fn linux_full_job_and_checkpoint_use_the_same_hash_contract() {
    let json = python(
        r#"
import json
from tests.test_winpe_deployment import Handoff
fixture = Handoff()
fixture.setUp()
try:
    fixture.saved_fixture()
    print(json.dumps(dict(data=(fixture.setup / 'monet/deployment.json').read_text(), sha256=fixture.hash)))
finally:
    fixture.doCleanups()
"#,
    );
    let data = json["data"].as_str().unwrap().as_bytes();
    monet_setup_check::deployment::Job::parse(data).unwrap();
    assert_eq!(
        monet_setup_check::deployment::digest(data),
        json["sha256"].as_str().unwrap()
    );
}

fn python(source: &str) -> serde_json::Value {
    let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
    let output = Command::new("python3")
        .args(["-c", source])
        .current_dir(root)
        .output()
        .unwrap();
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    serde_json::from_slice(&output.stdout).expect("fixture JSON")
}

#[test]
fn linux_preparation_manifest_is_accepted_without_translating_ids_or_units() {
    let json = python(
        r#"
import json
from tests.test_windows_partitions import Recovery
fixture = Recovery()
fixture.setUp()
try:
    esp = fixture.table['partitions'][0]
    esp['type'] = fixture.p.EFI_SYSTEM
    fixture.fs[esp['node']] = dict(TYPE='vfat', VERSION='FAT32', UUID='CAFE-1234')
    fixture.p.make_partitions(fixture.disk)
    print(json.dumps(fixture.p.deployment_manifest(fixture.disk)))
finally:
    fixture.doCleanups()
"#,
    );
    let manifest: Manifest = serde_json::from_value(json).unwrap();
    manifest.validate().unwrap();
    let volumes: Vec<_> = [&manifest.windows, &manifest.setup, &manifest.efi]
        .into_iter()
        .enumerate()
        .map(|(i, p)| Volume {
            volume_path: format!("\\\\?\\Volume{{22222222-2222-2222-2222-{:012}}}\\", i + 1),
            letters: match i {
                0 => vec!['W'],
                1 => vec!['S'],
                _ => vec![],
            },
            disk_number: 3,
            partition_number: i as u32 + 1,
            disk_guid: manifest.disk_guid.clone(),
            partition_guid: p.guid.clone(),
            partition_type: if i == 2 { EFI_SYSTEM } else { BASIC_DATA }.into(),
            offset: p.offset,
            length: p.length,
            filesystem: p.filesystem.clone(),
            filesystem_id: p.filesystem_id.clone(),
            read_only: false,
        })
        .collect();
    let result = select(&manifest, 'S', &volumes).unwrap();
    assert_eq!(
        (
            result.windows,
            result.setup,
            result.efi_disk,
            result.efi_partition
        ),
        ('W', 'S', 3, 3)
    );
}

#[test]
fn native_fat32_images_agree_with_linux_probe_for_512_and_4096_byte_sectors() {
    let json = python(
        r#"
import json, shutil, subprocess, tempfile
from pathlib import Path
if not shutil.which('mkfs.fat') or not shutil.which('blkid'):
    print(json.dumps({'skip': 'mkfs.fat/blkid are unavailable'}))
else:
    samples = []
    with tempfile.TemporaryDirectory(prefix='monet-efi-id-') as tmp:
        for sector in (512, 4096):
            image = Path(tmp) / ('efi-' + str(sector) + '.img')
            length = 131072 * sector
            with image.open('xb') as output:
                output.truncate(length)
            subprocess.run(['mkfs.fat', '-F', '32', '-S', str(sector), '-i', 'A1B2C3D4', str(image)],
                           capture_output=True, check=True, timeout=30)
            found = subprocess.run(['blkid', '--probe', '--output', 'export', str(image)],
                                   capture_output=True, text=True, check=True, timeout=10)
            fs = dict(line.split('=', 1) for line in found.stdout.splitlines() if '=' in line)
            assert fs['TYPE'] == 'vfat' and fs['VERSION'] == 'FAT32'
            with image.open('rb') as stream:
                samples.append(dict(boot=list(stream.read(4096)), length=length, serial=fs['UUID']))
    print(json.dumps(samples))
"#,
    );
    if let Some(reason) = json.get("skip") {
        eprintln!("Native FAT fixture skipped: {reason}");
        return;
    }
    for sample in json.as_array().unwrap() {
        let boot: Vec<u8> = serde_json::from_value(sample["boot"].clone()).unwrap();
        let length = sample["length"].as_u64().unwrap();
        let expected = sample["serial"].as_str().unwrap().replace('-', "");
        assert_eq!(fat32_id(&boot, length).as_deref(), Some(expected.as_str()));
        assert!(fat32_id(&boot, 4096).is_none());
    }
}

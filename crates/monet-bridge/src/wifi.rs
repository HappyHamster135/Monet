//! Keep profiles whose import failed, for example before a Wi-Fi driver is installed.
use std::fs;
use std::path::Path;

pub fn import_profiles(dir: &Path, mut import: impl FnMut(&Path) -> bool) -> (usize, usize) {
    let Ok(entries) = fs::read_dir(dir) else { return (0, 0) };
    let mut added = 0;
    let mut pending = 0;
    for path in entries.flatten().map(|e| e.path()).filter(|p| {
        p.is_file() && !p.is_symlink() && p.extension().is_some_and(|x| x.eq_ignore_ascii_case("xml"))
    }) {
        if import(&path) {
            added += 1;
            let _ = fs::remove_file(path);
        } else {
            pending += 1;
        }
    }
    (added, pending)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn failed_import_survives_until_the_driver_is_ready() {
        let dir = std::env::temp_dir().join(format!("monet-wifi-import-{}", std::process::id()));
        fs::create_dir_all(&dir).unwrap();
        fs::write(dir.join("one.xml"), b"fixture one").unwrap();
        fs::write(dir.join("two.XML"), b"fixture two").unwrap();
        fs::write(dir.join("keep.txt"), b"unrelated").unwrap();
        assert_eq!(import_profiles(&dir, |p| p.file_name().unwrap() == "one.xml"), (1, 1));
        assert!(!dir.join("one.xml").exists());
        assert_eq!(fs::read(dir.join("two.XML")).unwrap(), b"fixture two");
        assert_eq!(import_profiles(&dir, |_| false), (0, 1));
        assert_eq!(import_profiles(&dir, |_| true), (1, 0));
        assert!(dir.join("keep.txt").is_file());
        assert_eq!(import_profiles(&dir, |_| panic!("no profiles left")), (0, 0));
        fs::remove_dir_all(dir).unwrap();
    }
}

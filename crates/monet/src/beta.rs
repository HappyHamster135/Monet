//! Betas: a new Monet out for testing before it's released to everyone. Each has its own
//! image tag beside the release's `:latest`, `0.9.8-7-beta.1`, and `:beta` points at the
//! newest one that's fully out (tools/beta-release.py, .github/workflows/build.yml).
//!
//! A PC gets a beta only when someone chooses Install beta (Settings → Updates, with Show
//! beta versions on, or `monet update --beta`): it switches to that beta's own tag, which
//! never moves, so the daily update never brings another beta by itself. Once the release
//! of that version (or a newer one) is out, the daily update moves the PC back to `:latest`.

use serde_json::Value;

/// Monet's own images, the only ones that have betas (signed with Monet's key:
/// image/install-update-trust.py trusts it for both repositories, whatever the tag).
pub const REPOSITORIES: [&str; 2] = ["ghcr.io/happyhamster135/monet", "ghcr.io/happyhamster135/monet-amd"];
/// A beta's release page: its notes, and its USB sticks.
pub const NOTES: &str = "https://github.com/HappyHamster135/Monet/releases/tag/v";

/// A release's place in line, as Monet Bridge's ReleaseOrder: 0.9.8 < 0.9.8-5 < 0.9.9.
pub fn release_order(version: &str) -> Option<[u64; 4]> {
    let (base, update) = match version.split_once('-') {
        Some((base, update)) => (base, Some(update)),
        None => (version, None),
    };
    let mut parts = base.split('.');
    let mut order = [0; 4];
    for slot in order.iter_mut().take(3) {
        *slot = number(parts.next()?)?;
    }
    if parts.next().is_some() {
        return None;
    }
    if let Some(update) = update {
        order[3] = number(update)?;
    }
    Some(order)
}

fn number(text: &str) -> Option<u64> {
    if text.is_empty() || text.len() > 6 || !text.bytes().all(|b| b.is_ascii_digit()) {
        return None;
    }
    text.parse().ok()
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Beta {
    pub version: String,
    pub number: u64,
}

impl Beta {
    /// From a beta's image tag, `0.9.8-7-beta.1`.
    pub fn parse(tag: &str) -> Option<Beta> {
        let (version, count) = tag.rsplit_once("-beta.")?;
        release_order(version)?;
        let number = number(count).filter(|n| *n > 0 && !count.starts_with('0'))?;
        Some(Beta { version: version.to_string(), number })
    }

    pub fn tag(&self) -> String {
        format!("{}-beta.{}", self.version, self.number)
    }

    pub fn notes(&self) -> String {
        format!("{NOTES}{}", self.tag())
    }

    fn order(&self) -> ([u64; 4], u64) {
        (release_order(&self.version).unwrap_or_default(), self.number)
    }
}

/// The Monet a PC starts: its image's repository and tag, and the version it says it is.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Image {
    pub repository: String,
    pub tag: String,
    pub version: Option<String>,
}

impl Image {
    pub fn official(&self) -> bool {
        REPOSITORIES.contains(&self.repository.as_str())
    }

    /// The beta this is, when it's one of Monet's own.
    pub fn beta(&self) -> Option<Beta> {
        Beta::parse(&self.tag).filter(|_| self.official())
    }

    /// Where this Monet stands among betas: a release counts after every beta of its version.
    fn standing(&self, own_version: &str) -> Option<([u64; 4], u64)> {
        if let Some(beta) = self.beta() {
            return Some(beta.order());
        }
        let version = self.version.as_deref().and_then(release_order).or_else(|| release_order(own_version))?;
        Some((version, u64::MAX))
    }

    /// Whether `beta` is newer than this Monet (`own_version` when the image doesn't say).
    pub fn older_than(&self, beta: &Beta, own_version: &str) -> bool {
        self.standing(own_version).is_some_and(|standing| beta.order() > standing)
    }
}

/// "ostree-image-signed:docker://ghcr.io/x/monet:latest" → ("ghcr.io/x/monet", "latest").
/// None for an image pinned by digest, or without a tag.
pub fn parse_reference(reference: &str) -> Option<(String, String)> {
    let image = reference.rsplit_once("docker://").or_else(|| reference.rsplit_once("registry:"))?.1;
    if image.contains('@') {
        return None;
    }
    let (repository, tag) = image.rsplit_once(':')?;
    if tag.is_empty() || tag.contains('/') || !repository.contains('/') {
        return None;
    }
    Some((repository.to_string(), tag.to_string()))
}

/// From `rpm-ostree status --json`: the Monet this PC starts next, the one waiting for a
/// restart if there is one, else the one running.
pub fn next_image(status: &Value) -> Option<Image> {
    let deployments = status.get("deployments")?.as_array()?;
    let flagged = |key: &str| deployments.iter().find(|d| d.get(key).and_then(Value::as_bool) == Some(true));
    let deployment = flagged("staged").or_else(|| flagged("booted"))?;
    let (repository, tag) = parse_reference(deployment.get("container-image-reference")?.as_str()?)?;
    let version = deployment.get("version").and_then(Value::as_str).map(str::to_string);
    Some(Image { repository, tag, version })
}

/// What `skopeo inspect` says of an image: its manifest's digest, its version and, when
/// asked for, its repository's tags.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Inspected {
    pub digest: String,
    pub version: Option<String>,
    pub tags: Vec<String>,
}

pub fn parse_inspect(out: &[u8]) -> Option<Inspected> {
    let data: Value = serde_json::from_slice(out).ok()?;
    let digest = data.get("Digest")?.as_str()?;
    let hex = digest.strip_prefix("sha256:")?;
    if hex.len() != 64 || !hex.bytes().all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b)) {
        return None;
    }
    let labels = data.get("Labels");
    let version = ["org.opencontainers.image.version", "version"].iter()
        .find_map(|key| labels.and_then(|l| l.get(*key)).and_then(Value::as_str))
        .map(str::to_string);
    let tags = data.get("RepoTags").and_then(Value::as_array).map(|tags| {
        tags.iter().filter_map(Value::as_str).map(str::to_string).collect()
    }).unwrap_or_default();
    Some(Inspected { digest: digest.to_string(), version, tags })
}

/// The betas among a repository's tags, newest first.
pub fn betas(tags: &[String]) -> Vec<Beta> {
    let mut found: Vec<Beta> = tags.iter().filter_map(|tag| Beta::parse(tag)).collect();
    found.sort_by_key(|beta| std::cmp::Reverse(beta.order()));
    found.dedup();
    found
}

/// Whether a PC on `beta` moves to the release `latest`: the same version or newer, and not
/// the update that already didn't start on this PC (`went_back`, monet-boot's note).
pub fn leaves_beta(beta: &Beta, latest: &Inspected, went_back: Option<&str>) -> bool {
    if went_back == Some(latest.digest.as_str()) {
        return false;
    }
    match (latest.version.as_deref().and_then(release_order), release_order(&beta.version)) {
        (Some(release), Some(ours)) => release >= ours,
        _ => false,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn image(tag: &str, version: Option<&str>) -> Image {
        Image { repository: REPOSITORIES[0].into(), tag: tag.into(), version: version.map(Into::into) }
    }

    fn inspected(version: Option<&str>, digit: char) -> Inspected {
        Inspected { digest: format!("sha256:{}", digit.to_string().repeat(64)), version: version.map(Into::into), tags: vec![] }
    }

    #[test]
    fn orders_releases_as_bridge_does() {
        assert!(release_order("0.9.8-5") > release_order("0.9.8"));
        assert!(release_order("0.9.9") > release_order("0.9.8-12"));
        assert_eq!(release_order("0.9.8"), Some([0, 9, 8, 0]));
        for bad in ["", "0.9", "0.9.8.1", "0.9.8-", "0.9.8-x", "v0.9.8", "0.9.8-7-beta.1", "1.2.3-1234567"] {
            assert_eq!(release_order(bad), None, "{bad}");
        }
    }

    #[test]
    fn reads_beta_tags_only() {
        assert_eq!(Beta::parse("0.9.8-7-beta.1"), Some(Beta { version: "0.9.8-7".into(), number: 1 }));
        assert_eq!(Beta::parse("0.9.9-beta.12").map(|b| b.tag()), Some("0.9.9-beta.12".into()));
        for bad in ["latest", "beta", "0.9.8-7", "0.9.8-7-beta.0", "0.9.8-7-beta.01", "0.9.8-7-beta.", "0.9.8-7-beta.x",
                    "v0.9.8-7-beta.1", "0.9.8-7-beta.1-beta.2", "x-beta.1"] {
            assert_eq!(Beta::parse(bad), None, "{bad}");
        }
        assert_eq!(Beta::parse("0.9.8-7-beta.3").unwrap().notes(),
                   "https://github.com/HappyHamster135/Monet/releases/tag/v0.9.8-7-beta.3");
    }

    #[test]
    fn reads_the_image_a_pc_follows() {
        for (reference, expected) in [
            ("ostree-image-signed:docker://ghcr.io/happyhamster135/monet:latest", Some(("ghcr.io/happyhamster135/monet", "latest"))),
            ("ostree-image-signed:docker://ghcr.io/happyhamster135/monet-amd:0.9.8-7-beta.1",
             Some(("ghcr.io/happyhamster135/monet-amd", "0.9.8-7-beta.1"))),
            ("ostree-unverified-registry:ghcr.io/happyhamster135/monet:latest", Some(("ghcr.io/happyhamster135/monet", "latest"))),
            ("ostree-unverified-image:registry:localhost:5000/x/monet:1", Some(("localhost:5000/x/monet", "1"))),
            ("ostree-image-signed:docker://ghcr.io/happyhamster135/monet@sha256:abc", None),
            ("ostree-image-signed:docker://localhost:5000/monet", None),
            ("oci:/var/tmp/monet", None),
        ] {
            assert_eq!(parse_reference(reference), expected.map(|(r, t)| (r.to_string(), t.to_string())), "{reference}");
        }
        let status = serde_json::json!({"deployments": [
            {"booted": true, "version": "0.9.8-6", "container-image-reference": "ostree-image-signed:docker://ghcr.io/happyhamster135/monet:latest"},
            {"staged": true, "booted": false, "version": "0.9.8-7", "container-image-reference": "ostree-image-signed:docker://ghcr.io/happyhamster135/monet:0.9.8-7-beta.2"},
        ]});
        assert_eq!(next_image(&status), Some(image("0.9.8-7-beta.2", Some("0.9.8-7"))));
        let status = serde_json::json!({"deployments": [
            {"booted": false, "container-image-reference": "ostree-image-signed:docker://ghcr.io/happyhamster135/monet:0.9.8-7-beta.1"},
            {"booted": true, "container-image-reference": "ostree-image-signed:docker://ghcr.io/happyhamster135/monet:latest"},
        ]});
        assert_eq!(next_image(&status), Some(image("latest", None)));
        assert_eq!(next_image(&serde_json::json!({"deployments": [{"booted": true}]})), None);
        assert_eq!(next_image(&serde_json::json!({})), None);
    }

    #[test]
    fn only_monets_own_images_have_betas() {
        assert!(image("0.9.8-7-beta.1", None).beta().is_some());
        let other = Image { repository: "ghcr.io/someone/monet".into(), ..image("0.9.8-7-beta.1", None) };
        assert_eq!(other.beta(), None);
        assert!(!other.official());
    }

    #[test]
    fn offers_only_a_newer_beta() {
        let beta = |tag: &str| Beta::parse(tag).unwrap();
        // On the release 0.9.8-6: a beta of 0.9.8-7 is newer, one of 0.9.8-6 isn't.
        let release = image("latest", Some("0.9.8-6"));
        assert!(release.older_than(&beta("0.9.8-7-beta.1"), "0.0.0"));
        assert!(!release.older_than(&beta("0.9.8-6-beta.4"), "0.0.0"));
        assert!(!release.older_than(&beta("0.9.8-5-beta.1"), "0.0.0"));
        // An image that doesn't say its version: the running Monet's own.
        assert!(image("latest", None).older_than(&beta("0.9.8-7-beta.1"), "0.9.8-6"));
        assert!(!image("latest", Some("44.20261012.1")).older_than(&beta("0.9.8-7-beta.1"), "0.9.8-7"));
        // On beta 2: only a later beta.
        let on_beta = image("0.9.8-7-beta.2", Some("0.9.8-7"));
        assert!(!on_beta.older_than(&beta("0.9.8-7-beta.1"), "0.9.8-7"));
        assert!(!on_beta.older_than(&beta("0.9.8-7-beta.2"), "0.9.8-7"));
        assert!(on_beta.older_than(&beta("0.9.8-7-beta.3"), "0.9.8-7"));
        assert!(on_beta.older_than(&beta("0.9.8-8-beta.1"), "0.9.8-7"));
    }

    #[test]
    fn newest_betas_come_first() {
        let tags: Vec<String> = ["latest", "beta", "0.9.8-6", "0.9.8-7-beta.2", "0.9.8-7-beta.10", "0.9.8-6-beta.3",
                                 "0.9.9-beta.1", "sha256-abc.sig", "0.9.8-7-beta.1"].iter().map(|t| t.to_string()).collect();
        let order: Vec<String> = betas(&tags).iter().map(Beta::tag).collect();
        assert_eq!(order, ["0.9.9-beta.1", "0.9.8-7-beta.10", "0.9.8-7-beta.2", "0.9.8-7-beta.1", "0.9.8-6-beta.3"]);
    }

    #[test]
    fn a_beta_moves_to_its_release_or_a_newer_one() {
        let beta = Beta::parse("0.9.8-7-beta.2").unwrap();
        assert!(!leaves_beta(&beta, &inspected(Some("0.9.8-6"), 'a'), None));
        assert!(leaves_beta(&beta, &inspected(Some("0.9.8-7"), 'a'), None));
        assert!(leaves_beta(&beta, &inspected(Some("0.9.9"), 'a'), None));
        // A release that says no version (or something else) isn't taken for a newer one.
        assert!(!leaves_beta(&beta, &inspected(None, 'a'), None));
        assert!(!leaves_beta(&beta, &inspected(Some("44.20261012.1"), 'a'), None));
        // Not the release that already didn't start on this PC: the next one.
        let failed = format!("sha256:{}", "a".repeat(64));
        assert!(!leaves_beta(&beta, &inspected(Some("0.9.8-7"), 'a'), Some(&failed)));
        assert!(leaves_beta(&beta, &inspected(Some("0.9.8-7"), 'b'), Some(&failed)));
    }

    #[test]
    fn reads_what_the_registry_says() {
        let digest = format!("sha256:{}", "c".repeat(64));
        let out = serde_json::json!({"Digest": digest, "RepoTags": ["latest", "0.9.8-7-beta.1"],
                                     "Labels": {"org.opencontainers.image.version": "0.9.8-7", "version": "0.9.8-7"}});
        assert_eq!(parse_inspect(out.to_string().as_bytes()), Some(Inspected {
            digest: digest.clone(), version: Some("0.9.8-7".into()), tags: vec!["latest".into(), "0.9.8-7-beta.1".into()] }));
        let bare = serde_json::json!({"Digest": digest, "Labels": null});
        assert_eq!(parse_inspect(bare.to_string().as_bytes()), Some(Inspected { digest, version: None, tags: vec![] }));
        assert_eq!(parse_inspect(br#"{"Digest": "sha256:short"}"#), None);
        assert_eq!(parse_inspect(b"not json"), None);
    }
}

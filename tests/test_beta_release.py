"""Betas: numbered once, published under their own tags only, and released as they were tested.

Everything here runs against fakes: no registry, GitHub or remote git is reached.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import runpy
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("beta_release", ROOT / "tools/beta-release.py")
betas = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(betas)
NVIDIA, AMD = "ghcr.io/happyhamster135/monet", "ghcr.io/happyhamster135/monet-amd"
HEAD = "a" * 40


def listing(tags):
    return "".join(f"{sha}\trefs/tags/{tag}\n" for tag, sha in tags.items())


class FakeGit:
    """`git ls-remote --tags origin` and `git push origin SHA:refs/tags/TAG` on a dict of tags."""

    def __init__(self, tags, race=()):
        self.tags = dict(tags)
        self.race = list(race)  # tags another beta pushes just before this one
        self.pushed = []

    def __call__(self, *args, check=True):
        if args[:2] == ("ls-remote", "--tags"):
            return subprocess.CompletedProcess(args, 0, listing(self.tags), "")
        if args[0] == "push":
            sha, ref = args[2].split(":", 1)
            tag = ref.removeprefix("refs/tags/")
            if self.race:
                self.tags[self.race.pop(0)] = "f" * 40
            if tag in self.tags:
                return subprocess.CompletedProcess(args, 1, "", f" ! [rejected] {tag} -> {tag} (already exists)\n")
            self.tags[tag] = sha
            self.pushed.append(tag)
            return subprocess.CompletedProcess(args, 0, "", "")
        raise AssertionError(args)


class FakeRegistry:
    """Tags to manifest digests; copies keep the digest, as `skopeo copy --preserve-digests`."""

    def __init__(self, tags, refuse=()):
        self.tags = dict(tags)
        self.refuse = set(refuse)  # sources whose signature doesn't verify
        self.copies = []

    def digest(self, image):
        return self.tags.get(image)

    def copy(self, source, target):
        if source in self.refuse:
            raise subprocess.CalledProcessError(1, ["skopeo", "copy", source, target])
        repository, digest = source.split("@")
        assert target.startswith(repository + ":")
        self.copies.append(target)
        self.tags[target] = digest


def digest(digit):
    return "sha256:" + digit * 64


class Versions(unittest.TestCase):
    def test_versions_and_beta_tags(self):
        self.assertLess(betas.release_order("0.9.8"), betas.release_order("0.9.8-5"))
        self.assertLess(betas.release_order("0.9.8-12"), betas.release_order("0.9.9"))
        for bad in ("", "0.9", "v0.9.8", "0.9.8-x", "0.9.8-7-beta.1"):
            self.assertIsNone(betas.release_order(bad))
        self.assertEqual(betas.beta("v0.9.8-7-beta.1"), ("0.9.8-7", 1))
        self.assertEqual(betas.beta("0.9.9-beta.12"), ("0.9.9", 12))
        for bad in ("v0.9.8-7", "v0.9.8-7-beta.0", "v0.9.8-7-beta.01", "0.9.8-7-beta", "preview-v0.9.8-7",
                    "v0.9.8-7-beta.1x", "latest", "beta"):
            self.assertIsNone(betas.beta(bad), bad)
        # Sorted as numbers: beta 10 after beta 9.
        tags = ["v0.9.8-7-beta.9", "v0.9.8-7-beta.10", "v0.9.8-6-beta.11", "v0.9.9-beta.1"]
        self.assertEqual(sorted(tags, key=betas.beta_order),
                         ["v0.9.8-6-beta.11", "v0.9.8-7-beta.9", "v0.9.8-7-beta.10", "v0.9.9-beta.1"])

    def test_annotated_tags_count_as_their_commits(self):
        found = betas.remote_tags(f"{'1' * 40}\trefs/tags/v0.9.8-7-beta.1\n{'2' * 40}\trefs/tags/v0.9.8-7-beta.1^{{}}\n"
                                  f"{'3' * 40}\trefs/heads/main\n")
        self.assertEqual(found, {"v0.9.8-7-beta.1": "2" * 40})

    def test_released_version_tags_are_matched_exactly(self):
        """The release checks ask git for refs/tags/vVERSION: a beta's tag is never mistaken for it."""
        with tempfile.TemporaryDirectory() as folder:
            remote = Path(folder) / "remote.git"
            env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1",
                       GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.invalid",
                       GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.invalid")
            def run(*args):
                return subprocess.run(["git", *args], cwd=folder, env=env, capture_output=True, text=True, input="")
            self.assertEqual(run("init", "-q", "--bare", str(remote)).returncode, 0)
            tree = run("-C", str(remote), "mktree").stdout.strip()
            commit = run("-C", str(remote), "commit-tree", "-m", "x", tree).stdout.strip()
            self.assertRegex(commit, "^[0-9a-f]{40}$")
            for tag in ("v0.9.8-7-beta.1", "v0.9.8-6"):
                self.assertEqual(run("-C", str(remote), "tag", tag, commit).returncode, 0)
            for version, code in (("0.9.8-7", 2), ("0.9.8-6", 0), ("0.9.8", 2)):
                with self.subTest(version=version):
                    result = run("ls-remote", "--exit-code", "--tags", str(remote), f"refs/tags/v{version}")
                    self.assertEqual(result.returncode, code, result.stdout)


class Reserve(unittest.TestCase):
    def test_numbers_start_at_one_and_follow_this_versions_betas(self):
        git = FakeGit({"v0.9.8-6": "0" * 40})
        self.assertEqual(betas.reserve("0.9.8-7", HEAD, git), 1)
        self.assertEqual(git.pushed, ["v0.9.8-7-beta.1"])
        # Pushed again (or one that stopped halfway): the next number, never the same one.
        self.assertEqual(betas.reserve("0.9.8-7", HEAD, git), 2)
        git.tags["v0.9.8-6-beta.9"] = "0" * 40
        git.tags["v0.9.8-7-beta.10"] = "0" * 40
        self.assertEqual(betas.reserve("0.9.8-7", HEAD, git), 11)

    def test_two_betas_at_once_get_different_numbers(self):
        git = FakeGit({}, race=["v0.9.8-7-beta.1"])
        self.assertEqual(betas.reserve("0.9.8-7", HEAD, git), 2)
        self.assertEqual(git.tags["v0.9.8-7-beta.2"], HEAD)
        self.assertEqual(git.tags["v0.9.8-7-beta.1"], "f" * 40)

    def test_a_released_version_gets_no_beta(self):
        for released in ("v0.9.8-7", "v0.9.8-8", "v0.9.9"):
            with self.subTest(released=released):
                git = FakeGit({released: "0" * 40})
                with self.assertRaisesRegex(SystemExit, "already released"):
                    betas.reserve("0.9.8-7", HEAD, git)
                self.assertEqual(git.pushed, [])

    def test_other_push_failures_and_bad_input_stop(self):
        def failing(*args, check=True):
            if args[0] == "ls-remote":
                return subprocess.CompletedProcess(args, 0, "", "")
            return subprocess.CompletedProcess(args, 128, "", "fatal: Authentication failed")
        with self.assertRaisesRegex(RuntimeError, "Authentication failed"):
            betas.reserve("0.9.8-7", HEAD, failing)
        for version, commit in (("main", HEAD), ("0.9.8-7", "HEAD")):
            with self.assertRaises(ValueError):
                betas.reserve(version, commit, FakeGit({}))


class Promotion(unittest.TestCase):
    """Promote vs rebuild: only a published beta of this same source is released as it is."""

    def decide(self, tags, released, trees=None, head=HEAD, version="0.9.8-7"):
        asked = []
        def published():
            asked.append(True)
            return set(released)
        found = betas.promotion(version, head, "tree-head", tags, published,
                                lambda tag: (trees or {}).get(tag, "other-tree"))
        return found, bool(asked)

    def test_no_beta_builds_as_always_without_asking_github(self):
        self.assertEqual(self.decide({"v0.9.8-6": "0" * 40}, []), (None, False))
        # Another version's betas don't count.
        self.assertEqual(self.decide({"v0.9.8-6-beta.1": HEAD}, ["v0.9.8-6-beta.1"]), (None, False))

    def test_the_same_commit_is_promoted(self):
        self.assertEqual(self.decide({"v0.9.8-7-beta.1": HEAD}, ["v0.9.8-7-beta.1"]), ("0.9.8-7-beta.1", True))

    def test_the_same_files_from_another_commit_are_promoted(self):
        tags = {"v0.9.8-7-beta.1": "b" * 40}
        self.assertEqual(self.decide(tags, ["v0.9.8-7-beta.1"], {"v0.9.8-7-beta.1": "tree-head"})[0], "0.9.8-7-beta.1")

    def test_other_source_builds(self):
        self.assertEqual(self.decide({"v0.9.8-7-beta.1": "b" * 40}, ["v0.9.8-7-beta.1"])[0], None)

    def test_a_beta_that_never_finished_is_not_released(self):
        self.assertEqual(self.decide({"v0.9.8-7-beta.1": HEAD}, [])[0], None)
        self.assertEqual(self.decide({"v0.9.8-7-beta.1": HEAD}, ["v0.9.8-7"])[0], None)

    def test_the_newest_published_beta_of_this_source_is_chosen(self):
        tags = {"v0.9.8-7-beta.1": HEAD, "v0.9.8-7-beta.2": HEAD, "v0.9.8-7-beta.3": "b" * 40, "v0.9.8-7-beta.4": HEAD}
        # beta 4 never finished, beta 3 is other source: beta 2.
        self.assertEqual(self.decide(tags, ["v0.9.8-7-beta.1", "v0.9.8-7-beta.2", "v0.9.8-7-beta.3"])[0],
                         "0.9.8-7-beta.2")


class Promote(unittest.TestCase):
    def setUp(self):
        self.registry = FakeRegistry({f"{NVIDIA}:0.9.8-7-beta.2": digest("b"), f"{NVIDIA}:latest": digest("6"),
                                      f"{NVIDIA}:0.9.8-6": digest("6")})

    def test_the_tested_digest_becomes_the_version_then_latest(self):
        found = betas.promote(NVIDIA, "0.9.8-7", "0.9.8-7-beta.2", self.registry, lambda version: False)
        self.assertEqual(found, digest("b"))
        self.assertEqual(self.registry.copies, [f"{NVIDIA}:0.9.8-7", f"{NVIDIA}:latest"])
        self.assertEqual(self.registry.tags[f"{NVIDIA}:0.9.8-7"], digest("b"))
        self.assertEqual(self.registry.tags[f"{NVIDIA}:latest"], digest("b"))
        self.assertEqual(self.registry.tags[f"{NVIDIA}:0.9.8-7-beta.2"], digest("b"))

    def test_an_existing_version_is_never_replaced(self):
        self.registry.tags[f"{NVIDIA}:0.9.8-7"] = digest("c")
        with self.assertRaisesRegex(RuntimeError, "Refusing to replace an existing version"):
            betas.promote(NVIDIA, "0.9.8-7", "0.9.8-7-beta.2", self.registry, lambda version: False)
        self.assertEqual(self.registry.copies, [])
        self.assertEqual(self.registry.tags[f"{NVIDIA}:latest"], digest("6"))

    def test_a_rerun_after_the_version_tag_only_moves_latest(self):
        self.registry.tags[f"{NVIDIA}:0.9.8-7"] = digest("b")
        betas.promote(NVIDIA, "0.9.8-7", "0.9.8-7-beta.2", self.registry, lambda version: False)
        self.assertEqual(self.registry.copies, [f"{NVIDIA}:latest"])

    def test_a_released_version_keeps_its_image(self):
        self.assertIsNone(betas.promote(NVIDIA, "0.9.8-7", "0.9.8-7-beta.2", self.registry, lambda version: True))
        self.assertEqual(self.registry.copies, [])

    def test_a_signature_that_doesnt_verify_moves_nothing(self):
        self.registry.refuse.add(f"{NVIDIA}@{digest('b')}")
        with self.assertRaises(subprocess.CalledProcessError):
            betas.promote(NVIDIA, "0.9.8-7", "0.9.8-7-beta.2", self.registry, lambda version: False)
        self.assertEqual(self.registry.tags[f"{NVIDIA}:latest"], digest("6"))
        self.assertNotIn(f"{NVIDIA}:0.9.8-7", self.registry.tags)

    def test_a_missing_beta_or_another_versions_beta_is_refused(self):
        with self.assertRaisesRegex(RuntimeError, "isn't published"):
            betas.promote(NVIDIA, "0.9.8-7", "0.9.8-7-beta.3", self.registry, lambda version: False)
        for tag in ("0.9.8-6-beta.2", "v0.9.8-7-beta.2", "latest"):
            with self.assertRaises(ValueError):
                betas.promote(NVIDIA, "0.9.8-7", tag, self.registry, lambda version: False)
        self.assertEqual(self.registry.copies, [])


class Publish(unittest.TestCase):
    def test_a_newer_beta_or_the_release_keeps_this_one_unpublished(self):
        self.assertEqual(betas.newest("0.9.8-7", 2, {"v0.9.8-6", "v0.9.8-7-beta.1"}), (True, None))
        for releases in ({"v0.9.8-7-beta.3"}, {"v0.9.8-8-beta.1"}, {"v0.9.8-7"}, {"v0.9.9"}):
            with self.subTest(releases=releases):
                self.assertFalse(betas.newest("0.9.8-7", 2, releases)[0])

    def test_beta_moves_only_after_both_images_and_older_pages_go(self):
        registry = FakeRegistry({f"{NVIDIA}:0.9.8-7-beta.2": digest("b"), f"{AMD}:0.9.8-7-beta.2": digest("c"),
                                 f"{NVIDIA}:beta": digest("1"), f"{NVIDIA}:latest": digest("6")})
        deleted = []
        releases = {"v0.9.8-6", "v0.9.8-7-beta.1", "v0.9.8-6-beta.4", "v0.9.8-7-beta.2"}
        betas.publish("0.9.8-7", 2, [NVIDIA, AMD], registry, releases, deleted.append)
        self.assertEqual(registry.copies, [f"{NVIDIA}:beta", f"{AMD}:beta"])
        self.assertEqual(registry.tags[f"{NVIDIA}:beta"], digest("b"))
        self.assertEqual(registry.tags[f"{AMD}:beta"], digest("c"))
        self.assertEqual(registry.tags[f"{NVIDIA}:latest"], digest("6"))
        self.assertEqual(deleted, ["v0.9.8-7-beta.1", "v0.9.8-6-beta.4"])

    def test_a_missing_image_moves_nothing_and_deletes_nothing(self):
        registry = FakeRegistry({f"{NVIDIA}:0.9.8-7-beta.2": digest("b")})
        deleted = []
        with self.assertRaisesRegex(RuntimeError, "isn't published"):
            betas.publish("0.9.8-7", 2, [AMD, NVIDIA], registry, {"v0.9.8-7-beta.1"}, deleted.append)
        self.assertEqual((registry.copies, deleted), ([], []))

    def test_the_notes_say_its_a_beta_then_carry_this_versions_notes(self):
        notes = betas.notes("0.9.8-7", 1, "# Monet\n\nOpening.\n\n### New in 0.9.8-7: Things\n\n- **A.** B.\n\n### New in 0.9.8-6: Old\n\n- old\n")
        self.assertTrue(notes.startswith("**Monet 0.9.8-7 beta 1: not fully tested yet.**"))
        self.assertIn("Install beta", notes)
        self.assertIn("### New in 0.9.8-7: Things", notes)
        self.assertNotIn("New in 0.9.8-6", notes)


class Registry(unittest.TestCase):
    """The real skopeo commands, from a fake run(): signatures checked with Monet's key."""

    def test_digest_and_signature_checked_copy(self):
        calls = []
        def run(command, **kwargs):
            calls.append(command)
            if command[1] == "inspect":
                image = command[-1]
                if image.endswith(":missing"):
                    return subprocess.CompletedProcess(command, 1, b"", b"reading manifest: manifest unknown")
                if image.endswith(":broken"):
                    return subprocess.CompletedProcess(command, 1, b"", b"connection refused")
                return subprocess.CompletedProcess(command, 0, b'{"schemaVersion":2}', b"")
            return subprocess.CompletedProcess(command, 0, b"", b"")
        with tempfile.TemporaryDirectory() as folder:
            registry = betas.Registry(folder, run)
            self.assertEqual(registry.repositories, (NVIDIA, AMD))
            self.assertEqual(registry.digest(f"{NVIDIA}:x"), "sha256:" + hashlib.sha256(b'{"schemaVersion":2}').hexdigest())
            self.assertIsNone(registry.digest(f"{NVIDIA}:missing"))
            with self.assertRaisesRegex(RuntimeError, "connection refused"):
                registry.digest(f"{NVIDIA}:broken")
            registry.copy(f"{AMD}@{digest('b')}", f"{AMD}:latest")
            policy = json.loads((Path(folder) / "policy.json").read_text())
            self.assertEqual(policy["default"], [{"type": "reject"}])
            self.assertEqual(policy["transports"]["docker"][AMD], [{"type": "sigstoreSigned",
                "keyPath": str(ROOT / "image/monet-update.pub"), "signedIdentity": {"type": "matchRepository"}}])
            self.assertIn("use-sigstore-attachments: true", (Path(folder) / "registries.d/monet.yaml").read_text())
        copy = calls[-1]
        self.assertEqual(copy[copy.index("copy"):], ["copy", "--preserve-digests", "--remove-signatures",
                                                     f"docker://{AMD}@{digest('b')}", f"docker://{AMD}:latest"])
        self.assertIn("--policy", copy)


class PullPolicy(unittest.TestCase):
    def test_installed_pcs_trust_every_tag_of_monets_two_repositories(self):
        """The policy is per repository, with any tag: a beta's own tag, :beta, and :latest after
        a promotion are all checked against the same key."""
        install = runpy.run_path(str(ROOT / "image/install-update-trust.py"))
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "etc/containers").mkdir(parents=True)
            (root / "etc/containers/policy.json").write_text('{"default": [{"type": "insecureAcceptAnything"}]}')
            key = root / "key.pub"
            key.write_text("key")
            install["install"](root, key)
            docker = json.loads((root / "etc/containers/policy.json").read_text())["transports"]["docker"]
        self.assertEqual(set(docker), {NVIDIA, AMD})
        for scope in docker:
            self.assertNotIn(":", scope.split("/")[-1])   # no tag: every tag of the repository
            self.assertEqual(docker[scope][0]["signedIdentity"], {"type": "matchRepository"})


def workflow(name):
    """{job: {"if", "needs", "with", "steps": [{"name", "if", "run", ...}]}} from a workflow's own
    layout (two spaces a level), without a YAML library."""
    text = (ROOT / ".github/workflows" / name).read_text()
    jobs = {}
    body = text.split("\njobs:\n", 1)[1]
    parts = re.split(r"(?m)^  ([a-z][\w-]*):\n", body)
    for job, block in zip(parts[1::2], parts[2::2]):
        head, _, steps = block.partition("\n    steps:\n")
        found = {key: value for key, value in re.findall(r"(?m)^    (if|needs): (.*)$", head)}
        given = re.search(r"\n    with:\n((?:      .*\n)+)", head + "\n")
        found["with"] = dict(re.findall(r"(?m)^      ([a-z]+): (.*)$", given[1] if given else ""))
        found["steps"] = []
        for chunk in re.split(r"(?m)^      - ", steps)[1:]:
            lines = ("        " + chunk).splitlines()
            step, index = {}, 0
            while index < len(lines):
                match = re.match(r"^        (name|if|id|uses|run): ?(.*)$", lines[index])
                index += 1
                if not match:
                    continue
                key, value = match.groups()
                if key == "run" and value == "|":
                    run = []
                    while index < len(lines) and (lines[index].startswith("          ") or not lines[index].strip()):
                        run.append(lines[index][10:])
                        index += 1
                    value = "\n".join(run)
                step[key] = value
            found["steps"].append(step)
        jobs[job] = found
    return text, jobs


class Workflows(unittest.TestCase):
    """What only a real run proves is kept for it; this checks the wiring that decides it."""

    def setUp(self):
        self.build_text, self.build = workflow("build.yml")
        self.image_text, self.image = workflow("image.yml")

    def test_betas_come_only_from_the_beta_branch_after_the_checks(self):
        jobs = self.build
        self.assertEqual(jobs["beta"]["if"], "github.event_name != 'pull_request' && github.ref == 'refs/heads/beta'")
        self.assertEqual(jobs["beta"]["needs"], "[test, desktop]")
        self.assertEqual(jobs["beta-os"]["with"], {"beta": "${{ needs.beta.outputs.tag }}"})
        self.assertEqual(jobs["beta-release"]["needs"], "[beta, linux, windows, beta-os]")
        # The release path is the default branch's, as before; it only learns which beta to promote.
        self.assertEqual(jobs["check"]["if"],
                         "github.event_name != 'pull_request' && github.ref_name == github.event.repository.default_branch")
        self.assertEqual(jobs["os"]["with"], {"promote": "${{ needs.check.outputs.promote }}"})
        self.assertEqual(jobs["os"]["if"], "needs.check.outputs.new == 'true'")
        self.assertEqual(jobs["release"]["if"], "needs.check.outputs.new == 'true'")
        self.assertEqual([step.get("if") for step in jobs["check"]["steps"]],
                         [None, None, "steps.version.outputs.new == 'true'"])
        release = "\n".join(step.get("run", "") for step in jobs["release"]["steps"])
        self.assertIn('gh release create "v$VERSION" dist/*', release)
        self.assertIn('if gh release view "v$VERSION" >/dev/null 2>&1; then', release)
        beta_release = "\n".join(step.get("run", "") for step in jobs["beta-release"]["steps"])
        self.assertIn('gh release create "$RELEASE"', beta_release)
        self.assertIn('--title "Monet $VERSION beta $NUMBER"', beta_release)
        self.assertIn("--prerelease", beta_release)
        self.assertLess(beta_release.index("gh release create"), beta_release.index("beta-release.py publish"))
        self.assertNotIn("latest", beta_release)

    def test_a_beta_never_pushes_latest_or_the_version(self):
        self.assertIn("\n  schedule:\n", self.image_text)   # the weekly rebuild: no inputs, the release path
        for name in ("image", "image-amd"):
            steps = {step.get("name"): step for step in self.image[name]["steps"]}
            self.assertEqual(steps["Push"]["if"], "inputs.beta == '' && inputs.promote == ''")
            self.assertIn('bash tools/push-image.sh "$IMAGE" "$(cat VERSION)" "$GITHUB_OUTPUT"\n', steps["Push"]["run"] + "\n")
            self.assertEqual(steps["Push the beta (its own tag only)"]["if"], "inputs.beta != ''")
            self.assertIn('bash tools/push-image.sh "$IMAGE" "$(cat VERSION)" "$GITHUB_OUTPUT" "$BETA"',
                          steps["Push the beta (its own tag only)"]["run"])
            self.assertEqual(steps["Promote the tested beta"]["if"], "inputs.promote != ''")
            self.assertEqual(steps["Build"]["if"], "inputs.promote == ''")
            self.assertEqual(steps["The tested beta"]["if"], "inputs.promote != ''")
            for step in ("Push the beta (its own tag only)", "Promote the tested beta", "Push"):
                self.assertIn("python3 tools/require-release-checks.py", steps[step]["run"])
        for job in ("iso", "setup"):
            self.assertIn("github.event_name != 'schedule'", self.image[job]["if"])
            run = "\n".join(step.get("run", "") for step in self.image[job]["steps"])
            self.assertIn("TAG=${BETA:-$VERSION}", run)
            self.assertNotIn('"$IMAGE" "$VERSION" "$NVIDIA_DIGEST"', run)

    def test_shell_steps_parse(self):
        count = 0
        for jobs in (self.build, self.image):
            for job in jobs.values():
                for step in job["steps"]:
                    if "run" in step and "${{" not in step["run"]:
                        count += 1
                        result = subprocess.run(["bash", "-n"], input=step["run"], capture_output=True, text=True)
                        self.assertEqual(result.returncode, 0, (step.get("name"), result.stderr))
        self.assertGreater(count, 20)


if __name__ == "__main__":
    unittest.main()
